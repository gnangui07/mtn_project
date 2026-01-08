"""
But:
- Enregistrer les modèles de l'app orders dans l'admin et offrir des vues/colonnes utiles (aperçu des données, export, liens).

Étapes:
- Définir des ModelAdmin personnalisés pour FichierImporte et MSRNReport.
- Afficher un tableau HTML des données importées et des actions d'export.

Entrées:
- Actions de l'admin Django (HTTP), objets modèles.

Sorties:
- Pages d'administration enrichies avec aperçus, liens et boutons d'export.
"""
import os
from django import forms
from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import FichierImporte, MSRNReport, NumeroBonCommande, LigneFichier, MSRNSignatureTracking

# Try to import Celery tasks and helpers
try:
    from .tasks import import_fichier_task
    from .task_status_api import register_user_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False


class FichierImporteForm(forms.ModelForm):
    async_import = forms.BooleanField(
        required=False, 
        initial=False,
        label="Import en arrière-plan (Async)",
        help_text="Recommandé pour les gros fichiers (> 10 Mo). L'import se fera en tâche de fond et vous rendra la main immédiatement."
    )

    class Meta:
        model = FichierImporte
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not CELERY_AVAILABLE:
            self.fields['async_import'].disabled = True
            self.fields['async_import'].help_text = "Celery non disponible (Import synchrone uniquement)"


@admin.register(FichierImporte)
class FichierImporteAdmin(admin.ModelAdmin):
    """
    L'admin permet au superuser d'importer directement n'importe quel fichier via un unique champ 'File'.
    Après sauvegarde, on affiche directement les données sous forme tabulaire.
    """
    form = FichierImporteForm
    
    def save_model(self, request, obj, form, change):
        """Capture automatiquement l'utilisateur courant lors de l'enregistrement"""
        if not change:  # Seulement pour les nouveaux fichiers
            obj.utilisateur = request.user
        
        # Gestion de l'import Async
        is_async = form.cleaned_data.get('async_import')
        
        if is_async and CELERY_AVAILABLE and not change:
            # 1. Marquer pour sauter l'extraction automatique dans save()
            obj._skip_extraction = True
            
            # 2. Sauvegarder le fichier physique (upload)
            super().save_model(request, obj, form, change)
            
            # 3. Lancer la tâche Celery
            try:
                # On utilise le path absolu du fichier uploadé
                file_path = obj.fichier.path
                
                task = import_fichier_task.delay(
                    file_path=file_path,
                    user_id=request.user.id,
                    original_filename=os.path.basename(obj.fichier.name),
                    fichier_id=obj.id
                )
                
                # 4. Enregistrer la tâche pour le suivi UI
                register_user_task(request.user.id, task.id, 'import_fichier')
                
                # 5. Notifier l'utilisateur
                messages.info(
                    request, 
                    format_html(
                        "<strong>Import démarré en arrière-plan !</strong><br>"
                        "Vous pouvez continuer à naviguer. Tâche ID: <code>{}</code>",
                        task.id
                    )
                )
            except Exception as e:
                # Fallback si erreur de lancement de tâche
                messages.error(request, f"Erreur lors du lancement de la tâche async: {e}")
                # On pourrait relancer en synchrone ici si on voulait, 
                # mais pour l'instant on laisse l'utilisateur réessayer.
        else:
            # Comportement standard (Synchrone)
            super().save_model(request, obj, form, change)

    list_display = ['file_link', 'extension', 'date_importation', 'nombre_lignes', 'user_display', 'export_excel_button']
    readonly_fields = ('extension', 'date_importation', 'nombre_lignes', 'data_table_view', 'user_display')
    list_per_page = 20
    list_filter = ['extension', 'date_importation', 'utilisateur']
    search_fields = ['fichier', 'utilisateur__email', 'utilisateur__first_name', 'utilisateur__last_name']

    fieldsets = (
        (None, {
            'fields': ('fichier', 'async_import')
        }),
        ('File Metadata', {
            'fields': ('extension', 'date_importation', 'nombre_lignes'),
            'description': "Les champs ci-dessous sont remplis automatiquement après l'enregistrement."
        }),
        ('File Data', {
            'fields': ('data_table_view',),
            'description': "Affichage des données importées sous forme de tableau."
        }),
    )

    def data_table_view(self, obj):
        """
        Affiche les données sous forme de tableau HTML directement dans l'interface d'administration.
        """
        if not obj:
            return mark_safe("<p>Aucun objet trouvé</p>")
            
        # Récupérer les lignes du fichier
        lignes = obj.lignes.all().order_by('numero_ligne')
        
        # Vérifier s'il y a des données
        if not lignes.exists():
            return mark_safe("<p>Aucune donnée disponible</p>")
            
        # Préparer les données pour l'affichage
        donnees = [ligne.contenu for ligne in lignes if ligne.contenu]
        
        # Vérifier si on a des données valides
        if not donnees:
            return mark_safe("<p>Aucune donnée valide à afficher</p>")
            
        # Générer le tableau avec les données
        return mark_safe(self.generate_html_table(donnees))


    data_table_view.short_description = "Data View"
    
    def user_display(self, obj):
        """Affiche l'utilisateur qui a importé le fichier"""
        if obj.utilisateur:
            return f"{obj.utilisateur.get_full_name() or obj.utilisateur.email}"
        return "—"  # tiret cadratin pour valeur vide
    user_display.short_description = "Importé par"
    
    def file_link(self, obj):
        """Crée un lien vers la page de modification au lieu de télécharger le fichier"""
        if obj.fichier:
            # Créer un lien qui pointe vers la page de modification
            url = f'/admin/orders/fichierimporte/{obj.id}/change/'
            filename = os.path.basename(obj.fichier.name)
            return format_html('<a href="{}">{}</a>', url, filename)
        return "—"  # tiret cadratin pour valeur vide
    file_link.short_description = "File"
    
    def export_excel_button(self, obj):
        """Affiche un bouton pour exporter le fichier complet en Excel avec les données mises à jour"""
        if obj.id:
            url = f'/orders/export-fichier-complet/{obj.id}/'
            return format_html('<a href="{}" class="button" target="_blank">Exporter Excel</a>', url)
        return "—"  # tiret cadratin pour valeur vide
    export_excel_button.short_description = "Export Excel"
    
    def generate_html_table(self, content):
        """
        Génère un tableau HTML à partir des données du fichier importé
        """
        if not content:
            return "<p>Aucune donnée disponible</p>"
        
        # Style pour ressembler à Excel et occuper tout l'espace disponible
        style = """
        <style>
            /* Masquer les éléments d'interface Django pour avoir plus d'espace */
            #content h1 { display: none; }
            .module h2 { display: none; }
            #content-main .form-row > div.field-data_table_view { width: 100%; }
            .field-data_table_view label { display: none; }
            .field-data_table_view .readonly { margin: 0 !important; padding: 0 !important; }
            
            /* Style Excel */
            .data-table {
                border-collapse: collapse;
                table-layout: auto;
                min-width: 150% !important; /* Force une largeur minimale qui dépasse la largeur de l'écran */
                width: auto !important;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                border: 1px solid #d0d0d0;
                margin: 0;
                padding: 0;
                display: table !important; /* Assure que c'est bien un tableau */
            }
            .data-table th {
                background-color: #f0f0f0;
                font-weight: bold;
                text-align: center;
                padding: 6px 8px;
                border: 1px solid #d0d0d0;
                white-space: nowrap;
                position: sticky;
                top: 0;
                z-index: 10;
                color: #000;
                border-bottom: 2px solid #a0a0a0;
            }
            .data-table td {
                padding: 4px 8px;
                border: 1px solid #d0d0d0;
                white-space: nowrap;
                min-width: 80px;
            }
            .data-table tr:nth-child(even) {
                background-color: #fafafa;
            }
            .data-table tr:hover {
                background-color: #e8f4fc;
            }
            
            /* Container avec défilement horizontal et vertical - prise d'espace maximal */
            .data-container {
                overflow: scroll !important; /* Force le défilement dans les deux directions */
                overflow-x: scroll !important; /* Force explicitement le défilement horizontal */
                overflow-y: scroll !important; /* Force explicitement le défilement vertical */
                max-height: 90vh; /* Presque tout l'écran vertical */
                width: 98%;
                padding: 0;
                margin: 0;
                border: 1px solid #d0d0d0;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
                background-color: white;
                display: block !important;
            }
            
            /* Élargir la zone du tableau à 100% de la page */
            #container { max-width: none !important; width: 98% !important; margin: 0 auto !important; overflow-x: visible !important; }
            .form-panel { max-width: none !important; padding-top: 10px !important; overflow-x: visible !important; }
            #content { max-width: none !important; overflow-x: visible !important; }
            #content-main { overflow-x: visible !important; }
            .form-row { padding: 0 !important; margin: 0 !important; overflow-x: visible !important; }
            fieldset { overflow-x: visible !important; }
            .fieldset { overflow-x: visible !important; }
            /* Désactiver tous les overflows qui pourraient bloquer le défilement horizontal */
            .module { overflow: visible !important; }
            form { overflow: visible !important; }
            
            /* Message d'info Excel-like */
            .excel-info {
                background-color: #e8f4fc;
                padding: 6px 10px;
                margin-bottom: 6px;
                border: 1px solid #ccc;
                font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #333;
            }
        </style>
        
        <!-- Script pour maximiser l'espace du tableau -->
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                // Ajuster les dimensions pour maximiser l'espace
                const resizeTable = function() {
                    const containers = document.querySelectorAll('.data-container');
                    containers.forEach(container => {
                        container.style.maxHeight = (window.innerHeight - 150) + 'px';
                        // Force le défilement horizontal
                        if(container.querySelector('table')) {
                            const table = container.querySelector('table');
                            // S'assurer que le tableau est plus large que son conteneur
                            if(table.offsetWidth <= container.offsetWidth) {
                                table.style.minWidth = Math.max(container.offsetWidth * 1.5, 1500) + 'px';
                            }
                        }
                    });
                };
                
                // Exécuter au chargement et lors du redimensionnement
                resizeTable();
                window.addEventListener('resize', resizeTable);
                
                // Désactiver les marges inutiles et forcer le défilement horizontal
                const styleEl = document.createElement('style');
            });
        </script>
        
                styleEl.textContent = `
                    #container { padding-top: 10px !important; }
                    .data-container::-webkit-scrollbar { height: 12px !important; width: 12px !important; }
                    .data-container::-webkit-scrollbar-thumb { background: #c1c1c1; }
                `;
                document.head.appendChild(styleEl);
                
                // Vérifier si le défilement horizontal fonctionne, sinon ajouter des cellules vides pour élargir le tableau
                setTimeout(function() {
                    const tables = document.querySelectorAll('.data-table');
                    tables.forEach(table => {
                        if(table.offsetWidth <= table.parentElement.offsetWidth) {
                            // Ajouter des colonnes supplémentaires pour forcer le défilement
                            const headerRow = table.querySelector('thead tr');
                            if(headerRow) {
                                for(let i = 0; i < 5; i++) {
                                    const extraCell = document.createElement('th');
                                    extraCell.innerHTML = 'Extra ' + (i+1);
                                    extraCell.style.minWidth = '200px';
                                    headerRow.appendChild(extraCell);
                                }
                            }
                        }
                    });
                }, 500);
            });
        </script>
        """
        
        table_html = f'{style}<div class="data-container"><table class="data-table">'
        
        # Gérer différents types de contenu
        if isinstance(content, list) and content and isinstance(content[0], dict):
            # Données tabulaires (CSV, Excel, etc.)
            # Extraire les en-têtes de la première ligne
            headers = list(content[0].keys())
            
            # En-tête du tableau
            table_html += '<thead><tr>'
            for header in headers:
                table_html += f'<th>{header}</th>'
            table_html += '</tr></thead>'
            
            # Corps du tableau
            table_html += '<tbody>'
            for row in content:
                table_html += '<tr>'
                for header in headers:
                    value = row.get(header, '')
                    # Formater la valeur selon son type
                    if isinstance(value, (dict, list)):
                        import json
                        formatted_value = json.dumps(value, ensure_ascii=False)
                        table_html += f'<td>{formatted_value}</td>'
                    else:
                        table_html += f'<td>{value}</td>'
                table_html += '</tr>'
            table_html += '</tbody>'
        
        elif isinstance(content, dict) and 'lines' in content:
            # Pour les fichiers texte
            table_html += '<thead><tr><th>Line Number</th><th>Content</th></tr></thead>'
            table_html += '<tbody>'
            for i, line in enumerate(content['lines'], 1):
                table_html += f'<tr><td>{i}</td><td>{line}</td></tr>'
            table_html += '</tbody>'
        
        elif isinstance(content, dict) and not ('raw_bytes_hex' in content or 'error' in content):
            # Pour les objets JSON simples
            table_html += '<thead><tr><th>Key</th><th>Value</th></tr></thead>'
            table_html += '<tbody>'
            for key, value in content.items():
                # Formater la valeur selon son type
                if isinstance(value, (dict, list)):
                    import json
                    formatted_value = json.dumps(value, ensure_ascii=False)
                    table_html += f'<tr><td>{key}</td><td>{formatted_value}</td></tr>'
                else:
                    table_html += f'<tr><td>{key}</td><td>{value}</td></tr>'
            table_html += '</tbody>'
        
        elif isinstance(content, dict) and ('raw_bytes_hex' in content or 'error' in content or 'raw_text' in content):
            # Pour les fichiers binaires ou les erreurs
            table_html += '<thead><tr><th>Type</th><th>Content</th></tr></thead>'
            table_html += '<tbody>'
            if 'error' in content:
                table_html += f'<tr><td>Error</td><td>{content["error"]}</td></tr>'
            elif 'raw_bytes_hex' in content:
                hex_preview = content["raw_bytes_hex"][:500] + '...' if len(content["raw_bytes_hex"]) > 500 else content["raw_bytes_hex"]
                table_html += f'<tr><td>Binary (HEX)</td><td><div style="overflow-x:auto;max-height:300px;"><pre>{hex_preview}</pre></div></td></tr>'
            elif 'raw_text' in content:
                text_preview = content["raw_text"][:1000] + '...' if len(content["raw_text"]) > 1000 else content["raw_text"]
                table_html += f'<tr><td>Text</td><td><pre style="white-space:pre-wrap;">{text_preview}</pre></td></tr>'
            table_html += '</tbody>'
        
        table_html += '</table></div>'
        return table_html



    
class MSRNSignatureTrackingInline(admin.TabularInline):
    """
    Inline simplifié pour les signatures.
    Le superuser entre uniquement la date de signature.
    """
    model = MSRNSignatureTracking
    extra = 0
    min_num = 0
    can_delete = False
    
    fields = ('signatory_role', 'signatory_name', 'date_received', 'status')
    readonly_fields = ('signatory_role', 'signatory_name', 'status')
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('order')


class CPUFilter(admin.SimpleListFilter):
    """Filtre personnalisé par CPU"""
    title = 'CPU'
    parameter_name = 'cpu'
    
    def lookups(self, request, model_admin):
        cpus = MSRNReport.objects.exclude(
            cpu_snapshot__isnull=True
        ).exclude(
            cpu_snapshot=''
        ).values_list('cpu_snapshot', flat=True).distinct().order_by('cpu_snapshot')
        return [(cpu, cpu) for cpu in cpus if cpu]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(cpu_snapshot=self.value())
        return queryset


class ProjectManagerFilter(admin.SimpleListFilter):
    """Filtre personnalisé par Project Manager"""
    title = 'Project Manager'
    parameter_name = 'pm'
    
    def lookups(self, request, model_admin):
        pms = MSRNReport.objects.exclude(
            project_manager_snapshot__isnull=True
        ).exclude(
            project_manager_snapshot=''
        ).values_list('project_manager_snapshot', flat=True).distinct().order_by('project_manager_snapshot')
        return [(pm, pm) for pm in pms if pm]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(project_manager_snapshot=self.value())
        return queryset


@admin.register(MSRNReport)
class MSRNReportAdmin(admin.ModelAdmin):
    """
    Admin amélioré pour le suivi des MSRN avec:
    - Affichage du supplier, taux d'avancement
    - Chaque signataire en colonne avec nom + date réception
    - Filtres par CPU et Project Manager
    """
    
    list_display = (
        'report_number', 
        'bon_commande', 
        'supplier_display',
        'company_display',
        'montant_recu_display',
        'currency_display',
        'retention_rate_display',
        'progress_rate_display',
        'cpu_display',
        'pm_column',
        'coordinator_column',
        'senior_pm_column',
        'manager_portfolio_column',
        'gm_epmo_column',
        'senior_tech_lead_column',
        'vendor_column',
        'created_at', 
        'download_pdf',
        'edit_signatures_link',
    )
    
    list_filter = (
        'created_at',
        'workflow_status',
        CPUFilter,
        ProjectManagerFilter,
    )
    
    search_fields = (
        'report_number', 
        'bon_commande__numero', 
        'user',
        'supplier_snapshot',
        'cpu_snapshot',
        'project_manager_snapshot',
    )
    
    readonly_fields = (
        'report_number',
        'bon_commande',
        'created_at',
        'download_pdf',
        'montant_total_snapshot',
        'montant_recu_snapshot',
        'progress_rate_snapshot',
    )
    
    inlines = [MSRNSignatureTrackingInline]
    list_per_page = 25
    date_hierarchy = 'created_at'
    actions = ['export_to_excel']
    
    @admin.action(description="📥 Exporter les MSRN sélectionnés en Excel")
    def export_to_excel(self, request, queryset):
        """
        Exporte les rapports MSRN sélectionnés vers un fichier Excel professionnel.
        Appelle la fonction centralisée dans views_export.py.
        """
        from .views_export import export_msrn_selection_to_excel
        try:
            return export_msrn_selection_to_excel(queryset)
        except Exception as e:
            self.message_user(request, f"❌ Erreur lors de l'export Excel : {str(e)}", level='error')
            from django.shortcuts import redirect
            return None
    
    def _get_signatory_column(self, obj, role):
        """Génère le contenu d'une colonne signataire en se basant sur le tracking"""
        try:
            # Source de vérité : la table de suivi des signatures
            sig = obj.signature_tracking.filter(signatory_role=role).first()
        except Exception:
            sig = None
            
        # Si aucune entrée de signature n'existe pour ce rôle sur ce rapport, 
        # c'est que ce n'est pas un signataire requis pour ce CPU.
        if not sig:
            return mark_safe('<span style="color: #999;">-</span>')
        
        name = sig.signatory_name
        
        if sig.date_received:
            date_signed = sig.date_received.strftime('%d/%m/%Y')
            return format_html(
                '<div style="font-size: 11px; line-height: 1.4;">'
                '<strong>{}</strong><br>'
                '<span style="color: #28a745;">✅ Signé: {}</span>'
                '</div>',
                name, date_signed
            )
        else:
            return format_html(
                '<div style="font-size: 11px; line-height: 1.4;">'
                '<strong>{}</strong><br>'
                '<span style="color: #ffc107;">⏳ En attente</span>'
                '</div>',
                name
            )
    
    def pm_column(self, obj):
        return self._get_signatory_column(obj, 'project_manager')
    pm_column.short_description = 'Project Manager'
    
    def coordinator_column(self, obj):
        return self._get_signatory_column(obj, 'project_coordinator')
    coordinator_column.short_description = 'Coordinator'
    
    def senior_pm_column(self, obj):
        return self._get_signatory_column(obj, 'senior_pm')
    senior_pm_column.short_description = 'Senior PM'
    
    def manager_portfolio_column(self, obj):
        return self._get_signatory_column(obj, 'manager_portfolio')
    manager_portfolio_column.short_description = 'Manager Portfolio'
    
    def gm_epmo_column(self, obj):
        return self._get_signatory_column(obj, 'gm_epmo')
    gm_epmo_column.short_description = 'GM EPMO'

    def senior_tech_lead_column(self, obj):
        return self._get_signatory_column(obj, 'senior_technical_lead')
    senior_tech_lead_column.short_description = 'Snr Tech Lead'

    def vendor_column(self, obj):
        return self._get_signatory_column(obj, 'vendor')
    vendor_column.short_description = 'Vendor'
    
    def supplier_display(self, obj):
        return obj.supplier_snapshot or '-'
    supplier_display.short_description = 'Fournisseur'
    supplier_display.admin_order_field = 'supplier_snapshot'
    
    def progress_rate_display(self, obj):
        rate = obj.progress_rate_snapshot or 0
        try:
            rate_value = float(rate) if rate else 0
        except (ValueError, TypeError):
            rate_value = 0
        
        if rate_value >= 100:
            color = '#28a745'
        elif rate_value >= 50:
            color = '#ffc107'
        else:
            color = '#dc3545'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, rate
        )
    progress_rate_display.short_description = 'Taux'
    
    def cpu_display(self, obj):
        return obj.cpu_snapshot or '-'
    cpu_display.short_description = 'CPU'
    
    def company_display(self, obj):
        """Affiche la company (toujours MTN)"""
        return 'MTN'
    company_display.short_description = 'Company'
    
    def montant_recu_display(self, obj):
        """Affiche le montant reçu avec formatage localisé"""
        montant = obj.montant_recu_snapshot or 0
        try:
            # On formate d'abord en string pour être sûr, puis on passe à format_html
            formatted_montant = "{:,.0f}".format(float(montant)).replace(',', ' ')
            return format_html(
                '<span style="font-weight: 500;">{}</span>',
                formatted_montant
            )
        except (ValueError, TypeError):
            return '-'
    montant_recu_display.short_description = 'Montant Reçu'
    montant_recu_display.admin_order_field = 'montant_recu_snapshot'
    
    def currency_display(self, obj):
        """Affiche la devise (snapshot)"""
        return obj.currency_snapshot or 'XOF'
    currency_display.short_description = 'Devise'
    
    def retention_rate_display(self, obj):
        """Affiche le taux de rétention (snapshot) avec formatage"""
        rate = obj.retention_rate_snapshot or 0
        try:
            rate_value = float(rate) if rate else 0
        except (ValueError, TypeError):
            rate_value = 0
        
        if rate_value > 0:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">{}%</span>',
                rate_value
            )
        return mark_safe('<span style="color: #28a745;">0%</span>')
    retention_rate_display.short_description = 'Taux Rétention'
    
    def download_pdf(self, obj):
        if obj.pdf_file:
            return format_html(
                '<a href="{}" target="_blank" style="background: #1F5C99; color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 11px;">📄 PDF</a>', 
                obj.pdf_file.url
            )
        return mark_safe('<span style="color: #999;">-</span>')
    download_pdf.short_description = "PDF"
    
    def edit_signatures_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:orders_msrnsignaturetracking_changelist') + f'?msrn_report__id__exact={obj.id}'
        return format_html(
            '<a href="{}" style="background: #28a745; color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 11px;">✏️ Signatures</a>',
            url
        )
    edit_signatures_link.short_description = "Actions"


@admin.register(MSRNSignatureTracking)
class MSRNSignatureTrackingAdmin(admin.ModelAdmin):
    """
    Admin simplifié pour les signatures MSRN.
    Le superuser entre uniquement la date de signature.
    """
    
    list_display = (
        'msrn_report_link',
        'supplier_display',
        'signatory_role',
        'signatory_name',
        'date_received',
        'status_display',
    )
    
    list_editable = ('date_received',)
    
    list_filter = (
        'status',
        'signatory_role',
        'msrn_report__supplier_snapshot',
    )
    
    search_fields = (
        'msrn_report__report_number',
        'msrn_report__supplier_snapshot',
        'signatory_name',
    )
    
    list_per_page = 50
    ordering = ['-msrn_report__created_at', 'order']
    
    def msrn_report_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:orders_msrnreport_change', args=[obj.msrn_report.id])
        return format_html(
            '<a href="{}" style="font-weight: bold;">{}</a>',
            url, obj.msrn_report.report_number
        )
    msrn_report_link.short_description = 'MSRN'
    msrn_report_link.admin_order_field = 'msrn_report__report_number'
    
    def supplier_display(self, obj):
        return obj.msrn_report.supplier_snapshot or '-'
    supplier_display.short_description = 'Fournisseur'
    
    def status_display(self, obj):
        if obj.status == 'signed':
            return mark_safe('<span style="color: #28a745; font-weight: bold;">✅ Signé</span>')
        else:
            return mark_safe('<span style="color: #ffc107;">⏳ En attente</span>')
    status_display.short_description = 'Statut'