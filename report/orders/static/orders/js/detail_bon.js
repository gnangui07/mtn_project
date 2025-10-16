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
    
    // Gérer le bouton de génération de rapport MSRN
    const generateMsrnBtn = document.getElementById('generate-msrn-btn');
    if (generateMsrnBtn) {
        generateMsrnBtn.addEventListener('click', function() {
            const bonId = this.getAttribute('data-bon-id');
            const retentionBtn = document.getElementById('set-retention-btn');
            
            // Récupérer directement les valeurs de rétention déjà définies
            const retentionRate = retentionBtn ? retentionBtn.getAttribute('data-retention-rate') || 0 : 0;
            const retentionCause = retentionBtn ? retentionBtn.getAttribute('data-retention-cause') || '' : '';
            
            // Afficher une alerte de confirmation avec les informations du PO
            Swal.fire({
                title: 'Generate MSRN Report?',
                html: `
                    <div style="text-align: left; padding: 10px;">
                        <p style="margin-bottom: 15px;"><strong>Please confirm the following information:</strong></p>
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
                                <td style="padding: 8px;">${parseFloat(amountDelivered).toLocaleString()} ${currency}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid #ddd;">
                                <td style="padding: 8px; font-weight: bold;">Delivery Rate:</td>
                                <td style="padding: 8px;"><strong style="color: #28a745;">${deliveryRate}%</strong></td>
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
                confirmButtonText: 'OK, Generate MSRN',
                cancelButtonText: 'Cancel',
                width: '650px'
            }).then((result) => {
                if (result.isConfirmed) {
                    // L'utilisateur a confirmé, procéder à la génération
                    // Afficher un indicateur de chargement
                    Swal.fire({
                        title: 'Generating MSRN report',
                        text: 'Please wait...',
                        allowOutsideClick: false,
                        didOpen: () => {
                            Swal.showLoading();
                        }
                    });
                    
                    // Appeler l'API pour générer le rapport MSRN
                    fetch(`/orders/api/generate-msrn/${bonId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({
                    retention_rate: retentionRate,
                    retention_cause: retentionCause
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Fermer l'indicateur de chargement
                    Swal.close();
                    
                    // Rediriger directement vers l'URL de téléchargement
                    window.location.href = data.download_url;
                } else {
                    // Afficher un message d'erreur
                    Swal.fire({
                        icon: 'error',
                        title: 'Erreur',
                        text: data.error || 'An error occurred while generating the MSRN report.'
                    });
                }
            })
            .catch(error => {
                console.error('Error generating MSRN report:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Erreur',
                    text: 'An error occurred while generating the MSRN report.'
                });
            });
                }
            });
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
            // Rouge si Quantity Not Delivered = 0
            parentCell.style.backgroundColor = '#f8d7da';
            parentCell.style.color = '#721c24';
            parentCell.style.fontWeight = 'bold';
        } else if (quantityNotDelivered > 0) {
            // Vert s'il reste des quantités à livrer
            parentCell.style.backgroundColor = '#d4edda';
            parentCell.style.color = '#155724';
            parentCell.style.fontWeight = 'bold';
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
                // Afficher le modal de correction avec l'historique
                showCorrectionModal(data.history, rowIndices);
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
        
        // Filtrer les lignes qui ne sont pas encore complètement reçues
        const eligibleRows = [];
        const updates = [];
        
        for (const checkbox of selectedRows) {
            const businessId = checkbox.getAttribute('data-row');
            const quantityDeliveredInput = document.querySelector(`.quantity-delivered-input[data-row="${businessId}"]`);
            const orderedElement = document.querySelector(`.ordered-quantity[data-row="${businessId}"]`);
            
            if (quantityDeliveredInput && orderedElement) {
                const currentQuantityDelivered = parseFloat(quantityDeliveredInput.value) || 0;
                const orderedQuantity = parseFloat(orderedElement.textContent) || 0;
                const quantityNotDelivered = Math.max(0, orderedQuantity - currentQuantityDelivered);
                
                // Vérifier si la ligne n'est pas déjà complète
                if (quantityNotDelivered > 0) {
                    eligibleRows.push({
                        checkbox,
                        businessId,
                        quantityDeliveredInput,
                        quantityNotDeliveredElement: document.querySelector(`.quantity-not-delivered[data-row="${businessId}"]`),
                        orderedQuantity,
                        quantityNotDelivered
                    });
                    
                    // Préparer les données pour l'API en lot
                    updates.push({
                        business_id: businessId,
                        quantity_delivered: quantityNotDelivered, // Quantité à ajouter
                        ordered_quantity: orderedQuantity
                    });
                }
            }
        }
        
        // Compter uniquement les lignes éligibles
        const eligibleCount = eligibleRows.length;
        const totalSelected = selectedRows.length;
        const skippedCount = totalSelected - eligibleCount;
    
        if (eligibleCount === 0) {
            Swal.fire({
                icon: 'info',
                title: 'No eligible line',
                html: `
                    <div style="text-align: left;">
                        <p>The ${totalSelected} selected lines are already fully received.</p>
                        <p>The Quantity Delivered collective will only apply to lines with remaining quantity > 0.</p>
                    </div>
                `
            });
            return;
        }
        
        // Demander confirmation à l'utilisateur
        const { isConfirmed } = await Swal.fire({
            title: 'Confirm collective delivery',
            html: `
                <div style="text-align: left;">
                    <p>Selected lines: <strong>${totalSelected}</strong></p>
                    <p>Eligible lines: <strong>${eligibleCount}</strong> (remaining quantity > 0)</p>
                    <p>Skipped lines: <strong>${skippedCount}</strong> (already complete)</p>
                    <p>This action is irreversible. Do you want to continue?</p>
                </div>
            `,
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Yes, apply',
            cancelButtonText: 'Close',
            confirmButtonColor: '#28a745',
            cancelButtonColor: '#dc3545'
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
                    html: `Operation successful for <strong>${eligibleCount}</strong> lines<br>
                           (${skippedCount} lines skipped because already complete)`,
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
            if (isNaN(rate) || rate < 0 || rate > 10) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Validation',
                    text: 'The Payment Retention rate must be between 0 and 10%'
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
            .then(r => r.json())
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
        // Stocker la valeur originale et précédente au focus
        input.addEventListener('focus', function() {
            this.setAttribute('data-original-value', this.value);
            this.setAttribute('data-previous-value', this.value || '0');
        });
        
        // Validation pendant la saisie
        input.addEventListener('input', function() {
            // Autoriser les chiffres, un point décimal, et le signe moins au début
            // Supprimer tous les caractères non autorisés sauf - au début
            let value = this.value;
            
            // Permettre le signe moins seulement au début
            const hasMinusAtStart = value.startsWith('-');
            
            // Supprimer tous les caractères non numériques sauf le point et le minus au début
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
        });
        
        // Gestion de la touche Entrée
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation(); // Empêche la propagation de l'événement
                this.blur(); // Déclenche le blur qui va appeler la validation
                return false; // Empêche tout autre comportement par défaut
            }
        });
        
        // Gestion de la perte de focus du champ
        input.addEventListener('blur', async function() {
            // Toujours exécuter la logique de sauvegarde même si la valeur n'a pas changé
            const row = this.getAttribute('data-row');
            const orderedQuantityElement = document.querySelector(`.ordered-quantity[data-row="${row}"]`);
            const orderedQuantity = parseFloat(orderedQuantityElement?.textContent || this.getAttribute('data-ordered') || '0');
            
            // Récupérer la valeur actuelle de quantity delivered
            const currentQuantityDelivered = parseFloat(this.getAttribute('data-original-value') || '0');            
            
            let newValue = this.value.trim() === '' ? 0 : parseFloat(this.value);
            
            // Si la valeur n'est pas un nombre, utiliser 0
            if (isNaN(newValue)) {
                newValue = 0;
            }
            
            // Utiliser directement la nouvelle valeur saisie
            const quantityDelivered = newValue;
            
            // Validation intelligente pour les valeurs négatives (correction d'erreurs)
            if (quantityDelivered < 0) {
                // Vérifier que la valeur négative ne rend pas le total négatif
                const currentTotal = parseFloat(this.getAttribute('data-original-value') || '0');
                const newTotal = currentTotal + quantityDelivered;
                
                if (newTotal < 0) {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Correction impossible',
                        html: `The correction of ${quantityDelivered} would make the total negative.<br>
                               <strong>Current total:</strong> ${currentTotal}<br>
                               <strong>New total:</strong> ${newTotal}<br><br>
                               <em>Tip: To correct an error, enter a negative value equal to the error made.</em>`,
                        confirmButtonColor: '#3085d6',
                    });
                    this.value = this.getAttribute('data-original-value') || '0';
                    return;
                }
                
                // Demander confirmation pour les valeurs négatives (correction)
                const confirmResult = await Swal.fire({
                    title: 'Correction de réception',
                    html: `
                        <div style="text-align: left;">
                            <p><i class="fas fa-exclamation-triangle text-warning"></i> Register negative quantity for delivery reversal.</p>
                            <p><strong>Line:</strong> ${row}</p>
                            <p><strong>Actual delivered Quantity:</strong> ${currentTotal}</p>
                            <p><strong>Reversed quantity:</strong> ${quantityDelivered}</p>
                            <p><strong>Corrected Delivered Quantity:</strong> ${newTotal}</p>
                            <hr>
                            <p class="text-info"><small><i class="fas fa-info-circle"></i> Action will generate system Log for security Purpose .</small></p>
                        </div>
                    `,
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonColor: '#dc3545',
                    cancelButtonColor: '#6c757d',
                    confirmButtonText: 'Yes, reverse',
                    cancelButtonText: 'Close',
                    allowOutsideClick: false,
                    allowEscapeKey: false
                });
                
                if (!confirmResult.isConfirmed) {
                    this.value = this.getAttribute('data-original-value') || '0';
                    return;
                }
            }
            
            // Vérifier que la quantité positive ne dépasse pas la commande
            if (quantityDelivered > 0) {
                const currentTotal = parseFloat(this.getAttribute('data-original-value') || '0');
                const newTotal = currentTotal + quantityDelivered;
                
                if (newTotal > orderedQuantity) {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Quantité invalide',
                        html: `La quantité totale (${newTotal}) dépasserait la quantité commandée (${orderedQuantity}).<br>
                               <strong>Total actuel:</strong> ${currentTotal}<br>
                               <strong>Ajout demandé:</strong> ${quantityDelivered}<br>
                               <strong>Maximum possible:</strong> ${orderedQuantity - currentTotal}`,
                        confirmButtonColor: '#3085d6',
                    });
                    this.value = this.getAttribute('data-original-value') || '0';
                    return;
                }
            }
            
            // Toujours demander confirmation, que la valeur ait changé ou non
            const result = await Swal.fire({
                title: 'Confirm delivery',
                html: `
                    <div style="text-align: left;">
                        <p>Are you sure you want to register this delivery ?</p>
                        <p><strong>Line:</strong> ${row}</p>
                        <p><strong>Ordered Quantity:</strong> ${orderedQuantity}</p>
                        <p><strong>Incremental Delivered Quantity :</strong> ${quantityDelivered}</p>
                    </div>
                `,
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#3085d6',
                cancelButtonColor: '#d33',
                confirmButtonText: 'Yes, register',
                cancelButtonText: 'Close',
                allowOutsideClick: false,
                allowEscapeKey: false,
                showLoaderOnConfirm: true
            });
            
            if (result.isConfirmed) {
                // Envoyer la mise à jour au serveur
                try {
                    // Envoyer la quantité totale - la fonction saveQuantityDeliveredChanges s'occupe de la mise à jour UI
                    await saveQuantityDeliveredChanges(row, orderedQuantity, quantityDelivered);
                    
                } catch (error) {
                    console.error('Erreur lors de la sauvegarde:', error);
                    // En cas d'erreur, restaurer la valeur précédente
                    this.value = this.getAttribute('data-original-value') || '0';
                }    
            } else {
                // Annulation : restaurer la valeur précédente
                this.value = this.getAttribute('data-original-value') || '0';
                
                // Afficher une notification d'annulation
                Swal.fire({
                    position: 'top-end',
                    icon: 'info',
                    title: 'Operation cancelled',
                    showConfirmButton: false,
                    timer: 1500,
                    toast: true
                });
            }
        });
        
        // Gestion de la touche Entrée
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.blur(); // Déclenche l'événement blur
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
    const storageKey = 'columnPreferences_' + '{{ bon_number }}';
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
    const defaultColumns = ['Order', 'Order Description', 'Ordered','Price', 'Ordered Quantity','Quantity Delivered', 'Quantity Not Delivered', 'Receipt','Amount Delivered','Quantity Payable','Amount Payable'];
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
    const filterButtons = document.querySelectorAll('.filter-btn');
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
                const activeFilter = document.querySelector('.filter-btn.active');
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
