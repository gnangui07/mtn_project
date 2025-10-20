from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import logging
from decimal import Decimal, InvalidOperation
from .models import FichierImporte, ActivityLog, NumeroBonCommande, Reception, LigneFichier
from django.utils import timezone

# Configuration du logger
logger = logging.getLogger(__name__)


def get_price_from_ligne(ligne):
    """Extrait le prix unitaire d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return 0.0
    
    contenu = ligne.contenu
    
    # Chercher la colonne Prix/Price dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('price' in key_lower or 'prix' in key_lower or 'unit price' in key_lower or 'prix unitaire' in key_lower) and value:
            try:
                # Essayer de convertir en nombre
                return float(str(value).replace(',', '.').strip())
            except (ValueError, TypeError):
                pass
    
    return 0.0


def get_supplier_from_ligne(ligne):
    """Extrait le fournisseur d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return "N/A"
    
    contenu = ligne.contenu
    
    # Chercher la colonne Supplier/Fournisseur dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if 'supplier' in key_lower and value:
            return str(value)
    
    # Chercher d'autres colonnes qui pourraient contenir le fournisseur
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('fournisseur' in key_lower or 'vendeur' in key_lower or 'vendor' in key_lower) and value:
            return str(value)
    
    return "N/A"


def get_ordered_date_from_ligne(ligne):
    """Extrait la date de commande (Ordered) d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return "N/A"
    
    contenu = ligne.contenu
    
    # Chercher la colonne Ordered dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if key_lower == 'ordered' and value:
            return str(value)
    
    # Chercher d'autres colonnes qui pourraient contenir la date de commande
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('date' in key_lower and 'order' in key_lower) or ('date' in key_lower and 'commande' in key_lower) and value:
            return str(value)
    
    return "N/A"


def get_project_number_from_ligne(ligne):
    """Extrait le numéro de projet d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return "N/A"
    
    contenu = ligne.contenu
    
    # Chercher la colonne Project Number dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('project' in key_lower and 'number' in key_lower) or ('projet' in key_lower and 'numero' in key_lower) and value:
            return str(value)
    
    # Chercher d'autres colonnes qui pourraient contenir le numéro de projet
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('project' in key_lower or 'projet' in key_lower) and value:
            return str(value)
    
    return "N/A"


def get_task_number_from_ligne(ligne):
    """Extrait le numéro de tâche d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return "N/A"
    
    contenu = ligne.contenu
    
    # Chercher la colonne Task Number dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('task' in key_lower and 'number' in key_lower) or ('tache' in key_lower and 'numero' in key_lower) and value:
            return str(value)
    
    # Chercher d'autres colonnes qui pourraient contenir le numéro de tâche
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('task' in key_lower or 'tache' in key_lower) and value:
            return str(value)
    
    return "N/A"


def get_order_description_from_ligne(ligne):
    """Extrait la description de commande d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return "N/A"
    
    contenu = ligne.contenu
    
    # Chercher la colonne Order Description dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('order' in key_lower and 'description' in key_lower) or ('commande' in key_lower and 'description' in key_lower) and value:
            return str(value)
    
    # Chercher d'autres colonnes qui pourraient contenir la description de commande
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if 'description' in key_lower and value and 'line' not in key_lower:
            return str(value)
    
    return "N/A"


def get_schedule_from_ligne(ligne):
    """Extrait le schedule d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return "N/A"
    
    contenu = ligne.contenu
    
    # Chercher la colonne Schedule dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if 'schedule' in key_lower and value:
            return str(value)
    
    # Chercher d'autres colonnes qui pourraient contenir le schedule
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('planning' in key_lower or 'calendrier' in key_lower or 'echeance' in key_lower) and value:
            return str(value)
    
    return "N/A"


def get_line_from_ligne(ligne):
    """Extrait le numéro de ligne d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return "N/A"
    
    contenu = ligne.contenu
    
    # Chercher la colonne Line dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if 'line' in key_lower and value and 'description' not in key_lower:
            return str(value)
    
    # Chercher d'autres colonnes qui pourraient contenir le numéro de ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('ligne' in key_lower or 'row' in key_lower or 'item' in key_lower) and value:
            return str(value)
    
    return "N/A"


@csrf_exempt
def update_recipe_quantity(request, fichier_id):
    logger = logging.getLogger(__name__)
    
    # Log pour déboguer
    logger.info(f"API update_recipe_quantity appelée avec fichier_id={fichier_id}, méthode={request.method}")
    
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
                ).values('row_index', 'recipe_quantity', 'ordered_quantity', 'remaining_quantity', 'unit_price')
                
                # Convertir en dictionnaire pour un accès facile
                reception_dict = {}
                for item in receptions:
                    row_index = str(item['row_index'])
                    
                    # Récupérer les valeurs
                    recipe_quantity = float(item['recipe_quantity']) if item['recipe_quantity'] is not None else 0.0
                    ordered_quantity = float(item['ordered_quantity']) if item['ordered_quantity'] is not None else 0.0
                    remaining_quantity = float(item['remaining_quantity']) if item['remaining_quantity'] is not None else 0.0
                    unit_price = float(item['unit_price']) if item['unit_price'] is not None else 0.0
                    
                    # Calcul du remaining basé sur le cumul existant
                    remaining_quantity = max(0, ordered_quantity - recipe_quantity)  # Garantir >= 0
            
                    # Récupérer la ligne correspondante pour extraire le fournisseur
                    ligne = LigneFichier.objects.filter(
                        fichier=fichier,
                        numero_ligne=item['row_index']
                    ).first()
                    
                    # Extraire toutes les données additionnelles
                    supplier = get_supplier_from_ligne(ligne) if ligne else "N/A"
                    price = unit_price if unit_price > 0 else get_price_from_ligne(ligne) if ligne else 0.0
                    ordered_date = get_ordered_date_from_ligne(ligne) if ligne else "N/A"
                    project_number = get_project_number_from_ligne(ligne) if ligne else "N/A"
                    task_number = get_task_number_from_ligne(ligne) if ligne else "N/A"
                    order_description = get_order_description_from_ligne(ligne) if ligne else "N/A"
                    
                    reception_dict[row_index] = {
                      'recipe_quantity': recipe_quantity,
                      'ordered_quantity': ordered_quantity,
                      'remaining_quantity': remaining_quantity,
                      'unit_price': unit_price,
                      'price': price,
                      'supplier': supplier,
                      'ordered_date': ordered_date,
                      'project_number': project_number,
                      'task_number': task_number,
                      'order_description': order_description,
                      # Nouveau champ pour indiquer si la ligne est complète
                      'is_complete': recipe_quantity >= ordered_quantity
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
                row_index = data.get('row_index')
                new_recipe_quantity = data.get('recipe_quantity')  # Nouvelle quantité totale
                original_quantity = data.get('original_quantity')  # Quantité originale pour référence
                
                # Vérifier que tous les paramètres requis sont présents
                if not all([bon_number, row_index is not None, new_recipe_quantity is not None, original_quantity is not None]):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Données manquantes'
                    }, status=400)
                
                # Convertir en Decimal pour les calculs précis
                new_recipe_quantity = Decimal(str(new_recipe_quantity))
                original_quantity = Decimal(str(original_quantity))
                
                # Récupérer le bon de commande
                bon_commande = NumeroBonCommande.objects.get(numero=bon_number)
                
                # Permettre les valeurs négatives pour les corrections d'erreurs
                # Mais vérifier que le total final ne devient pas négatif
                if new_recipe_quantity < 0:
                    # Récupérer la quantité existante pour vérifier le total final
                    try:
                        reception = Reception.objects.get(
                            bon_commande=bon_commande,
                            fichier=fichier,
                            row_index=row_index
                        )
                        current_recipe = reception.recipe_quantity or Decimal('0')
                        final_total = current_recipe + new_recipe_quantity
                        
                        if final_total < 0:
                            return JsonResponse({
                                'status': 'error',
                                'message': f'La correction de {new_recipe_quantity} rendrait le total négatif (actuel: {current_recipe}, nouveau: {final_total})'
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
                        row_index=row_index
                    )
                    existing_recipe_quantity = reception.recipe_quantity or Decimal('0')
                except Reception.DoesNotExist:
                    existing_recipe_quantity = Decimal('0')
                
                # Ajouter la nouvelle quantité à la quantité existante
                total_recipe_quantity = existing_recipe_quantity + new_recipe_quantity
                
                # Vérifier que la quantité totale ne dépasse pas la quantité commandée
                if total_recipe_quantity > original_quantity:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'La quantité totale reçue ({total_recipe_quantity}) dépasse la quantité commandée ({original_quantity})'
                    }, status=400)
                
                # Calculer la quantité restante
                remaining_quantity = original_quantity - total_recipe_quantity
                
                # Mettre à jour ou créer l'entrée de réception
                reception, created = Reception.objects.update_or_create(
                    bon_commande=bon_commande,
                    fichier=fichier,
                    row_index=row_index,
                    defaults={
                        'recipe_quantity': total_recipe_quantity,
                        'ordered_quantity': original_quantity,
                        'remaining_quantity': remaining_quantity,
                        'user': request.user.email if hasattr(request, 'user') and request.user.is_authenticated else None
                    }
                )
                
                # Calculer le taux d'avancement actuel
                taux_avancement = bon_commande.taux_avancement()
                
                # Créer une entrée dans le journal d'activité avec le taux d'avancement actuel
                ActivityLog.objects.create(
                    bon_commande=bon_number,
                    fichier=fichier,
                    row_index=row_index,
                    ordered_quantity=original_quantity,
                    recipe_quantity=new_recipe_quantity,  # Quantité individuelle entrée par l'utilisateur
                    remaining_quantity=remaining_quantity,
                    user=reception.user,
                    cumulative_recipe=total_recipe_quantity,  # Quantité cumulative totale
                    progress_rate=taux_avancement
                )
                
                # Générer et enregistrer le rapport MSRN
                from .reports import generate_msrn_report
                from .models import MSRNReport
                from django.core.files import File
                
                try:
                    # Créer et sauvegarder le rapport (le report_number sera généré automatiquement)
                    report = MSRNReport(
                        bon_commande=bon_commande,
                        user=request.user if hasattr(request, 'user') and request.user.is_authenticated else None
                    )
                    report.save()
                    
                    # Générer le PDF avec le numéro de rapport qui vient d'être créé
                    pdf_buffer = generate_msrn_report(bon_commande, report.report_number, user_email=request.user.email if hasattr(request, 'user') and request.user.is_authenticated else None)
                    
                    # Mettre à jour le fichier PDF avec le bon numéro
                    report.pdf_file.save(
                        f"MSRN-{report.report_number}.pdf",
                        File(pdf_buffer)
                    )
                    report.save()
                    
                    logger.info(f"Rapport MSRN généré avec succès: MSRN-{report.report_number}")
                    
                except Exception as e:
                    logger.error(f"Erreur lors de la génération du rapport MSRN: {str(e)}", exc_info=True) 
                    # Ne pas échouer la requête si la génération du rapport échoue
                
                # Préparer la réponse JSON avec le total cumulé
                response_data = {
                    'status': 'success',
                    'recipe_quantity': float(total_recipe_quantity),  # Utiliser le total cumulé
                    'ordered_quantity': float(original_quantity),
                    'remaining_quantity': float(remaining_quantity),
                    'taux_avancement': float(bon_commande.taux_avancement()),
                    'montant_total_recu': float(bon_commande.montant_recu()),
                    'msrn_report_id': report.id if 'report' in locals() else None  # Ajout de l'ID du rapport
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


@require_http_methods(["GET"])
def get_activity_logs(request):
    # Fonction pour récupérer les données additionnelles d'une réception
    def get_additional_data_for_reception(log):
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
                row_index=log.row_index
            ).first()
            
            if reception and reception.unit_price:
                data['price'] = float(reception.unit_price)
            
            # Récupérer la ligne du fichier pour extraire les autres données
            ligne = LigneFichier.objects.filter(
                fichier=log.fichier,
                numero_ligne=log.row_index
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
    """
    Récupère les logs d'activité avec possibilité de filtrage
    """
    try:
        # Récupérer les paramètres de filtrage
        bon_number = request.GET.get('bon_number', '')
        start_date = request.GET.get('start_date', '')
        end_date = request.GET.get('end_date', '')
        user = request.GET.get('user', '')
        
        # Construire la requête de base
        logs = ActivityLog.objects.all()
        
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
        logs = logs.order_by('action_date')[:500]
        
        # Créer un compteur par bon de commande pour les numéros de réception
        reception_counters = {}
        
        # Trier tous les logs par date (du plus ancien au plus récent)
        logs = sorted(logs, key=lambda x: x.action_date)
        
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
                    # Récupérer les données brutes du fichier
                    contenu_data = log.fichier.get_raw_data()
                    
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
            
            # Calcul du numéro de réception (R1, R2, ...)
            bon_key = log.bon_commande
            reception_counters.setdefault(bon_key, 0)
            reception_counters[bon_key] += 1
            reception_number = f"R{reception_counters[bon_key]}"
            
            # Vérifier si le log a déjà un taux d'avancement stocké
            if hasattr(log, 'progress_rate') and log.progress_rate is not None:
                # Utiliser le taux d'avancement déjà stocké dans le log
                try:
                    progress_rate = float(log.progress_rate)
                    progress_rate = round(progress_rate, 2)  # Arrondir à 2 décimales
                except (ValueError, TypeError):
                    progress_rate = 0
            else:
                # Calculer le taux d'avancement au moment de cette réception
                try:
                    # Chercher le bon de commande correspondant
                    bon_commande = NumeroBonCommande.objects.get(numero=bon_key)
                    
                    # Trouver tous les logs jusqu'à ce log (inclus) par ordre chronologique
                    logs_jusqu_ici = [l for l in logs if l.action_date <= log.action_date]
                    
                    # Créer un dictionnaire pour stocker la dernière valeur de chaque réception
                    # Clé : (bon_commande, fichier_id, row_index)
                    # Valeur : montant de la réception
                    dernieres_receptions = {}
                    
                    # Parcourir tous les logs jusqu'à celui-ci (inclus)
                    for l in logs_jusqu_ici:
                        if l.bon_commande == bon_key:  # Seulement pour ce bon de commande
                            try:
                                # Récupérer la réception correspondante
                                reception = Reception.objects.filter(
                                    bon_commande__numero=bon_key,
                                    fichier=l.fichier,
                                    row_index=l.row_index
                                ).first()
                                
                                if reception:
                                    # Mettre à jour la dernière valeur pour cette ligne
                                    reception_key = (bon_key, reception.fichier.id, reception.row_index)
                                    dernieres_receptions[reception_key] = reception.recipe_quantity * reception.unit_price
                            except Exception as e:
                                logger.warning(f"Erreur lors de la récupération de la réception: {str(e)}")
                    
                    # Calculer le montant total reçu jusqu'à ce moment (historique)
                    # Ce montant représente la somme cumulée des réceptions jusqu'à la date de cette activité
                    from decimal import Decimal
                    montant_recu_cumule = sum(dernieres_receptions.values(), Decimal('0'))
                    montant_total = bon_commande.montant_total()  # Montant total de la commande (constant)
                    
                    # Calculer le taux d'avancement
                    if montant_total > 0:
                        progress_rate = (montant_recu_cumule / montant_total) * 100
                        progress_rate = round(progress_rate, 2)  # Arrondir à 2 décimales
                    else:
                        progress_rate = 0
                except (NumeroBonCommande.DoesNotExist, ZeroDivisionError, ValueError, TypeError) as e:
                    logger.warning(f"Erreur lors du calcul du taux d'avancement: {str(e)}")
                    progress_rate = 0
            
            # Récupérer TOUTES les réceptions pour cette ligne
            line_receptions = ActivityLog.objects.filter(
                bon_commande=log.bon_commande,
                fichier=log.fichier,
                row_index=log.row_index
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
                # Si nous n'avons pas de description pour la réception actuelle, essayer de la trouver dans le fichier
                all_line_descriptions = {}
                
                # Utiliser le fichier de la réception actuelle comme référence
                if log.fichier and log.fichier.contenu:
                    try:
                        contenu_data = json.loads(log.fichier.contenu)
                        if isinstance(contenu_data, list) and len(contenu_data) > 0:
                            line_desc_key = None
                            order_key = None
                            
                            for key in contenu_data[0].keys():
                                key_lower = key.lower() if key else ''
                                if 'description' in key_lower and 'line' in key_lower:
                                    line_desc_key = key
                                elif key_lower in ['order', 'po_number', 'bon_commande', 'num_bc', 'commande']:
                                    order_key = key
                            
                            if order_key and line_desc_key:
                                # Parcourir toutes les lignes pour trouver les descriptions
                                for row in contenu_data:
                                    if order_key in row and str(row[order_key]) == str(log.bon_commande):
                                        if line_desc_key in row:
                                            # Utiliser la description de ligne pour toutes les réceptions de ce bon
                                            all_line_descriptions[log.bon_commande] = str(row[line_desc_key]) if row[line_desc_key] is not None else ''
                                            break
                        
                        # Si nous avons trouvé une description, l'utiliser pour toutes les réceptions précédentes
                        if log.bon_commande in all_line_descriptions:
                            for prev_log in previous_receptions:
                                previous_line_descriptions[prev_log.id] = all_line_descriptions[log.bon_commande]
                    except Exception as e:
                        logger.warning(f"Erreur lors de la récupération des descriptions de ligne: {str(e)}")
                
                # Si nous n'avons toujours pas de description, essayer de la trouver dans les fichiers des réceptions précédentes
                if not all_line_descriptions:
                    for prev_log in previous_receptions:
                        # Essayer de récupérer la description depuis le fichier de cette réception précédente
                        prev_line_description = ''
                        if prev_log.fichier and prev_log.fichier.contenu:
                            try:
                                prev_contenu_data = json.loads(prev_log.fichier.contenu)
                                if isinstance(prev_contenu_data, list) and len(prev_contenu_data) > 0:
                                    # Trouver les clés nécessaires
                                    prev_line_desc_key = None
                                    prev_order_key = None
                                    
                                    for key in prev_contenu_data[0].keys():
                                        key_lower = key.lower() if key else ''
                                        if 'description' in key_lower and 'line' in key_lower:
                                            prev_line_desc_key = key
                                        elif key_lower in ['order', 'po_number', 'bon_commande', 'num_bc', 'commande']:
                                            prev_order_key = key
                                    
                                    if prev_order_key and prev_line_desc_key:
                                        # Chercher la ligne correspondant au bon de commande
                                        for row in prev_contenu_data:
                                            if prev_order_key in row and str(row[prev_order_key]) == str(prev_log.bon_commande):
                                                if prev_line_desc_key in row:
                                                    prev_line_description = str(row[prev_line_desc_key]) if row[prev_line_desc_key] is not None else ''
                                                break
                            except Exception as e:
                                logger.warning(f"Erreur lors de la récupération de la description pour la réception précédente {prev_log.id}: {str(e)}")
                        
                        # Utiliser cette description ou une chaîne vide si rien n'a été trouvé
                        previous_line_descriptions[prev_log.id] = prev_line_description or ''
            
            # Calculer les numéros de réception pour les réceptions précédentes
            previous_reception_numbers = {}
            if previous_receptions:
                # Récupérer tous les logs pour ce bon de commande jusqu'à la date actuelle, triés par date
                all_logs_for_bon = [l for l in logs if l.bon_commande == log.bon_commande and l.action_date <= log.action_date]
                all_logs_for_bon.sort(key=lambda x: x.action_date)
                
                # Calculer les numéros de réception
                for i, prev_log in enumerate(all_logs_for_bon, 1):
                    previous_reception_numbers[prev_log.id] = i
            
            # Pour les montants, nous devons utiliser EXACTEMENT la même logique que pour le progress_rate
            # Nous allons donc recalculer le montant reçu cumulé de la même manière
            try:
                # Récupérer le bon de commande
                bon_commande = NumeroBonCommande.objects.get(numero=log.bon_commande)
                montant_total = float(bon_commande.montant_total())
                
                # Recalculer le montant reçu cumulé en utilisant exactement la même logique
                # que celle utilisée pour le calcul du taux d'avancement
                bon_key = log.bon_commande
                
                # Trouver tous les logs jusqu'à ce log (inclus) par ordre chronologique
                logs_jusqu_ici = [l for l in logs if l.action_date <= log.action_date]
                
                # Créer un dictionnaire pour stocker la dernière valeur de chaque réception
                dernieres_receptions = {}
                
                # Parcourir tous les logs jusqu'à celui-ci (inclus)
                for l in logs_jusqu_ici:
                    if l.bon_commande == bon_key:  # Seulement pour ce bon de commande
                        try:
                            # Récupérer la réception correspondante
                            reception = Reception.objects.filter(
                                bon_commande__numero=bon_key,
                                fichier=l.fichier,
                                row_index=l.row_index
                            ).first()
                            
                            if reception:
                                # Mettre à jour la dernière valeur pour cette ligne
                                reception_key = (bon_key, reception.fichier.id, reception.row_index)
                                dernieres_receptions[reception_key] = reception.recipe_quantity * reception.unit_price
                        except Exception as e:
                            logger.warning(f"Erreur lors de la récupération de la réception: {str(e)}")
                
                # Calculer le montant total reçu jusqu'à ce moment (historique)
                from decimal import Decimal
                montant_recu_cumule = sum(dernieres_receptions.values(), Decimal('0'))
                montant_recu = float(montant_recu_cumule)
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des montants: {str(e)}")
                montant_total = 0
                montant_recu = 0
            
            # Récupérer les données additionnelles pour cette ligne
            additional_data = get_additional_data_for_reception(log)
            
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
                'row_index': log.row_index,
                'item_reference': log.item_reference or '',
                'ordered_quantity': float(log.ordered_quantity),
                'recipe_quantity': float(log.recipe_quantity),
                'cumulative_recipe': float(log.cumulative_recipe) if hasattr(log, 'cumulative_recipe') and log.cumulative_recipe is not None else None,
                'remaining_quantity': float(log.remaining_quantity),
                'user': log.user or 'Anonyme',
                'action_date': log.action_date.strftime('%Y-%m-%d %H:%M:%S'),
                'action_time': log.action_date.strftime('%H:%M:%S'),
                'action_date_only': log.action_date.strftime('%Y-%m-%d'),
                'initial_quantity': float(log.ordered_quantity) + float(log.recipe_quantity),
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
                        'recipe_quantity': float(r.recipe_quantity),
                        'remaining_quantity': float(r.remaining_quantity),
                        'cumulative_recipe': float(r.cumulative_recipe) if r.cumulative_recipe else None,
                        'user': r.user or 'Anonyme',
                        'line': get_additional_data_for_reception(r)['line']
                    }
                    for r in line_receptions
                ],
                'previous_receptions': [
                    {
                        'id': r.id,
                        'bon_commande': r.bon_commande,
                        'row_index': r.row_index,
                        'line_description': previous_line_descriptions.get(r.id, ''),
                        'ordered_quantity': float(r.ordered_quantity),
                        'recipe_quantity': float(r.recipe_quantity),
                        'cumulative_recipe': float(r.cumulative_recipe) if hasattr(r, 'cumulative_recipe') and r.cumulative_recipe is not None else None,
                        'remaining_quantity': float(r.remaining_quantity),
                        'action_date': r.action_date.strftime('%Y-%m-%d'),
                        'user': r.user or 'Anonyme',
                        'reception_number': f"R{previous_reception_numbers.get(r.id, 1)}",
                        'price': get_additional_data_for_reception(r)['price'],
                        'supplier': get_additional_data_for_reception(r)['supplier'],
                        'ordered_date': get_additional_data_for_reception(r)['ordered_date'],
                        'project_number': get_additional_data_for_reception(r)['project_number'],
                        'task_number': get_additional_data_for_reception(r)['task_number'],
                        'order_description': get_additional_data_for_reception(r)['order_description'],
                        'schedule': get_additional_data_for_reception(r)['schedule'],
                        'line': get_additional_data_for_reception(r)['line']
                    }
                    for r in previous_receptions
                ]
            }
            
            results.append(log_data)
        
        return JsonResponse({
            'status': 'success',
            'count': len(results),
            'data': results
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


@csrf_exempt
@require_http_methods(["POST"])
def reset_recipe_quantity(request, fichier_id):
    """
    API pour réinitialiser toutes les quantités reçues (Recipe) pour un bon de commande.
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
            logger.info(f"Réinitialisation des quantités Recipe pour le bon {bon_number} par {user}")
            
            # Créer une entrée dans le journal d'activité pour la réinitialisation
            if deleted_count > 0:
                ActivityLog.objects.create(
                    bon_commande=bon_number,
                    fichier=fichier,
                    row_index=-1,  # Valeur spéciale pour indiquer une réinitialisation globale
                    ordered_quantity=0,
                    recipe_quantity=0,
                    remaining_quantity=0,
                    user=user,
                    action_date=timezone.now()
                )
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Toutes les quantités Recipe pour le bon {bon_number} ont été réinitialisées ({deleted_count} entrées supprimées).'
                })
            else:
                return JsonResponse({
                    'status': 'success',
                    'message': f'Aucune donnée Recipe à réinitialiser pour le bon {bon_number}.'
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
        logger.exception(f"Erreur lors de la réinitialisation des quantités Recipe: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
