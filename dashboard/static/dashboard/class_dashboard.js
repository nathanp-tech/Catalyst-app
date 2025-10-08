// /static/dashboard/class_dashboard.js

document.addEventListener('DOMContentLoaded', function() {
    // --- SETUP DES ÉLÉMENTS PRINCIPAUX ---
    const modal = document.getElementById('studentModal');
    const studentGrid = document.getElementById('student-grid-container');

    // S'il n'y a pas de modale ou de grille d'élèves, on arrête le script.
    if (!modal || !studentGrid) {
        console.error("Éléments nécessaires (modale ou grille d'élèves) non trouvés.");
        return;
    }

    const modalStudentName = document.getElementById('modal-student-name');
    const detailsContainer = document.getElementById('modal-performance-details');
    const closeButton = modal.querySelector('.close-button');

    // --- FONCTIONS HELPERS ---
    function formatDuration(seconds) {
        if (isNaN(seconds) || seconds < 0) return "N/A";
        if (seconds < 60) return `${Math.round(seconds)} sec`;
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.round(seconds % 60);
        return `${minutes}m ${remainingSeconds}s`;
    }

    // --- LOGIQUE D'AFFICHAGE DE LA MODALE ---
    function displayPerformance(card) {
        const studentName = card.dataset.studentName;
        let performanceData;
        
        try {
            performanceData = JSON.parse(card.dataset.performance);
        } catch (e) {
            console.error("Erreur d'analyse JSON:", e, card.dataset.performance);
            detailsContainer.innerHTML = '<p class="empty-state">Impossible de lire les données de performance.</p>';
            return;
        }

        modalStudentName.textContent = `Progression de ${studentName}`;

        if (performanceData.length === 1) {
            // Vue détaillée pour un seul exercice
            const perf = performanceData[0];
            const statusClass = perf.status === 'Terminé' ? 'status-completed' : 'status-inprogress';
            detailsContainer.innerHTML = `
                <div class="single-exercise-details">
                    <h3>${perf.doc_title}</h3>
                    <ul class="performance-list">
                        <li><strong>Statut:</strong> <span class="status-badge ${statusClass}">${perf.status}</span></li>
                        <li><strong>Tentatives:</strong> ${perf.attempts}</li>
                        <li><strong>Messages échangés:</strong> ${perf.message_count}</li>
                        <li><strong>Temps total passé:</strong> ${formatDuration(perf.total_duration_seconds)}</li>
                        <li><strong>Dernière activité:</strong> ${perf.last_activity}</li>
                    </ul>
                    <div class="modal-actions">
                        <a href="${perf.latest_session_url}" class="button-primary">Voir la dernière session</a>
                    </div>
                </div>`;
        } else if (performanceData.length > 0) {
            // Vue tableau pour plusieurs exercices
            const rows = performanceData.map(perf => {
                const statusClass = perf.status === 'Terminé' ? 'status-completed' : 'status-inprogress';
                return `
                    <tr>
                        <td>${perf.doc_title}</td>
                        <td><span class="status-badge ${statusClass}">${perf.status}</span></td>
                        <td class="text-center">${perf.attempts}</td>
                        <td class="text-center">${perf.message_count}</td>
                        <td>${formatDuration(perf.total_duration_seconds)}</td>
                        <td><a href="${perf.latest_session_url}" class="button-secondary">Voir session</a></td>
                    </tr>`;
            }).join('');
            
            detailsContainer.innerHTML = `
                <table class="modal-table">
                    <thead><tr><th>Exercice</th><th>Statut</th><th>Tentatives</th><th>Messages</th><th>Temps total</th><th>Détails</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table>`;
        } else {
            detailsContainer.innerHTML = '<p class="empty-state">Aucune activité enregistrée pour cet élève avec les filtres actuels.</p>';
        }
    }

    function openModal() {
        modal.style.display = 'block';
    }

    function closeModal() {
        modal.style.display = 'none';
    }

    // --- NOUVELLE MÉTHODE : DÉLÉGATION D'ÉVÉNEMENTS ---
    studentGrid.addEventListener('click', function(event) {
        // On cherche l'élément .student-card le plus proche de l'endroit où l'utilisateur a cliqué
        const card = event.target.closest('.student-card');

        // Si on a bien trouvé une carte (et pas un clic dans le vide entre les cartes)
        if (card) {
            console.log("Carte élève cliquée :", card.dataset.studentName);
            displayPerformance(card);
            openModal();
        }
    });

    // --- GESTION DE LA FERMETURE DE LA MODALE ---
    closeButton.addEventListener('click', closeModal);
    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            closeModal();
        }
    });
    window.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeModal();
        }
    });

    console.log("Système de tableau de bord initialisé avec la méthode de délégation.");
});