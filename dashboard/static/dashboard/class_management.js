document.addEventListener('DOMContentLoaded', () => {
    // --- MODAL HANDLING ---
    const studentModal = document.getElementById('studentModal');
    const moveStudentModal = document.getElementById('moveStudentModal');
    const modals = [studentModal, moveStudentModal];

    modals.forEach(modal => {
        if (!modal) return;
        const closeBtn = modal.querySelector('.close-button');
        closeBtn.addEventListener('click', () => modal.style.display = 'none');
    });

    window.addEventListener('click', (event) => {
        modals.forEach(modal => {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        });
    });

    // --- API HELPER ---
    async function apiCall(url, method, body) {
        const headers = { 'X-CSRFToken': csrfToken };
        const options = { method, headers };
        if (method === 'POST') {
            options.body = body;
        }
        const response = await fetch(url, options);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Une erreur est survenue.');
        }
        return response.json();
    }

    // --- CLASS ACTIONS ---
    document.getElementById('addClassBtn').addEventListener('click', () => {
        const className = prompt("Entrez le nom de la nouvelle classe :");
        if (className) {
            const formData = new FormData();
            formData.append('class_name', className);
            apiCall(classCreateUrl, 'POST', formData)
                .then(() => window.location.reload())
                .catch(err => alert(`Erreur : ${err.message}`));
        }
    });

    document.querySelectorAll('.rename-class-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const classCard = e.target.closest('.class-card');
            const classId = classCard.dataset.classId;
            const currentName = classCard.querySelector('.class-name').textContent;
            const newName = prompt("Entrez le nouveau nom de la classe :", currentName);

            if (newName && newName !== currentName) {
                const formData = new FormData();
                formData.append('action', 'rename');
                formData.append('new_name', newName);
                apiCall(`${classActionUrlTemplate}${classId}/action/`, 'POST', formData)
                    .then(data => {
                        classCard.querySelector('.class-name').textContent = data.name;
                    })
                    .catch(err => alert(`Erreur : ${err.message}`));
            }
        });
    });

    document.querySelectorAll('.delete-class-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const classCard = e.target.closest('.class-card');
            const classId = classCard.dataset.classId;
            const className = classCard.querySelector('.class-name').textContent;

            if (confirm(`Êtes-vous sûr de vouloir supprimer la classe "${className}" ? Cette action est irréversible.`)) {
                const formData = new FormData();
                formData.append('action', 'delete');
                apiCall(`${classActionUrlTemplate}${classId}/action/`, 'POST', formData)
                    .then(() => classCard.remove())
                    .catch(err => alert(`Erreur : ${err.message}`));
            }
        });
    });

    // --- STUDENT ACTIONS ---
    document.getElementById('addStudentBtn').addEventListener('click', () => {
        document.getElementById('studentForm').reset();
        document.getElementById('studentModalTitle').textContent = "Ajouter un élève";
        studentModal.style.display = 'block';
    });

    document.getElementById('studentForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        apiCall(studentCreateUrl, 'POST', formData)
            .then(() => window.location.reload())
            .catch(err => alert(`Erreur : ${err.message}`));
    });

    document.querySelectorAll('.move-student-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const studentItem = e.target.closest('.student-item');
            const studentId = studentItem.dataset.studentId;
            const studentName = studentItem.querySelector('span').textContent.trim();

            document.getElementById('moveStudentId').value = studentId;
            document.getElementById('moveStudentName').textContent = studentName;
            moveStudentModal.style.display = 'block';
        });
    });

    document.getElementById('moveStudentForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const studentId = formData.get('student_id');
        formData.append('action', 'move');

        apiCall(`${studentActionUrlTemplate}${studentId}/action/`, 'POST', formData)
            .then(() => window.location.reload())
            .catch(err => alert(`Erreur : ${err.message}`));
    });

    document.querySelectorAll('.delete-student-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const studentItem = e.target.closest('.student-item');
            const studentId = studentItem.dataset.studentId;
            const studentName = studentItem.querySelector('span').textContent.trim();

            if (confirm(`Êtes-vous sûr de vouloir supprimer l'élève "${studentName}" ? Toutes ses données (sessions, etc.) seront perdues.`)) {
                const formData = new FormData();
                formData.append('action', 'delete');
                apiCall(`${studentActionUrlTemplate}${studentId}/action/`, 'POST', formData)
                    .then(() => studentItem.remove())
                    .catch(err => alert(`Erreur : ${err.message}`));
            }
        });
    });
});

