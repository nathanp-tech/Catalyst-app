// /static/dashboard/class_dashboard_groups.js
document.addEventListener('DOMContentLoaded', () => {
    // --- SÉLECTION DES ÉLÉMENTS ---
    const startBtn = document.getElementById('startGroupCreationBtn');
    const sendBtn = document.getElementById('sendToGroupCreatorBtn');
    const manualModeBtn = document.getElementById('manualGroupCreationBtn');
    const finalizeBtn = document.getElementById('finalizeGroupsBtn');
    const saveManualBtn = document.getElementById('saveManualGroupsBtn');
    const numGroupsInput = document.getElementById('numGroupsInput');
    const chatbox = document.getElementById('groupCreatorChatbox');
    const messageInput = document.getElementById('groupCreatorInput');
    const configStep = document.getElementById('groupConfigStep');
    const chatStep = document.getElementById('groupChatStep');
    const manualStep = document.getElementById('manualGroupStep');
    const studentPoolEl = document.getElementById('studentPool');
    const groupColumnsContainerEl = document.getElementById('groupColumnsContainer');

    let chatHistory = [];

    const getSelectedClassId = () => {
        return document.getElementById('group-select').value;
    };

    // --- FONCTIONS D'AFFICHAGE ---
    const displayLoading = (isLoading) => {
        if (isLoading) {
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'chat-message tutor';
            loadingDiv.innerHTML = `<div class="spinner" style="width: 20px; height: 20px; border-width: 3px;"></div>`;
            chatbox.appendChild(loadingDiv);
            chatbox.scrollTop = chatbox.scrollHeight;
        } else {
            const spinnerMsg = chatbox.querySelector('.spinner');
            if (spinnerMsg) spinnerMsg.parentElement.remove();
        }
    };

    const renderGroupChat = () => {
        // Supprime l'indicateur de chargement avant de redessiner
        const spinnerMsg = chatbox.querySelector('.spinner');
        if (spinnerMsg) spinnerMsg.parentElement.remove();

        chatbox.innerHTML = chatHistory.map(msg => 
            `<div class="chat-message ${msg.role === 'user' ? 'user' : 'tutor'}">${msg.content.replace(/\n/g, '<br>')}</div>`
        ).join('');
        chatbox.scrollTop = chatbox.scrollHeight;
    };

    // --- LOGIQUE API ---
    const callGroupCreatorAPI = async () => {
        sendBtn.disabled = true;
        messageInput.disabled = true;
        displayLoading(true);
        
        const classId = getSelectedClassId();
        const numGroups = numGroupsInput.value;

        try {
            const response = await fetch(window.GROUP_CREATOR_CONFIG.apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.GROUP_CREATOR_CONFIG.csrfToken
                },
                body: JSON.stringify({
                    class_id: classId,
                    num_groups: numGroups,
                    messages: chatHistory
                })
            });
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            // Détecter si la réponse de l'IA est le JSON final
            try {
                const finalGroups = JSON.parse(data.reply);
                if (finalGroups.groups) {
                    chatHistory.push({ role: 'assistant', content: "Voici la répartition finale des groupes. Vous pouvez la valider." });
                    finalizeBtn.style.display = 'block';
                    finalizeBtn.onclick = async () => {
                        const configName = prompt("Donnez un nom à cette configuration de groupes (ex: Projet Volcans):");
                        if (configName) {
                            await saveGroups(configName, finalGroups.groups);
                            window.location.reload(); // Recharger pour voir les groupes
                        }
                    };
                    sendBtn.style.display = 'none';
                    messageInput.style.display = 'none';
                }
            } catch (e) {
                // Ce n'est pas le JSON final, c'est un message normal
            }

            chatHistory.push({ role: 'assistant', content: data.reply });
            renderGroupChat();

        } catch (error) {
            console.error("Erreur API:", error);
            chatHistory.push({ role: 'assistant', content: `Désolé, une erreur est survenue: ${error.message}` });
            renderGroupChat();
        } finally {
            displayLoading(false);
            sendBtn.disabled = false;
            messageInput.disabled = false;
            messageInput.focus();
        }
    };

    startBtn.addEventListener('click', () => {
        configStep.style.display = 'none';
        chatStep.style.display = 'block';
        callGroupCreatorAPI(); // Premier appel pour obtenir la suggestion initiale
    });

    // --- ÉVÉNEMENTS ---
    sendBtn.addEventListener('click', () => {
        const userMessage = messageInput.value.trim();
        if (!userMessage) return;

        chatHistory.push({ role: 'user', content: userMessage });
        renderGroupChat();
        messageInput.value = '';
        callGroupCreatorAPI();
    });

    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendBtn.click();
        }
    });

    document.querySelectorAll('.use-config-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const item = e.target.closest('.saved-group-item');
            const config = JSON.parse(item.dataset.config);
            const numGroups = e.target.dataset.numGroups;
            
            configStep.style.display = 'none';
            manualStep.style.display = 'block';
            setupManualCreationUI(numGroups, config);
        });
    });

    manualModeBtn.addEventListener('click', () => {
        chatStep.style.display = 'none';
        manualStep.style.display = 'block';
        setupManualCreationUI();
    });

    saveManualBtn.addEventListener('click', async () => {
        const groups = [];
        const groupColumns = groupColumnsContainerEl.querySelectorAll('.group-column');
        groupColumns.forEach(col => {
            const studentNames = [];
            col.querySelectorAll('.student-item').forEach(item => {
                studentNames.push(item.textContent.trim());
            });
            groups.push(studentNames);
        });
        const configName = prompt("Donnez un nom à cette configuration de groupes (ex: Projet Volcans):");
        if (configName) {
            await saveGroups(configName, groups);
            window.location.reload(); // Recharger pour voir les groupes
        }
    });

    // --- LOGIQUE DE CRÉATION MANUELLE (DRAG & DROP) ---
    function setupManualCreationUI(numGroups = null, prefilledGroups = null) {
        // 1. Créer les colonnes de groupe
        const numGroupValue = numGroups || parseInt(numGroupsInput.value, 10);
        groupColumnsContainerEl.innerHTML = '';
        for (let i = 1; i <= numGroupValue; i++) {
            const col = document.createElement('div');
            col.className = 'group-column';
            col.dataset.groupId = i;
            col.innerHTML = `<h5>Groupe ${i}</h5>`;
            groupColumnsContainerEl.appendChild(col);
        }

        // 2. Préparer la liste de tous les élèves
        const allStudents = new Map();
        const studentCards = document.querySelectorAll('.student-card');
        studentCards.forEach(card => {
            const studentName = card.querySelector('.student-name').textContent.trim();
            const studentId = card.closest('a').href.split('student_id=')[1].split('&')[0];
            allStudents.set(studentName, studentId);
        });

        // 3. Remplir les colonnes si une configuration est fournie
        if (prefilledGroups) {
            const groupColumns = groupColumnsContainerEl.querySelectorAll('.group-column');
            prefilledGroups.forEach((group, index) => {
                group.forEach(studentName => {
                    if (allStudents.has(studentName)) {
                        const li = createStudentDraggable(studentName, allStudents.get(studentName));
                        groupColumns[index].appendChild(li);
                        allStudents.delete(studentName); // Retirer de la liste des élèves à placer
                    }
                });
            });
        }

        // 4. Placer les élèves restants dans la colonne "à placer"
        studentPoolEl.innerHTML = '';
        for (const [studentName, studentId] of allStudents.entries()) {
            studentPoolEl.appendChild(createStudentDraggable(studentName, studentId));
        }

        // 5. Attacher les événements de drag & drop à tous les éléments créés
        const draggables = document.querySelectorAll('.student-item[draggable="true"]');
        const containers = [studentPoolEl, ...document.querySelectorAll('.group-column')];

        draggables.forEach(draggable => {
            draggable.addEventListener('dragstart', () => {
                // Ajoute un léger délai pour que le navigateur "prenne" l'élément
                setTimeout(() => draggable.classList.add('dragging'), 0);
            });
            draggable.addEventListener('dragend', () => {
                draggable.classList.remove('dragging');
            });
        });

        containers.forEach(container => {
            container.addEventListener('dragover', e => {
                e.preventDefault();
                container.classList.add('drag-over');
            });
            container.addEventListener('dragleave', () => {
                container.classList.remove('drag-over');
            });
            container.addEventListener('drop', e => {
                e.preventDefault();
                container.classList.remove('drag-over');
                const draggable = document.querySelector('.dragging');
                if (draggable) {
                    // Si le conteneur est une colonne de groupe, on l'ajoute à la fin
                    if (container.classList.contains('group-column')) {
                        container.appendChild(draggable);
                    } else { // Sinon (c'est la liste d'élèves), on l'ajoute au début
                        container.prepend(draggable);
                    }
                }
            });
        });
    }

    function createStudentDraggable(studentName, studentId) {
        const li = document.createElement('li');
        li.className = 'student-item manual';
        li.textContent = studentName;
        li.draggable = true;
        li.dataset.studentId = studentId;
        return li;
    }

    // --- LOGIQUE DE SAUVEGARDE ---
    async function saveGroups(name, groups) {
        const classId = getSelectedClassId();
        try {
            const response = await fetch(window.GROUP_CREATOR_CONFIG.saveUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.GROUP_CREATOR_CONFIG.csrfToken
                },
                body: JSON.stringify({ class_id: classId, name, groups })
            });
            const data = await response.json();
            if (!data.success) throw new Error(data.message);
            alert("Configuration des groupes enregistrée avec succès !");
        } catch (error) {
            alert(`Erreur lors de la sauvegarde : ${error.message}`);
        }
    }
});
