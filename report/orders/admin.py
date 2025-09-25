import os
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import FichierImporte, MSRNReport, NumeroBonCommande, LigneFichier


@admin.register(FichierImporte)
class FichierImporteAdmin(admin.ModelAdmin):
    """
    L'admin permet au superuser d'importer directement n'importe quel fichier via un unique champ 'File'.
    Après sauvegarde, on affiche directement les données sous forme tabulaire.
    """
    
    def save_model(self, request, obj, form, change):
        """Capture automatiquement l'utilisateur courant lors de l'enregistrement"""
        if not change:  # Seulement pour les nouveaux fichiers
            obj.utilisateur = request.user
        super().save_model(request, obj, form, change)

    list_display = ('file_link', 'extension', 'date_importation', 'nombre_lignes', 'user_display', 'export_excel_button')
    readonly_fields = ('extension', 'date_importation', 'nombre_lignes', 'data_table_view', 'user_display')

    fieldsets = (
        (None, {
            'fields': ('fichier',)
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
            return f"{obj.utilisateur.username}"
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
                font-family: 'Segoe UI', Arial, sans-serif;
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



    
@admin.register(MSRNReport)
class MSRNReportAdmin(admin.ModelAdmin):
    list_display = ('report_number', 'bon_commande', 'user', 'created_at', 'download_pdf')
    readonly_fields = ('download_pdf',)
    search_fields = ('report_number', 'bon_commande__numero', 'user__username')
    list_filter = ('created_at',)

    def download_pdf(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank">Télécharger</a>', obj.pdf_file.url)
        return "Aucun fichier"
    download_pdf.short_description = "Fichier PDF"