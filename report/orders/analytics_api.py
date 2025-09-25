from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import logging
from django.db.models import Sum, Count, Case, When, IntegerField, F, Q, Avg
from django.db.models.functions import TruncMonth, TruncDay, TruncHour, ExtractHour, ExtractWeekDay
from .models import ActivityLog, NumeroBonCommande, FichierImporte, Reception
from datetime import datetime, timedelta

# Configuration du logger
logger = logging.getLogger(__name__)

@require_http_methods(["GET"])
def get_heatmap_data(request):
    """
    Récupère les données pour la carte thermique des activités:
    - Distribution des activités par jour de la semaine et heure
    - Intensité basée sur le nombre d'activités ou les quantités reçues
    """
    try:
        # Récupérer la période demandée (par défaut 30 jours)
        period = int(request.GET.get('period', 30))
        # Vérifier que la période est valide
        valid_periods = [7, 30, 90, 365]
        if period not in valid_periods:
            period = 30
            
        # Définir la date de début en fonction de la période
        today = timezone.now().date()
        start_date = today - timezone.timedelta(days=period)
        
        # Type de données pour la carte thermique
        data_type = request.GET.get('data_type', 'activity_count')
        valid_types = ['activity_count', 'reception_quantity', 'reception_ratio']
        if data_type not in valid_types:
            data_type = 'activity_count'
        
        # Récupérer les activités dans la période
        activities = ActivityLog.objects.filter(action_date__gte=start_date)
        
        # Préparer la structure de données pour la carte thermique
        # Jours de la semaine (0 = Lundi, 6 = Dimanche)
        days = [0, 1, 2, 3, 4, 5, 6]
        # Heures de la journée (0-23)
        hours = list(range(24))
        
        # Initialiser la matrice de données
        heatmap_data = []
        
        # Agréger les données selon le type demandé
        if data_type == 'activity_count':
            # Compter le nombre d'activités par jour et heure
            activity_counts = activities.annotate(
                # Extraire le jour de la semaine (0=dimanche, 1=lundi, ..., 6=samedi)
                weekday=ExtractWeekDay('action_date'),
                hour=ExtractHour('action_date')
            ).values('weekday', 'hour').annotate(
                count=Count('id')
            )
            
            # Créer un dictionnaire pour un accès facile
            data_dict = {}
            for item in activity_counts:
                # Ajuster pour que lundi = 0 (Django utilise dimanche = 1)
                # En SQLite, ExtractWeekDay retourne 1 pour dimanche, 2 pour lundi, etc.
                # On veut 0 pour lundi, 1 pour mardi, ..., 6 pour dimanche
                weekday = (item['weekday'] - 1) % 7
                # Pour avoir lundi=0, mardi=1, ..., dimanche=6
                weekday = (weekday + 6) % 7
                hour = item['hour']
                data_dict[(weekday, hour)] = item['count']
            
            # Construire les données finales
            for day in days:
                for hour in hours:
                    value = data_dict.get((day, hour), 0)
                    if value > 0:  # Ne pas inclure les valeurs nulles pour optimiser
                        heatmap_data.append({
                            'day': day,
                            'hour': hour,
                            'value': value
                        })
        
        elif data_type == 'reception_quantity':
            # Somme des quantités reçues par jour et heure
            reception_quantities = activities.filter(quantity_delivered__gt=0).annotate(
                weekday=ExtractWeekDay('action_date'),
                hour=ExtractHour('action_date')
            ).values('weekday', 'hour').annotate(
                total_quantity=Sum('quantity_delivered')
            )
            
            # Créer un dictionnaire pour un accès facile
            data_dict = {}
            for item in reception_quantities:
                # Même ajustement que pour activity_counts
                weekday = (item['weekday'] - 1) % 7
                # Pour avoir lundi=0, mardi=1, ..., dimanche=6
                weekday = (weekday + 6) % 7
                hour = item['hour']
                data_dict[(weekday, hour)] = float(item['total_quantity'])
            
            # Construire les données finales
            for day in days:
                for hour in hours:
                    value = data_dict.get((day, hour), 0)
                    if value > 0:  # Ne pas inclure les valeurs nulles
                        heatmap_data.append({
                            'day': day,
                            'hour': hour,
                            'value': value
                        })
        
        elif data_type == 'reception_ratio':
            # Calculer le ratio moyen de réception par jour et heure
            reception_ratios = activities.filter(quantity_delivered__gt=0).annotate(
                weekday=ExtractWeekDay('action_date'),
                hour=ExtractHour('action_date'),
                # Calculer le ratio pour chaque activité
                ratio=F('quantity_delivered') / (F('quantity_delivered') + F('quantity_not_delivered')) * 100
            ).values('weekday', 'hour').annotate(
                avg_ratio=Avg('ratio')
            )
            
            # Créer un dictionnaire pour un accès facile
            data_dict = {}
            for item in reception_ratios:
                weekday = (item['weekday'] - 1) % 7
                hour = item['hour']
                data_dict[(weekday, hour)] = float(item['avg_ratio'])
            
            # Construire les données finales
            for day in days:
                for hour in hours:
                    value = data_dict.get((day, hour), 0)
                    if value > 0:  # Ne pas inclure les valeurs nulles
                        heatmap_data.append({
                            'day': day,
                            'hour': hour,
                            'value': value
                        })
        
        # Préparer les labels pour l'affichage
        day_labels = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        hour_labels = [f'{h:02d}:00' for h in hours]
        
        # Préparer la réponse
        response_data = {
            'status': 'success',
            'heatmap_data': heatmap_data,
            'day_labels': day_labels,
            'hour_labels': hour_labels,
            'data_type': data_type
        }
        
        return JsonResponse(response_data)
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des données de la carte thermique: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_http_methods(["GET"])
def get_analytics_data(request):
    """
    Récupère les données analytiques pour le tableau de bord selon les spécifications:
    1. Nombre de bons partiellement reçus (au moins une réception)
    2. Taux de réception global pour ces bons
    3. Nombre de bons entièrement reçus (ordered_quantity = 0)
    4. Graphique circulaire: bons partiellement reçus vs jamais reçus
    5. Histogramme: bons partiellement reçus par mois
    6. Courbe d'évolution: bons entièrement reçus dans le temps
    """
    try:
        # Récupérer la période demandée (par défaut 30 jours)
        period = int(request.GET.get('period', 30))
        # Vérifier que la période est valide
        valid_periods = [7, 30, 90, 365]
        if period not in valid_periods:
            period = 30
            
        # Définir la date de début en fonction de la période
        now = timezone.now()
        today = now.date()
        start_date = now - timezone.timedelta(days=period)

        
        # 1. Nombre de bons partiellement reçus (au moins une réception)
        # Récupérer tous les bons de commande ayant au moins une réception
        bons_avec_reception = Reception.objects.filter(
            quantity_delivered__gt=0
        ).values('bon_commande').distinct()
        nb_bons_avec_reception = bons_avec_reception.count()    
        
        # Récupérer le nombre total de bons de commande
        total_bons = NumeroBonCommande.objects.count()
        
        # 2. Taux de réception global pour les bons partiellement reçus
        # Calculer le pourcentage de réception pour chaque bon de commande, puis faire la moyenne
        latest_logs = {}
       # Récupérer les IDs de bons sous forme de chaînes
        bon_ids = list(bons_avec_reception.values_list('bon_commande', flat=True))
        bon_ids_str = [str(b) for b in bon_ids]

        for log in ActivityLog.objects.filter(
            bon_commande__in=bon_ids_str,
            action_date__gte=start_date
).order_by('bon_commande', '-action_date'):

            if log.bon_commande not in latest_logs:
                latest_logs[log.bon_commande] = log
        
        # Calculer le pourcentage de réception pour chaque bon de commande
        pourcentages_reception = []
        for log in latest_logs.values():
            # La quantité commandée est la somme de quantity_delivered et quantity_not_delivered
            ordered = float(log.quantity_delivered) + float(log.quantity_not_delivered)
            received = float(log.quantity_delivered)
            
            # Calculer le pourcentage de réception pour ce bon de commande
            if ordered > 0:
                pourcentage = (received / ordered) * 100
                pourcentages_reception.append(pourcentage)
        
        # Calculer le taux de réception global comme la moyenne des pourcentages
        taux_reception_global = sum(pourcentages_reception) / len(pourcentages_reception) if pourcentages_reception else 0
        taux_reception_global = round(taux_reception_global, 2)
        
        # Pour référence, calculer aussi les totaux
        total_ordered = sum(float(log.quantity_delivered) + float(log.quantity_not_delivered) for log in latest_logs.values())
        total_quantity_delivered = sum(float(log.quantity_delivered) for log in latest_logs.values())
        
        # 3. Nombre de bons entièrement reçus (ordered_quantity = quantity_delivered)
        # Récupérer tous les bons de commande où ordered_quantity = quantity_delivered
        from django.db.models import Q, F
        
        # Récupérer les bons où au moins une ligne est complètement reçue
        bons_avec_lignes_completes = Reception.objects.filter(
            ordered_quantity=F('quantity_delivered'),
            ordered_quantity__gt=0  # Éviter les cas où les deux sont à 0
        ).values('bon_commande').distinct()
        
        # Vérifier que toutes les lignes du bon sont complètement reçues
        bons_entierement_recus = []
        for bon in bons_avec_lignes_completes:
            bon_id = bon['bon_commande']
            # Compter le nombre total de lignes pour ce bon
            total_lignes = Reception.objects.filter(bon_commande_id=bon_id).count()
            # Compter le nombre de lignes complètement reçues
            lignes_completes = Reception.objects.filter(
                bon_commande_id=bon_id,
                ordered_quantity=F('quantity_delivered'),
                ordered_quantity__gt=0
            ).count()
            # Si toutes les lignes sont complètement reçues
            if total_lignes > 0 and total_lignes == lignes_completes:
                bons_entierement_recus.append(bon_id)
        
        nb_bons_entierement_recus = len(bons_entierement_recus)
        
        # 4. Données pour le graphique circulaire: bons partiellement reçus vs jamais reçus
        nb_bons_sans_reception = total_bons - nb_bons_avec_reception
        
        # 5. Données pour l'histogramme: bons partiellement reçus par mois
        # Grouper les réceptions par mois
        receptions_par_mois = ActivityLog.objects.filter(
            quantity_delivered__gt=0,
            action_date__gte=start_date
        ).annotate(
            mois=TruncMonth('action_date')
        ).values('mois').annotate(
            nb_bons=Count('bon_commande', distinct=True)
        ).order_by('mois')
        
        # Formater les données pour l'histogramme
        mois_labels = []
        mois_values = []
        
        for item in receptions_par_mois:
            mois_labels.append(item['mois'].strftime('%b %Y'))
            mois_values.append(item['nb_bons'])
        
        # 6. Données pour la courbe d'évolution: quantités reçues par jour
        # Grouper les quantités reçues par jour
        evolution_bons_complets = ActivityLog.objects.filter(
            quantity_delivered__gt=0,
            action_date__gte=start_date
        ).values('action_date__date').annotate(
            nb_bons=Sum('quantity_delivered')
        ).order_by('action_date__date')
        
        # Formater les données pour la courbe d'évolution
        dates = []
        counts = []
        
        # Créer un dictionnaire pour stocker les valeurs par date
        evolution_data = {}
        
        # Initialiser toutes les dates de la période avec 0
        for i in range(period):
            date_key = (today - timezone.timedelta(days=i)).strftime('%Y-%m-%d')
            evolution_data[date_key] = 0
        
        # Remplir avec les données réelles
        for item in evolution_bons_complets:
            date_key = item['action_date__date'].strftime('%Y-%m-%d')
            evolution_data[date_key] = item['nb_bons']
        
        # Convertir en listes pour le graphique
        dates = list(evolution_data.keys())
        counts = list(evolution_data.values())
        
        # Préparer la réponse avec toutes les données demandées
        response_data = {
            'status': 'success',
            'bons_avec_reception': nb_bons_avec_reception,
            'taux_reception_global': taux_reception_global,
            'bons_entierement_recus': nb_bons_entierement_recus,
            'pourcentage_bons_entierement_recus': round((nb_bons_entierement_recus / total_bons) * 100, 2) if total_bons > 0 else 0,
            'total_bons': total_bons,
            
            # Données pour le graphique circulaire
            'pie_chart': {
                'labels': ['Bons avec réception', 'Bons sans réception'],
                'values': [nb_bons_avec_reception, nb_bons_sans_reception]
            },
            
            # Données pour l'histogramme
            'bar_chart': {
                'labels': mois_labels,
                'values': mois_values
            },
            
            # Données pour la courbe d'évolution
            'line_chart': {
                'dates': dates,
                'counts': counts
            }
        }
        
        return JsonResponse(response_data)
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des données analytiques: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
