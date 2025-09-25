from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_protect
from django.core.files import File
from django.contrib.auth.decorators import login_required
from decimal import Decimal, InvalidOperation
import json
import logging
from .models import NumeroBonCommande, MSRNReport, Reception
from .reports import generate_msrn_report
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)

@csrf_protect
@login_required
def generate_msrn_report_api(request, bon_id):
    """
    API pour générer manuellement un rapport MSRN pour un bon de commande.
    
    Méthode: POST
    Paramètres:
    - retention_rate: taux de rétention (optionnel, défaut: 0)
    - retention_cause: cause de la rétention (requis si retention_rate > 0)
    
    Retourne:
    - success: True/False
    - msrn_report_id: ID du rapport généré
    - report_number: Numéro du rapport
    - download_url: URL pour télécharger le rapport
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    # Récupérer le bon de commande
    try:
        bon_commande = NumeroBonCommande.objects.get(id=bon_id)
    except NumeroBonCommande.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Bon de commande non trouvé'}, status=404)
    
    # Récupérer les paramètres de rétention
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}
    
    try:
        retention_rate = Decimal(data.get('retention_rate', bon_commande.retention_rate or '0'))
    except (TypeError, ValueError, InvalidOperation):
        retention_rate = bon_commande.retention_rate or Decimal('0')
    
    retention_cause = data.get('retention_cause', bon_commande.retention_cause or '')
    
    # Valider le taux de rétention
    if retention_rate < 0 or retention_rate > 10:
        return JsonResponse({'success': False, 'error': 'Le taux de rétention doit être compris entre 0 et 10%'}, status=400)
            
    if retention_rate > 0 and not retention_cause:
        return JsonResponse({'success': False, 'error': 'La cause de la rétention est requise pour un taux supérieur à 0%'}, status=400)
    
    # Créer et sauvegarder le rapport
    try:
        # Créer le rapport MSRN
        report = MSRNReport(
            bon_commande=bon_commande,
            user=request.user.username,
            retention_rate=retention_rate,
            retention_cause=retention_cause
        )
        report.save()
        
        # Générer le PDF avec le numéro de rapport qui vient d'être créé
        pdf_buffer = generate_msrn_report(bon_commande, report.report_number, username=request.user.username)
        
        # Mettre à jour le fichier PDF avec le bon numéro
        report.pdf_file.save(
            f"MSRN-{report.report_number}.pdf",
            File(pdf_buffer)
        )
        report.save()
        
        logger.info(f"Rapport MSRN généré avec succès: MSRN-{report.report_number}")
        
        # Préparer la réponse
        return JsonResponse({
            'success': True,
            'msrn_report_id': report.id,
            'report_number': report.report_number,
            'download_url': f"/orders/msrn-report/{report.id}/",
            'message': f"Rapport MSRN-{report.report_number} généré avec succès"
        })
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération du rapport MSRN: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': f"Erreur lors de la génération du rapport: {str(e)}"}, status=500)

@login_required
def update_msrn_retention(request, msrn_id):
    """
    API pour mettre à jour le taux de rétention et la cause d'un rapport MSRN existant.
    
    Méthode: POST
    Paramètres:
    - retention_rate: taux de rétention (0-10%)
    - retention_cause: cause de la rétention (requis si retention_rate > 0)
    
    Retourne:
    - success: True/False
    - msrn_report: informations mises à jour du rapport
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    # Récupérer le rapport MSRN
    try:
        msrn_report = get_object_or_404(MSRNReport, id=msrn_id)
    except MSRNReport.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Rapport MSRN non trouvé'}, status=404)
    
    # Récupérer les paramètres de rétention
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Format JSON invalide'}, status=400)
    
    try:
        retention_rate = Decimal(data.get('retention_rate', '0'))
    except (TypeError, ValueError, InvalidOperation):
        return JsonResponse({'success': False, 'error': 'Taux de rétention invalide'}, status=400)
    
    retention_cause = data.get('retention_cause', '')
    
    # Valider le taux de rétention
    if retention_rate < 0 or retention_rate > 10:
        return JsonResponse({'success': False, 'error': 'Le taux de rétention doit être compris entre 0 et 10%'}, status=400)
            
    if retention_rate > 0 and not retention_cause:
        return JsonResponse({'success': False, 'error': 'La cause de la rétention est requise pour un taux supérieur à 0%'}, status=400)
    
    # Mettre à jour le rapport MSRN
    try:
        # Sauvegarder les anciennes valeurs pour le log
        old_retention_rate = msrn_report.retention_rate
        old_retention_cause = msrn_report.retention_cause
        
        # Mettre à jour les valeurs de rétention
        msrn_report.retention_rate = retention_rate
        msrn_report.retention_cause = retention_cause
        msrn_report.retention_rate_snapshot = retention_rate
        
        # Recalculer les montants si le bon de commande est disponible
        if msrn_report.bon_commande:
            bon = msrn_report.bon_commande
            
            # S'assurer que les snapshots sont préservés
            if msrn_report.montant_total_snapshot is None:
                msrn_report.montant_total_snapshot = bon.montant_total()
            
            if msrn_report.montant_recu_snapshot is None:
                msrn_report.montant_recu_snapshot = bon.montant_recu()
                
            if msrn_report.progress_rate_snapshot is None:
                msrn_report.progress_rate_snapshot = bon.taux_avancement()
            
            # Utiliser les snapshots pour les calculs
            total_amount = msrn_report.montant_recu_snapshot
            
            # Calculer le montant de rétention et le montant payable
            retention_amount = total_amount * (retention_rate / 100)
            total_payable_amount = total_amount - retention_amount
            
            # Mettre à jour les montants dans le rapport MSRN
            msrn_report.retention_amount = retention_amount
            msrn_report.retention_amount_snapshot = retention_amount
            msrn_report.payable_amount = total_payable_amount
            msrn_report.payable_amount_snapshot = total_payable_amount
            
            # Mettre à jour le snapshot des données des réceptions avec les nouvelles valeurs de rétention
            # Utiliser les réceptions du snapshot original pour préserver la structure du rapport
            if msrn_report.receptions_data_snapshot:
                # Utiliser les réceptions du snapshot original
                original_receptions = msrn_report.receptions_data_snapshot
                receptions_snapshot = []
                
                for reception_data in original_receptions:
                    # Recalculer seulement quantity_payable et amount_payable avec le nouveau taux
                    quantity_payable = Decimal(str(reception_data['quantity_delivered'])) * (1 - retention_rate / 100)
                    amount_payable = Decimal(str(reception_data['amount_delivered'])) * (1 - retention_rate / 100)
                    
                    # Conserver toutes les autres données du snapshot original
                    receptions_snapshot.append({
                        'id': reception_data['id'],
                        'line_description': reception_data.get('line_description', 'N/A'),
                        'ordered_quantity': reception_data['ordered_quantity'],
                        'received_quantity': reception_data.get('received_quantity', reception_data.get('quantity_delivered', 0)),
                        'quantity_delivered': reception_data['quantity_delivered'],
                        'quantity_not_delivered': reception_data['quantity_not_delivered'],
                        'amount_delivered': reception_data['amount_delivered'],
                        'quantity_payable': float(quantity_payable),
                        'amount_payable': float(amount_payable),
                        'line': reception_data.get('line', 'N/A')
                    })
            else:
                # Fallback : utiliser les réceptions actuelles si pas de snapshot
                receptions = Reception.objects.filter(bon_commande=bon)
                receptions_snapshot = []
                
                for reception in receptions:
                    # Calculer les nouvelles valeurs avec le taux de rétention
                    quantity_payable = reception.quantity_delivered * (1 - retention_rate / 100)
                    amount_payable = reception.amount_delivered * (1 - retention_rate / 100)
                    
                    # Récupérer line_description et line_info depuis les fichiers
                    line_description = "N/A"
                    line = "N/A"
                    
                    for fichier in bon.fichiers.all():
                        # Utiliser business_id pour retrouver la ligne correspondante
                        business_id_parts = reception.business_id.split('_')
                        if len(business_id_parts) >= 2:
                            try:
                                ligne_numero = int(business_id_parts[1])  # Extraire le numéro de ligne du business_id
                                for ligne in fichier.lignes.filter(numero_ligne=ligne_numero):
                                    contenu = ligne.contenu
                                    
                                    # Chercher la description de ligne
                                    for key, value in contenu.items():
                                        key_lower = key.lower() if key else ''
                                        if ('description' in key_lower or 'desc' in key_lower) and value:
                                            line_description = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                                            break
                                    
                                    # Chercher les informations de ligne (Line)
                                    for key, value in contenu.items():
                                        key_lower = key.lower() if key else ''
                                        if ('line' in key_lower and 'description' not in key_lower) and value:
                                            line = str(value)
                                            break
                                    
                                    if line_description != "N/A":
                                        break
                                if line_description != "N/A":
                                    break
                            except (ValueError, IndexError):
                                # Si on ne peut pas extraire le numéro de ligne du business_id
                                pass
                    
                    receptions_snapshot.append({
                        'id': reception.id,
                        'line_description': line_description,
                        'ordered_quantity': float(reception.ordered_quantity),
                        'received_quantity': float(reception.received_quantity) if reception.received_quantity is not None else 0,
                        'quantity_delivered': float(reception.quantity_delivered),
                        'quantity_not_delivered': float(reception.quantity_not_delivered),
                        'amount_delivered': float(reception.amount_delivered),
                        'quantity_payable': float(quantity_payable),
                        'amount_payable': float(amount_payable),
                        'line': line
                    })
            
            # Sauvegarder le snapshot des données des réceptions
            msrn_report.receptions_data_snapshot = receptions_snapshot
        
        # Sauvegarder les modifications
        msrn_report.save()
        
        # Régénérer le PDF avec les nouvelles valeurs de rétention
        if msrn_report.bon_commande:
            pdf_buffer = generate_msrn_report(msrn_report.bon_commande, msrn_report.report_number, msrn_report=msrn_report,username=request.user.username)
            
            # Mettre à jour le fichier PDF
            msrn_report.pdf_file.save(
                f"MSRN-{msrn_report.report_number}.pdf",
                File(pdf_buffer),
                save=False  # Ne pas sauvegarder tout de suite pour éviter double sauvegarde
            )
            msrn_report.save()
        
        logger.info(f"Rétention mise à jour pour le rapport MSRN-{msrn_report.report_number}: {old_retention_rate}% -> {retention_rate}%")
        
        # Préparer la réponse
        return JsonResponse({
            'success': True,
            'msrn_report': {
                'id': msrn_report.id,
                'report_number': msrn_report.report_number,
                'retention_rate': float(msrn_report.retention_rate),
                'retention_cause': msrn_report.retention_cause,
                'retention_amount': float(msrn_report.retention_amount) if msrn_report.retention_amount else 0,
                'total_payable_amount': float(msrn_report.payable_amount) if msrn_report.payable_amount else 0,
                'download_url': f"/orders/msrn-report/{msrn_report.id}/"
            },
            'message': f"Rétention mise à jour pour le rapport MSRN-{msrn_report.report_number}"
        })
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la rétention du rapport MSRN: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': f"Erreur lors de la mise à jour de la rétention: {str(e)}"}, status=500)
