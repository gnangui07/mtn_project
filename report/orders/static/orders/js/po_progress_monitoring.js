document.addEventListener('DOMContentLoaded', function() {
    'use strict';

    const exportBtn = document.querySelector('.export-excel-btn');
    
    // Fonction pour récupérer le jeton CSRF (même logique que detail_bon.js)
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    if (exportBtn) {
        exportBtn.addEventListener('click', async function(e) {
            e.preventDefault();
            
            // URL de base pour l'export (récupérée du href actuel ou codée en dur si besoin)
            // On suppose que le href pointe vers l'URL synchrone
            const baseUrl = this.getAttribute('href');
            const asyncUrl = `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}async=1`;

            try {
                // Afficher un loader initial
                Swal.fire({
                    title: 'Démarrage de l\'export...',
                    text: 'Veuillez patienter',
                    allowOutsideClick: false,
                    didOpen: () => {
                        Swal.showLoading();
                    }
                });

                const response = await fetch(asyncUrl, {
                    method: 'GET',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCookie('csrftoken')
                    }
                });

                if (!response.ok) {
                    throw new Error(`Erreur serveur (${response.status})`);
                }

                const contentType = response.headers.get("content-type");
                
                if (contentType && contentType.includes("application/json")) {
                    const data = await response.json();
                    
                    if (data.async && data.poll_url) {
                        // Mode Asynchrone
                        Swal.close();
                        
                        // Notification Toast
                        Swal.fire({
                            icon: 'info',
                            title: 'Export démarré',
                            text: 'La génération du fichier Excel se fait en arrière-plan. Vous serez notifié une fois terminé.',
                            toast: true,
                            position: 'top-end',
                            showConfirmButton: false,
                            timer: 5000
                        });

                        // ON NE FAIT PLUS DE POLLING ICI.
                        // Le système global (global_notifications.js) s'en chargera.
                        return;
                    } else {
                        // Fallback: Si le serveur renvoie du JSON mais pas async (ex: erreur)
                        Swal.fire('Info', data.message || 'Réponse inattendue', 'info');
                    }
                } else {
                    // Si ce n'est pas du JSON, c'est peut-être le fichier direct (mode synchrone fallback)
                    // Mais fetch ne télécharge pas automatiquement, il faut gérer le blob
                    const blob = await response.blob();
                    const downloadUrl = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = downloadUrl;
                    a.download = 'po_progress_monitoring.xlsx'; // Nom par défaut
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(downloadUrl);
                    Swal.close();
                }

            } catch (error) {
                console.error('Erreur export:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Erreur',
                    text: 'Impossible de lancer l\'export. Veuillez réessayer.'
                });
            }
        });
    }
});
