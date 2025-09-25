// custom_modal.js

// Variable globale pour stocker les données du modal actuel
let currentModalData = null;

// Fonction pour ouvrir le modal de détails personnalisé
function openDetailModal(log) {
    // Stocker les données dans la variable globale pour l'export
    currentModalData = log;
    
    // Onglet Résumé
    document.getElementById('modal-total-amount').textContent = 
        parseFloat(log.ordered_quantity).toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    
    // Utiliser exclusivement cumulative_recipe pour la quantité reçue cumulée
    document.getElementById('modal-amount-received').textContent = 
        parseFloat(log.cumulative_recipe || 0).toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    
    document.getElementById('modal-currency').textContent = log.currency || 'EUR';
    
    document.getElementById('modal-progress-rate').textContent = 
        parseFloat(log.progress_rate).toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    
    // Affichage des montants total et reçu
    const formatNumber = (num) => {
        return parseFloat(num).toLocaleString('fr-FR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    };
    
    document.getElementById('modal-po-amount').textContent = formatNumber(log.po_amount);
    document.getElementById('modal-received-amount').textContent = formatNumber(log.received_amount);
    
    // Afficher le champ Line
    document.getElementById('modal-line').textContent = log.line || 'N/A';
    
    // Onglet Détails - Remplir le tableau Current Reception avec les mêmes en-têtes que la page principale
    const currentReceptionTbody = document.getElementById('current-reception-tbody');
    currentReceptionTbody.innerHTML = '';
    
    // L'API fait déjà le filtrage correct, donc on utilise directement les réceptions précédentes
    const receptionsPrecedentes = (log.previous_receptions || []).sort((a, b) => {
        return new Date(a.action_date) - new Date(b.action_date);
    });
    
    // Afficher les réceptions précédentes
    receptionsPrecedentes.forEach(reception => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${reception.reception_number || 'N/A'}</td>
            <td>${reception.bon_commande || 'N/A'}</td>
            <td>${reception.line_description || 'N/A'}</td>
            <td>${reception.order_description || 'N/A'}</td>
            <td>${reception.supplier || 'N/A'}</td>
            <td>${reception.ordered_date || 'N/A'}</td>
            <td>${reception.project_number || 'N/A'}</td>
            <td>${reception.task_number || 'N/A'}</td>
            <td>${reception.schedule || 'N/A'}</td>
            <td>${reception.line || 'N/A'}</td>
            <td>${parseFloat(reception.ordered_quantity || 0).toFixed(2)}</td>
            <td>${parseFloat(reception.cumulative_recipe || 0).toFixed(2)}</td>
            <td>${parseFloat(reception.quantity_not_delivered || 0).toFixed(2)}</td>
            <td>${parseFloat(reception.price || 0).toFixed(2)} ${log.currency || 'XOF'}</td>
        `;
        currentReceptionTbody.appendChild(row);
    });
    
    // Ajouter la ligne actuelle (mise en évidence)
    const currentRow = document.createElement('tr');
    currentRow.classList.add('table-primary'); // Mise en évidence de la ligne actuelle
    currentRow.innerHTML = `
        <td>${log.reception_number || 'N/A'}</td>
        <td>${log.bon_commande || 'N/A'}</td>
        <td>${log.line_description || 'N/A'}</td>
        <td>${log.order_description || 'N/A'}</td>
        <td>${log.supplier || 'N/A'}</td>
        <td>${log.ordered_date || 'N/A'}</td>
        <td>${log.project_number || 'N/A'}</td>
        <td>${log.task_number || 'N/A'}</td>
        <td>${log.schedule || 'N/A'}</td>
        <td>${log.line || 'N/A'}</td>
        <td>${parseFloat(log.ordered_quantity || 0).toFixed(2)}</td>
        <td>${parseFloat(log.cumulative_recipe || 0).toFixed(2)}</td>
        <td>${parseFloat(log.quantity_not_delivered || 0).toFixed(2)}</td>
        <td>${parseFloat(log.price || 0).toFixed(2)} ${log.currency || 'XOF'}</td>
    `;
    currentReceptionTbody.appendChild(currentRow);
        
    // Remplir l'historique des réceptions
    const historyBody = document.getElementById('reception-history-table').querySelector('tbody');
    historyBody.innerHTML = '';
    
    if (log.line_receptions && log.line_receptions.length > 0) {
        // Trier les réceptions par date (de la plus ancienne à la plus récente)
        const sortedReceptions = [...log.line_receptions].sort((a, b) => {
            return new Date(a.date) - new Date(b.date);
        });
        
        // Utiliser directement les données du modèle ActivityLog
        sortedReceptions.forEach(reception => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${reception.date}</td>
                <td>${reception.order}</td>
                <td>${reception.line || 'N/A'}</td>
                <td>${parseFloat(reception.ordered_quantity || 0).toFixed(2)}</td>
                <td>${parseFloat(reception.quantity_delivered || 0).toFixed(2)}</td>
                <td>${parseFloat(reception.cumulative_recipe || 0).toFixed(2)}</td>
                <td>${parseFloat(reception.quantity_not_delivered || 0).toFixed(2)}</td>
            `;
            historyBody.appendChild(row);
        });
    } else {
        historyBody.innerHTML = '<tr><td colspan="6" class="text-center py-4">Aucune réception précédente</td></tr>';
    }
    
    // Afficher le modal personnalisé
    const modal = document.getElementById('detailModal');
    modal.classList.add('show');
    
    // Empêcher le défilement du body
    document.body.style.overflow = 'hidden';
}

// Fonction pour fermer le modal personnalisé
function closeDetailModal() {
    const modal = document.getElementById('detailModal');
    if (modal) {
        modal.classList.remove('show');
        // Rétablir le défilement 
        document.body.style.overflow = '';
    }
}

// Fonction d'export Excel améliorée avec 3 onglets
function exportToExcel() {
    if (!currentModalData) {
        alert('No data to export');
        return;
    }
    
    // Créer un nouveau classeur Excel
    const wb = XLSX.utils.book_new();
    
    // ==================== ONGLET 1: SUMMARY ====================
    const summaryData = [];
    
    // En-tête du résumé
    summaryData.push(['RECEPTION DETAILS SUMMARY']);
    summaryData.push(['']); // Ligne vide
    
    // Informations générales
    summaryData.push(['General Information']);
    summaryData.push(['Reception Number', currentModalData.reception_number || 'N/A']);
    summaryData.push(['Purchase Order', currentModalData.bon_commande || 'N/A']);
    summaryData.push(['Imported File', currentModalData.fichier_importe || 'N/A']);
    summaryData.push(['Date', currentModalData.action_date_only || 'N/A']);
    summaryData.push(['User', currentModalData.user || 'N/A']);
    summaryData.push(['']); // Ligne vide
    
    // Informations de commande
    summaryData.push(['Order Information']);
    summaryData.push(['Ordered Quantity', parseFloat(currentModalData.ordered_quantity || 0).toFixed(2)]);
    summaryData.push(['Quantity Delivered', parseFloat(currentModalData.cumulative_recipe || 0).toFixed(2)]);
    summaryData.push(['PO Amount', `${parseFloat(currentModalData.po_amount || 0).toFixed(2)} ${currentModalData.currency || 'EUR'}`]);
    summaryData.push(['']); // Ligne vide
    
    // Statut de réception
    summaryData.push(['Reception Status']);
    summaryData.push(['Amount Delivered', `${parseFloat(currentModalData.received_amount || 0).toFixed(2)} ${currentModalData.currency || 'EUR'}`]);
    summaryData.push(['Progress Rate', `${parseFloat(currentModalData.progress_rate || 0).toFixed(2)}%`]);
    
    // Créer la feuille Summary
    const summaryWs = XLSX.utils.aoa_to_sheet(summaryData);
    
    // Formatage de la feuille Summary
    summaryWs['!cols'] = [{wch: 25}, {wch: 30}]; // Largeur des colonnes
    
    // ==================== ONGLET 2: CURRENT RECEPTION ====================
    const detailsData = [];
    
    // En-tête des détails
    detailsData.push(['CURRENT RECEPTION DETAILS']);
    detailsData.push(['']); // Ligne vide
    
    // En-têtes du tableau de détails - identiques à ceux de la page principale
    detailsData.push([
        'Reception',
        'Order Number',
        'Line Description',
        'Order Description',
        'Supplier',
        'Ordered Date',
        'Project Number',
        'Task Number',
        'Schedule',
        'Line',
        'Ordered Quantity',
        'Quantity Delivered (Cumulative)',  // Remplacer 'Quantity Delivered'
        'Quantity Not Delivered',
        'Price'
    ]);
    
    // L'API fait déjà le filtrage correct, donc on utilise directement les réceptions précédentes
    const receptionsPrecedentes = (currentModalData.previous_receptions || []).sort((a, b) => {
        return new Date(a.action_date) - new Date(b.action_date);
    });
    
    // Ajouter les réceptions précédentes
    receptionsPrecedentes.forEach(reception => {
        detailsData.push([
            reception.reception_number || 'N/A',
            reception.bon_commande || 'N/A',
            reception.line_description || 'N/A',
            reception.order_description || 'N/A',
            reception.supplier || 'N/A',
            reception.ordered_date || 'N/A',
            reception.project_number || 'N/A',
            reception.task_number || 'N/A',
            reception.schedule || 'N/A',
            reception.line || 'N/A',
            parseFloat(reception.ordered_quantity || 0).toFixed(2),
            parseFloat(reception.cumulative_recipe || 0).toFixed(2),
            parseFloat(reception.quantity_not_delivered || 0).toFixed(2),
            `${parseFloat(reception.price || 0).toFixed(2)} ${currentModalData.currency || 'XOF'}`
        ]);
    });
    
    // Ajouter la réception actuelle
    detailsData.push([
        currentModalData.reception_number || 'N/A',
        currentModalData.bon_commande || 'N/A',
        currentModalData.line_description || 'N/A',
        currentModalData.order_description || 'N/A',
        currentModalData.supplier || 'N/A',
        currentModalData.ordered_date || 'N/A',
        currentModalData.project_number || 'N/A',
        currentModalData.task_number || 'N/A',
        currentModalData.schedule || 'N/A',
        currentModalData.line || 'N/A',
        parseFloat(currentModalData.ordered_quantity || 0).toFixed(2),
        parseFloat(currentModalData.cumulative_recipe || 0).toFixed(2),
        parseFloat(currentModalData.quantity_not_delivered || 0).toFixed(2),
        `${parseFloat(currentModalData.price || 0).toFixed(2)} ${currentModalData.currency || 'XOF'}`
    ]);
    
    // Créer la feuille Details
    const detailsWs = XLSX.utils.aoa_to_sheet(detailsData);
    
    // Formatage de la feuille Details
    detailsWs['!cols'] = [
        {wch: 15}, {wch: 20}, {wch: 25}, {wch: 20}, {wch: 12}, 
        {wch: 15}, {wch: 12}, {wch: 15}, {wch: 12}, {wch: 12}, {wch: 15}, {wch: 15}, {wch: 15}, {wch: 15}
    ];
    
    // ==================== ONGLET 3: RECEPTION HISTORY ====================
    const historyData = [];
    
    // En-tête de l'historique
    historyData.push(['RECEPTION HISTORY']);
    historyData.push(['']); // Ligne vide
    
    // En-têtes du tableau d'historique
    historyData.push([
        'Date',
        'Order Number',
        'Ordered Quantity',
        'Quantity Delivered (Per Reception)',  // Remplacer 'Quantity Delivered'
        'Cumulative Reception',
        'Quantity Not Delivered'
    ]);
    
    // Ajouter les données d'historique
    if (currentModalData.line_receptions && currentModalData.line_receptions.length > 0) {
        // Trier les réceptions par date
        const sortedReceptions = [...currentModalData.line_receptions].sort((a, b) => {
            return new Date(a.date) - new Date(b.date);
        });
        
        // Utiliser directement les données du modèle ActivityLog
        sortedReceptions.forEach(reception => {
            historyData.push([
                reception.date || 'N/A',
                reception.order || 'N/A',
                parseFloat(reception.ordered_quantity || 0).toFixed(2),
                parseFloat(reception.quantity_delivered || 0).toFixed(2),
                reception.cumulative_recipe === 0 || reception.cumulative_recipe === '0' ? '0.00' : (reception.cumulative_recipe !== null && reception.cumulative_recipe !== undefined ? parseFloat(reception.cumulative_recipe).toFixed(2) : 'N/A'),
                parseFloat(reception.quantity_not_delivered || 0).toFixed(2)
            ]);
        });
    } else {
        historyData.push(['No previous receptions found', '', '', '', '', '']);
    }
    
    // Créer la feuille History
    const historyWs = XLSX.utils.aoa_to_sheet(historyData);
    
    // Formatage de la feuille History
    historyWs['!cols'] = [{wch: 12}, {wch: 15}, {wch: 15}, {wch: 15}, {wch: 18}, {wch: 15}];
    
    // ==================== ASSEMBLAGE DU CLASSEUR ====================
    
    // Ajouter les feuilles au classeur
    XLSX.utils.book_append_sheet(wb, summaryWs, 'Summary');
    XLSX.utils.book_append_sheet(wb, detailsWs, 'Current Reception');
    XLSX.utils.book_append_sheet(wb, historyWs, 'Reception History');
    
    // Générer le nom de fichier
    const filename = `Reception_Details_${currentModalData.reception_number || 'Unknown'}_${currentModalData.bon_commande || 'Unknown'}_${currentModalData.action_date_only || 'Unknown'}.xlsx`;
    
    // Télécharger le fichier
    XLSX.writeFile(wb, filename);
    
    // Afficher un message de confirmation
    console.log('Excel file exported successfully with 3 tabs:', filename);
}

// Rendre la fonction exportToExcel accessible globalement
window.exportToExcel = exportToExcel;

// Fonction utilitaire pour formater les nombres
function formatCurrency(amount, currency) {
    return `${parseFloat(amount || 0).toFixed(2)} ${currency || 'EUR'}`;
}

// Fonction utilitaire pour formater les pourcentages
function formatPercentage(rate) {
    return `${parseFloat(rate || 0).toFixed(2)}%`;
}

// Gestionnaire d'événement pour la fermeture du modal
document.addEventListener('click', function(event) {
    // Vérifier si le modal est ouvert
    const modal = document.getElementById('detailModal');
    if (!modal || !modal.classList.contains('show')) {
        return;
    }
    
    // Fermer si clic sur le bouton de fermeture ou l'overlay
    if (event.target.id === 'closeDetailModal' || 
        event.target.classList.contains('custom-modal-overlay') ||
        event.target.classList.contains('custom-modal-close')) {
        closeDetailModal();
    }
});

// Fermeture avec la touche Echap
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeDetailModal();
    }
});
