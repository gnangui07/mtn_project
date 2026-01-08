// Fonction initHeatmap supprimée (carte thermique retirée)

// Fonction pour initialiser et mettre à jour la carte thermique (SUPPRIMÉE)
function initHeatmap_REMOVED() {
    // Référence à l'élément DOM pour la carte thermique
    const heatmapContainer = document.getElementById('heatmap-chart');
    const dataTypeSelect = document.getElementById('heatmap-data-type');
    
    // Vérifier si les éléments existent
    if (!heatmapContainer || !dataTypeSelect) return;
    
    // Variables pour stocker les données et l'instance de la carte thermique
    let heatmapInstance = null;
    let currentPeriod = 30; // Par défaut, même période que le tableau de bord
    
    // Fonction pour charger les données de la carte thermique
    function loadHeatmapData(period, dataType) {
        // Afficher l'indicateur de chargement
        const loadingIndicator = document.getElementById('analytics-loading');
        if (loadingIndicator) {
            loadingIndicator.style.display = 'flex';
        }
        
        // Construire l'URL avec les paramètres
        const url = `/orders/api/analytics/heatmap/?period=${period}&data_type=${dataType}`;
        
        // Effectuer la requête AJAX
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Erreur réseau: ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    // Mettre à jour la carte thermique avec les nouvelles données
                    updateHeatmap(data);
                } else {
                    console.error('Erreur lors du chargement des données:', data.message);
                    showError('Erreur lors du chargement des données de la carte thermique.');
                }
                
                // Masquer l'indicateur de chargement
                if (loadingIndicator) {
                    loadingIndicator.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Erreur lors du chargement des données:', error);
                showError('Erreur lors du chargement des données de la carte thermique.');
                
                // Masquer l'indicateur de chargement
                if (loadingIndicator) {
                    loadingIndicator.style.display = 'none';
                }
            });
    }
    
    // Fonction pour mettre à jour la carte thermique
    function updateHeatmap(data) {
        // Nettoyer le conteneur
        heatmapContainer.innerHTML = '';
        
        // Créer une nouvelle instance de heatmap.js
        heatmapInstance = h337.create({
            container: heatmapContainer,
            radius: 15,
            maxOpacity: 0.9,
            minOpacity: 0.1,
            blur: 0.85,
            gradient: {
                0.2: '#ffffcc',
                0.4: '#fed976',
                0.6: '#fd8d3c',
                0.8: '#e31a1c',
                1.0: '#800026'
            }
        });
        
        // Calculer les dimensions de la grille
        const containerWidth = heatmapContainer.offsetWidth;
        const containerHeight = heatmapContainer.offsetHeight;
        const cellWidth = containerWidth / 24; // 24 heures
        const cellHeight = containerHeight / 7; // 7 jours
        
        // Préparer les données pour heatmap.js
        const points = [];
        let max = 0;
        
        // Transformer les données pour la carte thermique
        data.heatmap_data.forEach(item => {
            const x = item.hour * cellWidth + cellWidth / 2;
            const y = item.day * cellHeight + cellHeight / 2;
            const value = item.value;
            
            points.push({
                x: Math.round(x),
                y: Math.round(y),
                value: value
            });
            
            // Mettre à jour la valeur maximale
            if (value > max) {
                max = value;
            }
        });
        
        // Définir les données pour la carte thermique
        heatmapInstance.setData({
            max: max,
            data: points
        });
        
        // Ajouter les étiquettes pour les jours et les heures
        addHeatmapLabels(data.day_labels, data.hour_labels, cellWidth, cellHeight);
        
        // Ajouter des tooltips interactifs
        addHeatmapTooltips(data, cellWidth, cellHeight);
    }
    
    // Fonction pour ajouter les étiquettes à la carte thermique
    function addHeatmapLabels(dayLabels, hourLabels, cellWidth, cellHeight) {
        // Créer un conteneur pour les étiquettes
        const labelsContainer = document.createElement('div');
        labelsContainer.className = 'heatmap-labels-container';
        labelsContainer.style.position = 'absolute';
        labelsContainer.style.top = '0';
        labelsContainer.style.left = '0';
        labelsContainer.style.width = '100%';
        labelsContainer.style.height = '100%';
        labelsContainer.style.pointerEvents = 'none';
        
        // Ajouter les étiquettes des jours (axe Y)
        dayLabels.forEach((day, index) => {
            const label = document.createElement('div');
            label.className = 'heatmap-day-label';
            label.textContent = day;
            label.style.position = 'absolute';
            label.style.left = '5px';
            label.style.top = (index * cellHeight + cellHeight / 2) + 'px';
            label.style.transform = 'translateY(-50%)';
            label.style.fontSize = '10px';
            label.style.color = '#666';
            labelsContainer.appendChild(label);
        });
        
        // Ajouter les étiquettes des heures (axe X)
        hourLabels.forEach((hour, index) => {
            // N'afficher que quelques heures pour éviter l'encombrement
            if (index % 3 === 0) {
                const label = document.createElement('div');
                label.className = 'heatmap-hour-label';
                label.textContent = hour;
                label.style.position = 'absolute';
                label.style.top = '5px';
                label.style.left = (index * cellWidth + cellWidth / 2) + 'px';
                label.style.transform = 'translateX(-50%)';
                label.style.fontSize = '10px';
                label.style.color = '#666';
                labelsContainer.appendChild(label);
            }
        });
        
        // Ajouter le conteneur d'étiquettes à la carte thermique
        heatmapContainer.appendChild(labelsContainer);
    }
    
    // Fonction pour ajouter des tooltips interactifs
    function addHeatmapTooltips(data, cellWidth, cellHeight) {
        // Créer un élément pour le tooltip
        const tooltip = document.createElement('div');
        tooltip.className = 'heatmap-tooltip';
        tooltip.style.display = 'none';
        document.body.appendChild(tooltip);
        
        // Créer un dictionnaire pour un accès facile aux données
        const dataDict = {};
        data.heatmap_data.forEach(item => {
            dataDict[`${item.day}-${item.hour}`] = item.value;
        });
        
        // Ajouter l'événement mousemove pour afficher le tooltip
        heatmapContainer.addEventListener('mousemove', function(e) {
            // Calculer la position de la souris relative au conteneur
            const rect = heatmapContainer.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            // Déterminer la cellule survolée
            const hourIndex = Math.floor(x / cellWidth);
            const dayIndex = Math.floor(y / cellHeight);
            
            // Vérifier si les indices sont valides
            if (hourIndex >= 0 && hourIndex < 24 && dayIndex >= 0 && dayIndex < 7) {
                const value = dataDict[`${dayIndex}-${hourIndex}`] || 0;
                const dayLabel = data.day_labels[dayIndex];
                const hourLabel = data.hour_labels[hourIndex];
                
                // Déterminer le texte du tooltip en fonction du type de données
                let valueText = '';
                switch (data.data_type) {
                    case 'activity_count':
                        valueText = `${value} activité(s)`;
                        break;
                    case 'reception_quantity':
                        valueText = `${value.toFixed(2)} unités reçues`;
                        break;
                    case 'reception_ratio':
                        valueText = `${value.toFixed(2)}% de réception`;
                        break;
                    default:
                        valueText = `Valeur: ${value}`;
                }
                
                // Mettre à jour le contenu du tooltip
                tooltip.innerHTML = `<strong>${dayLabel}, ${hourLabel}</strong><br>${valueText}`;
                
                // Positionner le tooltip près du curseur
                tooltip.style.left = (e.pageX + 10) + 'px';
                tooltip.style.top = (e.pageY + 10) + 'px';
                tooltip.style.display = 'block';
            } else {
                // Masquer le tooltip si en dehors de la grille
                tooltip.style.display = 'none';
            }
        });
        
        // Masquer le tooltip lorsque la souris quitte le conteneur
        heatmapContainer.addEventListener('mouseleave', function() {
            tooltip.style.display = 'none';
        });
    }
    
    // Fonction pour afficher un message d'erreur
    function showError(message) {
        const errorContainer = document.getElementById('analytics-error');
        if (errorContainer) {
            errorContainer.textContent = message;
            errorContainer.style.display = 'block';
        }
    }
    
    // Écouter les changements de type de données
    dataTypeSelect.addEventListener('change', function() {
        loadHeatmapData(currentPeriod, this.value);
    });
    
    // Écouter les changements de période
    const periodButtons = document.querySelectorAll('.period-btn');
    periodButtons.forEach(button => {
        button.addEventListener('click', function() {
            currentPeriod = parseInt(this.dataset.period);
            loadHeatmapData(currentPeriod, dataTypeSelect.value);
        });
    });
    
    // Charger les données initiales
    loadHeatmapData(currentPeriod, dataTypeSelect.value);
}

document.addEventListener('DOMContentLoaded', function() {
    // Références aux éléments DOM
    const bonSelect = document.getElementById('bon-select');
    const activityLogsBody = document.getElementById('activity-logs-body');
    const noResultsDiv = document.getElementById('no-results');
    const loadingSpinner = document.getElementById('loading-spinner');
    
    // Initialiser Select2 avec chargement automatique au changement
    $(bonSelect).select2({
        placeholder: 'Sélectionnez un bon de commande',
        allowClear: true,
        width: '100%'
    }).on('select2:select', function (e) {
        // Déclencher le chargement immédiat des données
        loadActivityLogs();
    });
    
    // Fonction pour charger la liste de tous les bons de commande
    function loadAllBons() {
        // Afficher l'indicateur de chargement
        loadingSpinner.style.display = 'block';
        
        fetch(getAllBonsUrl)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Stocker la liste des bons avec réception pour vérification ultérieure
                    window.bonsWithReception = new Set(data.bons_with_reception);
                    
                    // Vider le sélecteur et ajouter l'option par défaut
                    bonSelect.innerHTML = '<option value="">Select a purchase order</option>';
                    
                    // Ajouter les options au sélecteur
                    data.data.forEach(bonNumber => {
                        const option = new Option(bonNumber, bonNumber);
                        bonSelect.add(option);
                    });
                    
                    // Rafraîchir Select2 après avoir ajouté les options
                    $(bonSelect).trigger('change');
                    
                    // Masquer l'indicateur de chargement
                    loadingSpinner.style.display = 'none';
                } else {
                    console.error('Erreur lors du chargement des bons de commande:', data.message);
                    loadingSpinner.style.display = 'none';
                    noResultsDiv.style.display = 'block';
                    noResultsDiv.innerHTML = '<i class="fas fa-exclamation-triangle mr-2"></i> Erreur lors du chargement des bons de commande.';
                }
            })
            .catch(error => {
                console.error('Erreur lors du chargement des bons de commande:', error);
                loadingSpinner.style.display = 'none';
                noResultsDiv.style.display = 'block';
                noResultsDiv.innerHTML = '<i class="fas fa-exclamation-triangle mr-2"></i> Erreur lors du chargement des bons de commande.';
            });
    }
    
    // Fonction pour charger les logs d'activité
    function loadActivityLogs() {
        // Si aucun bon de commande n'est sélectionné, ne rien faire
        if (!bonSelect.value) {
            activityLogsBody.innerHTML = '';
            noResultsDiv.style.display = 'none';
            return;
        }
        
        // Afficher l'indicateur de chargement
        loadingSpinner.style.display = 'block';
        noResultsDiv.style.display = 'none';
        activityLogsBody.innerHTML = '';
        
        // Construire l'URL avec les paramètres de filtrage
        let url = getActivityLogsUrl;
        const params = new URLSearchParams();
        
        // Toujours filtrer par bon de commande sélectionné
        params.append('bon_number', bonSelect.value);
        
        // Ajouter les paramètres à l'URL
        url += '?' + params.toString();
        
        // Effectuer la requête AJAX
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Erreur réseau: ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                // Masquer l'indicateur de chargement
                loadingSpinner.style.display = 'none';
                
                if (data.status === 'success' && data.data && data.data.length > 0) {
                    // Afficher tous les résultats dans le tableau (y compris les corrections négatives)
                    data.data.forEach(log => {
                        // Traiter tous les logs, y compris ceux avec des valeurs négatives (corrections)
                        const row = document.createElement('tr');
                        row.classList.add('clickable-row');
                        
                        // Ajouter une classe spéciale pour les corrections négatives
                        if (parseFloat(log.quantity_delivered) < 0) {
                            row.classList.add('correction-row');
                        }
                        
                        // Stocker toutes les données dans des attributs data
                        row.dataset.log = JSON.stringify(log);
                        
                        // Formater les valeurs numériques
                        const formatNumber = (num) => {
                            const parsedNum = parseFloat(num);
                            return Number.isInteger(parsedNum) ? parsedNum.toString() : parsedNum.toFixed(2);
                        };
                        
                        // Extraire la date et l'heure
                        const dateParts = log.action_date_only.split('-');
                        const formattedDate = `${dateParts[2]}/${dateParts[1]}/${dateParts[0]}`;
                        
                        // Formater le taux d'avancement
                        const progressRate = parseFloat(log.progress_rate).toFixed(2);
                        
                        row.innerHTML = `
                            <td>${log.reception_number}</td>
                            <td>${log.user}</td>
                            <td>${formattedDate}</td>
                            <td>${log.action_time}</td>
                            <td>${progressRate}%</td>
                        `;
                        
                        activityLogsBody.appendChild(row);
                    });
                    
                    // Ajouter les gestionnaires de clic
                    document.querySelectorAll('.clickable-row').forEach(row => {
                        row.addEventListener('click', function() {
                            const logData = JSON.parse(this.dataset.log);
                            openDetailModal(logData);
                        });
                    });
                    
                    // Vérifier si des lignes ont été ajoutées
                    if (activityLogsBody.children.length === 0) {
                        // Aucune ligne avec des entrées en Receipt
                        noResultsDiv.style.display = 'block';
                        noResultsDiv.innerHTML = `<i class="fas fa-info-circle mr-2"></i> No delivery for the purchase order ${bonSelect.value}.`;
                    }
                } else {
                    // Afficher un message si aucun résultat
                    noResultsDiv.style.display = 'block';
                    noResultsDiv.innerHTML = '<i class="fas fa-info-circle mr-2"></i> No result found.';
                }
            })
            .catch(error => {
                console.error('Erreur lors du chargement des logs:', error);
                loadingSpinner.style.display = 'none';
                noResultsDiv.style.display = 'block';
                noResultsDiv.innerHTML = '<i class="fas fa-exclamation-triangle mr-2"></i> Erreur lors du chargement des données.';
            });
    }
    
    // Charger tous les bons de commande disponibles
    loadAllBons();
});
