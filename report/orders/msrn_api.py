"""But:
- Offrir des APIs pour générer le rapport MSRN et mettre à jour la rétention.

Étapes:
- generate_msrn_report_api: valider, récupérer le bon, créer le rapport, générer le PDF, envoyer l'email, renvoyer un JSON.
- update_msrn_retention: valider, charger le rapport, mettre à jour rétention, recalcule, régénérer PDF, renvoyer un JSON.

Entrées:
- generate: POST JSON (retention_rate, retention_cause), bon_id en URL.
- update: POST JSON (retention_rate, retention_cause), msrn_id en URL.

Sorties:
- JsonResponse: succès/erreur, identifiants et URL de téléchargement.
"""
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_protect
from django.core.files import File
from django.contrib.auth.decorators import login_required
from django.db import transaction
from decimal import Decimal, InvalidOperation
import json
import logging
import time
from .models import NumeroBonCommande, MSRNReport, Reception
from .reports import generate_msrn_report
from django.shortcuts import get_object_or_404
from .emails import send_msrn_notification

# Import Celery tasks avec fallback si non disponible
try:
    from .tasks import generate_msrn_pdf_task
    from .task_status_api import register_user_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

logger = logging.getLogger(__name__)

@csrf_protect
@login_required
@transaction.atomic  # CRITIQUE: Transaction atomique pour éviter les données incohérentes
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
    # Autoriser uniquement POST
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    # Récupérer le bon de commande avec prefetch pour réduire les requêtes
    try:
        bon_commande = NumeroBonCommande.objects.prefetch_related(
            'fichiers__lignes',
            'receptions'
        ).get(id=bon_id)
    except NumeroBonCommande.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Bon de commande non trouvé'}, status=404)
    
    # Récupérer les paramètres de rétention (JSON)
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}
    
    try:
        retention_rate = Decimal(data.get('retention_rate', bon_commande.retention_rate or '0'))
    except (TypeError, ValueError, InvalidOperation):
        retention_rate = bon_commande.retention_rate or Decimal('0')
    
    retention_cause = data.get('retention_cause', bon_commande.retention_cause or '')
    
    # Valider le taux de rétention (0 à 10%)
    if retention_rate < 0 or retention_rate > 100:
        return JsonResponse({'success': False, 'error': 'Le taux de rétention doit être compris entre 0 et 100%'}, status=400)
            
    if retention_rate > 0 and not retention_cause:
        return JsonResponse({'success': False, 'error': 'La cause de la rétention est requise pour un taux supérieur à 0%'}, status=400)
    
    # Créer et sauvegarder le rapport, générer le PDF et notifier
    try:
        # Créer le rapport MSRN (Initialisation en base)
        report = MSRNReport(
            bon_commande=bon_commande,
            user=request.user.email,
            retention_rate=retention_rate,
            retention_cause=retention_cause
        )
        report.save()
        
        # Mode Asynchrone (Celery)
        if CELERY_AVAILABLE:
            logger.info(f"Lancement tâche async pour {report.report_number}")
            task = generate_msrn_pdf_task.delay(report.id, request.user.id)
            
            # Enregistrer la tâche pour le polling utilisateur
            try:
                register_user_task(request.user.id, task.id, 'generate_msrn')
            except Exception:
                pass
                
            return JsonResponse({
                'success': True,
                'async': True,
                'task_id': task.id,
                'msrn_report_id': report.id,
                'report_number': report.report_number,
                'message': f"La génération du rapport {report.report_number} a démarré en arrière-plan."
            })

        # Mode Synchrone (Fallback)
        logger.info(f"Génération synchrone pour {report.report_number}")
        start_time = time.time()
        
        # Générer le PDF avec le numéro de rapport qui vient d'être créé
        pdf_buffer = generate_msrn_report(bon_commande, report.report_number, user_email=request.user.email)
        
        # Enregistrer le PDF dans le champ fichier du rapport
        # Format du nom de fichier: MSRN250020-CI-OR-3000001373.pdf (au lieu de MSRN-MSRN250020-...)
        report.pdf_file.save(
            f"{report.report_number}-{bon_commande.numero}.pdf",
            File(pdf_buffer)
        )
        report.save()
        
        # Envoyer la notification email aux superusers (non bloquant pour la réponse)
        try:
            send_msrn_notification(report)
        except Exception as email_error:
            logger.error(f"Erreur email MSRN: {email_error}")
        
        return JsonResponse({
            'success': True,
            'async': False,
            'msrn_report_id': report.id,
            'report_number': report.report_number,
            'download_url': f"/orders/msrn-report/{report.id}/",
            'message': f"Rapport {report.report_number} généré avec succès"
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
    
    # Récupérer le rapport MSRN (retourner un JSON 404 plutôt qu'une page HTML)
    try:
        msrn_report = MSRNReport.objects.get(id=msrn_id)
    except MSRNReport.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Rapport MSRN non trouvé'}, status=404)
    
    # Récupérer les paramètres de rétention (JSON)
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
    if retention_rate < 0 or retention_rate > 100:
        return JsonResponse({'success': False, 'error': 'Le taux de rétention doit être compris entre 0 et 100%'}, status=400)
            
    if retention_rate > 0 and not retention_cause:
        return JsonResponse({'success': False, 'error': 'La cause de la rétention est requise pour un taux supérieur à 0%'}, status=400)
    
    # Mettre à jour le rapport MSRN et recalculer les montants
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
            
            # OPTIMISATION: S'assurer que Payment Terms est préservé (2 requêtes optimisées)
            if not msrn_report.payment_terms_snapshot:
                from .models import Reception, LigneFichier
                try:
                    # Récupérer une réception avec son business_id uniquement (1 requête)
                    reception = Reception.objects.filter(
                        bon_commande=bon
                    ).only('business_id').first()
                    
                    if reception and reception.business_id:
                        # Chercher la ligne correspondante via business_id (1 requête)
                        ligne = LigneFichier.objects.filter(
                            business_id=reception.business_id
                        ).only('contenu').first()
                        
                        if ligne and ligne.contenu:
                            contenu = ligne.contenu
                            # Chercher directement 'Payment Terms'
                            if 'Payment Terms' in contenu and contenu['Payment Terms']:
                                val = str(contenu['Payment Terms']).strip()
                                if val and val.lower() not in ['n/a', 'na', '', 'none']:
                                    msrn_report.payment_terms_snapshot = val
                except Exception:
                    pass
            
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
                        'line': reception_data.get('line', 'N/A'),
                        'schedule': reception_data.get('schedule', 'N/A')
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
                    schedule = "N/A"
                    
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
                                    
                                    # Chercher les informations de schedule (Schedule)
                                    for key, value in contenu.items():
                                        key_lower = key.lower() if key else ''
                                        if ('schedule' in key_lower) and value:
                                            schedule = str(value)
                                            break
                                
                                if line_description != "N/A" or line != "N/A" or schedule != "N/A":
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
                        'line': line,
                        'schedule': schedule
                    })
            
            # Sauvegarder le snapshot des données des réceptions
            msrn_report.receptions_data_snapshot = receptions_snapshot
        
        # Sauvegarder les modifications
        msrn_report.save()
        
        # Régénérer le PDF avec les nouvelles valeurs de rétention
        if msrn_report.bon_commande:
            pdf_buffer = generate_msrn_report(msrn_report.bon_commande, msrn_report.report_number, msrn_report=msrn_report, user_email=request.user.email)
            
            # Mettre à jour le fichier PDF
            msrn_report.pdf_file.save(
                f"{msrn_report.report_number}-{msrn_report.bon_commande.numero}.pdf",
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
