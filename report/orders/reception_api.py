"""
APIs liées aux réceptions (mise à jour et réinitialisation des quantités)
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
import json
import logging
from decimal import Decimal, InvalidOperation
from .models import FichierImporte, ActivityLog, NumeroBonCommande, Reception, LigneFichier, round_decimal
from .data_extractors import (
    get_price_from_ligne, get_supplier_from_ligne, get_ordered_date_from_ligne,
    get_project_number_from_ligne, get_task_number_from_ligne, get_order_description_from_ligne,
    get_schedule_from_ligne, get_line_from_ligne
)
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
# Configuration du logger
logger = logging.getLogger(__name__)


@csrf_protect
@login_required
def update_quantity_delivered(request, fichier_id):
    logger = logging.getLogger(__name__)
    
    # Log pour déboguer
    logger.info(f"API update_quantity_delivered appelée avec fichier_id={fichier_id}, méthode={request.method}")
    
    try:
        fichier = FichierImporte.objects.get(id=fichier_id)
        logger.info(f"Fichier trouvé: {fichier}")
        
        # Gestion de la méthode GET pour récupérer les données
        if request.method == 'GET':
            bon_number = request.GET.get('bon_number')
            if not bon_number:
                return JsonResponse({'status': 'error', 'message': 'Paramètre bon_number requis'}, status=400)
            
            try:
                # Récupérer le bon de commande
                bon_commande = NumeroBonCommande.objects.get(numero=bon_number)
                
                # Récupérer toutes les réceptions pour ce bon de commande et ce fichier
                receptions = Reception.objects.filter(
                    bon_commande=bon_commande,
                    fichier=fichier
                ).values('business_id', 'quantity_delivered', 'ordered_quantity', 'quantity_not_delivered', 'unit_price','amount_delivered', 'amount_not_delivered', 'quantity_payable', 'amount_payable')
                
                # Convertir en dictionnaire pour un accès facile
                reception_dict = {}
                for item in receptions:
                    business_id = str(item['business_id']) if item['business_id'] else 'N/A'
                    
                    # Récupérer les valeurs
                    quantity_delivered = float(item['quantity_delivered']) if item['quantity_delivered'] is not None else 0.0
                    ordered_quantity = float(item['ordered_quantity']) if item['ordered_quantity'] is not None else 0.0
                    quantity_not_delivered = float(item['quantity_not_delivered']) if item['quantity_not_delivered'] is not None else 0.0
                    unit_price = float(item['unit_price']) if item['unit_price'] is not None else 0.0
                    amount_delivered = float(item['amount_delivered']) if item['amount_delivered'] is not None else 0.0
                    amount_not_delivered = float(item['amount_not_delivered']) if item['amount_not_delivered'] is not None else 0.0
                    quantity_payable = float(item['quantity_payable']) if item['quantity_payable'] is not None else 0.0
                    amount_payable = float(item['amount_payable']) if item['amount_payable'] is not None else 0.0
                    
                    # Récupérer la ligne correspondante pour extraire le fournisseur
                    ligne = LigneFichier.objects.filter(
                        fichier=fichier,
                        business_id=item['business_id']
                    ).first()
                    
                    # Extraire toutes les données additionnelles
                    supplier = get_supplier_from_ligne(ligne) if ligne else "N/A"
                    project_number = get_project_number_from_ligne(ligne) if ligne else "N/A"
                    schedule = get_schedule_from_ligne(ligne) if ligne else "N/A"
                    line= get_line_from_ligne(ligne) if ligne else "N/A"
                    task_number = get_task_number_from_ligne(ligne) if ligne else "N/A"
                    order_description = get_order_description_from_ligne(ligne) if ligne else "N/A"
                    
                    
                    reception_dict[business_id] = {
                      'quantity_delivered': quantity_delivered,
                      'ordered_quantity': ordered_quantity,
                      'quantity_not_delivered': quantity_not_delivered,
                      'unit_price': unit_price,
                      'quantity_payable': quantity_payable,
                      'amount_payable': amount_payable,
                      'amount_delivered': amount_delivered,
                      'amount_not_delivered': amount_not_delivered,
                      'supplier': supplier,
                      'project_number': project_number,
                      'task_number': task_number,
                      'order_description': order_description,
                      'schedule': schedule,
                      'line': line,
                      'is_complete': quantity_delivered >= ordered_quantity
                    }
                
                return JsonResponse({
                    'status': 'success',
                    'receptions': reception_dict
                })
                
            except NumeroBonCommande.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Bon de commande non trouvé'}, status=404)
        
        # Gestion de la méthode POST pour la mise à jour
        elif request.method == 'POST':
            try:
                data = json.loads(request.body)
                bon_number = data.get('bon_number')
                business_id = data.get('business_id')
                new_quantity_delivered = round_decimal(Decimal(str(data.get('quantity_delivered'))))  # Nouvelle quantité totale
                original_quantity = round_decimal(Decimal(str(data.get('original_quantity'))))  # Quantité originale pour référence
                
                # Vérifier que tous les paramètres requis sont présents
                if not all([bon_number, business_id, new_quantity_delivered is not None, original_quantity is not None]):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Données manquantes'
                    }, status=400)
                
                # Récupérer le bon de commande
                bon_commande = NumeroBonCommande.objects.get(numero=bon_number)
                
                # Récupérer le prix unitaire depuis la ligne du fichier
                try:
                    ligne_fichier = LigneFichier.objects.get(fichier=fichier, business_id=business_id)
                    unit_price = Decimal(str(get_price_from_ligne(ligne_fichier)))
                except (LigneFichier.DoesNotExist, ValueError):
                    unit_price = Decimal('0.00')
                
                # Permettre les valeurs négatives pour les corrections d'erreurs
                # Mais vérifier que le total final ne devient pas négatif
                if new_quantity_delivered < 0:
                    # Récupérer la quantité existante pour vérifier le total final
                    try:
                        reception = Reception.objects.get(
                            bon_commande=bon_commande,
                            fichier=fichier,
                            business_id=business_id
                        )
                        current_quantity_delivered = reception.quantity_delivered or Decimal('0')
                        final_total = current_quantity_delivered + new_quantity_delivered
                        
                        if final_total < 0:
                            return JsonResponse({
                                'status': 'error',
                                'message': f'La correction de {new_quantity_delivered} rendrait le total négatif (actuel: {current_quantity_delivered}, nouveau: {final_total})'
                            }, status=400)
                    except Reception.DoesNotExist:
                        # Si aucune réception n'existe, on ne peut pas avoir une valeur négative
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Impossible d\'appliquer une correction négative sur une ligne sans réception existante'
                        }, status=400)
                
                # Récupérer la réception existante si elle existe
                try:
                    reception = Reception.objects.get(
                        bon_commande=bon_commande,
                        fichier=fichier,
                        business_id=business_id
                    )
                    existing_quantity_delivered = reception.quantity_delivered or Decimal('0')
                except Reception.DoesNotExist:
                    existing_quantity_delivered = Decimal('0')
                
                # Ajouter la nouvelle quantité à la quantité existante
                total_quantity_delivered = existing_quantity_delivered + new_quantity_delivered
                
                # Vérifier que la quantité totale ne dépasse pas la quantité commandée
                if total_quantity_delivered > original_quantity:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'La quantité totale reçue ({total_quantity_delivered}) dépasse la quantité commandée ({original_quantity})'
                    }, status=400)
                
                # Calculer la quantité restante
                quantity_not_delivered = original_quantity - total_quantity_delivered
                
                # Mettre à jour ou créer l'entrée de réception
                reception, created = Reception.objects.update_or_create(
                    bon_commande=bon_commande,
                    fichier=fichier,
                    business_id=business_id,
                    defaults={
                        'quantity_delivered': total_quantity_delivered,
                        'ordered_quantity': original_quantity,
                        'quantity_not_delivered': quantity_not_delivered,
                        'user': request.user.email if hasattr(request, 'user') and request.user.is_authenticated else None,
                        'date_modification': timezone.now(),
                        'unit_price': unit_price,
                        # Forcer le recalcul de ces champs dans save()
                        'amount_delivered': None,
                        'quantity_payable': None,
                        'amount_payable': None
                    }
                )
                
                # Les champs amount_done et quantity_payable sont calculés automatiquement dans save()
                
                # Calculer le taux d'avancement actuel
                taux_avancement = bon_commande.taux_avancement()
                
                # Créer une entrée dans le journal d'activité avec le taux d'avancement actuel
                ActivityLog.objects.create(
                    bon_commande=bon_number,
                    fichier=fichier,
                    business_id=business_id,
                    ordered_quantity=original_quantity,
                    quantity_delivered=new_quantity_delivered,  # Quantité individuelle entrée par l'utilisateur
                    quantity_not_delivered=quantity_not_delivered,
                    user=reception.user,
                    cumulative_recipe=total_quantity_delivered,  # Quantité cumulative totale
                    progress_rate=taux_avancement
                )
                
                # La génération automatique du rapport MSRN a été supprimée
                # Les rapports MSRN sont maintenant générés manuellement via l'API generate_msrn_report
                report = None
                
                # Forcer le refresh du bon_commande depuis la DB pour obtenir les valeurs à jour
                bon_commande.refresh_from_db()
                
                # Préparer la réponse avec les nouvelles valeurs
                response_data = {
                    'status': 'success',
                    'quantity_delivered': float(total_quantity_delivered),
                    'ordered_quantity': float(original_quantity),
                    'quantity_not_delivered': float(quantity_not_delivered),
                    'amount_delivered': float(reception.amount_delivered),
                    'amount_not_delivered': float(reception.amount_not_delivered),
                    'quantity_payable': float(reception.quantity_payable),
                    'amount_payable': float(reception.amount_payable),  # Ajout du nouveau champ
                    'taux_avancement': float(bon_commande.taux_avancement()),
                    'montant_total_recu': float(bon_commande.montant_recu()),
                    'montant_total': float(bon_commande.montant_total()),
                    'msrn_report_id': None
                }
                
                return JsonResponse(response_data)
                
            except NumeroBonCommande.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Bon de commande non trouvé'}, status=404)
            except InvalidOperation:
                return JsonResponse({'status': 'error', 'message': 'Format de quantité invalide'}, status=400)
            except Exception as e:
                logger.error(f"Erreur lors de l'enregistrement de la réception: {str(e)}")
                return JsonResponse({'status': 'error', 'message': f'Erreur: {str(e)}'}, status=500)
        
        else:
            return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée'}, status=405)
    
    except FichierImporte.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Fichier non trouvé'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Format JSON invalide'}, status=400)
    except Exception as e:
        logger.exception(f"Erreur lors de la mise à jour des quantités: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'Erreur serveur: {str(e)}'}, status=500)


@csrf_protect
@login_required
@require_http_methods(["POST"])
def bulk_update_receptions(request, fichier_id):
    """
    API pour mettre à jour plusieurs réceptions en une seule requête (quantity delivered collectif).
    
    Paramètres attendus dans le corps de la requête:
    - bon_number: Numéro du bon de commande
    - updates: Liste des mises à jour [{"business_id": str, "quantity_delivered": float, "ordered_quantity": float}]
    """
    logger = logging.getLogger(__name__)
    
    try:
        fichier = FichierImporte.objects.get(id=fichier_id)
        data = json.loads(request.body)
        bon_number = data.get('bon_number')
        updates = data.get('updates', [])
        
        if not bon_number:
            return JsonResponse({'status': 'error', 'message': 'Numéro de bon de commande manquant'}, status=400)
        
        if not updates:
            return JsonResponse({'status': 'error', 'message': 'Aucune mise à jour fournie'}, status=400)
        
        # Récupérer le bon de commande
        bon_commande = NumeroBonCommande.objects.get(numero=bon_number)
        
        updated_receptions = []
        
        # Traiter chaque mise à jour
        for update in updates:
            business_id = update.get('business_id')
            new_quantity_delivered = round_decimal(Decimal(str(update.get('quantity_delivered'))))
            original_quantity = round_decimal(Decimal(str(update.get('ordered_quantity'))))
            
            if business_id is None or new_quantity_delivered is None or original_quantity is None:
                continue
            
            # Récupérer le prix unitaire
            try:
                ligne_fichier = LigneFichier.objects.get(fichier=fichier, business_id=business_id)
                unit_price = Decimal(str(get_price_from_ligne(ligne_fichier)))
            except (LigneFichier.DoesNotExist, ValueError):
                unit_price = Decimal('0.00')
            
            # Récupérer la réception existante
            try:
                reception = Reception.objects.get(
                    bon_commande=bon_commande,
                    fichier=fichier,
                    business_id=business_id
                )
                existing_quantity_delivered = reception.quantity_delivered or Decimal('0')
            except Reception.DoesNotExist:
                existing_quantity_delivered = Decimal('0')
            
            # Calculer la nouvelle quantité totale
            total_quantity_delivered = existing_quantity_delivered + new_quantity_delivered
            
            # Validation
            if total_quantity_delivered > original_quantity:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Business ID {business_id}: quantité totale ({total_quantity_delivered}) dépasse la quantité commandée ({original_quantity})'
                }, status=400)
            
            if total_quantity_delivered < 0:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Business ID {business_id}: la quantité totale ne peut pas être négative'
                }, status=400)
            
            # Calculer la quantité restante
            quantity_not_delivered = original_quantity - total_quantity_delivered
            
            # Mettre à jour ou créer la réception
            reception, created = Reception.objects.update_or_create(
                bon_commande=bon_commande,
                fichier=fichier,
                business_id=business_id,
                defaults={
                    'quantity_delivered': total_quantity_delivered,
                    'ordered_quantity': original_quantity,
                    'quantity_not_delivered': quantity_not_delivered,
                    'user': request.user.email if hasattr(request, 'user') and request.user.is_authenticated else None,
                    'date_modification': timezone.now(),
                    'unit_price': unit_price
                }
            )
            
            # Créer une entrée dans le journal d'activité
            ActivityLog.objects.create(
                bon_commande=bon_number,
                fichier=fichier,
                business_id=business_id,
                ordered_quantity=original_quantity,
                quantity_delivered=new_quantity_delivered,
                quantity_not_delivered=quantity_not_delivered,
                user=reception.user,
                cumulative_recipe=total_quantity_delivered,
                progress_rate=bon_commande.taux_avancement()
            )
            
            updated_receptions.append({
                'business_id': business_id,
                'quantity_delivered': float(total_quantity_delivered),
                'quantity_not_delivered': float(quantity_not_delivered),
                'amount_delivered': float(reception.amount_delivered),
                'amount_not_delivered': float(reception.amount_not_delivered),
                'quantity_payable': float(reception.quantity_payable),
                'amount_payable': float(reception.amount_payable)
            })
        
        # Forcer le refresh du bon_commande depuis la DB pour obtenir les valeurs à jour
        bon_commande.refresh_from_db()
        
        # Recalculer les totaux après toutes les mises à jour
        taux_avancement = bon_commande.taux_avancement()
        montant_total_recu = bon_commande.montant_recu()
        
        logger.info(f"[BULK_UPDATE] Bon {bon_number}: {len(updated_receptions)} lignes mises à jour. Taux: {taux_avancement}%, Montant reçu: {montant_total_recu}")
        
        return JsonResponse({
            'status': 'success',
            'updated_receptions': updated_receptions,
            'taux_avancement': float(taux_avancement),
            'montant_total_recu': float(montant_total_recu)
        })
        
    except NumeroBonCommande.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Bon de commande non trouvé'}, status=404)
    except FichierImporte.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Fichier non trouvé'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Format JSON invalide'}, status=400)
    except Exception as e:
        logger.exception(f"Erreur lors de la mise à jour collective: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_protect
@require_http_methods(["POST"])
def reset_quantity_delivered(request, fichier_id):
    """
    API pour réinitialiser toutes les quantités reçues (Quantity Delivered) pour un bon de commande.
    Supprime toutes les entrées Reception pour le bon de commande spécifié.
    
    Paramètres attendus dans le corps de la requête:
    - bon_number: Numéro du bon de commande à réinitialiser
    """
    try:
        # Récupérer le fichier importé
        fichier = FichierImporte.objects.get(id=fichier_id)
        
        # Récupérer les données du corps de la requête
        data = json.loads(request.body)
        bon_number = data.get('bon_number')
        
        if not bon_number:
            return JsonResponse({
                'status': 'error', 
                'message': 'Numéro de bon de commande manquant'
            }, status=400)
        
        try:
            # Récupérer le bon de commande
            bon_commande = NumeroBonCommande.objects.get(numero=bon_number)
            
            # Supprimer toutes les réceptions pour ce bon de commande et ce fichier
            deleted_count, _ = Reception.objects.filter(
                bon_commande=bon_commande,
                fichier=fichier
            ).delete()
            
            # Journaliser l'action de réinitialisation
            user = request.user.email if hasattr(request, 'user') and request.user.is_authenticated else 'Utilisateur anonyme'
            logger.info(f"Réinitialisation des quantités Quantity Delivered pour le bon {bon_number} par {user}")
            
            # Créer une entrée dans le journal d'activité pour la réinitialisation
            if deleted_count > 0:
                ActivityLog.objects.create(
                    bon_commande=bon_number,
                    fichier=fichier,
                    business_id="RESET_ALL",  # Valeur spéciale pour indiquer une réinitialisation globale
                    ordered_quantity=0,
                    quantity_delivered=0,
                    quantity_not_delivered=0,
                    user=user,
                    action_date=timezone.now()
                )
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Toutes les quantités Quantity Delivered pour le bon {bon_number} ont été réinitialisées ({deleted_count} entrées supprimées).'
                })
            else:
                return JsonResponse({
                    'status': 'success',
                    'message': f'Aucune donnée Quantity Delivered à réinitialiser pour le bon {bon_number}.'
                })
                
        except NumeroBonCommande.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Bon de commande {bon_number} non trouvé'
            }, status=404)
    
    except FichierImporte.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Fichier non trouvé'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Format JSON invalide'}, status=400)
    except Exception as e:
        logger.exception(f"Erreur lors de la réinitialisation des quantités Quantity Delivered: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_protect
@require_http_methods(["POST"])
def update_retention(request, bon_id):
    """API pour mettre à jour le taux de rétention (global au bon)
    - Valide le taux (0-10%) et la cause (requise si taux > 0)
    - Persiste sur NumeroBonCommande (retention_rate, retention_cause)
    - Met à jour le dernier MSRNReport du bon (retention_rate, retention_cause, retention_amount, payable_amount)
    - Déclenche le recalcul global des quantity_payable via le save() de NumeroBonCommande
    """
    try:
        data = json.loads(request.body)
        retention_rate = data.get('retention_rate')
        retention_cause = data.get('retention_cause')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Format JSON invalide'}, status=400)
    
    # Validation
    if retention_rate is None:
        return JsonResponse({'status': 'error', 'message': 'Le taux de rétention est requis'}, status=400)
        
    try:
        retention_rate = Decimal(retention_rate)
    except (InvalidOperation, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Le taux de rétention doit être un nombre'}, status=400)
    
    if retention_rate < 0 or retention_rate > 10:
        return JsonResponse({'status': 'error', 'message': 'Le taux de rétention doit être entre 0 et 10%'}, status=400)
        
    if retention_rate > 0 and not retention_cause:
        return JsonResponse({'status': 'error', 'message': 'La cause de la rétention est requise pour un taux supérieur à 0%'}, status=400)

    # Récupérer le bon de commande
    bon_commande = get_object_or_404(NumeroBonCommande, id=bon_id)
    
    # Mettre à jour NumeroBonCommande
    bon_commande.retention_rate = retention_rate
    # Champ optionnel selon modèle
    if hasattr(bon_commande, 'retention_cause'):
        bon_commande.retention_cause = retention_cause
    bon_commande.save()
    
    # Forcer la mise à jour des réceptions avec la même logique que download_msrn_report
    from django.db.models import F, ExpressionWrapper, DecimalField
    from django.db.models.functions import Coalesce
    
    # Facteur de rétention en Decimal explicite
    retention_factor = Decimal('1') - (retention_rate / Decimal('100'))
    receptions = Reception.objects.filter(bon_commande=bon_commande)
    
    # Étape 1: Mettre à jour quantity_payable
    receptions.update(
        quantity_payable=ExpressionWrapper(
            Coalesce(F('quantity_delivered'), Decimal('0')) * retention_factor,
            output_field=DecimalField()
        )
    )
    
    # Étape 2: Mettre à jour amount_payable en utilisant la nouvelle valeur de quantity_payable
    receptions.update(
        amount_payable=ExpressionWrapper(
            F('quantity_payable') * Coalesce(F('unit_price'), Decimal('0')),
            output_field=DecimalField()
        )
    )
    
    # Calculer montants pour MSRNReport
    try:
        from .models import MSRNReport
        montant_total = bon_commande.montant_total()
        montant_recu = bon_commande.montant_recu()
        # Ne pas quantifier/arrondir ici; conserver la précision complète
        retention_amount = (montant_total * retention_rate / Decimal('100'))
        payable_amount = (montant_recu - retention_amount)
        
        # SUPPRIMÉ: Ne plus mettre à jour automatiquement les anciens rapports MSRN
        # Les rapports historiques doivent conserver leurs valeurs d'origine
        # Seuls les nouveaux rapports générés utiliseront les nouveaux taux de rétention
    except Exception as e:
        logger.warning(f"Erreur lors du calcul des montants pour MSRNReport: {e}")
    
    return JsonResponse({
        'status': 'success',
        'message': 'Taux de rétention mis à jour avec succès',
        'retention_rate': float(retention_rate),
        'retention_cause': retention_cause
    })


@csrf_protect
@require_http_methods(["GET"])
def get_receptions(request, bon_id):
    """
    Récupère toutes les réceptions d'un bon de commande avec leurs valeurs quantity_payable et amount_payable
    """
    try:
        # Récupérer le bon de commande
        bon_commande = get_object_or_404(NumeroBonCommande, id=bon_id)
        
        # Récupérer toutes les réceptions
        receptions = Reception.objects.filter(bon_commande=bon_commande)
        
        # Formater les données pour la réponse JSON
        receptions_data = [{
            'id': reception.id,
            'business_id': reception.business_id,
            'quantity_delivered': float(reception.quantity_delivered) if reception.quantity_delivered else 0,
            'quantity_payable': float(reception.quantity_payable) if reception.quantity_payable else 0,
            'amount_payable': float(reception.amount_payable) if reception.amount_payable else 0,
            'unit_price': float(reception.unit_price) if reception.unit_price else 0
        } for reception in receptions]
        
        return JsonResponse({
            'status': 'success',
            'receptions': receptions_data
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_protect
@require_http_methods(["GET"])
def get_reception_history(request, fichier_id):
    """
    Récupère l'historique des réceptions pour les business_ids spécifiés d'un bon de commande
    basé sur les données ActivityLog

    Paramètres GET:
    - bon_number: Numéro du bon de commande
    - business_ids: Liste des business_ids (séparés par des virgules)
    """
    try:
        # Récupérer le fichier importé
        fichier = FichierImporte.objects.get(id=fichier_id)
        
        # Récupérer les paramètres
        bon_number = request.GET.get('bon_number')
        business_ids_str = request.GET.get('business_ids', '')
        
        if not bon_number:
            return JsonResponse({'status': 'error', 'message': 'Paramètre bon_number requis'}, status=400)
        
        if not business_ids_str:
            return JsonResponse({'status': 'error', 'message': 'Paramètre business_ids requis'}, status=400)
        
        # Convertir la chaîne en liste de business_ids
        business_ids = [bid.strip() for bid in business_ids_str.split(',') if bid.strip()]
        
        # Récupérer l'historique des activités pour ces business_ids
        history_data = {}
        
        for business_id in business_ids:
            # Récupérer tous les logs d'activité pour cette ligne
            activity_logs = ActivityLog.objects.filter(
                bon_commande=bon_number,
                fichier=fichier,
                business_id=business_id
            ).order_by('action_date')
            
            # Récupérer la réception actuelle pour avoir les totaux
            try:
                current_reception = Reception.objects.get(
                    bon_commande__numero=bon_number,
                    fichier=fichier,
                    business_id=business_id
                )
                current_total = float(current_reception.quantity_delivered) if current_reception.quantity_delivered else 0
                ordered_quantity = float(current_reception.ordered_quantity) if current_reception.ordered_quantity else 0
            except Reception.DoesNotExist:
                current_total = 0
                ordered_quantity = 0
            
            # Formater l'historique
            history_entries = []
            for log in activity_logs:
                history_entries.append({
                    'id': log.id,
                    'date': log.action_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'user': log.user or 'Système',
                    'quantity_delivered': float(log.quantity_delivered) if log.quantity_delivered else 0,
                    'cumulative_total': float(log.cumulative_recipe) if log.cumulative_recipe else 0,
                    'progress_rate': float(log.progress_rate) if log.progress_rate else 0
                })
            
            history_data[business_id] = {
                'current_total': current_total,
                'ordered_quantity': ordered_quantity,
                'history': history_entries
            }
        
        return JsonResponse({
            'status': 'success',
            'bon_number': bon_number,
            'history': history_data
        })
        
    except FichierImporte.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Fichier non trouvé'}, status=404)
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération de l'historique des réceptions: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_protect
@require_http_methods(["POST"])
def bulk_correction_quantity_delivered(request, fichier_id):
    """
    API pour appliquer des corrections groupées aux quantités reçues
    
    Paramètres attendus:
    - bon_number: Numéro du bon de commande
    - corrections: Liste de dictionnaires contenant:
        - business_id: ID métier de la ligne
        - correction_value: Valeur de correction (peut être négative)
        - original_quantity: Quantité commandée originale
    """
    try:
        # Récupérer le fichier importé
        fichier = FichierImporte.objects.get(id=fichier_id)
        
        # Récupérer les données du corps de la requête
        data = json.loads(request.body)
        bon_number = data.get('bon_number')
        corrections = data.get('corrections', [])
        
        if not bon_number:
            return JsonResponse({'status': 'error', 'message': 'Numéro de bon de commande manquant'}, status=400)
        
        if not corrections:
            return JsonResponse({'status': 'error', 'message': 'Aucune correction spécifiée'}, status=400)
        
        # Récupérer le bon de commande
        try:
            bon_commande = NumeroBonCommande.objects.get(numero=bon_number)
        except NumeroBonCommande.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Bon de commande non trouvé'}, status=404)
        
        # Résultats pour chaque correction
        results = []
        errors = []
        
        # Traiter chaque correction
        for correction in corrections:
            try:
                business_id = correction.get('business_id')
                correction_value = Decimal(str(correction.get('correction_value')))
                original_quantity = Decimal(str(correction.get('original_quantity')))
                
                if business_id is None:
                    errors.append(f"Business ID manquant pour une correction")
                    continue
                
                # Récupérer la réception existante
                try:
                    reception = Reception.objects.get(
                        bon_commande=bon_commande,
                        fichier=fichier,
                        business_id=business_id
                    )
                    current_quantity = reception.quantity_delivered or Decimal('0')
                except Reception.DoesNotExist:
                    if correction_value < 0:
                        errors.append(f"Business ID {business_id}: Impossible d'appliquer une correction négative sans réception existante")
                        continue
                    current_quantity = Decimal('0')
                
                # Calculer la nouvelle quantité totale
                new_total = current_quantity + correction_value
                
                # Validations
                if new_total < 0:
                    errors.append(f"Business ID {business_id}: La correction rendrait le total négatif (actuel: {current_quantity}, correction: {correction_value})")
                    continue
                
                if new_total > original_quantity:
                    errors.append(f"Business ID {business_id}: Le total dépasserait la quantité commandée (nouveau: {new_total}, commandé: {original_quantity})")
                    continue
                
                # Récupérer le prix unitaire
                try:
                    ligne_fichier = LigneFichier.objects.get(fichier=fichier, business_id=business_id)
                    unit_price = Decimal(str(get_price_from_ligne(ligne_fichier)))
                except (LigneFichier.DoesNotExist, ValueError):
                    unit_price = Decimal('0.00')
                
                # Calculer la quantité restante
                quantity_not_delivered = original_quantity - new_total
                
                # Mettre à jour ou créer l'entrée de réception
                reception, created = Reception.objects.update_or_create(
                    bon_commande=bon_commande,
                    fichier=fichier,
                    business_id=business_id,
                    defaults={
                        'quantity_delivered': new_total,
                        'ordered_quantity': original_quantity,
                        'quantity_not_delivered': quantity_not_delivered,
                        'user': request.user.email if hasattr(request, 'user') and request.user.is_authenticated else None,
                        'date_modification': timezone.now(),
                        'unit_price': unit_price
                    }
                )
                
                # Créer une entrée dans le journal d'activité
                ActivityLog.objects.create(
                    bon_commande=bon_number,
                    fichier=fichier,
                    business_id=business_id,
                    ordered_quantity=original_quantity,
                    quantity_delivered=correction_value,  # Valeur de correction individuelle
                    quantity_not_delivered=quantity_not_delivered,
                    user=reception.user,
                    cumulative_recipe=new_total,  # Nouvelle quantité cumulative
                    progress_rate=bon_commande.taux_avancement()
                )
                
                # Ajouter le résultat de cette correction
                results.append({
                    'business_id': business_id,
                    'correction_applied': float(correction_value),
                    'new_total': float(new_total),
                    'previous_total': float(current_quantity),
                    'quantity_delivered': float(reception.quantity_delivered),
                    'quantity_not_delivered': float(reception.quantity_not_delivered),
                    'amount_delivered': float(reception.amount_delivered),
                    'amount_not_delivered': float(reception.amount_not_delivered),
                    'quantity_payable': float(reception.quantity_payable),
                    'amount_payable': float(reception.amount_payable),
                })
                
            except (ValueError, TypeError, InvalidOperation) as e:
                errors.append(f"Business ID {business_id}: Erreur de format - {str(e)}")
            except Exception as e:
                errors.append(f"Business ID {business_id}: Erreur - {str(e)}")
        
        # Forcer le refresh du bon_commande depuis la DB pour obtenir les valeurs à jour
        bon_commande.refresh_from_db()
        
        # Calculer les totaux mis à jour après toutes les corrections
        taux_avancement = bon_commande.taux_avancement()
        montant_total_recu = bon_commande.montant_recu()
        montant_total = bon_commande.montant_total()
        
        logger.info(f"[BULK_CORRECTION] Bon {bon_number}: {len(results)} corrections appliquées. Taux: {taux_avancement}%, Montant reçu: {montant_total_recu}")
        
        return JsonResponse({
            'status': 'success',
            'message': f'{len(results)} corrections appliquées avec succès',
            'results': results,
            'errors': errors,
            'taux_avancement': float(taux_avancement),
            'montant_total_recu': float(montant_total_recu),
            'montant_total': float(montant_total)
        })
        
    except FichierImporte.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Fichier non trouvé'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Format JSON invalide'}, status=400)
    except Exception as e:
        logger.exception(f"Erreur lors des corrections groupées: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)