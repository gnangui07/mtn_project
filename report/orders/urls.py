from django.urls import path, include
from django.views.generic.base import RedirectView
from . import (
    api,
    compensation_letter_api,
    delay_evaluation_api,
    msrn_api,
    penalty_amount_api,
    penalty_amendment_api,
    penalty_api,
    reception_api,
    views,
    views_export,
)


app_name = 'orders'

urlpatterns = [
    # Pages principales
    path('', views.accueil, name='accueil'),
    path('reception/', views.accueil, name='reception'),
    
    # Gestion des fichiers comme des bons de commande
    path('bons/<int:bon_id>/', views.details_bon, name='details_bon'),
    path('bons/search/', views.search_bon, name='search_bon'),
    path('consultation/', views.consultation, name='consultation'),
    path('import/', views.import_fichier, name='import_fichier'),
    path('po-progress-monitoring/', views.po_progress_monitoring, name='po_progress_monitoring'),
   
    # Téléchargement des fichiers
    path('telecharger/<int:fichier_id>/', views.telecharger_fichier, name='telecharger_fichier'),
    path('telecharger/<int:fichier_id>/<str:format_export>/', views.telecharger_fichier, name='telecharger_fichier_format'),
    path('export-excel/<int:bon_id>/', views_export.export_bon_excel, name='export_bon_excel'),
    path('export-fichier-complet/<int:fichier_id>/', views_export.export_fichier_complet, name='export_fichier_complet'),
    path('export-po-progress-monitoring/', views_export.export_po_progress_monitoring, name='export_po_progress_monitoring'),

    # API endpoints (pour compatibilité)
    path('api/update-quantity-delivered/<int:fichier_id>/', reception_api.update_quantity_delivered, name='update_quantity_delivered'),
    path('api/receptions/<int:fichier_id>/bulk_update/', reception_api.bulk_update_receptions, name='bulk_update_receptions'),
    path('api/reset-quantity-delivered/<int:fichier_id>/', reception_api.reset_quantity_delivered, name='reset_quantity_delivered'),
    path('api/bons/<int:bon_id>/update-retention/', reception_api.update_retention, name='update_retention'),
    path('api/bons/<int:bon_id>/receptions/', reception_api.get_receptions, name='get_receptions'),
    
    # Nouvelles APIs pour correction groupée
    path('api/reception-history/<int:fichier_id>/', reception_api.get_reception_history, name='get_reception_history'),
    path('api/bulk-correction/<int:fichier_id>/', reception_api.bulk_correction_quantity_delivered, name='bulk_correction_quantity_delivered'),
   
    
    # Journal d'activité
    path('api/activity-logs/', api.get_activity_logs, name='get_activity_logs'),
    path('api/all-bons/', api.get_all_bons, name='get_all_bons'),
    
    # Téléchargement des rapports MSRN
    path('msrn-report/<int:report_id>/', views.download_msrn_report, name='download_msrn_report'),
    path('msrn/archive/', views.msrn_archive, name='msrn_archive'),
    path('msrn/<int:msrn_id>/export-po-lines/', views_export.export_msrn_po_lines, name='export_msrn_po_lines'),
    path('api/generate-msrn/<int:bon_id>/', msrn_api.generate_msrn_report_api, name='generate_msrn_report_api'),
    path('api/msrn/<int:msrn_id>/update-retention/', msrn_api.update_msrn_retention, name='update_msrn_retention'),
    path('api/generate-penalty/<int:bon_id>/', penalty_api.generate_penalty_report_api, name='generate_penalty_report_api'),
    path('api/generate-penalty-amendment/<int:bon_id>/', penalty_amendment_api.generate_penalty_amendment_report_api, name='generate_penalty_amendment_report_api'),
    path('api/get-penalty-amount/<int:bon_id>/', penalty_amount_api.get_penalty_amount_api, name='get_penalty_amount_api'),
    path('api/generate-delay-evaluation/<int:bon_id>/', delay_evaluation_api.generate_delay_evaluation_report_api, name='generate_delay_evaluation_report_api'),
    path('api/generate-compensation-letter/<int:bon_id>/', compensation_letter_api.generate_compensation_letter_api, name='generate_compensation_letter_api'),
    
    # Analytics API
    path('api/analytics/', include('orders.urls_analytics')),
    
    # Évaluation des fournisseurs
    path('vendor-evaluation/<int:bon_commande_id>/', views.vendor_evaluation, name='vendor_evaluation'),
    path('vendor-evaluations/', views.vendor_evaluation_list, name='vendor_evaluation_list'),
    path('vendor-evaluation-detail/<int:evaluation_id>/', views.vendor_evaluation_detail, name='vendor_evaluation_detail'),
    path('export-vendor-evaluations/', views_export.export_vendor_evaluations, name='export_vendor_evaluations'),
    path('vendor-ranking/', views.vendor_ranking, name='vendor_ranking'),
    path('export-vendor-ranking/', views_export.export_vendor_ranking, name='export_vendor_ranking'),
    
    # Timeline delays
    path('timeline-delays/<int:bon_commande_id>/', views.timeline_delays, name='timeline_delays'),
    path('api/update-delays/<int:timeline_id>/', views.update_delays, name='update_delays'),
  
]
