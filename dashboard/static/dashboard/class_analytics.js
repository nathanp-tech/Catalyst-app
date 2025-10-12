// /static/dashboard/class_analytics.js
document.addEventListener('DOMContentLoaded', () => {
    const openBtn = document.getElementById('openAnalyticsBtn');
    const analyticsModal = document.getElementById('analyticsModal');

    // Si les éléments de base n'existent pas, on ne fait rien.
    if (!openBtn || !analyticsModal) {
        return;
    }

    // Sélection des éléments internes à la modale
    const closeBtn = analyticsModal.querySelector('.close-button');
    const chartsContainer = document.getElementById('analyticsChartsContainer');
    const modalTitle = document.getElementById('analyticsModalTitle');
    const metricSelector = document.getElementById('metricSelector');

    // Vérification que tous les éléments de la modale sont bien présents
    if (!closeBtn || !chartsContainer || !modalTitle || !metricSelector) {
        console.error("Un ou plusieurs éléments de la modale d'analyse sont manquants.");
        return;
    }

    let comparisonChart = null;
    let distributionChart = null;
    let analyticsData = null;

    const errorColors = {
        calcul: '#3498db',
        substitution: '#f1c40f',
        procedure: '#e74c3c',
        conceptuelle: '#9b59b6'
    };

    const metricLabels = {
        total_errors: 'Total des erreurs',
        total_duration_minutes: 'Temps total (min)',
        total_sessions: 'Nombre de sessions',
        total_messages: 'Nombre de messages'
    };

    const fetchData = async () => {
        const classId = document.getElementById('group-select').value;
        if (!classId) {
            alert("Veuillez d'abord sélectionner une classe.");
            return;
        }
        
        chartsContainer.innerHTML = '<div class="spinner" style="margin: 50px auto;"></div>';
        analyticsModal.style.display = 'block';

        try {
            const url = window.GROUP_CREATOR_CONFIG.analyticsApiUrlTemplate + classId + '/';
            const response = await fetch(url);
            if (!response.ok) throw new Error(`Erreur serveur: ${response.statusText}`);
            
            const data = await response.json();
            if (data.error) throw new Error(data.error);
            
            analyticsData = data.analytics;
            modalTitle.textContent = `Analyse de la Classe : ${data.class_name}`;
            
            chartsContainer.innerHTML = `
                <div class="chart-wrapper"><canvas id="comparisonChart"></canvas></div>
                <div class="chart-wrapper"><canvas id="distributionChart"></canvas></div>
            `;
            
            createComparisonChart(metricSelector.value);
            createDistributionChart();

        } catch (error) {
            chartsContainer.innerHTML = `<p style="color: red; text-align: center;">Erreur lors du chargement des données : ${error.message}</p>`;
        }
    };

    const createComparisonChart = (metric) => {
        if (comparisonChart) comparisonChart.destroy();
        
        const canvas = document.getElementById('comparisonChart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        
        const labels = analyticsData.map(d => d.student_name);
        const data = analyticsData.map(d => d[metric]);

        comparisonChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: metricLabels[metric],
                    data: data,
                    backgroundColor: 'rgba(74, 144, 226, 0.6)',
                    borderColor: 'rgba(74, 144, 226, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
                plugins: { legend: { display: false }, title: { display: true, text: 'Comparaison des élèves' } }
            }
        });
    };

    const createDistributionChart = () => {
        if (distributionChart) distributionChart.destroy();

        const canvas = document.getElementById('distributionChart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        const labels = analyticsData.map(d => d.student_name);
        
        const datasets = Object.keys(errorColors).map(errorKey => ({
            label: errorKey.charAt(0).toUpperCase() + errorKey.slice(1),
            data: analyticsData.map(d => (d.error_distribution && d.error_distribution[errorKey]) || 0),
            backgroundColor: errorColors[errorKey]
        }));

        distributionChart = new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { title: { display: true, text: 'Répartition des types d\'erreurs' } },
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true, ticks: { stepSize: 1 } }
                }
            }
        });
    };

    openBtn.addEventListener('click', fetchData);
    metricSelector.addEventListener('change', (e) => {
        if (analyticsData) createComparisonChart(e.target.value);
    });
    closeBtn.addEventListener('click', () => analyticsModal.style.display = 'none');
    window.addEventListener('click', (e) => {
        if (e.target === analyticsModal) analyticsModal.style.display = 'none';
    });
});
