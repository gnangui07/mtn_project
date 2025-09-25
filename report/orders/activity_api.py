"""
APIs liées aux logs d'activité et aux bons de commande
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
import json
import logging
from django.contrib.auth.decorators import login_required
from .models import FichierImporte, ActivityLog, NumeroBonCommande, Reception, LigneFichier
from .data_extractors import (
    get_price_from_ligne, get_supplier_from_ligne, get_ordered_date_from_ligne,
    get_project_number_from_ligne, get_task_number_from_ligne, get_order_description_from_ligne,
    get_schedule_from_ligne, get_line_from_ligne
)

# Configuration du logger
logger = logging.getLogger(__name__)


def get_additional_data_for_reception(log):
    """Fonction pour récupérer les données additionnelles d'une réception"""
    try:
        # Initialiser les valeurs par défaut
        data = {
            'price': 0.0,
            'supplier': "N/A",
            'ordered_date': "N/A",
            'project_number': "N/A",
            'task_number': "N/A",
            'order_description': "N/A",
            'schedule': "N/A",
            'line': "N/A"
        }
        
        # Essayer d'abord de récupérer le prix depuis la réception
        reception = Reception.objects.filter(
            bon_commande__numero=log.bon_commande,
            fichier=log.fichier,
            business_id=log.business_id
        ).first()
        
        if reception and reception.unit_price:
            data['price'] = float(reception.unit_price)
        
        # Récupérer la ligne du fichier pour extraire les autres données
        ligne = LigneFichier.objects.filter(
            fichier=log.fichier,
            business_id=log.business_id
        ).first()
        
        if ligne:
            # Si pas de prix dans la réception, chercher dans la ligne du fichier
            if data['price'] == 0.0:
                data['price'] = get_price_from_ligne(ligne)
            
            # Récupérer les autres données
            data['supplier'] = get_supplier_from_ligne(ligne)
            data['ordered_date'] = get_ordered_date_from_ligne(ligne)
            data['project_number'] = get_project_number_from_ligne(ligne)
            data['task_number'] = get_task_number_from_ligne(ligne)
            data['order_description'] = get_order_description_from_ligne(ligne)
            data['schedule'] = get_schedule_from_ligne(ligne)
            data['line'] = get_line_from_ligne(ligne)
        else:
            # Si pas de ligne trouvée, essayer de récupérer le fournisseur depuis le bon de commande
            try:
                bon_commande = NumeroBonCommande.objects.get(numero=log.bon_commande)
                data['supplier'] = bon_commande.get_supplier()
            except Exception:
                pass
        
        return data
        
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération des données additionnelles: {str(e)}")
    
    # En cas d'erreur, retourner les valeurs par défaut
    return {
        'price': 0.0,
        'supplier': "N/A",
        'ordered_date': "N/A",
        'project_number': "N/A",
        'task_number': "N/A",
        'order_description': "N/A",
        'schedule': "N/A",
        'line': "N/A"
    }

@login_required
@require_http_methods(["GET"])
def get_activity_logs(request):
    """
    Récupère les logs d'activité avec possibilité de filtrage
    """
    try:
        # Récupérer les paramètres de filtrage
        bon_number = request.GET.get('bon_number', '')
        start_date = request.GET.get('start_date', '')
        end_date = request.GET.get('end_date', '')
        user = request.GET.get('user', '')
        # Pagination
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1
        try:
            page_size = int(request.GET.get('page_size', '50'))
        except ValueError:
            page_size = 50
        page_size = max(1, min(page_size, 100))  # borner la taille de page
        
        # Construire la requête de base
        logs = ActivityLog.objects.select_related('fichier').all()
        
        # Appliquer les filtres si présents
        if bon_number:
            logs = logs.filter(bon_commande__icontains=bon_number)
        
        if start_date:
            logs = logs.filter(action_date__gte=start_date)
        
        if end_date:
            logs = logs.filter(action_date__lte=end_date)
        
        if user:
            logs = logs.filter(user__icontains=user)
        
        # Trier les logs par date pour avoir l'ordre chronologique
        logs = logs.order_by('action_date')
        
        # Pagination
        paginator = Paginator(logs, page_size)
        page_obj = paginator.get_page(page)
        logs = list(page_obj.object_list)
        total_count = paginator.count
        has_next = page_obj.has_next()
        has_previous = page_obj.has_previous()
        
        # Créer un compteur par bon de commande pour les numéros de réception (sur la page courante)
        reception_counters = {}
        
        # Caches pour éviter des recalculs
        raw_data_cache = {}  # fichier_id -> raw_data list (ou None)
        additional_data_cache = {}  # (fichier_id, business_id) -> dict
        
        # Formater les résultats
        results = []
        for log in logs:
            try:
                fichier_nom = log.fichier.fichier.name.split('/')[-1] if log.fichier and log.fichier.fichier else 'N/A'
            except:
                fichier_nom = 'N/A'
                
            # Récupérer la Line Description si disponible
            line_description = ''
            
            # Si le fichier existe, essayer de récupérer la description
            if log.fichier and log.bon_commande:
                try:
                    # Récupérer les données brutes du fichier (avec cache)
                    if log.fichier_id not in raw_data_cache:
                        raw_data_cache[log.fichier_id] = log.fichier.get_raw_data()
                    contenu_data = raw_data_cache.get(log.fichier_id)
                    
                    # Vérifier que les données sont valides
                    if not isinstance(contenu_data, list) or len(contenu_data) == 0:
                        logger.warning(f"Format de données invalide pour le fichier {log.fichier.id}")
                        raise ValueError("Format de données invalide")
                    
                    # Trouver la clé pour Line Description et Order
                    line_desc_key = None
                    order_key = None
                    
                    for key in contenu_data[0].keys():
                        key_lower = key.lower() if key else ''
                        if 'description' in key_lower and 'line' in key_lower:
                            line_desc_key = key
                        elif key_lower in ['order', 'po_number', 'bon_commande', 'num_bc', 'commande']:
                            order_key = key
                    
                    # Si on a trouvé les clés nécessaires
                    if order_key and line_desc_key:
                        # Chercher la ligne correspondant au bon de commande
                        for row in contenu_data:
                            if order_key in row and str(row[order_key]) == str(log.bon_commande):
                                if line_desc_key in row:
                                    line_description = str(row[line_desc_key]) if row[line_desc_key] is not None else ''
                                break
                    
                    # Log pour débogage
                    logger.info(f"Line Description pour bon {log.bon_commande}: '{line_description}'")
                    
                except Exception as e:
                    logger.warning(f"Erreur lors de la récupération de l'Line Description pour le log {log.id}: {str(e)}")
            
            # Calcul du numéro de réception (R1, R2, ...) sur l'ensemble trié de la page
            bon_key = log.bon_commande
            reception_counters.setdefault(bon_key, 0)
            reception_counters[bon_key] += 1
            reception_number = f"R{reception_counters[bon_key]}"
            
            # Utiliser le taux d'avancement déjà stocké
            try:
                progress_rate = float(log.progress_rate) if getattr(log, 'progress_rate', None) is not None else 0.0
                progress_rate = round(progress_rate, 2)
            except (ValueError, TypeError):
                progress_rate = 0.0
            
            # Récupérer TOUTES les réceptions pour cette ligne
            line_receptions = ActivityLog.objects.filter(
                bon_commande=log.bon_commande,
                fichier=log.fichier,
                business_id=log.business_id
            ).order_by('action_date')
            
            # Récupérer toutes les réceptions précédentes pour le même bon de commande
            all_previous_receptions = ActivityLog.objects.filter(
                bon_commande=log.bon_commande,
                action_date__lt=log.action_date
            ).order_by('action_date')
            
            # Garder TOUTES les réceptions précédentes (pas seulement la plus récente par ligne)
            # Exclure seulement la réception actuelle exacte
            previous_receptions = [r for r in all_previous_receptions if r.id != log.id]
            previous_receptions.sort(key=lambda x: x.action_date)
            
            # Récupérer les descriptions de lignes pour les réceptions précédentes
            # Utiliser la même logique que pour la réception actuelle
            previous_line_descriptions = {}
            
            # Utiliser la description de ligne actuelle comme référence pour toutes les réceptions précédentes
            # Si nous avons une description de ligne pour la réception actuelle, l'utiliser pour toutes les réceptions précédentes
            if line_description:
                # Appliquer directement la description de ligne actuelle à toutes les réceptions précédentes
                for prev_log in previous_receptions:
                    previous_line_descriptions[prev_log.id] = line_description
            else:
                # Si pas de description pour la réception actuelle, ne pas lancer de parsings coûteux
                previous_line_descriptions = {}
            
            # Calculer les numéros de réception pour les réceptions précédentes
            previous_reception_numbers = {}
            if previous_receptions:
                # Récupérer tous les logs pour ce bon de commande jusqu'à la date actuelle, triés par date
                all_logs_for_bon = [l for l in logs if l.bon_commande == log.bon_commande and l.action_date <= log.action_date]
                all_logs_for_bon.sort(key=lambda x: x.action_date)
                
                # Calculer les numéros de réception
                for i, prev_log in enumerate(all_logs_for_bon, 1):
                    previous_reception_numbers[prev_log.id] = i
            
            # Montants: utiliser directement progress_rate stocké
            try:
                bon_commande = NumeroBonCommande.objects.get(numero=log.bon_commande)
                montant_total = float(bon_commande.montant_total())
                montant_recu = round((progress_rate / 100.0) * montant_total, 2)
            except Exception:
                montant_total = 0.0
                montant_recu = 0.0
            
            # Récupérer les données additionnelles pour cette ligne
            cache_key = (log.fichier_id, log.business_id)
            if cache_key not in additional_data_cache:
                additional_data_cache[cache_key] = get_additional_data_for_reception(log)
            additional_data = additional_data_cache[cache_key]
            
            # Récupérer la devise du bon de commande
            try:
                bon_commande = NumeroBonCommande.objects.get(numero=log.bon_commande)
                currency = bon_commande.get_currency()
            except:
                currency = 'XOF'  # Valeur par défaut
            
            # Ajouter ces données au résultat
            log_data = {
                'id': log.id,
                'bon_commande': log.bon_commande,
                'fichier_importe': fichier_nom,
                'business_id': log.business_id,
                'item_reference': log.item_reference or '',
                'ordered_quantity': float(log.ordered_quantity),
                'quantity_delivered': float(log.quantity_delivered),
                'cumulative_recipe': float(log.cumulative_recipe) if hasattr(log, 'cumulative_recipe') and log.cumulative_recipe is not None else None,
                'quantity_not_delivered': float(log.quantity_not_delivered),
                'user': log.user or 'Anonyme',
                'action_date': log.action_date.strftime('%Y-%m-%d %H:%M:%S'),
                'action_time': log.action_date.strftime('%H:%M:%S'),
                'action_date_only': log.action_date.strftime('%Y-%m-%d'),
                'initial_quantity': float(log.ordered_quantity) + float(log.quantity_delivered),
                'line_description': line_description,
                'reception_number': reception_number,
                'progress_rate': progress_rate,
                'po_amount': montant_total,
                'received_amount': montant_recu,
                'price': additional_data['price'],
                'supplier': additional_data['supplier'],
                'ordered_date': additional_data['ordered_date'],
                'project_number': additional_data['project_number'],
                'task_number': additional_data['task_number'],
                'order_description': additional_data['order_description'],
                'schedule': additional_data['schedule'],
                'line': additional_data['line'],
                'currency': currency,
                'line_receptions': [
                    {
                        'date': r.action_date.strftime('%Y-%m-%d'),
                        'order': r.bon_commande,
                        'ordered_quantity': float(r.ordered_quantity),
                        'quantity_delivered': float(r.quantity_delivered),
                        'quantity_not_delivered': float(r.quantity_not_delivered),
                        'cumulative_recipe': float(r.cumulative_recipe) if r.cumulative_recipe else None,
                        'user': r.user or 'Anonyme',
                        'line': additional_data_cache.get((r.fichier_id, r.business_id))['line'] if (r.fichier_id, r.business_id) in additional_data_cache else get_additional_data_for_reception(r)['line']
                    }
                    for r in line_receptions
                ],
                'previous_receptions': [
                    {
                        'id': r.id,
                        'bon_commande': r.bon_commande,
                        'business_id': r.business_id,
                        'line_description': previous_line_descriptions.get(r.id, ''),
                        'ordered_quantity': float(r.ordered_quantity),
                        'quantity_delivered': float(r.quantity_delivered),
                        'cumulative_recipe': float(r.cumulative_recipe) if hasattr(r, 'cumulative_recipe') and r.cumulative_recipe is not None else None,
                        'quantity_not_delivered': float(r.quantity_not_delivered),
                        'action_date': r.action_date.strftime('%Y-%m-%d'),
                        'user': r.user or 'Anonyme',
                        'reception_number': f"R{previous_reception_numbers.get(r.id, 1)}",
                        'price': (additional_data_cache.get((r.fichier_id, r.business_id)) or get_additional_data_for_reception(r))['price'],
                        'supplier': (additional_data_cache.get((r.fichier_id, r.business_id)) or get_additional_data_for_reception(r))['supplier'],
                        'ordered_date': (additional_data_cache.get((r.fichier_id, r.business_id)) or get_additional_data_for_reception(r))['ordered_date'],
                        'project_number': (additional_data_cache.get((r.fichier_id, r.business_id)) or get_additional_data_for_reception(r))['project_number'],
                        'task_number': (additional_data_cache.get((r.fichier_id, r.business_id)) or get_additional_data_for_reception(r))['task_number'],
                        'order_description': (additional_data_cache.get((r.fichier_id, r.business_id)) or get_additional_data_for_reception(r))['order_description'],
                        'schedule': (additional_data_cache.get((r.fichier_id, r.business_id)) or get_additional_data_for_reception(r))['schedule'],
                        'line': (additional_data_cache.get((r.fichier_id, r.business_id)) or get_additional_data_for_reception(r))['line']
                    }
                    for r in previous_receptions
                ]
            }
            
            results.append(log_data)
        
        return JsonResponse({
            'status': 'success',
            'count': len(results),
            'data': results,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'has_next': has_next,
            'has_previous': has_previous,
        })
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des logs d'activité: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_http_methods(["GET"])
def get_all_bons(request):
    """
    Récupère la liste de tous les numéros de bons de commande
    """
    try:
        # Récupérer tous les bons de commande distincts
        bons = NumeroBonCommande.objects.values_list('numero', flat=True).distinct()
        bon_numbers = list(bons)
        
        # Trier les numéros de bons de commande
        bon_numbers.sort()
        
        # Récupérer les bons qui ont des réceptions
        bons_with_logs = ActivityLog.objects.values_list('bon_commande', flat=True).distinct()
        bons_with_reception = list(bons_with_logs)
        
        return JsonResponse({
            'status': 'success',
            'data': bon_numbers,
            'bons_with_reception': bons_with_reception
        })
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des bons de commande: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
