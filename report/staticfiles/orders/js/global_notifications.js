// Global Notifications System
// This script runs on every page to check for completed async tasks

document.addEventListener('DOMContentLoaded', function() {
    // Only run if user is logged in (check for a known element or cookie if possible, 
    // but here we rely on the API returning empty list if not logged in)
    
    // OPTIMISATION: Intervalle de polling plus court pour une meilleure réactivité
    // 2000ms était un peu long, 1000ms est un bon compromis réactivité/charge serveur
    const NOTIFICATION_INTERVAL = 1000; // Check every 1 second
    
    // Function to get CSRF token
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

    let isPageUnloading = false;
    window.addEventListener('beforeunload', () => {
        isPageUnloading = true;
    });

    async function checkNotifications() {
        if (isPageUnloading) return;

        try {
            // Check if page is visible to avoid polling when tab is backgrounded
            if (document.hidden) return;

            const response = await fetch('/orders/api/check-notifications/');
            
            // If 401/403 (logged out), stop polling
            if (response.status === 401 || response.status === 403) {
                console.warn('User logged out, stopping notifications polling');
                return; // Stop polling
            }
            
            if (!response.ok) return;

            const data = await response.json();
            
            if (data.notifications && data.notifications.length > 0) {
                if (!isPageUnloading) {
                    data.notifications.forEach(notification => {
                        handleNotification(notification);
                    });
                }
            }
        } catch (error) {
            // Silent fail for network errors, especially during navigation
            if (isPageUnloading || error.name === 'AbortError') return;

            if (error.name !== 'AbortError') {
                 // Check for network error specifically
                 const errorMsg = error.message || '';
                 if (errorMsg.includes('NetworkError') || 
                     errorMsg.includes('Failed to fetch') || 
                     errorMsg.includes('Network request failed')) {
                     return;
                 }
                 console.debug('Notification check failed:', error);
            }
        }
    }

    function handleNotification(notification) {
        const result = notification.result;
        
        if (notification.status === 'SUCCESS' && result) {
            // Success Notification
            let title = 'Tâche terminée';
            let html = '';
            let icon = 'success';

            // Customize message based on task type (inferred from result structure)
            if (result.report_number) {
                // MSRN Report
                title = 'MSRN Généré';
                // Use filename if available to show full identifier (MSRN + PO), otherwise fallback to report_number
                const displayName = result.filename ? result.filename.replace('.pdf', '') : result.report_number;
                html = `Le rapport MSRN <strong>${displayName}</strong> a été généré avec succès.<br><br>
                        <a href="/orders/msrn-report/${result.report_id}/" class="btn btn-sm btn-primary">Ouvrir le rapport</a>`;
            } else if (result.filename && (result.download_url || result.log_id)) {
                // Other PDF Reports (Penalty, etc.)
                // Clean filename for display (remove ID if needed, but filename from backend is usually safe now)
                title = 'Document Généré';
                const downloadLink = result.download_url || '#';
                html = `Le document <strong>${result.filename}</strong> est prêt.<br><br>
                        <a href="${downloadLink}" target="_blank" class="btn btn-sm btn-primary">Télécharger</a>`;
            } else if (result.content_base64) {
                // Export Excel (Base64 content)
                title = 'Export Terminé';
                const filename = result.filename || 'export.xlsx';
                
                try {
                    const byteCharacters = atob(result.content_base64);
                    const byteNumbers = new Array(byteCharacters.length);
                    for (let i = 0; i < byteCharacters.length; i++) {
                        byteNumbers[i] = byteCharacters.charCodeAt(i);
                    }
                    const byteArray = new Uint8Array(byteNumbers);
                    const blob = new Blob([byteArray], { type: result.content_type || 'application/octet-stream' });
                    const downloadUrl = window.URL.createObjectURL(blob);
                    
                    html = `Le fichier <strong>${filename}</strong> est prêt.<br><br>
                            <a href="${downloadUrl}" download="${filename}" class="btn btn-sm btn-success">Télécharger</a>`;
                } catch (e) {
                    console.error("Erreur conversion base64", e);
                    html = `Votre export est prêt mais une erreur est survenue lors de la préparation du téléchargement.`;
                }
            } else if (result.file_content) {
                // Export Excel
                title = 'Export Terminé';
                // Handle base64 download if needed, or link
                html = `Votre export est prêt.`;
            }

            // Display Toast
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: icon,
                    title: title,
                    html: html,
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: false,
                    showCloseButton: true,
                    timer: 10000, // Show for 10s
                    timerProgressBar: true,
                    didOpen: (toast) => {
                        toast.addEventListener('mouseenter', Swal.stopTimer)
                        toast.addEventListener('mouseleave', Swal.resumeTimer)
                    }
                });
            }
        } else if (notification.status === 'FAILURE') {
            // Failure Notification
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'Erreur',
                    text: `Une tâche a échoué: ${notification.error || 'Erreur inconnue'}`,
                    toast: true,
                    position: 'top-end',
                    timer: 5000
                });
            }
        }
    }

    // Start polling loop
    setInterval(checkNotifications, NOTIFICATION_INTERVAL);
});
