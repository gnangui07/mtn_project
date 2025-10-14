// Script pour le tableau de bord analytique professionnel
document.addEventListener('DOMContentLoaded', function() {
    // Références aux éléments DOM
    const periodButtons = document.querySelectorAll('.period-btn');
    const dashboardContainer = document.getElementById('analytics-dashboard');
    const loadingIndicator = document.getElementById('analytics-loading');
    
    // Variables pour les graphiques
    let pieChart = null;
    let barChart = null;
    let lineChart = null;
    
    // Période par défaut
    let currentPeriod = 30;
    
    // Initialiser les gestionnaires d'événements pour les boutons de période
    periodButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Mettre à jour la période active
            currentPeriod = parseInt(this.dataset.period);
            
            // Mettre à jour l'UI pour le bouton actif
            periodButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            // Charger les données pour la nouvelle période
            loadAnalyticsData(currentPeriod);
        });
    });
    
    // Fonction pour charger les données analytiques
    function loadAnalyticsData(period) {
        // Afficher l'indicateur de chargement
        if (loadingIndicator) {
            loadingIndicator.style.display = 'flex';
        }
        
        // Construire l'URL avec le paramètre de période
        const url = `/orders/api/analytics/?period=${period}`;
        
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
                    // Mettre à jour les statistiques
                    updateStatistics(data);
                    
                    // Mettre à jour les graphiques
                    updateCharts(data);
                } else {
                    console.error('Erreur lors du chargement des données:', data.message);
                    showError('Erreur lors du chargement des données analytiques.');
                }
                
                // Masquer l'indicateur de chargement
                if (loadingIndicator) {
                    loadingIndicator.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Erreur lors du chargement des données:', error);
                showError('Erreur lors du chargement des données analytiques.');
                
                // Masquer l'indicateur de chargement
                if (loadingIndicator) {
                    loadingIndicator.style.display = 'none';
                }
            });
    }
    
    // Fonction pour mettre à jour les statistiques (simplifiée)
    function updateStatistics(data) {
        // Mettre à jour le nombre de bons avec réception
        const bonsAvecReceptionElement = document.getElementById('bons-avec-reception');
        if (bonsAvecReceptionElement) {
            bonsAvecReceptionElement.textContent = data.bons_avec_reception.toLocaleString();
        }
        
        // Mettre à jour le nombre total de bons
        const totalBonsElement = document.getElementById('total-bons');
        if (totalBonsElement) {
            totalBonsElement.textContent = data.total_bons.toLocaleString();
        }
        
        // Ajouter des animations de comptage pour les valeurs numériques
        animateValue('bons-avec-reception', 0, data.bons_avec_reception, 1000);
        animateValue('total-bons', 0, data.total_bons, 1000);
    }
    
    // Fonction pour animer les valeurs numériques
    function animateValue(elementId, start, end, duration) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        const startValue = parseInt(start);
        const endValue = parseInt(end);
        const range = endValue - startValue;
        const minFrame = 30; // 30ms par frame pour une animation fluide
        const frames = Math.max(1, Math.min(60, Math.abs(range))); // Entre 1 et 60 frames
        const stepTime = Math.max(minFrame, Math.floor(duration / frames));
        let current = startValue;
        const increment = range / frames;
        
        const timer = setInterval(function() {
            current += increment;
            if ((increment >= 0 && current >= endValue) || (increment < 0 && current <= endValue)) {
                clearInterval(timer);
                current = endValue;
            }
            element.textContent = Math.round(current).toLocaleString();
        }, stepTime);
    }
    
    // Fonction pour mettre à jour les graphiques (simplifiée)
    function updateCharts(data) {
        // Mettre à jour uniquement le graphique circulaire
        updatePieChart(data.pie_chart);
    }
    
    // Fonction pour mettre à jour le graphique circulaire
    function updatePieChart(pieData) {
        const pieChartCanvas = document.getElementById('pie-chart');
        if (!pieChartCanvas) return;
        
        // Détruire le graphique existant s'il existe
        if (pieChart) {
            pieChart.destroy();
        }
        
        // Créer le nouveau graphique
        const ctx = pieChartCanvas.getContext('2d');
        pieChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: pieData.labels,
                datasets: [{
                    data: pieData.values,
                    backgroundColor: [
                        'rgba(255, 200, 0, 0.9)',  // Jaune MTN plus doux
                        'rgba(108, 117, 125, 0.6)'  // Gris plus doux
                    ],
                    borderColor: [
                        'rgba(255, 255, 255, 0.8)',
                        'rgba(255, 255, 255, 0.8)'
                    ],
                    borderWidth: 1,
                    hoverOffset: 10,
                    borderRadius: 6,
                    spacing: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                radius: '90%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        align: 'center',
                        labels: {
                            padding: 15,
                            boxWidth: 12,
                            usePointStyle: true,
                            pointStyle: 'circle',
                            font: {
                                size: 12,
                                family: '"Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                                weight: 500
                            },
                            color: '#495057',
                            generateLabels: function(chart) {
                                const data = chart.data;
                                if (data.labels.length && data.datasets.length) {
                                    return data.labels.map((label, i) => {
                                        const value = data.datasets[0].data[i];
                                        const total = data.datasets[0].data.reduce((a, b) => a + b, 0);
                                        const percentage = Math.round((value / total) * 100);
                                        return {
                                            text: `${label}: ${value} (${percentage}%)`,
                                            fillStyle: data.datasets[0].backgroundColor[i],
                                            hidden: false,
                                            lineCap: 'round',
                                            lineDash: [],
                                            lineDashOffset: 0,
                                            lineJoin: 'round',
                                            lineWidth: 1,
                                            strokeStyle: data.datasets[0].borderColor[i],
                                            pointStyle: 'circle',
                                            rotation: 0
                                        };
                                    });
                                }
                                return [];
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleFont: {
                            size: 13,
                            weight: 'bold',
                            family: '"Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
                        },
                        bodyFont: {
                            size: 13,
                            family: '"Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
                        },
                        padding: 12,
                        cornerRadius: 6,
                        displayColors: true,
                        usePointStyle: true,
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.raw;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = Math.round((value / total) * 100);
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }
    
    // Fonctions updateBarChart et updateLineChart supprimées (graphiques retirés)
    
    // Fonction pour afficher un message d'erreur
    function showError(message) {
        const errorContainer = document.getElementById('analytics-error');
        if (errorContainer) {
            errorContainer.textContent = message;
            errorContainer.style.display = 'block';
        }
    }
    
    // Charger les données initiales avec la période par défaut
    loadAnalyticsData(currentPeriod);
});
