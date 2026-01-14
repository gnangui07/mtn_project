// Fonction pour récupérer le jeton CSRF
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

// Attendre que le DOM soit chargé
document.addEventListener('DOMContentLoaded', function() {
    'use strict';
    
    // Global unload flag for this page
    let isPageUnloading = false;
    let activeTaskController = null;
    
    // Map pour stocker les modifications en attente (pré-enregistrement)
    const pendingChanges = new Map();

    window.addEventListener('beforeunload', () => {
        isPageUnloading = true;
        if (activeTaskController) {
            activeTaskController.abort();
        }
    });
    
    // Bouton pour télécharger/générer un document (Penalité, Évaluation, MSRN)
    const downloadDocumentBtn = document.getElementById('download-document');
    if (downloadDocumentBtn) {
        downloadDocumentBtn.addEventListener('click', async function() {
            const bonId = this.getAttribute('data-bon-id');
            // Utiliser la variable globale bonNumber définie dans le template, sinon l'attribut, sinon 'PO'
            const currentBonNumber = (typeof bonNumber !== 'undefined' && bonNumber) ? bonNumber : (this.getAttribute('data-bon-number') || 'PO');

            const retentionBtn = document.getElementById('set-retention-btn');
            const retentionRate = retentionBtn ? retentionBtn.getAttribute('data-retention-rate') || 0 : 0;
            const retentionCause = retentionBtn ? retentionBtn.getAttribute('data-retention-cause') || '' : '';

            const montantTotalRecuElement = document.querySelector('.montant-total-recue');
            const tauxAvancementElement = document.querySelector('.taux-avancement');
            const currentAmountDelivered = montantTotalRecuElement ? montantTotalRecuElement.textContent.trim() : amountDelivered;
            const currentDeliveryRate = tauxAvancementElement ? tauxAvancementElement.textContent.trim().replace('%', '') : deliveryRate;

            const { value: formValues, isConfirmed } = await Swal.fire({
                title: 'Quel document souhaitez-vous générer ?'
                , html: `
                    <div class="text-start">
                        <div class="form-check mb-3">
                            <input class="form-check-input" type="radio" name="document-type" id="doc-delay" value="delay">
                            <label class="form-check-label" for="doc-delay">
                                Évaluation des Délais de Livraison
                            </label>
                        </div>
                        <div class="form-check mb-2">
                            <input class="form-check-input" type="radio" name="document-type" id="doc-penalty" value="penalty" checked>
                            <label class="form-check-label" for="doc-penalty">
                                Fiche de Pénalité
                            </label>
                        </div>
                        <div class="form-check mb-3">
                            <input class="form-check-input" type="radio" name="document-type" id="doc-compensation-letter" value="compensation-letter">
                            <label class="form-check-label" for="doc-compensation-letter">
                                Lettre de Demande de Compensation
                            </label>
                        </div>
                        <div class="form-check mb-3">
                            <input class="form-check-input" type="radio" name="document-type" id="doc-penalty-amendment" value="penalty-amendment">
                            <label class="form-check-label" for="doc-penalty-amendment">
                                Fiche d'amendement de pénalité
                            </label>
                        </div>
                        <div class="form-check mb-3">
                            <input class="form-check-input" type="radio" name="document-type" id="doc-msrn" value="msrn">
                            <label class="form-check-label" for="doc-msrn">
                                Rapport MSRN
                            </label>
                        </div>
                    </div>
                `
                , showCancelButton: true
                , confirmButtonText: 'Télécharger'
                , cancelButtonText: 'Annuler'
                , focusConfirm: false
                , preConfirm: () => {
                    const selected = document.querySelector('input[name="document-type"]:checked');
                    if (!selected) {
                        Swal.showValidationMessage('Veuillez choisir un document.');
                        return false;
                    }
                    return {
                        type: selected.value
                    };
                }
            });

            if (!isConfirmed || !formValues) {
                return;
            }

            const showGeneratingPopup = () => {
                Swal.fire({
                    icon: 'info',
                    title: 'Traitement en cours',
                    text: 'Lancement de la génération...',
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: false,
                    timer: 3000
                });
            };

            const triggerDownload = async (url, filename, payload = {}, reportType = 'Document') => {
                try {
                    showGeneratingPopup();
                    
                    // Create controller for this request
                    activeTaskController = new AbortController();

                    const response = await fetch(url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken')
                        },
                        body: JSON.stringify(payload),
                        signal: activeTaskController.signal
                    });

                    if (!response.ok) {
                        throw new Error(`Erreur serveur (${response.status})`);
                    }

                    const contentType = response.headers.get("content-type");
                    if (contentType && contentType.indexOf("application/json") !== -1) {
                        const data = await response.json();
                        
                        if (data.async) {
                            // Mode Asynchrone : Fermer le popup bloquant et notifier
                            Swal.close();
                            
                            // Notification non bloquante (Toast)
                            Swal.fire({
                                icon: 'info',
                                title: 'Génération démarrée',
                                text: 'La génération du document se fait en arrière-plan. Vous serez notifié une fois terminé.',
                                toast: true,
                                position: 'top-end',
                                showConfirmButton: false,
                                timer: 5000
                            });

                            // ON NE FAIT PLUS DE POLLING ICI.
                            // Le système global (global_notifications.js) s'en chargera.
                            return; 
                        }
                    }

                    const blob = await response.blob();
                    const downloadUrl = window.URL.createObjectURL(blob);

                    Swal.fire({
                        icon: 'success',
                        title: reportType + ' généré',
                        html: `Le rapport <strong>${reportType}</strong> a été généré avec succès.<br>
                               Un email de notification a été envoyé aux destinataires et vous avez été mis en copie.<br><br>
                               <a href="${downloadUrl}" class="btn btn-outline-primary" download="${filename}">Télécharger le rapport</a>`,
                        didClose: () => {
                            window.URL.revokeObjectURL(downloadUrl);
                        }
                    });
                } catch (error) {
                    // Ignore errors if page is unloading or it's a network error
                    if (isPageUnloading || error.name === 'AbortError') return;
                    
                    const errorMsg = error.message || '';
                    if (errorMsg.includes('NetworkError') || 
                        errorMsg.includes('Failed to fetch') || 
                        errorMsg.includes('Network request failed')) {
                        console.warn('NetworkError during download trigger (likely due to navigation), ignoring.');
                        return;
                    }

                    console.error('Erreur lors du téléchargement :', error);
                    
                    // ULTIMATE PROTECTION: Never show NetworkError to user
                    // This handles the race condition where fetch fails before isPageUnloading is set
                    const finalErrorMsg = error.message || '';
                    if (finalErrorMsg.includes('NetworkError') || 
                        finalErrorMsg.includes('Failed to fetch') || 
                        finalErrorMsg.includes('Network request failed')) {
                        return;
                    }

                    Swal.fire({
                        icon: 'error',
                        title: 'Erreur',
                        text: finalErrorMsg || 'Impossible de générer le document.'
                    });
                }
            };

            if (formValues.type === 'penalty') {
                try {
                    await triggerDownload(
                        `/orders/api/generate-penalty/${bonId}/`,
                        `PenaltySheet-${bonNumber}.pdf`,
                        {},
                        'Fiche de Pénalité'
                    );
                } catch (error) {
                    // Gestion d'erreur déjà faite dans triggerDownload
                }
            } else if (formValues.type === 'delay') {
                try {
                    await triggerDownload(
                        `/orders/api/generate-delay-evaluation/${bonId}/`,
                        `DelayEvaluation-${bonNumber}.pdf`,
                        {},
                        'Évaluation des Délais de Livraison'
                    );
                } catch (error) {
                    // Gestion d'erreur déjà faite dans triggerDownload
                }
            } else if (formValues.type === 'penalty-amendment') {
                try {
                    // Fetch penalty amount with loading message
                    let defaultPenalty = '0';
                    try {
                        // Show loading message while calculating penalty
                        Swal.fire({
                            title: 'Veuillez Patienter',
                            text: 'Affichage du formulaire en cours...',
                            icon: 'info',
                            showConfirmButton: false,
                            allowOutsideClick: false
                        });
                        
                        const penaltyResponse = await fetch(`/orders/api/get-penalty-amount/${bonId}/`, {
                            method: 'GET',
                            headers: {
                                'X-CSRFToken': getCookie('csrftoken')
                            }
                        });
                        
                        if (penaltyResponse.ok) {
                            const penaltyData = await penaltyResponse.json();
                            if (penaltyData.success && penaltyData.penalty_due) {
                                defaultPenalty = penaltyData.penalty_due;
                            }
                        }
                        
                        Swal.close(); // Close loading message
                    } catch (error) {
                        console.warn('Could not fetch penalty amount:', error);
                        Swal.close(); // Close loading message even on error
                    }

                    const { value: amendmentValues, isConfirmed: amendmentConfirmed } = await Swal.fire({
                        title: 'Compléter la fiche',
                        html: `
                            <div class="text-start">
                                <div class="mb-3">
                                    <label for="amendment-supplier-plea" class="form-label fw-bold">Doléance du fournisseur</label>
                                    <textarea id="amendment-supplier-plea" class="form-control" rows="3" placeholder="Saisir la doléance..."></textarea>
                                </div>
                                <div class="mb-3">
                                    <label for="amendment-pm-proposal" class="form-label fw-bold">Proposition du PM</label>
                                    <textarea id="amendment-pm-proposal" class="form-control" rows="3" placeholder="Saisir la proposition..."></textarea>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label fw-bold">Statut de la pénalité</label>
                                    <div class="d-flex gap-3">
                                        <div class="form-check">
                                            <input class="form-check-input" type="radio" name="amendment-status" id="amendment-status-annulee" value="annulee">
                                            <label class="form-check-label" for="amendment-status-annulee">Annulée</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="radio" name="amendment-status" id="amendment-status-reduite" value="reduite">
                                            <label class="form-check-label" for="amendment-status-reduite">Réduite</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="radio" name="amendment-status" id="amendment-status-reconduite" value="reconduite" checked>
                                            <label class="form-check-label" for="amendment-status-reconduite">Reconduite</label>
                                        </div>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label for="amendment-new-penalty" class="form-label fw-bold">Nouvelle pénalité due</label>
                                    <input type="text" id="amendment-new-penalty" class="form-control" placeholder="Ex: 125000" value="${defaultPenalty}">
                                </div>
                            </div>
                        `,
                        showCancelButton: true,
                        confirmButtonText: 'Générer',
                        cancelButtonText: 'Annuler',
                        focusConfirm: false,
                        preConfirm: () => {
                            const supplierPlea = document.getElementById('amendment-supplier-plea').value.trim();
                            const pmProposal = document.getElementById('amendment-pm-proposal').value.trim();
                            const statusInput = document.querySelector('input[name="amendment-status"]:checked');
                            const newPenalty = document.getElementById('amendment-new-penalty').value.trim();

                            return {
                                supplierPlea,
                                pmProposal,
                                status: statusInput ? statusInput.value : '',
                                newPenalty,
                            };
                        },
                    });

                    if (!amendmentConfirmed || !amendmentValues) {
                        return;
                    }

                    await triggerDownload(
                        `/orders/api/generate-penalty-amendment/${bonId}/`,
                        `PenaltyAmendment-${bonNumber}.pdf`,
                        {
                            supplier_plea: amendmentValues.supplierPlea,
                            pm_proposal: amendmentValues.pmProposal,
                            penalty_status: amendmentValues.status,
                            new_penalty_due: amendmentValues.newPenalty,
                        },
                        'Fiche d\'Amendement de Pénalité'
                    );
                } catch (error) {
                    console.error('Erreur lors de la génération de la fiche amendement :', error);
                    Swal.fire({
                        icon: 'error',
                        title: 'Erreur',
                        text: error.message || 'Impossible de générer la fiche d\'amendement.'
                    });
                }
            } else if (formValues.type === 'msrn') {
                try {
                    Swal.fire({
                        title: 'Veuillez confirmer',
                        html: `
                            <div style="text-align: left; padding: 10px;">
                                <p style="margin-bottom: 15px;"><strong>Confirmer les informations MSRN :</strong></p>
                                <table style="width: 100%; border-collapse: collapse;">
                                    <tr style="border-bottom: 1px solid #ddd;">
                                        <td style="padding: 8px; font-weight: bold;">Purchase Order:</td>
                                        <td style="padding: 8px;">${bonNumber}</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #ddd;">
                                        <td style="padding: 8px; font-weight: bold;">Supplier:</td>
                                        <td style="padding: 8px;">${supplier}</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #ddd;">
                                        <td style="padding: 8px; font-weight: bold;">PO Amount:</td>
                                        <td style="padding: 8px;">${parseFloat(poAmount).toLocaleString()} ${currency}</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #ddd;">
                                        <td style="padding: 8px; font-weight: bold;">Amount Delivered:</td>
                                        <td style="padding: 8px;">${currentAmountDelivered} ${currency}</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #ddd;">
                                        <td style="padding: 8px; font-weight: bold;">Delivery Rate:</td>
                                        <td style="padding: 8px;"><strong style="color: #28a745;">${currentDeliveryRate}%</strong></td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #ddd;">
                                        <td style="padding: 8px; font-weight: bold;">Payment Retention Rate:</td>
                                        <td style="padding: 8px;"><strong style="color: ${parseFloat(retentionRate) > 0 ? '#dc3545' : '#6c757d'};">${retentionRate}%</strong></td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px; font-weight: bold;">Retention Cause:</td>
                                        <td style="padding: 8px; font-style: italic;">${retentionCause}</td>
                                    </tr>
                                </table>
                            </div>
                        `,
                        icon: 'question',
                        showCancelButton: true,
                        confirmButtonColor: '#28a745',
                        cancelButtonColor: '#6c757d',
                        confirmButtonText: 'OK, Générer MSRN',
                        cancelButtonText: 'Annuler',
                        width: '650px'
                    }).then(async (result) => {
                        if (!result.isConfirmed) {
                            return;
                        }

                        showGeneratingPopup();

                        try {
                            const response = await fetch(`/orders/api/generate-msrn/${bonId}/`, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': getCookie('csrftoken')
                                },
                                body: JSON.stringify({
                                    retention_rate: retentionRate,
                                    retention_cause: retentionCause
                                })
                            });

                            if (!response.ok) {
                                throw new Error(`Erreur serveur (${response.status})`);
                            }

                            const data = await response.json();

                            if (data.async) {
                                // Mode Asynchrone : Fermer le popup bloquant et notifier
                                Swal.close();
                                
                                // Notification non bloquante (Toast)
                                Swal.fire({
                                    icon: 'info',
                                    title: 'Génération démarrée',
                                    text: 'La génération du rapport se fait en arrière-plan. Vous serez notifié une fois terminé.',
                                    toast: true,
                                    position: 'top-end',
                                    showConfirmButton: false,
                                    timer: 5000
                                });

                                // ON NE FAIT PLUS DE POLLING ICI.
                                // Le système global s'en chargera.
                                return;
                            } else if (data.success) {
                                Swal.fire({
                                    icon: 'success',
                                    title: 'MSRN généré',
                                    html: `Le rapport MSRN <strong>MSRN-${data.report_number}</strong> a été généré.<br>
                                           Un email de notification a été envoyé aux destinataires et vous avez été mis en copie.<br><br>
                                           <a href="${data.download_url}" class="btn btn-outline-primary">Ouvrir le rapport</a>`,
                                });
                            } else {
                                throw new Error(data.error || 'Une erreur est survenue lors de la génération du rapport MSRN.');
                            }
                        } catch (error) {
                            // ULTIMATE PROTECTION for MSRN flow
                            const finalErrorMsg = error.message || '';
                            if (isPageUnloading || 
                                error.name === 'AbortError' || 
                                finalErrorMsg.includes('NetworkError') || 
                                finalErrorMsg.includes('Failed to fetch') || 
                                finalErrorMsg.includes('Network request failed')) {
                                return;
                            }

                            console.error('Erreur lors de la génération MSRN :', error);
                            Swal.fire({
                                icon: 'error',
                                title: 'Erreur',
                                text: finalErrorMsg || 'Impossible de générer le rapport MSRN.'
                            });
                        }
                    });
                } catch (error) {
                    // ULTIMATE PROTECTION for MSRN flow outer catch
                    const finalErrorMsg = error.message || '';
                    if (isPageUnloading || 
                        error.name === 'AbortError' || 
                        finalErrorMsg.includes('NetworkError') || 
                        finalErrorMsg.includes('Failed to fetch') || 
                        finalErrorMsg.includes('Network request failed')) {
                        return;
                    }

                    console.error('Erreur lors de la génération MSRN :', error);
                    Swal.fire({
                        icon: 'error',
                        title: 'Erreur',
                        text: finalErrorMsg || 'Impossible de générer le rapport MSRN.'
                    });
                }
            } else if (formValues.type === 'compensation-letter') {
                try {
                    await triggerDownload(
                        `/orders/api/generate-compensation-letter/${bonId}/`,
                        `Lettre_Compensation_${bonNumber}.pdf`,
                        {},
                        'Lettre de Demande de Compensation'
                    );
                } catch (error) {
                    // Gestion d'erreur déjà faite dans triggerDownload
                }
            }
        });
    }
    // Initialiser les tooltips Bootstrap si disponibles
    if (window.bootstrap && typeof bootstrap.Tooltip === 'function') {
        const tooltipTriggerList = Array.from(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.forEach(el => new bootstrap.Tooltip(el));
    }
    // Récupérer tous les champs de saisie de type Quantity Delivered
    const quantityDeliveredInputs = document.querySelectorAll('.quantity-delivered-input[data-row]'); // Mettre à jour le sélecteur pour les inputs recipe-input avec l'attribut data-row
    
    // Fonction pour appliquer la couleur à la cellule Quantity Not Delivered
    function applyQuantityNotDeliveredColor(element, quantityNotDelivered) {
        const parentCell = element.closest('td');
        if (!parentCell) return;
        
        if (quantityNotDelivered === 0) {
            // Vert si Quantity Not Delivered = 0 (Tout est livré)
            parentCell.style.setProperty('background-color', '#d4edda', 'important');
            parentCell.style.setProperty('color', '#155724', 'important');
            parentCell.style.setProperty('font-weight', 'bold', 'important');
        } else if (quantityNotDelivered > 0) {
            // Rouge s'il reste des quantités à livrer
            parentCell.style.setProperty('background-color', '#f8d7da', 'important');
            parentCell.style.setProperty('color', '#721c24', 'important');
            parentCell.style.setProperty('font-weight', 'bold', 'important');
        }
    }
    
    // Calculer automatiquement les quantités restantes au chargement de la page
    quantityDeliveredInputs.forEach(input => {
        const row = input.getAttribute('data-row');
        const orderedElement = document.querySelector(`.ordered-quantity[data-row="${row}"]`);
        const quantityNotDeliveredElement = document.querySelector(`.quantity-not-delivered[data-row="${row}"]`);
        
        if (orderedElement && quantityNotDeliveredElement) {
            const orderedQuantity = parseFloat(orderedElement.textContent) || 0;
            const quantityDelivered = parseFloat(input.value) || 0;
            const quantityNotDelivered = Math.max(0, orderedQuantity - quantityDelivered);
            
            // Mettre à jour la quantité restante
            quantityNotDeliveredElement.textContent = quantityNotDelivered;
            
            // Appliquer la couleur selon la valeur de Quantity Not Delivered
            applyQuantityNotDeliveredColor(quantityNotDeliveredElement, quantityNotDelivered);
        }
    });
    
    // ===== GESTION DE LA SÉLECTION MULTIPLE ET DU QUANTITY DELIVERED COLLECTIF =====
    const selectAllCheckbox = document.getElementById('select-all-rows');
    const rowCheckboxes = document.querySelectorAll('.row-checkbox');
    const collectiveQuantityDeliveredContainer = document.getElementById('collective-quantity-delivered-container');
    const applyCollectiveQuantityDeliveredButton = document.getElementById('apply-collective-quantity-delivered');
    
    // Variables pour gérer le mode de sélection
    let selectionMode = null; // 'reception' ou 'correction'
    let isSelectingForCorrection = false;
    
    // Fonction pour mettre à jour l'affichage du bouton Quantity Delivered collectif
    function updateCollectiveQuantityDeliveredButtonVisibility() {
        const selectedRows = document.querySelectorAll('.row-checkbox:checked');
        const selectedCountBadge = document.getElementById('selected-count-badge');
        
        // Mettre à jour le compteur
        if (selectedCountBadge) {
            selectedCountBadge.textContent = selectedRows.length;
        }
        
        // Afficher le bouton seulement si au moins 1 ligne est sélectionnée et en mode réception
        if (selectedRows.length >= 1 && selectionMode === 'reception') {
            collectiveQuantityDeliveredContainer.style.display = 'block';
            
            // Animation subtile pour attirer l'attention
            collectiveQuantityDeliveredContainer.classList.add('pulse-animation');
            setTimeout(() => {
                collectiveQuantityDeliveredContainer.classList.remove('pulse-animation');
            }, 500);
        } else {
            collectiveQuantityDeliveredContainer.style.display = 'none';
        }
    }
    
    // Fonction pour afficher l'alerte de choix du mode
    async function showModeSelectionAlert() {
        const result = await Swal.fire({
            title: 'Group action',
            text: 'What do you want to do with the selected lines?',
            icon: 'question',
            showCancelButton: true,
            showCloseButton: true,
            confirmButtonText: '<i class="fas fa-plus-circle me-2"></i>Group Delivery',
            cancelButtonText: '<i class="fas fa-edit me-2"></i>Group Correction',
            confirmButtonColor: '#28a745',
            cancelButtonColor: '#fd7e14',
            allowOutsideClick: true,
            allowEscapeKey: true,
            customClass: {
                confirmButton: 'btn-lg',
                cancelButton: 'btn-lg'
            }
        });
        
        if (result.isConfirmed) {
            // Mode réception groupée (existant)
            selectionMode = 'reception';
            updateCollectiveQuantityDeliveredButtonVisibility();
        } else if (result.dismiss === Swal.DismissReason.cancel) {
            // Mode correction groupée (nouveau)
            selectionMode = 'correction';
            isSelectingForCorrection = true;
            showCorrectionSelectionInterface();
        } else {
            // Annulation - décocher toutes les lignes
            resetSelection();
        }
    }
    
    // Fonction pour afficher l'interface de sélection pour correction
    function showCorrectionSelectionInterface() {
        // Créer et afficher le bouton de validation de sélection
        if (!document.getElementById('validate-correction-selection')) {
            const validationButton = document.createElement('div');
            validationButton.id = 'validate-correction-selection';
            validationButton.style.cssText = `
                position: fixed;
                bottom: 30px;
                right: 30px;
                z-index: 1000;
                display: block;
            `;
            validationButton.innerHTML = `
                <button class="btn btn-warning btn-lg shadow">
                    <i class="fas fa-check me-2"></i>Valider la sélection pour correction
                    <span class="badge bg-light text-dark ms-2" id="correction-count-badge">0</span>
                </button>
            `;
            document.body.appendChild(validationButton);
            
            // Ajouter l'événement click
            validationButton.querySelector('button').addEventListener('click', validateCorrectionSelection);
        }
        
        // Mettre à jour le compteur
        updateCorrectionSelectionCount();
        
        // Ajouter une classe CSS pour indiquer le mode correction
        document.body.classList.add('correction-selection-mode');
    }
    
    // Fonction pour mettre à jour le compteur de sélection pour correction
    function updateCorrectionSelectionCount() {
        const selectedRows = document.querySelectorAll('.row-checkbox:checked');
        const correctionCountBadge = document.getElementById('correction-count-badge');
        if (correctionCountBadge) {
            correctionCountBadge.textContent = selectedRows.length;
        }
    }
    
    // Fonction pour valider la sélection pour correction
    async function validateCorrectionSelection() {
        const selectedRows = Array.from(document.querySelectorAll('.row-checkbox:checked'));
        
        if (selectedRows.length === 0) {
            Swal.fire({
                icon: 'warning',
                title: 'No line selected',
                text: 'Please select at least one line to correct',
                confirmButtonColor: '#3085d6'
            });
            return;
        }
        
        // Récupérer les indices des lignes sélectionnées
        const rowIndices = selectedRows.map(checkbox => checkbox.getAttribute('data-row'));
        
        // Récupérer l'historique des réceptions pour ces lignes
        try {
            const response = await fetch(`/orders/api/reception-history/${bonId}/?bon_number=${encodeURIComponent(bonNumber)}&business_ids=${rowIndices.join(',')}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                }
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                // Ask user for correction mode
                const { value: correctionMode } = await Swal.fire({
                    title: 'Correction Mode',
                    text: 'How do you want to apply the correction?',
                    icon: 'question',
                    input: 'radio',
                    inputOptions: {
                        'manual': 'Manual / Individual Correction (View History)',
                        'specific': 'Apply Specific Correction to All Selected Lines'
                    },
                    inputValue: 'manual',
                    showCancelButton: true,
                    confirmButtonText: 'Next',
                    confirmButtonColor: '#28a745',
                    cancelButtonColor: '#6c757d',
                    inputValidator: (value) => {
                        if (!value) {
                            return 'You need to choose an option!'
                        }
                    }
                });

                if (!correctionMode) return;

                if (correctionMode === 'manual') {
                    // Show existing modal with history
                    showCorrectionModal(data.history, rowIndices);
                } else {
                    // Specific mode: ask for value
                    const { value: qty } = await Swal.fire({
                        title: 'Enter Correction Value',
                        html: `
                            <p>Enter the value to apply to <strong>ALL</strong> ${rowIndices.length} selected lines.</p>
                            <p class="text-danger"><small><i class="fas fa-info-circle"></i> Use a negative number (e.g. -3) to remove quantity.</small></p>
                        `,
                        input: 'text',
                        inputPlaceholder: 'Ex: -1.0',
                        showCancelButton: true,
                        confirmButtonText: 'Apply Correction',
                        confirmButtonColor: '#d33', // Red because it's usually destructive/correction
                        cancelButtonColor: '#6c757d',
                        inputValidator: (value) => {
                            if (!value || isNaN(parseFloat(value))) {
                                return 'Please enter a valid number';
                            }
                            if (parseFloat(value) === 0) {
                                return 'Correction value cannot be 0';
                            }
                        }
                    });

                    if (!qty) return;

                    const correctionValue = parseFloat(qty);
                    
                    // Prepare bulk correction data
                    const correctionsList = [];
                    rowIndices.forEach(businessId => {
                        const lineData = data.history[businessId];
                        if (lineData) {
                            correctionsList.push({
                                business_id: businessId,
                                correction_value: correctionValue,
                                original_quantity: lineData.ordered_quantity
                            });
                        }
                    });

                    // Call Bulk Correction API
                    // Re-use logic from setupCorrectionModalEventHandlers or call API directly
                    Swal.fire({
                        title: 'Applying corrections',
                        text: 'Please wait...',
                        allowOutsideClick: false,
                        didOpen: () => {
                            Swal.showLoading();
                        }
                    });
                    
                    try {
                        const response = await fetch(`/orders/api/bulk-correction/${bonId}/`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': getCookie('csrftoken')
                            },
                            body: JSON.stringify({
                                bon_number: bonNumber,
                                corrections: correctionsList
                            })
                        });
                        
                        const resultData = await response.json();
                        
                        if (resultData.status === 'success') {
                             // Mettre à jour l'interface avec les nouvelles valeurs
                             if (resultData.results) {
                                resultData.results.forEach(result => {
                                    const businessId = result.business_id;
                                    const quantityDeliveredInput = document.querySelector(`.quantity-delivered-input[data-row="${businessId}"]`);
                                    const quantityNotDeliveredElement = document.querySelector(`.quantity-not-delivered[data-row="${businessId}"]`);
                                    const amountDeliveredElement = document.querySelector(`.amount-delivered[data-row="${businessId}"]`);
                                    const amountNotDeliveredElement = document.querySelector(`.amount-not-delivered[data-row="${businessId}"]`);
                                    const quantityPayableElement = document.querySelector(`.quantity-payable[data-row="${businessId}"]`);
                                    const amountPayableElement = document.querySelector(`.amount-payable[data-row="${businessId}"]`);
                                    
                                    if (quantityDeliveredInput) {
                                        quantityDeliveredInput.value = result.quantity_delivered;
                                        quantityDeliveredInput.setAttribute('data-original-value', result.quantity_delivered);
                                    }
                                    if (quantityNotDeliveredElement) {
                                        quantityNotDeliveredElement.textContent = result.quantity_not_delivered;
                                    }
                                    if (amountDeliveredElement) {
                                        amountDeliveredElement.textContent = result.amount_delivered.toFixed(2);
                                    }
                                    if (amountNotDeliveredElement) {
                                        amountNotDeliveredElement.textContent = result.amount_not_delivered.toFixed(2);
                                    }
                                    if (quantityPayableElement) {
                                        quantityPayableElement.textContent = result.quantity_payable.toFixed(2);
                                    }
                                    if (amountPayableElement) {
                                        amountPayableElement.textContent = result.amount_payable.toFixed(2);
                                    }
                                });
                             }

                            // Update totals
                            if (resultData.taux_avancement !== undefined) {
                                const taux = document.querySelector('.taux-avancement');
                                if (taux) taux.textContent = resultData.taux_avancement.toFixed(2) + '%';
                            }
                            if (resultData.montant_total_recu !== undefined) {
                                const mtr = document.querySelector('.montant-total-recue');
                                if (mtr) mtr.textContent = resultData.montant_total_recu.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                            }

                            let msg = `${resultData.results.length} corrections applied successfully`;
                            if (resultData.errors && resultData.errors.length > 0) {
                                msg += `\n\nErrors:\n${resultData.errors.join('\n')}`;
                            }

                            Swal.fire({
                                icon: resultData.errors && resultData.errors.length > 0 ? 'warning' : 'success',
                                title: 'Corrections applied',
                                text: msg,
                                confirmButtonColor: '#28a745'
                            });
                            
                            resetSelection();
                        } else {
                            throw new Error(resultData.message || 'Error applying corrections');
                        }
                    } catch (error) {
                        console.error('Error:', error);
                        Swal.fire({
                            icon: 'error',
                            title: 'Error',
                            text: error.message || 'An error occurred',
                            confirmButtonColor: '#dc3545'
                        });
                    }
                }
            } else {
                throw new Error(data.message || 'Error retrieving history');
            }
            
        } catch (error) {
            console.error('Error retrieving history:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Error retrieving history',
                confirmButtonColor: '#dc3545'
            });
        }
    }
    
    // Fonction pour réinitialiser la sélection
    function resetSelection() {
        // Décocher toutes les lignes
        rowCheckboxes.forEach(checkbox => checkbox.checked = false);
        selectAllCheckbox.checked = false;
        
        // Réinitialiser le mode
        selectionMode = null;
        isSelectingForCorrection = false;
        
        // Supprimer l'interface de correction si elle existe
        const validationButton = document.getElementById('validate-correction-selection');
        if (validationButton) {
            validationButton.remove();
        }
        
        // Supprimer la classe CSS du mode correction
        document.body.classList.remove('correction-selection-mode');
        
        // Mettre à jour la visibilité
        updateCollectiveQuantityDeliveredButtonVisibility();
    }
    
    // Gestionnaire pour la case à cocher "Sélectionner tout"
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            rowCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
            
            // Si au moins 1 ligne est sélectionnée, demander le mode
            const selectedRows = document.querySelectorAll('.row-checkbox:checked');
            if (selectedRows.length >= 1 && selectionMode === null) {
                showModeSelectionAlert();
            } else if (selectionMode === 'reception') {
                updateCollectiveQuantityDeliveredButtonVisibility();
            } else if (selectionMode === 'correction') {
                updateCorrectionSelectionCount();
            }
        });
    }
    
    // Gestionnaire pour les cases à cocher individuelles
    rowCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            // Mettre à jour la case "Sélectionner tout" si nécessaire
            if (!this.checked) {
                selectAllCheckbox.checked = false;
            } else {
                // Vérifier si toutes les cases sont cochées
                const allChecked = Array.from(rowCheckboxes).every(cb => cb.checked);
                selectAllCheckbox.checked = allChecked;
            }
            
            // Vérifier le nombre de lignes sélectionnées
            const selectedRows = document.querySelectorAll('.row-checkbox:checked');
            
            // Si au moins 1 ligne est sélectionnée et aucun mode n'est défini, demander le mode
            if (selectedRows.length >= 1 && selectionMode === null) {
                showModeSelectionAlert();
            } else if (selectionMode === 'reception') {
                updateCollectiveQuantityDeliveredButtonVisibility();
            } else if (selectionMode === 'correction') {
                updateCorrectionSelectionCount();
            }
        });
    });
    
    // Fonction pour sauvegarder les modifications de quantités reçues
    // options.suppressRetentionPrompt (bool) permet de désactiver l'alerte de rétention (utilisé pour la réception collective)
    function saveQuantityDeliveredChanges(row, ordered_quantity, quantity_delivered, options = {}) {
        const quantityDeliveredInput = document.querySelector(`.quantity-delivered-input[data-row="${row}"]`);
        const quantityNotDeliveredElement = document.querySelector(`.quantity-not-delivered[data-row="${row}"]`);
        const amountDeliveredElement = document.querySelector(`.amount-delivered[data-row="${row}"]`);
        const amountNotDeliveredElement = document.querySelector(`.amount-not-delivered[data-row="${row}"]`);
        const quantityPayableElement = document.querySelector(`.quantity-payable[data-row="${row}"]`);
        const amountPayableElement = document.querySelector(`.amount-payable[data-row="${row}"]`);
        
        // Récupérer l'ancienne valeur avant modification et s'assurer que c'est un nombre
        const oldValue = parseFloat(quantityDeliveredInput?.getAttribute('data-original-value') || '0');
        
        // S'assurer que les quantités sont des nombres
        ordered_quantity = parseFloat(ordered_quantity) || 0;
        quantity_delivered = parseFloat(quantity_delivered) || 0;
        
        return new Promise((resolve, reject) => {
            fetch(`/orders/api/update-quantity-delivered/${bonId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({
                    business_id: row,
                    original_quantity: parseFloat(ordered_quantity).toFixed(2),
                    quantity_delivered: parseFloat(quantity_delivered).toFixed(2),
                    bon_number: bonNumber,
                    timestamp: new Date().toISOString()
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'error') {
                    // Restaurer l'ancienne valeur en cas d'erreur
                    if (quantityDeliveredInput) quantityDeliveredInput.value = oldValue;
                    throw new Error(data.message);
                }
                
                // Mettre à jour l'interface avec les valeurs du serveur
                if (quantityDeliveredInput && quantityNotDeliveredElement && amountDeliveredElement && quantityPayableElement && amountPayableElement) {
                    // Convertir les valeurs en nombres pour éviter les problèmes de formatage
                    const quantityDeliveredQty = parseFloat(data.quantity_delivered) || 0;
                    const quantityNotDeliveredQty = parseFloat(data.quantity_not_delivered) || 0;
                    const orderedQty = parseFloat(data.ordered_quantity) || 0;
                    
                    // Mettre à jour la valeur affichée avec le formatage approprié
                    quantityDeliveredInput.value = quantityDeliveredQty.toString();
                    quantityNotDeliveredElement.textContent = quantityNotDeliveredQty.toString();
                    
                    // Appliquer la couleur à Quantity Not Delivered
                    applyQuantityNotDeliveredColor(quantityNotDeliveredElement, quantityNotDeliveredQty);
                    
                    // Mettre à jour les attributs data avec les valeurs numériques
                    quantityDeliveredInput.setAttribute('data-original', orderedQty.toString());
                    quantityDeliveredInput.setAttribute('data-ordered', orderedQty.toString());
                    quantityDeliveredInput.setAttribute('data-original-value', quantityDeliveredQty.toString());
                    
                    // Mettre à jour la valeur précédente pour la prochaine modification
                    quantityDeliveredInput.setAttribute('data-previous-value', '0');
                    
                    // Mettre à jour le taux d'avancement si disponible
                    if (data.taux_avancement !== undefined) {
                        const tauxAvancementElement = document.querySelector('.taux-avancement');
                        if (tauxAvancementElement) {
                            tauxAvancementElement.textContent = data.taux_avancement.toFixed(2) + '%';
                        }
                    }
                    
                    // Mettre à jour le montant total reçu si disponible
                    if (data.montant_total_recu !== undefined) {
                        const montantTotalRecuElement = document.querySelector('.montant-total-recue');
                        if (montantTotalRecuElement) {
                            // Formater le nombre avec des séparateurs de milliers
                            montantTotalRecuElement.textContent = data.montant_total_recu.toLocaleString('fr-FR', {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2
                            });
                        }
                    }
                    
                    // Mettre à jour Amount Delivered, Amount Not Delivered et Quantity Payable
                    amountDeliveredElement.textContent = data.amount_delivered.toFixed(2);
                    if (amountNotDeliveredElement) {
                        amountNotDeliveredElement.textContent = data.amount_not_delivered.toFixed(2);
                    }
                    quantityPayableElement.textContent = data.quantity_payable.toFixed(2);
                    amountPayableElement.textContent = data.amount_payable.toFixed(2);
                    
                    // Forcer le recalcul du style si nécessaire
                    quantityDeliveredInput.style.removeProperty('border-color');
                    
                    // Afficher une notification de succès
                    Swal.fire({
                        icon: 'success',
                        title: 'Success',
                        text: 'The delivery has been registered successfully',
                        toast: true,
                        position: 'top-end',
                        showConfirmButton: false,
                        timer: 3000
                    });

                    // Le code d'affichage automatique du bouton de téléchargement MSRN a été supprimé
                    // Les rapports MSRN sont maintenant générés manuellement via un bouton dédié
                }
                
                resolve(data);
            })
            .catch(error => {
                console.error('Error saving:', error);
                
                // Restaurer la valeur précédente en cas d'erreur
                if (quantityDeliveredInput) quantityDeliveredInput.value = oldValue;
                
                // Afficher l'erreur
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: error.message || 'An error occurred while saving',
                    confirmButtonColor: '#3085d6',
                });
                
                reject(error);
            });
        });
    }
    

    // Fonction pour mettre à jour les valeurs de quantity payable
    function updateQuantityPayableValues(retentionRate) {
        const retentionFactor = 1 - (retentionRate / 100);
        
        // Mettre à jour toutes les lignes
        document.querySelectorAll('.quantity-delivered-input').forEach(input => {
            const row = input.getAttribute('data-row');
            const quantityDelivered = parseFloat(input.value) || 0;
            const quantityPayableElement = document.querySelector(`.quantity-payable[data-row="${row}"]`);
            const amountPayableElement = document.querySelector(`.amount-payable[data-row="${row}"]`);
            const unitPriceElement = document.querySelector(`.unit-price[data-row="${row}"]`);
            
            // Calculer la nouvelle quantité payable
            const newQuantityPayable = quantityDelivered * retentionFactor;
            
            // Mettre à jour quantity_payable
            if (quantityPayableElement) {
                quantityPayableElement.textContent = newQuantityPayable.toFixed(2);
            }
            
            // Mettre à jour amount_payable
            if (amountPayableElement && unitPriceElement) {
                const unitPrice = parseFloat(unitPriceElement.textContent) || 0;
                const newAmountPayable = newQuantityPayable * unitPrice;
                amountPayableElement.textContent = newAmountPayable.toFixed(2);
            }
        });
    }
    
    // Fonction pour récupérer les valeurs mises à jour depuis le serveur
    function refreshPayableValues(bonCommandeId) {
        fetch(`/orders/api/bons/${bonCommandeId}/receptions/`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.receptions) {
                // Mettre à jour les valeurs dans l'interface
                data.receptions.forEach(reception => {
                    const row = reception.business_id;
                    const quantityPayableElement = document.querySelector(`.quantity-payable[data-row="${row}"]`);
                    const amountPayableElement = document.querySelector(`.amount-payable[data-row="${row}"]`);
                    
                    if (quantityPayableElement) {
                        quantityPayableElement.textContent = parseFloat(reception.quantity_payable).toFixed(2);
                    }
                    
                    if (amountPayableElement) {
                        amountPayableElement.textContent = parseFloat(reception.amount_payable).toFixed(2);
                    }
                });
            }
        })
        .catch(error => {
            console.error('Error retrieving values:', error);
        });
    }

    // SUPPRIMÉ: fonction handleMsrnDownload qui causait des problèmes avec les anciens rapports
    // Les téléchargements MSRN se font maintenant uniquement via l'historique MSRN

    // Fonction pour appliquer le Quantity Delivered collectif
    async function applyCollectiveQuantityDelivered() {
        const selectedRows = Array.from(document.querySelectorAll('.row-checkbox:checked'));
        
        if (selectedRows.length === 0) return;

        // Étape 1 : Choisir le mode de réception
        const { value: receptionMode } = await Swal.fire({
            title: 'Collective Reception Mode',
            text: 'How do you want to apply the reception?',
            icon: 'question',
            input: 'radio',
            inputOptions: {
                'full': 'Receive All Remaining (Complete Lines)',
                'partial': 'Receive Specific Quantity per Line',
                'target_rate': 'Reach Target Progress Rate'
            },
            inputValue: 'full',
            showCancelButton: true,
            confirmButtonText: 'Next',
            confirmButtonColor: '#28a745',
            cancelButtonColor: '#6c757d',
            inputValidator: (value) => {
                if (!value) {
                    return 'You need to choose an option!'
                }
            }
        });

        if (!receptionMode) return;

        // --- MODE CIBLE (TARGET RATE) ---
        if (receptionMode === 'target_rate') {
            // VERIFICATION PERMISSION CÔTÉ CLIENT
            if (typeof isSuperUser !== 'undefined' && !isSuperUser) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Accès Refusé',
                    text: 'Cette fonctionnalité "Target Rate" est strictement réservée aux administrateurs.',
                    confirmButtonColor: '#d33'
                });
                return;
            }

            // Récupérer le taux actuel
            const currentRateEl = document.querySelector('.taux-avancement');
            // Gérer le format '71,50%' ou '71.50%'
            let currentRateText = currentRateEl ? currentRateEl.textContent.replace('%', '').trim() : '0';
            currentRateText = currentRateText.replace(',', '.');
            const currentRate = parseFloat(currentRateText) || 0;

            const { value: targetRateVal, isDismissed } = await Swal.fire({
                title: 'Apply Percentage to Remaining Quantity',
                html: `
                    <div class="text-start">
                        <p>Current Progress Rate: <strong>${currentRate.toFixed(2)}%</strong></p>
                        <p>Enter the percentage to apply to the <strong>Quantity Not Delivered</strong>.</p>
                        <div class="alert alert-info">
                            <small><i class="fas fa-info-circle"></i> Example: Entering <strong>99</strong> means receiving 99% of the remaining quantity for each selected line.</small>
                        </div>
                    </div>
                `,
                input: 'text',
                inputPlaceholder: 'Ex: 99',
                showCancelButton: true,
                confirmButtonText: 'Apply',
                confirmButtonColor: '#28a745',
                cancelButtonColor: '#6c757d',
                inputValidator: (value) => {
                    if (!value) return 'Please enter a percentage';
                    // Remplacer virgule par point pour le parsing
                    const val = parseFloat(value.replace(',', '.'));
                    if (isNaN(val)) return 'Please enter a valid number';
                    if (val <= 0) return 'Percentage must be greater than 0';
                    if (val > 100) return 'Percentage cannot exceed 100%';
                }
            });

            if (isDismissed || !targetRateVal) return;

            const targetRate = parseFloat(targetRateVal.replace(',', '.'));
            
            // Préparer les données pour l'API
            const linesInfo = [];
            selectedRows.forEach(checkbox => {
                const businessId = checkbox.getAttribute('data-row');
                const orderedElement = document.querySelector(`.ordered-quantity[data-row="${businessId}"]`);
                if (orderedElement) {
                    const orderedQty = parseFloat(orderedElement.textContent) || 0;
                    linesInfo.push({
                        business_id: businessId,
                        ordered_quantity: orderedQty
                    });
                }
            });

            if (linesInfo.length === 0) {
                 Swal.fire('Error', 'No valid lines selected', 'error');
                 return;
            }

            // Appel API spécifique pour le taux cible
            applyCollectiveQuantityDeliveredButton.disabled = true;
            applyCollectiveQuantityDeliveredButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Calculating...';

            try {
                const response = await fetch(`/orders/api/apply-target-rate/${bonId}/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({
                        bon_number: bonNumber,
                        target_rate: targetRate,
                        lines_info: linesInfo
                    })
                });

                const data = await response.json();

                if (data.status === 'success') {
                    // Recharger les données pour mettre à jour l'interface
                    fetchQuantityDeliveredData();
                    
                    // Mettre à jour les totaux globaux si renvoyés
                    if (data.taux_avancement !== undefined) {
                        const taux = document.querySelector('.taux-avancement');
                        if (taux) taux.textContent = data.taux_avancement.toFixed(2) + '%';
                    }
                     if (data.montant_total_recu !== undefined) {
                        const mtr = document.querySelector('.montant-total-recue');
                        if (mtr) mtr.textContent = data.montant_total_recu.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    }

                    Swal.fire({
                        icon: 'success',
                        title: 'Target Rate Applied',
                        text: `Successfully applied target rate of ${targetRate}%.`,
                        timer: 2000,
                        showConfirmButton: false
                    });
                    
                    resetSelection();
                } else {
                    throw new Error(data.message || 'Error applying target rate');
                }

            } catch (error) {
                console.error('Error:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: error.message || 'An error occurred',
                    confirmButtonColor: '#dc3545'
                });
            } finally {
                applyCollectiveQuantityDeliveredButton.disabled = false;
                applyCollectiveQuantityDeliveredButton.innerHTML = '<i class="fas fa-check-circle me-2"></i> Apply collective Quantity Delivered';
            }

            return; // Fin du traitement pour target_rate
        }

        let specificQuantity = 0;
        
        // Étape 2 : Si partiel, demander la quantité
        if (receptionMode === 'partial') {
            const { value: qty, isDismissed } = await Swal.fire({
                title: 'Enter Quantity',
                text: 'Please enter the quantity to receive for EACH selected line:',
                input: 'text', // Utiliser text pour mieux gérer les formats
                inputPlaceholder: 'Ex: 1.0',
                showCancelButton: true,
                confirmButtonText: 'Validate',
                confirmButtonColor: '#28a745',
                cancelButtonColor: '#6c757d',
                inputValidator: (value) => {
                    if (!value || isNaN(parseFloat(value)) || parseFloat(value) <= 0) {
                        return 'Please enter a valid positive number';
                    }
                }
            });

            if (isDismissed || !qty) return;
            specificQuantity = parseFloat(qty);
        }

        // Filtrer les lignes et préparer les mises à jour
        const eligibleRows = [];
        const updates = [];
        let skippedCount = 0;
        
        for (const checkbox of selectedRows) {
            const businessId = checkbox.getAttribute('data-row');
            const quantityDeliveredInput = document.querySelector(`.quantity-delivered-input[data-row="${businessId}"]`);
            const orderedElement = document.querySelector(`.ordered-quantity[data-row="${businessId}"]`);
            
            if (quantityDeliveredInput && orderedElement) {
                const currentQuantityDelivered = parseFloat(quantityDeliveredInput.value) || 0;
                const orderedQuantity = parseFloat(orderedElement.textContent) || 0;
                const quantityNotDelivered = Math.max(0, orderedQuantity - currentQuantityDelivered);
                
                // Calculer la quantité à ajouter selon le mode
                let quantityToAdd = 0;
                
                if (receptionMode === 'full') {
                    quantityToAdd = quantityNotDelivered;
                } else {
                    // Mode partiel : on prend le min entre la quantité demandée et le reste à livrer
                    // Pour éviter de dépasser la commande
                    quantityToAdd = Math.min(specificQuantity, quantityNotDelivered);
                }

                // Si quantityToAdd > 0, on traite la ligne
                if (quantityToAdd > 0) {
                    eligibleRows.push({
                        checkbox,
                        businessId,
                        quantityToAdd
                    });
                    
                    // Préparer les données pour l'API en lot
                    // Note: L'API attend 'quantity_delivered' qui est la quantité à AJOUTER (incrémentale)
                    // ou la nouvelle quantité totale ? Vérifions saveQuantityDeliveredChanges.
                    // saveQuantityDeliveredChanges envoie "quantity_delivered" qui semble être la NOUVELLE quantité TOTALE (valeur de l'input).
                    // Mais bulk_update (backend) ?
                    // Regardons detail_bon.js saveQuantityDeliveredChanges:
                    // body: JSON.stringify({ ... quantity_delivered: parseFloat(quantity_delivered).toFixed(2) ... })
                    // Donc c'est la quantité TOTALE.
                    // Cependant, le code précédent de applyCollectiveQuantityDelivered faisait:
                    // quantity_delivered: quantityNotDelivered
                    // Ce qui semblait être un bug ou une confusion si l'API attend le total.
                    // ATTENTION: Le backend reception_api.bulk_update_receptions attend probablement un DELTA ou un TOTAL ?
                    // Le code JS précédent faisait: quantity_delivered: quantityNotDelivered.
                    // Si quantityNotDelivered = 10 et current = 0, on envoie 10. (Total = 10). Correct.
                    // Si quantityNotDelivered = 5 et current = 5 (total ordered 10), on envoie 5.
                    // -> Si l'API attend le TOTAL, on devrait envoyer (current + quantityNotDelivered) = 10.
                    // -> Si l'API attend le DELTA, on envoie 5.
                    
                    // Vérifions le code JS précédent :
                    // const quantityNotDelivered = Math.max(0, orderedQuantity - currentQuantityDelivered);
                    // updates.push({ ..., quantity_delivered: quantityNotDelivered, ... });
                    
                    // Si l'API attend le TOTAL, le code précédent était FAUX pour les lignes partiellement livrées.
                    // EX: Ordered 10, Current 2. Remaining 8.
                    // Code précédent envoyait 8.
                    // Si c'est TOTAL, la nouvelle valeur devient 8 (au lieu de 10).
                    // Si c'est DELTA, ça ajoute 8 -> 10.
                    
                    // HYPOTHÈSE LA PLUS SÛRE : L'API bulk_update fonctionne probablement comme update_quantity_delivered
                    // qui prend la valeur absolue (Total).
                    // Dans ce cas, le code précédent avait un bug pour les livraisons partielles existantes.
                    // MAIS, je vais assumer que je dois envoyer la quantité à AJOUTER (Delta) SI l'endpoint est spécifique bulk_update.
                    // Ou alors je calcule le nouveau total.
                    
                    // Regardons le code précédent à nouveau.
                    // updates.push({ quantity_delivered: quantityNotDelivered })
                    // Si c'était "Receive All Remaining", le but est d'arriver à Ordered Quantity.
                    // Si j'envoie "Remaining", et que l'API écrase la valeur, alors Total = Remaining.
                    // C'est faux si Current > 0.
                    // Exemple: Ordered 10, Current 2. Remaining 8.
                    // Si j'envoie 8, et que l'API met à jour à 8, alors on a perdu les 2 précédents ? Non, on a reculé.
                    // OU ALORS, "Receive All Remaining" signifie "Set Quantity Delivered = Ordered Quantity".
                    // Ordered = 10.
                    // Code précédent envoyait: 8.
                    // Ça ne colle pas si l'API attend le Total.
                    
                    // Je vais vérifier reception_api.py si possible, mais je ne peux pas lire le backend maintenant facilement sans perdre le focus.
                    // Je vais parier sur le fait que je dois envoyer la quantité à AJOUTER (Delta).
                    // Car le backend reception_api.bulk_update_receptions fait: total = existing + new.
                    
                    // Donc:
                    updates.push({
                        business_id: businessId,
                        quantity_delivered: quantityToAdd, // On envoie le DELTA (quantité à ajouter)
                        ordered_quantity: orderedQuantity
                    });
                } else {
                    skippedCount++;
                }
            }
        }
        
        const eligibleCount = eligibleRows.length;
        const totalSelected = selectedRows.length;
        
        if (eligibleCount === 0) {
            Swal.fire({
                icon: 'info',
                title: 'No eligible line',
                text: 'All selected lines are already fully received or the requested quantity is 0.'
            });
            return;
        }
        
        // Confirmation finale
        const { isConfirmed } = await Swal.fire({
            title: 'Confirm collective delivery',
            html: `
                <div style="text-align: left;">
                    <p><strong>Mode:</strong> ${receptionMode === 'full' ? 'Full Reception' : 'Partial Reception (' + specificQuantity + '/line)'}</p>
                    <p>Selected lines: <strong>${totalSelected}</strong></p>
                    <p>Eligible lines: <strong>${eligibleCount}</strong></p>
                    <p>Skipped lines: <strong>${skippedCount}</strong></p>
                    <hr>
                    <p>This will update the delivered quantities for these lines.</p>
                </div>
            `,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Yes, apply',
            cancelButtonText: 'Cancel',
            confirmButtonColor: '#28a745',
            cancelButtonColor: '#d33'
        });
        
        if (isConfirmed) {
            applyCollectiveQuantityDeliveredButton.disabled = true;
            applyCollectiveQuantityDeliveredButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Processing...';
            
            try {
                // Appel API en lot
                const response = await fetch(`/orders/api/receptions/${bonId}/bulk_update/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({
                        bon_number: bonNumber,
                        updates: updates
                    })
                });
                
                const data = await response.json();
                
                if (data.status !== 'success') {
                    throw new Error(data.message || 'Error processing bulk update');
                }
                
                // Mettre à jour l'interface avec les données retournées
                if (data.updated_receptions) {
                    data.updated_receptions.forEach(reception => {
                        const businessId = reception.business_id;
                        const quantityDeliveredInput = document.querySelector(`.quantity-delivered-input[data-row="${businessId}"]`);
                        const quantityNotDeliveredElement = document.querySelector(`.quantity-not-delivered[data-row="${businessId}"]`);
                        const amountDeliveredElement = document.querySelector(`.amount-delivered[data-row="${businessId}"]`);
                        const amountNotDeliveredElement = document.querySelector(`.amount-not-delivered[data-row="${businessId}"]`);
                        const quantityPayableElement = document.querySelector(`.quantity-payable[data-row="${businessId}"]`);
                        const amountPayableElement = document.querySelector(`.amount-payable[data-row="${businessId}"]`);
                        
                        if (quantityDeliveredInput) {
                            quantityDeliveredInput.value = reception.quantity_delivered.toString();
                            quantityDeliveredInput.setAttribute('data-original-value', reception.quantity_delivered.toString());
                        }
                        if (quantityNotDeliveredElement) {
                            quantityNotDeliveredElement.textContent = reception.quantity_not_delivered.toString();
                            // Mettre à jour la couleur
                            applyQuantityNotDeliveredColor(quantityNotDeliveredElement, reception.quantity_not_delivered);
                        }
                        if (amountDeliveredElement) {
                            amountDeliveredElement.textContent = reception.amount_delivered.toFixed(2);
                        }
                        if (amountNotDeliveredElement) {
                            amountNotDeliveredElement.textContent = reception.amount_not_delivered.toFixed(2);
                        }
                        if (quantityPayableElement) {
                            quantityPayableElement.textContent = reception.quantity_payable.toFixed(2);
                        }
                        if (amountPayableElement) {
                            amountPayableElement.textContent = reception.amount_payable.toFixed(2);
                        }
                    });
                }
                
                // Mettre à jour les métriques globales
                if (data.taux_avancement !== undefined) {
                    const tauxAvancementElement = document.querySelector('.taux-avancement');
                    if (tauxAvancementElement) {
                        tauxAvancementElement.textContent = data.taux_avancement.toFixed(2) + '%';
                    }
                }
                
                if (data.montant_total_recu !== undefined) {
                    const montantTotalRecuElement = document.querySelector('.montant-total-recue');
                    if (montantTotalRecuElement) {
                        montantTotalRecuElement.textContent = data.montant_total_recu.toLocaleString('fr-FR', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2
                        });
                    }
                }
                
                Swal.fire({
                    icon: 'success',
                    title: 'Collective delivery applied',
                    html: `Operation successful for <strong>${eligibleCount}</strong> lines`,
                    confirmButtonColor: '#28a745'
                });
                
            } catch (error) {
                console.error('Error applying collective delivery:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'An error occurred while applying collective delivery. Please try again.',
                    confirmButtonColor: '#dc3545'
                });
            } finally {
                // Réactiver le bouton
                applyCollectiveQuantityDeliveredButton.disabled = false;
                applyCollectiveQuantityDeliveredButton.innerHTML = '<i class="fas fa-check-circle me-2"></i> Apply collective Quantity Delivered';
                
                // Réinitialiser complètement l'état après réception groupée
                resetSelection();
            }
        }
    }

    // Assigner la fonction au bouton Quantity Delivered collectif
    if (applyCollectiveQuantityDeliveredButton) {
        applyCollectiveQuantityDeliveredButton.addEventListener('click', applyCollectiveQuantityDelivered);
    }

    // Gestion du modal de rétention (custom modal)
    (function initRetentionCustomModal() {
        const modal = document.getElementById('retentionModalCustom');
        const overlay = document.getElementById('retentionModalOverlay');
        const btnOpen = document.getElementById('set-retention-btn');
        const btnClose = document.getElementById('retentionModalClose');
        const btnCancel = document.getElementById('retentionModalCancel');
        const btnSave = document.getElementById('saveRetentionBtn');
        const inputRate = document.getElementById('retentionRate');
        const inputCause = document.getElementById('retentionCause');
        
        if (!btnOpen || !modal || !overlay || !btnSave || !inputRate || !inputCause) return;

        function openModal() {
            // Pré-remplissage
            const currentRate = parseFloat(btnOpen.getAttribute('data-retention-rate') || '0') || 0;
            const currentCause = btnOpen.getAttribute('data-retention-cause') || '';
            inputRate.value = currentRate;
            inputCause.value = currentCause;

            modal.classList.remove('hidden');
            modal.setAttribute('aria-hidden', 'false');
            // Focus premier champ
            setTimeout(() => inputRate.focus(), 0);
        }

        function closeModal() {
            modal.classList.add('hidden');
            modal.setAttribute('aria-hidden', 'true');
        }

        // Ouverture
        btnOpen.addEventListener('click', openModal);

        // Fermetures
        overlay.addEventListener('click', closeModal);
        if (btnClose) btnClose.addEventListener('click', closeModal);
        if (btnCancel) btnCancel.addEventListener('click', closeModal);
        document.addEventListener('keydown', (e) => {
            if (!modal.classList.contains('hidden') && e.key === 'Escape') closeModal();
        });

        // Sauvegarde
        btnSave.addEventListener('click', function() {
            const rate = parseFloat(inputRate.value);
            const cause = (inputCause.value || '').trim();

            // Validation stricte
            if (isNaN(rate) || rate < 0 || rate > 100) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Validation',
                    text: 'The Payment Retention rate must be between 0 and 100%'
                });
                inputRate.focus();
                return;
            }
            if (rate > 0 && !cause) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Validation',
                    text: 'The cause of the retention is required for a rate > 0%'
                });
                inputCause.focus();
                return;
            }

            // API call
            fetch(`/orders/api/bons/${bonCommandeId}/update-retention/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({
                    retention_rate: rate,
                    retention_cause: cause
                })
            })
            .then(r => {
                // DEBUG: Voir la réponse brute
                return r.text().then(text => {
                    console.log('Réponse brute du serveur:', text);
                    try {
                        return JSON.parse(text);
                    } catch (e) {
                        console.error('Erreur JSON.parse:', e);
                        throw new Error(`Réserve invalide: ${text.substring(0, 200)}`);
                    }
                });
            })
            .then(data => {
                if (data.status !== 'success') throw new Error(data.message || 'Erreur API');

                // Mise à jour UI temporaire
                updateQuantityPayableValues(rate);
                btnOpen.setAttribute('data-retention-rate', rate.toString());
                btnOpen.setAttribute('data-retention-cause', cause);
                
                // Récupérer les valeurs réelles depuis le serveur
                refreshPayableValues(bonCommandeId);

                closeModal();

                Swal.fire({
                    icon: 'success',
                    title: 'Success',
                    text: 'The retention has been applied successfully',
                    timer: 2500,
                    showConfirmButton: false
                });
            })
            .catch(err => {
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: err.message || 'An error occurred'
                });
            });
        });
    })();
    
    // Gestionnaire d'événements pour les champs Quantity Delivered
    quantityDeliveredInputs.forEach(input => {
        
        // Fonction utilitaire pour obtenir la valeur originale de manière robuste
        function getOriginalValue(inputElement) {
            // Priorité: data-original-value > data-current-total > 0
            let val = inputElement.getAttribute('data-original-value');
            if (val !== null && val !== '' && !isNaN(parseFloat(val))) {
                return parseFloat(val);
            }
            val = inputElement.getAttribute('data-current-total');
            if (val !== null && val !== '' && !isNaN(parseFloat(val))) {
                return parseFloat(val);
            }
            return 0;
        }
        
        // Fonction pour mettre à jour visuellement Quantity Not Delivered
        function updateQuantityNotDeliveredDisplay(row, orderedQuantity, currentTotal, increment) {
            const quantityNotDeliveredElement = document.querySelector(`.quantity-not-delivered[data-row="${row}"]`);
            if (quantityNotDeliveredElement) {
                const newTotal = currentTotal + increment;
                const notDelivered = Math.max(0, orderedQuantity - newTotal);
                quantityNotDeliveredElement.textContent = notDelivered.toString();
                applyQuantityNotDeliveredColor(quantityNotDeliveredElement, notDelivered);
            }
        }
        
        // Fonction pour restaurer Quantity Not Delivered à sa valeur originale
        function restoreQuantityNotDeliveredDisplay(row, orderedQuantity, currentTotal) {
            const quantityNotDeliveredElement = document.querySelector(`.quantity-not-delivered[data-row="${row}"]`);
            if (quantityNotDeliveredElement) {
                const notDelivered = Math.max(0, orderedQuantity - currentTotal);
                quantityNotDeliveredElement.textContent = notDelivered.toString();
                applyQuantityNotDeliveredColor(quantityNotDeliveredElement, notDelivered);
            }
        }
        
        // Stocker la valeur originale au focus
        input.addEventListener('focus', function() {
            const currentValue = this.value.trim();
            // Stocker le total actuel livré (avant modification)
            if (currentValue !== '' && !isNaN(parseFloat(currentValue))) {
                this.setAttribute('data-original-value', currentValue);
                this.setAttribute('data-current-total', currentValue);
            } else {
                // Si vide, utiliser data-current-total existant ou 0
                const existingTotal = this.getAttribute('data-current-total') || '0';
                this.setAttribute('data-original-value', existingTotal);
            }
            // Stocker la valeur de l'input avant modification pour restauration
            this.setAttribute('data-input-before-edit', currentValue);
        });
        
        // Validation pendant la saisie
        input.addEventListener('input', function() {
            let value = this.value;
            
            // Permettre le signe moins seulement au début
            const hasMinusAtStart = value.startsWith('-');
            
            // Supprimer tous les caractères non numériques sauf le point et le minus
            value = value.replace(/[^0-9.-]/g, '');
            
            // S'assurer que le minus n'apparaît qu'au début
            if (hasMinusAtStart) {
                value = '-' + value.replace(/-/g, '');
            } else {
                value = value.replace(/-/g, '');
            }
            
            // S'assurer qu'il n'y a qu'un seul point décimal
            const parts = value.split('.');
            if (parts.length > 2) {
                value = parts[0] + '.' + parts.slice(1).join('');
            }
            
            this.value = value;
            
            // Mise à jour visuelle en temps réel de Quantity Not Delivered
            const row = this.getAttribute('data-row');
            const orderedQuantityElement = document.querySelector(`.ordered-quantity[data-row="${row}"]`);
            const orderedQuantity = parseFloat(orderedQuantityElement?.textContent || this.getAttribute('data-ordered') || '0');
            const currentTotal = getOriginalValue(this);
            const increment = value === '' || isNaN(parseFloat(value)) ? 0 : parseFloat(value);
            
            updateQuantityNotDeliveredDisplay(row, orderedQuantity, currentTotal, increment);
        });
        
        // Gestion de la perte de focus - stocke en mémoire (pré-enregistrement)
        input.addEventListener('blur', function() {
            const row = this.getAttribute('data-row');
            const orderedQuantityElement = document.querySelector(`.ordered-quantity[data-row="${row}"]`);
            const orderedQuantity = parseFloat(orderedQuantityElement?.textContent || this.getAttribute('data-ordered') || '0');
            const currentTotal = getOriginalValue(this);
            const inputBeforeEdit = this.getAttribute('data-input-before-edit') || currentTotal.toString();
            
            let increment = this.value.trim() === '' ? 0 : parseFloat(this.value);
            if (isNaN(increment)) {
                increment = 0;
            }
            
            // Si pas d'incrément, restaurer et nettoyer
            if (increment === 0) {
                this.value = inputBeforeEdit;
                pendingChanges.delete(row);
                this.classList.remove('pending-change');
                restoreQuantityNotDeliveredDisplay(row, orderedQuantity, currentTotal);
                return;
            }
            
            // Validation pour les valeurs négatives (correction)
            if (increment < 0) {
                const newTotal = currentTotal + increment;
                if (newTotal < 0) {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Correction impossible',
                        html: `La correction de <strong>${increment}</strong> rendrait le total négatif.<br>
                               <strong>Total actuel:</strong> ${currentTotal}<br>
                               <strong>Total après correction:</strong> ${newTotal}`,
                        confirmButtonColor: '#3085d6',
                    });
                    // Restaurer la valeur de l'input et l'affichage
                    this.value = inputBeforeEdit;
                    pendingChanges.delete(row);
                    this.classList.remove('pending-change');
                    restoreQuantityNotDeliveredDisplay(row, orderedQuantity, currentTotal);
                    return;
                }
            }
            
            // Validation pour les valeurs positives
            if (increment > 0) {
                const newTotal = currentTotal + increment;
                if (newTotal > orderedQuantity) {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Quantité invalide',
                        html: `Le total (<strong>${newTotal}</strong>) dépasserait la quantité commandée (<strong>${orderedQuantity}</strong>).<br>
                               <strong>Total actuel:</strong> ${currentTotal}<br>
                               <strong>Ajout demandé:</strong> ${increment}<br>
                               <strong>Maximum possible:</strong> ${Math.max(0, orderedQuantity - currentTotal)}`,
                        confirmButtonColor: '#3085d6',
                    });
                    // Restaurer la valeur de l'input et l'affichage
                    this.value = inputBeforeEdit;
                    pendingChanges.delete(row);
                    this.classList.remove('pending-change');
                    restoreQuantityNotDeliveredDisplay(row, orderedQuantity, currentTotal);
                    return;
                }
            }
            
            // Stocker la modification en attente (pré-enregistrement)
            pendingChanges.set(row, {
                row: row,
                orderedQuantity: orderedQuantity,
                quantityDelivered: increment,
                originalValue: currentTotal,
                inputBeforeEdit: inputBeforeEdit,
                input: this
            });
            this.classList.add('pending-change');
        });
        
        // Gestion des touches clavier (navigation + confirmation)
        input.addEventListener('keydown', async function(e) {
            const allInputs = Array.from(document.querySelectorAll('.quantity-delivered-input'));
            const currentIndex = allInputs.indexOf(this);
            
            // Navigation avec flèches haut/bas
            if (e.key === 'ArrowDown' || (e.key === 'Tab' && !e.shiftKey)) {
                e.preventDefault();
                const nextIndex = currentIndex + 1;
                if (nextIndex < allInputs.length) {
                    this.blur();
                    allInputs[nextIndex].focus();
                    allInputs[nextIndex].select();
                }
                return;
            }
            
            if (e.key === 'ArrowUp' || (e.key === 'Tab' && e.shiftKey)) {
                e.preventDefault();
                const prevIndex = currentIndex - 1;
                if (prevIndex >= 0) {
                    this.blur();
                    allInputs[prevIndex].focus();
                    allInputs[prevIndex].select();
                }
                return;
            }
            
            // Touche Escape pour annuler la modification en cours
            if (e.key === 'Escape') {
                e.preventDefault();
                const row = this.getAttribute('data-row');
                const inputBeforeEdit = this.getAttribute('data-input-before-edit') || '0';
                this.value = inputBeforeEdit;
                pendingChanges.delete(row);
                this.classList.remove('pending-change');
                
                // Restaurer Quantity Not Delivered
                const orderedQuantityElement = document.querySelector(`.ordered-quantity[data-row="${row}"]`);
                const orderedQuantity = parseFloat(orderedQuantityElement?.textContent || '0');
                const currentTotal = getOriginalValue(this);
                restoreQuantityNotDeliveredDisplay(row, orderedQuantity, currentTotal);
                
                this.blur();
                return;
            }
            
            // Touche Entrée - affiche l'alerte de confirmation
            if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation();
                
                // D'abord, déclencher le blur pour capturer la valeur actuelle
                this.blur();
                
                // Attendre un court instant pour que le blur soit traité
                await new Promise(resolve => setTimeout(resolve, 50));
                
                // Si aucune modification en attente, ne rien faire
                if (pendingChanges.size === 0) {
                    return;
                }
                
                // Construire le résumé des modifications
                let summaryHtml = '<div style="text-align: left; max-height: 300px; overflow-y: auto;">';
                summaryHtml += `<p><strong>${pendingChanges.size} modification(s) en attente :</strong></p>`;
                summaryHtml += '<table style="width: 100%; border-collapse: collapse;">';
                summaryHtml += '<tr style="background: #f5f5f5;"><th style="padding: 5px; border: 1px solid #ddd;">Ligne</th><th style="padding: 5px; border: 1px solid #ddd;">Incrément</th><th style="padding: 5px; border: 1px solid #ddd;">Nouveau Total</th></tr>';
                
                pendingChanges.forEach((change, row) => {
                    const newTotal = change.originalValue + change.quantityDelivered;
                    const color = change.quantityDelivered < 0 ? '#dc3545' : '#28a745';
                    summaryHtml += `<tr>
                        <td style="padding: 5px; border: 1px solid #ddd;">${row}</td>
                        <td style="padding: 5px; border: 1px solid #ddd; color: ${color}; font-weight: bold;">${change.quantityDelivered > 0 ? '+' : ''}${change.quantityDelivered}</td>
                        <td style="padding: 5px; border: 1px solid #ddd;">${newTotal}</td>
                    </tr>`;
                });
                summaryHtml += '</table></div>';
                
                // Afficher l'alerte de confirmation
                const result = await Swal.fire({
                    title: 'Confirmer les réceptions',
                    html: summaryHtml,
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonColor: '#28a745',
                    cancelButtonColor: '#dc3545',
                    confirmButtonText: 'Valider',
                    cancelButtonText: 'Annuler',
                    allowOutsideClick: false,
                    allowEscapeKey: false
                });
                
                if (result.isConfirmed) {
                    // Sauvegarder toutes les modifications
                    const savePromises = [];
                    pendingChanges.forEach((change) => {
                        savePromises.push(
                            saveQuantityDeliveredChanges(change.row, change.orderedQuantity, change.quantityDelivered)
                                .then(() => {
                                    change.input.classList.remove('pending-change');
                                })
                                .catch(error => {
                                    console.error(`Erreur sauvegarde ligne ${change.row}:`, error);
                                    // En cas d'erreur, restaurer cette ligne
                                    change.input.value = change.inputBeforeEdit;
                                    change.input.classList.remove('pending-change');
                                    restoreQuantityNotDeliveredDisplay(
                                        change.row, 
                                        change.orderedQuantity, 
                                        change.originalValue
                                    );
                                })
                        );
                    });
                    
                    await Promise.all(savePromises);
                    pendingChanges.clear();
                    
                    Swal.fire({
                        position: 'top-end',
                        icon: 'success',
                        title: 'Réceptions enregistrées',
                        showConfirmButton: false,
                        timer: 1500,
                        toast: true
                    });
                } else {
                    // Annuler - restaurer les valeurs originales
                    pendingChanges.forEach((change) => {
                        change.input.value = change.inputBeforeEdit;
                        change.input.classList.remove('pending-change');
                        // Restaurer aussi Quantity Not Delivered
                        restoreQuantityNotDeliveredDisplay(
                            change.row, 
                            change.orderedQuantity, 
                            change.originalValue
                        );
                    });
                    pendingChanges.clear();
                    
                    Swal.fire({
                        position: 'top-end',
                        icon: 'info',
                        title: 'Modifications annulées',
                        showConfirmButton: false,
                        timer: 1500,
                        toast: true
                    });
                }
                
                return false;
            }
        });
    });
    
    // Les gestionnaires d'événements du modal ont été supprimés car nous utilisons maintenant confirm()
    
    // Fonction pour récupérer les données de réception depuis l'API
    function fetchQuantityDeliveredData() {
        // Envoyer à l'API en utilisant les variables définies dans le template
        fetch(`/orders/api/update-quantity-delivered/${bonId}/?bon_number=${encodeURIComponent(bonNumber)}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.receptions) {
                // Mettre à jour l'interface avec les données reçues
                for (const businessId in data.receptions) {
                    const quantityDeliveredInput = document.querySelector(`.quantity-delivered-input[data-row="${businessId}"]`);
                    const orderedElement = document.querySelector(`.ordered-quantity[data-row="${businessId}"]`);
                    const quantityNotDeliveredElement = document.querySelector(`.quantity-not-delivered[data-row="${businessId}"]`);
                    const amountDeliveredElement = document.querySelector(`.amount-delivered[data-row="${businessId}"]`);
                    const amountNotDeliveredElement = document.querySelector(`.amount-not-delivered[data-row="${businessId}"]`);
                    const quantityPayableElement = document.querySelector(`.quantity-payable[data-row="${businessId}"]`);
                    const amountPayableElement = document.querySelector(`.amount-payable[data-row="${businessId}"]`);
                    
                    if (quantityDeliveredInput && orderedElement && quantityNotDeliveredElement && amountDeliveredElement && quantityPayableElement && amountPayableElement) {
                        // Mettre à jour la quantité commandée originale dans Ordered Quantity
                        orderedElement.textContent = data.receptions[businessId].ordered_quantity;
                        
                        // Mettre à jour la valeur de Quantity Delivered avec la valeur cumulée
                        quantityDeliveredInput.value = data.receptions[businessId].quantity_delivered;
                        
                        // Mettre à jour la quantité restante dans la colonne Quantity Not Delivered
                        quantityNotDeliveredElement.textContent = data.receptions[businessId].quantity_not_delivered;
                        
                        // Mettre à jour les attributs data pour conserver la cohérence
                        quantityDeliveredInput.setAttribute('data-original', data.receptions[businessId].ordered_quantity);
                        quantityDeliveredInput.setAttribute('data-ordered', data.receptions[businessId].ordered_quantity);
                        
                        // Mettre à jour Amount Delivered, Amount Not Delivered et Quantity Payable
                        amountDeliveredElement.textContent = data.receptions[businessId].amount_delivered.toFixed(2);
                        if (amountNotDeliveredElement) {
                            amountNotDeliveredElement.textContent = data.receptions[businessId].amount_not_delivered.toFixed(2);
                        }
                        quantityPayableElement.textContent = data.receptions[businessId].quantity_payable.toFixed(2);
                        amountPayableElement.textContent = data.receptions[businessId].amount_payable.toFixed(2);
                    }
                }
                console.log('Data loaded successfully');
            }
        })
        .catch(error => {
            console.error('Error loading delivery data:', error);
        });
    }
    
    // Récupérer les données de réception depuis le serveur au chargement
    fetchQuantityDeliveredData();
    
    // Fonction pour afficher le modal de correction avec l'historique
    function showCorrectionModal(historyData, rowIndices) {
        // Créer le contenu HTML du modal
        let modalContent = `
            <div class="correction-modal-content">
                <h6 class="mb-3"><i class="fas fa-history me-2"></i>History of deliveries</h6>
        `;
        
        // Pour chaque ligne sélectionnée
        rowIndices.forEach(businessId => {
            const lineData = historyData[businessId];
            if (!lineData) return;
            
            modalContent += `
                <div class="line-correction-section mb-4">
                    <h6 class="line-title">
                        <i class="fas fa-list-ol me-2"></i>Business ID ${businessId}
                        <span class="badge bg-info ms-2">quantity_delivered: ${lineData.current_total}</span>
                        <span class="badge bg-secondary ms-1">ordered_quantity: ${lineData.ordered_quantity}</span>
                    </h6>
                    
                    <div class="history-entries mb-3">
            `;
            
            if (lineData.history.length === 0) {
                modalContent += `<p class="text-muted"><i class="fas fa-info-circle me-1"></i>No deliveries registered</p>`;
            } else {
                modalContent += `<div class="table-responsive">
                    <table class="table table-sm table-striped">
                        <thead>
                            <tr>
                                <th>Reception</th>
                                <th>action_date</th>
                                <th>user</th>
                                <th>quantity_delivered</th>
                                <th>cumulative_recipe</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                lineData.history.forEach((entry, index) => {
                    const isNegative = entry.quantity_delivered < 0;
                    const quantityClass = isNegative ? 'text-danger' : 'text-success';
                    const quantityIcon = isNegative ? 'fas fa-minus-circle' : 'fas fa-plus-circle';
                    const receptionNumber = `R${index + 1}`;
                    
                    modalContent += `
                        <tr>
                            <td><span class="badge bg-primary">${receptionNumber}</span></td>
                            <td><small>${entry.date}</small></td>
                            <td><small>${entry.user}</small></td>
                            <td class="${quantityClass}">
                                <i class="${quantityIcon} me-1"></i>${entry.quantity_delivered}
                            </td>
                            <td><strong>${entry.cumulative_total}</strong></td>
                            <td>
                                <button class="btn btn-sm btn-outline-danger cancel-reception-btn" 
                                        data-row="${businessId}" 
                                        data-correction="${-entry.quantity_delivered}"
                                        data-original="${lineData.ordered_quantity}">
                                    <i class="fas fa-undo me-1"></i>Annuler
                                </button>
                            </td>
                        </tr>
                    `;
                });
                
                modalContent += `</tbody></table></div>`;
            }
            
            modalContent += `
                    </div>
                    
                    <div class="custom-correction-section">
                        <label class="form-label"><i class="fas fa-edit me-1"></i>Correction personnalisée:</label>
                        <div class="input-group">
                            <input type="number" class="form-control custom-correction-input" 
                                   data-row="${businessId}" 
                                   data-original="${lineData.ordered_quantity}"
                                   placeholder="Entrer valeur de correction (ex: -3 pour annuler 3)">
                            <button class="btn btn-outline-primary apply-custom-correction-btn" 
                                    data-row="${businessId}">
                                <i class="fas fa-check me-1"></i>Appliquer
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });
        
        modalContent += `
                <div class="modal-actions mt-4">
                    <button class="btn btn-success me-2" id="apply-all-corrections">
                        <i class="fas fa-check-circle me-2"></i>Appliquer toutes les corrections
                    </button>
                    <button class="btn btn-secondary" id="cancel-corrections">
                        <i class="fas fa-times me-2"></i>Annuler
                    </button>
                </div>
            </div>
        `;
        
        // Afficher le modal avec SweetAlert2
        Swal.fire({
            title: 'Group correction of deliveries',
            html: modalContent,
            width: '80%',
            showConfirmButton: false,
            showCancelButton: false,
            allowOutsideClick: false,
            customClass: {
                container: 'correction-modal-container'
            },
            didOpen: () => {
                // Ajouter les gestionnaires d'événements pour les boutons du modal
                setupCorrectionModalEventHandlers(historyData, rowIndices);
            }
        });
    }
    
    // Fonction pour configurer les gestionnaires d'événements du modal de correction
    function setupCorrectionModalEventHandlers(historyData, rowIndices) {
        const corrections = {}; // Stockage des corrections à appliquer
        
        // Gestionnaire pour les boutons d'annulation de réception spécifique
        document.querySelectorAll('.cancel-reception-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const businessId = this.getAttribute('data-row');
                const correctionValue = parseFloat(this.getAttribute('data-correction'));
                const originalQuantity = parseFloat(this.getAttribute('data-original'));
                
                // Ajouter cette correction à la liste
                if (!corrections[businessId]) {
                    corrections[businessId] = [];
                }
                corrections[businessId].push({
                    correction_value: correctionValue,
                    original_quantity: originalQuantity
                });
                
                // Désactiver le bouton pour éviter les doublons
                this.disabled = true;
                this.innerHTML = '<i class="fas fa-check me-1"></i>Ajouté';
                this.classList.remove('btn-outline-danger');
                this.classList.add('btn-success');
            });
        });
        
        // Gestionnaire pour les boutons de correction personnalisée
        document.querySelectorAll('.apply-custom-correction-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const businessId = this.getAttribute('data-row');
                const input = document.querySelector(`.custom-correction-input[data-row="${businessId}"]`);
                const correctionValue = parseFloat(input.value);
                const originalQuantity = parseFloat(input.getAttribute('data-original'));
                
                if (isNaN(correctionValue) || correctionValue === 0) {
                    alert('Please enter a valid correction value (different from 0)');
                    return;
                }
                
                // Ajouter cette correction à la liste
                if (!corrections[businessId]) {
                    corrections[businessId] = [];
                }
                corrections[businessId].push({
                    correction_value: correctionValue,
                    original_quantity: originalQuantity
                });
                
                // Désactiver le champ et le bouton
                input.disabled = true;
                this.disabled = true;
                this.innerHTML = '<i class="fas fa-check me-1"></i>Added';
                this.classList.remove('btn-outline-primary');
                this.classList.add('btn-success');
            });
        });
        
        // Gestionnaire pour appliquer toutes les corrections
        document.getElementById('apply-all-corrections').addEventListener('click', async function() {
            // Vérifier qu'il y a des corrections à appliquer
            const correctionsList = [];
            for (const businessId in corrections) {
                corrections[businessId].forEach(correction => {
                    correctionsList.push({
                        business_id: businessId,
                        correction_value: correction.correction_value,
                        original_quantity: correction.original_quantity
                    });
                });
            }
            
            if (correctionsList.length === 0) {
                Swal.fire({
                    icon: 'warning',
                    title: 'No correction',
                    text: 'Please select at least one correction to apply'
                });
                return;
            }
            
            // Confirmer l'application des corrections
            const confirmResult = await Swal.fire({
                title: 'Confirm corrections',
                html: `
                    <div style="text-align: left;">
                        <p>You are about to apply <strong>${correctionsList.length}</strong> corrections.</p>
                        <p>This action is irreversible.</p>
                        <p>Do you want to continue?</p>
                    </div>
                `,
                icon: 'question',
                showCancelButton: true,
                confirmButtonText: 'Yes, apply',
                cancelButtonText: 'Close',
                confirmButtonColor: '#28a745',
                cancelButtonColor: '#dc3545'
            });
            
            if (!confirmResult.isConfirmed) return;
            
            // Afficher un indicateur de chargement
            Swal.fire({
                title: 'Applying corrections',
                text: 'Please wait...',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });
            
            try {
                // Appeler l'API de correction groupée
                const response = await fetch(`/orders/api/bulk-correction/${bonId}/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({
                        bon_number: bonNumber,
                        corrections: correctionsList
                    })
                });
                
                const data = await response.json();
                
                if (data.status === 'success') {
                    // Mettre à jour l'interface avec les nouvelles valeurs
                    data.results.forEach(result => {
                        const businessId = result.business_id;
                        const quantityDeliveredInput = document.querySelector(`.quantity-delivered-input[data-row="${businessId}"]`);
                        const quantityNotDeliveredElement = document.querySelector(`.quantity-not-delivered[data-row="${businessId}"]`);
                        const amountDeliveredElement = document.querySelector(`.amount-delivered[data-row="${businessId}"]`);
                        const amountNotDeliveredElement = document.querySelector(`.amount-not-delivered[data-row="${businessId}"]`);
                        const quantityPayableElement = document.querySelector(`.quantity-payable[data-row="${businessId}"]`);
                        const amountPayableElement = document.querySelector(`.amount-payable[data-row="${businessId}"]`);
                        
                        if (quantityDeliveredInput) {
                            quantityDeliveredInput.value = result.quantity_delivered;
                            quantityDeliveredInput.setAttribute('data-original-value', result.quantity_delivered);
                        }
                        if (quantityNotDeliveredElement) {
                            quantityNotDeliveredElement.textContent = result.quantity_not_delivered;
                        }
                        if (amountDeliveredElement) {
                            amountDeliveredElement.textContent = result.amount_delivered.toFixed(2);
                        }
                        if (amountNotDeliveredElement) {
                            amountNotDeliveredElement.textContent = result.amount_not_delivered.toFixed(2);
                        }
                        if (quantityPayableElement) {
                            quantityPayableElement.textContent = result.quantity_payable.toFixed(2);
                        }
                        if (amountPayableElement) {
                            amountPayableElement.textContent = result.amount_payable.toFixed(2);
                        }
                    });
                    
                    // Mettre à jour les totaux globaux
                    if (data.taux_avancement !== undefined) {
                        const tauxAvancementElement = document.querySelector('.taux-avancement');
                        if (tauxAvancementElement) {
                            tauxAvancementElement.textContent = data.taux_avancement.toFixed(2) + '%';
                        }
                    }
                    
                    if (data.montant_total_recu !== undefined) {
                        const montantTotalRecuElement = document.querySelector('.montant-total-recue');
                        if (montantTotalRecuElement) {
                            montantTotalRecuElement.textContent = data.montant_total_recu.toLocaleString('fr-FR', {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2
                            });
                        }
                    }
                    
                    // Afficher le résultat
                    let resultMessage = `${data.results.length} corrections applied successfully`;
                    if (data.errors.length > 0) {
                        resultMessage += `\n\nErrors:\n${data.errors.join('\n')}`;
                    }
                    
                    Swal.fire({
                        icon: data.errors.length > 0 ? 'warning' : 'success',
                        title: 'Corrections applied',
                        text: resultMessage,
                        confirmButtonColor: '#28a745'
                    });
                    
                    // Reset selection
                    resetSelection();
                    
                } else {
                    throw new Error(data.message || 'Error applying corrections');
                }
                
            } catch (error) {
                console.error('Error applying corrections:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: error.message || 'An error occurred while applying corrections',
                    confirmButtonColor: '#dc3545'
                });
            }
        });
        
        // Gestionnaire pour annuler
        document.getElementById('cancel-corrections').addEventListener('click', function() {
            Swal.close();
            resetSelection();
        });
    }
    
    // Initialiser l'affichage du bouton Quantity Delivered collectif
    updateCollectiveQuantityDeliveredButtonVisibility();
    
    // Initialiser les tooltips Bootstrap pour l'aide contextuelle
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // ===== GESTION DU PANNEAU DE SÉLECTION DES COLONNES =====
    // Références aux éléments du DOM
    const sidebar = document.getElementById('columnSelectorSidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggleButton = document.getElementById('toggleColumnSelector');
    const closeButton = document.getElementById('closeColumnSelector');
    const applyButton = document.getElementById('applyColumnSelection');
    const selectAllButton = document.getElementById('selectAllColumns');
    const deselectAllButton = document.getElementById('deselectAllColumns');
    const resetButton = document.getElementById('resetColumnSelection');
    
    // Clé de stockage pour les préférences de colonnes
    const storageKey = 'columnPreferences_' + bonNumber;
    let selectedColumns = [];
    
    // Fonction pour ouvrir le panneau latéral
    function openSidebar() {
        sidebar.style.transform = 'translateX(0)';
        overlay.style.display = 'block';
        document.body.style.overflow = 'hidden'; // Empêcher le défilement du corps
    }
    
    // Fonction pour fermer le panneau latéral
    function closeSidebar() {
        sidebar.style.transform = 'translateX(100%)';
        overlay.style.display = 'none';
        document.body.style.overflow = ''; // Rétablir le défilement du corps
    }
    
    // Fonction pour appliquer la visibilité des colonnes
    function applyColumnVisibility(columns) {
        const table = document.querySelector('.data-table');
        if (!table) return;
        
        const headers = table.querySelectorAll('thead th');
        const rows = table.querySelectorAll('tbody tr');
        
        // Ignorer la première colonne (numéro de ligne)
        for (let i = 1; i < headers.length; i++) {
            const headerText = headers[i].textContent.trim();
            
            // Vérifier si la colonne doit être visible
            // Traiter Receipt et Quantity Delivered comme équivalents
            let isVisible = columns.includes(headerText);
            
            // Si l'en-tête est Recipe et que Quantity Delivered est sélectionné, ou vice versa
            if ((headerText === 'Quantity Delivered' && columns.includes('Quantity Delivered')) || 
                (headerText === 'Quantity Delivered' && columns.includes('Quantity Delivered'))) {
                isVisible = true;
            }
            
            // Définir la visibilité de l'en-tête
            headers[i].style.display = isVisible ? '' : 'none';
            
            // Remplacer "Quantity Delivered" par "Quantity Delivered" dans l'affichage
            if (headerText === 'Quantity Delivered' && isVisible) {
                headers[i].textContent = 'Quantity Delivered';
            }
            
            // Définir la visibilité des cellules correspondantes dans chaque ligne
            rows.forEach(row => {
                const cells = row.querySelectorAll('td');
                if (cells.length > i) {
                    cells[i].style.display = isVisible ? '' : 'none';
                }
            });
        }
    }
    
    // Fonction pour mettre à jour les cases à cocher en fonction des colonnes sélectionnées
    function updateCheckboxes(columns) {
        document.querySelectorAll('.column-checkbox').forEach(checkbox => {
            // Si la valeur est "Recipe", vérifier si "Receipt" est dans les colonnes sélectionnées
            if (checkbox.value === 'Quantity Delivered') {
                checkbox.checked = columns.includes('Quantity Delivered');
                // Mettre à jour le libellé pour afficher "Receipt" au lieu de "Recipe"
                const label = checkbox.nextElementSibling;
                if (label && label.tagName === 'LABEL') {
                    label.textContent = 'Quantity Delivered';
                }
            } else {
                checkbox.checked = columns.includes(checkbox.value);
            }
        });
    }
    
    // Fonction pour sélectionner toutes les colonnes
    function selectAllColumns() {
        const allColumns = [];
        document.querySelectorAll('.column-checkbox').forEach(checkbox => {
            checkbox.checked = true;
            allColumns.push(checkbox.value);
        });
        return allColumns;
    }
    
    // Fonction pour désélectionner toutes les colonnes
    function deselectAllColumns() {
        document.querySelectorAll('.column-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });
        return [];
    }
    
    // Fonction pour sauvegarder les préférences de colonnes
    function savePreferences() {
        // Cette fonction est conservée pour compatibilité mais n'utilise plus localStorage
        // Elle pourrait être modifiée pour utiliser une API serveur si nécessaire
    }
    
    // Fonction pour appliquer les changements
    function applyChanges() {
        selectedColumns = [];
        document.querySelectorAll('.column-checkbox:checked').forEach(checkbox => {
            selectedColumns.push(checkbox.value);
        });
        
        applyColumnVisibility(selectedColumns);
        savePreferences();
        closeSidebar();
    }
    
    // Initialiser les préférences de colonnes
    // Par défaut, seules certaines colonnes spécifiques sont sélectionnées
    const defaultColumns = ['Line Description', 'Ordered','Price', 'Ordered Quantity','Quantity Delivered', 'Quantity Not Delivered','Amount Delivered','Amount Not Delivered','Quantity Payable','Amount Payable'];
    selectedColumns = defaultColumns;
    updateCheckboxes(selectedColumns);
    applyColumnVisibility(selectedColumns);
    
    // Événements
    if (toggleButton) {
        toggleButton.addEventListener('click', openSidebar);
    }
    
    if (closeButton) {
        closeButton.addEventListener('click', closeSidebar);
    }
    
    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
    }
    
    if (applyButton) {
        applyButton.addEventListener('click', applyChanges);
    }
    
    if (selectAllButton) {
        selectAllButton.addEventListener('click', () => {
            selectedColumns = selectAllColumns();
        });
    }
    
    if (deselectAllButton) {
        deselectAllButton.addEventListener('click', () => {
            selectedColumns = deselectAllColumns();
        });
    }
    
    if (resetButton) {
        resetButton.addEventListener('click', () => {
            localStorage.removeItem(storageKey);
            selectedColumns = Array.from(document.querySelectorAll('.column-checkbox')).map(cb => cb.value);
            updateCheckboxes(selectedColumns);
            applyColumnVisibility(selectedColumns);
            closeSidebar();
        });
    }

    // ========================================
    // GESTION DES FILTRES DE LIVRAISON
    // ========================================
    
    function updateDeliveryCounts() {
        const allRows = document.querySelectorAll('.data-row');
        let partialCount = 0;
        let fullCount = 0;
        
        allRows.forEach(row => {
            const qtyDelivered = parseFloat(row.dataset.quantityDelivered || 0);
            const qtyOrdered = parseFloat(row.dataset.orderedQuantity || 0);
            
            if (qtyDelivered > 0 && qtyDelivered < qtyOrdered) {
                partialCount++;
            } else if (qtyDelivered > 0 && qtyDelivered >= qtyOrdered) {
                fullCount++;
            }
        });
        
        // Mettre à jour les badges de comptage
        document.getElementById('count-all').textContent = allRows.length;
        document.getElementById('count-partial').textContent = partialCount;
        document.getElementById('count-full').textContent = fullCount;
    }
    
    function applyDeliveryFilter(filterType) {
        const allRows = document.querySelectorAll('.data-row');
        let visibleCount = 0;
        
        allRows.forEach(row => {
            const qtyDelivered = parseFloat(row.dataset.quantityDelivered || 0);
            const qtyOrdered = parseFloat(row.dataset.orderedQuantity || 0);
            let shouldShow = false;
            
            switch(filterType) {
                case 'all':
                    shouldShow = true;
                    break;
                case 'partially-delivered':
                    // Quantity Delivered > 0 ET < Ordered Quantity
                    shouldShow = qtyDelivered > 0 && qtyDelivered < qtyOrdered;
                    break;
                case 'fully-delivered':
                    // Quantity Delivered >= Ordered Quantity (et > 0)
                    shouldShow = qtyDelivered > 0 && qtyDelivered >= qtyOrdered;
                    break;
            }
            
            if (shouldShow) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });
        
        // Mettre à jour le badge du tableau
        const tableBadge = document.querySelector('.card-header .badge');
        if (tableBadge) {
            tableBadge.textContent = `${visibleCount} items`;
        }
    }
    
    // Initialiser les compteurs au chargement
    updateDeliveryCounts();
    
    // Gérer les clics sur les boutons de filtre
    const filterButtons = document.querySelectorAll('.spectrum-filter-btn');
    filterButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            // Retirer la classe active de tous les boutons
            filterButtons.forEach(b => b.classList.remove('active'));
            // Ajouter la classe active au bouton cliqué
            this.classList.add('active');
            
            // Appliquer le filtre
            const filterType = this.dataset.filter;
            applyDeliveryFilter(filterType);
        });
    });
    
    // Mettre à jour les compteurs quand Quantity Delivered change
    const quantityInputs = document.querySelectorAll('.quantity-delivered-input');
    quantityInputs.forEach(input => {
        input.addEventListener('change', function() {
            // Mettre à jour l'attribut data de la ligne parente
            const row = this.closest('.data-row');
            if (row) {
                row.dataset.quantityDelivered = this.value;
                updateDeliveryCounts();
                
                // Réappliquer le filtre actif
                const activeFilter = document.querySelector('.spectrum-filter-btn.active');
                if (activeFilter) {
                    applyDeliveryFilter(activeFilter.dataset.filter);
                }
                
                // Mettre à jour la couleur de Quantity Not Delivered
                const rowId = this.getAttribute('data-row');
                const orderedElement = document.querySelector(`.ordered-quantity[data-row="${rowId}"]`);
                const quantityNotDeliveredElement = document.querySelector(`.quantity-not-delivered[data-row="${rowId}"]`);
                
                if (orderedElement && quantityNotDeliveredElement) {
                    const orderedQuantity = parseFloat(orderedElement.textContent) || 0;
                    const quantityDelivered = parseFloat(this.value) || 0;
                    const quantityNotDelivered = Math.max(0, orderedQuantity - quantityDelivered);
                    
                    // Mettre à jour la valeur affichée
                    quantityNotDeliveredElement.textContent = quantityNotDelivered;
                    
                    // Réappliquer la couleur
                    applyQuantityNotDeliveredColor(quantityNotDeliveredElement, quantityNotDelivered);
                }
            }
        });
    });
});
