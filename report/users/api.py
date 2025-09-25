"""
API utilisateurs (lecture seule) pour le tableau de bord vocal.

Expose un résumé d'activité lié aux imports, réceptions et rapports MSRN
associés à l'utilisateur courant.
"""
 
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Sum

# Orders models
from orders.models import FichierImporte, ActivityLog, MSRNReport, NumeroBonCommande, Reception


@login_required
def activity_summary(request):
    """
    Résumé d'activité pour le message vocal.
    - Fenêtre principale: hier (00:00-23:59)
    - Fallback: dernier événement dans les 30 derniers jours
    Dates renvoyées en ISO (YYYY-MM-DD). La localisation se fait côté client.
    """
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    user = request.user
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    last_30_start = today - timedelta(days=30)

    # Imports
    imports_y = FichierImporte.objects.filter(utilisateur=user, date_importation__date=yesterday)
    has_imports_yesterday = imports_y.exists()
    import_date_yesterday = imports_y.order_by('-date_importation').first().date_importation.date().isoformat() if has_imports_yesterday else ''

    last_import = (
        FichierImporte.objects
        .filter(utilisateur=user, date_importation__date__gte=last_30_start)
        .order_by('-date_importation')
        .first()
    )
    last_import_date = last_import.date_importation.date().isoformat() if last_import else ''
    # Nombre de BC présents dans le dernier fichier importé par l'utilisateur
    last_import_po_count = (
        NumeroBonCommande.objects.filter(fichiers=last_import).distinct().count()
        if last_import else 0
    )
    # Nombre total de BC présents sur la plateforme
    total_po_count = NumeroBonCommande.objects.count()

    # Réceptions via ActivityLog, liées aux fichiers de l'utilisateur
    receptions_y = ActivityLog.objects.filter(
        fichier__utilisateur=user,
        action_date__date=yesterday,
    )
    has_receptions_yesterday = receptions_y.exists()
    bons_reception_yesterday = list(receptions_y.values_list('bon_commande', flat=True).distinct())

    # Détails supplémentaires des réceptions d'hier, basés sur les entrées Reception modifiées hier
    receptions_lines_y = Reception.objects.filter(
        fichier__utilisateur=user,
        date_modification__date=yesterday,
    )
    rec_y_count = receptions_lines_y.count()
    rec_y_po_count = receptions_lines_y.values('bon_commande').distinct().count()
    # Totaux sur les lignes modifiées hier (valeurs courantes)
    rec_y_total_quantity_delivered = float(receptions_lines_y.aggregate(s=Sum('quantity_delivered'))['s'] or 0)
    rec_y_total_quantity_not_delivered = float(receptions_lines_y.aggregate(s=Sum('quantity_not_delivered'))['s'] or 0)
    # Corrections négatives approximées: logs avec "Recipe" négatif
    neg_corrections_y = receptions_y.filter(quantity_delivered__lt=0).count()

    # Dernières réceptions (30 jours) - on prend la dernière date et les BCs de cette date
    last_reception_log = (
        ActivityLog.objects
        .filter(fichier__utilisateur=user, action_date__date__gte=last_30_start)
        .order_by('-action_date')
        .first()
    )
    if last_reception_log:
        last_receptions_date = last_reception_log.action_date.date().isoformat()
        # Récupérer les BC distincts pour cette date-là
        same_day_logs = ActivityLog.objects.filter(
            fichier__utilisateur=user,
            action_date__date=last_reception_log.action_date.date(),
        )
        last_bons_reception = list(same_day_logs.values_list('bon_commande', flat=True).distinct())
    else:
        last_receptions_date = ''
        last_bons_reception = []

    # Tendances sur 7 jours (nombre de réceptions par jour)
    last_7_start = today - timedelta(days=7)
    trend_qs = (
        ActivityLog.objects
        .filter(fichier__utilisateur=user, action_date__date__gte=last_7_start, action_date__date__lte=today)
        .values('action_date__date')
        .annotate(c=Count('id'))
        .order_by('action_date__date')
    )
    receptions_trend_7d = [
        {'date': str(row['action_date__date']), 'count': row['c']} for row in trend_qs
    ]
    total_7d = sum(x['count'] for x in receptions_trend_7d) if receptions_trend_7d else 0
    avg_per_day_7d = total_7d / len(receptions_trend_7d) if receptions_trend_7d else 0
    most_active_day_7d = max(receptions_trend_7d, key=lambda x: x['count']) if receptions_trend_7d else None

    # MSRN d'hier pour les BC présents dans des fichiers de l'utilisateur
    user_bcs = NumeroBonCommande.objects.filter(fichiers__utilisateur=user).distinct()
    msrn_y = MSRNReport.objects.filter(bon_commande__in=user_bcs, created_at__date=yesterday).order_by('-created_at')
    has_msrn_yesterday = msrn_y.exists()
    bon_msrn_yesterday = msrn_y.first().bon_commande.numero if has_msrn_yesterday else ''

    last_msrn = (
        MSRNReport.objects
        .filter(bon_commande__in=user_bcs, created_at__date__gte=last_30_start)
        .order_by('-created_at')
        .first()
    )
    last_msrn_bc = last_msrn.bon_commande.numero if last_msrn else ''
    last_msrn_date = last_msrn.created_at.date().isoformat() if last_msrn else ''

    # Compteurs MSRN
    msrn_count_yesterday = msrn_y.count()
    msrn_count_30d = MSRNReport.objects.filter(bon_commande__in=user_bcs, created_at__date__gte=last_30_start).count()

    # BC avec réceptions récentes (hier) mais sans MSRN existante
    bcs_yesterday = NumeroBonCommande.objects.filter(numero__in=bons_reception_yesterday)
    bcs_missing_msrn_y = [bc.numero for bc in bcs_yesterday if not bc.msrn_reports.exists()]

    # Progress/retention (moyenne du taux d'avancement enregistré hier s'il existe)
    progress_vals = receptions_y.exclude(progress_rate__isnull=True).values_list('progress_rate', flat=True)
    avg_progress_rate_y = float(sum([float(p) for p in progress_vals]) / len(progress_vals)) if progress_vals else 0.0

    return JsonResponse({
        'yesterday': str(yesterday),
        'has_imports_yesterday': has_imports_yesterday,
        'import_date_yesterday': import_date_yesterday,
        'last_import_date': last_import_date,
        # Détails import
        'last_import_filename': (last_import.fichier.name if last_import and last_import.fichier else ''),
        'last_import_lines': (last_import.nombre_lignes if last_import else 0),
        'last_import_po_count': last_import_po_count,
        'total_po_count': total_po_count,

        'has_receptions_yesterday': has_receptions_yesterday,
        'bons_reception_yesterday': bons_reception_yesterday,
        'last_receptions_date': last_receptions_date,
        'last_bons_reception': last_bons_reception,
        # Détails réceptions
        'rec_y_count': rec_y_count,
        'rec_y_po_count': rec_y_po_count,
        'rec_y_total_quantity_delivered': rec_y_total_quantity_delivered,
        'rec_y_total_quantity_not_delivered': rec_y_total_quantity_not_delivered,
        'neg_corrections_y': neg_corrections_y,
        # Tendances
        'receptions_trend_7d': receptions_trend_7d,
        'avg_per_day_7d': avg_per_day_7d,
        'most_active_day_7d': most_active_day_7d,

        'has_msrn_yesterday': has_msrn_yesterday,
        'bon_msrn_yesterday': bon_msrn_yesterday,
        'last_msrn_bc': last_msrn_bc,
        'last_msrn_date': last_msrn_date,
        # MSRN
        'msrn_count_yesterday': msrn_count_yesterday,
        'msrn_count_30d': msrn_count_30d,
        'bcs_missing_msrn_y': bcs_missing_msrn_y,
        'avg_progress_rate_y': avg_progress_rate_y,
    })
