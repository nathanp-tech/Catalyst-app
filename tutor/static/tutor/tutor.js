document.addEventListener('DOMContentLoaded', () => {

    // --- SÉLECTION DES ÉLÉMENTS DU DOM ---
    const questionCard = document.getElementById('questionCard');
    const questionImageDisplay = document.getElementById('questionImageDisplay');
    const endExerciseBtn = document.getElementById('endExerciseBtn');
    const chatbox = document.getElementById('chatbox');
    const textInput = document.getElementById('textInput');
    const sendBtn = document.getElementById('sendBtn');
    const canvasContainer = document.getElementById('canvas-container');
    const penTool = document.getElementById('penTool');
    const eraserTool = document.getElementById('eraserTool');
    const lineTool = document.getElementById('lineTool');
    const rectTool = document.getElementById('rectTool');
    const circleTool = document.getElementById('circleTool');
    const textTool = document.getElementById('textTool');
    const selectTool = document.getElementById('selectTool');
    const undoBtn = document.getElementById('undoBtn');
    const redoBtn = document.getElementById('redoBtn');
    const colorPicker = document.getElementById('colorPicker');
    const sizeSlider = document.getElementById('sizeSlider');
    const clearCanvasBtn = document.getElementById('clearCanvasBtn');
    const thicknessIcon = document.getElementById('thickness-icon');
    const fullscreenBtn = document.getElementById('fullscreenBtn');
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const zoomResetBtn = document.getElementById('zoomResetBtn');
    const questionZoomPercent = document.getElementById('questionZoomPercent');
    const leftPanel = document.querySelector('.left-panel');
    const whiteboardWorkspace = document.querySelector('.whiteboard-workspace');
    

    // --- VARIABLES D'ÉTAT ---
    let chatHistory = [];
    let uploadedImage = null;
    let fabricCanvas = null;
    const whiteboardState = {
        penColor: '#000000',
        penSize: 5,
        eraserSize: 20,
        tool: 'pen',
    };
    let history = [];
    let redoStack = [];
    let isDrawingShape = false;
    let shapeStartPoint = null;
    let currentPdf = null;
    let saveInterval = null;
    let currentPageNum = 1;
    let totalPages = 1;
    let questionZoomLevel = 1;

    // --- CONFIGURATION ---
    if (typeof pdfjsLib !== 'undefined') {
        pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.11.338/pdf.worker.min.js`;
    }
    const sessionData = JSON.parse(document.getElementById('session-data').textContent);

    // ===================================================================
    // ===                  INITIALISATION DE L'APP                    ===
    // ===================================================================
    
    function initialize() {
        attachEventListeners();
        setupWhiteboard();
        if (sessionData.ongoing_session) {
            restoreSession();
        }
    }

    async function restoreSession() {
        if (sessionData.initial_chat_history) {
            chatHistory = sessionData.initial_chat_history;
            renderChatHistory();
        }
        if (sessionData.whiteboard_state) {
            // Attendre que le canvas soit prêt
            setTimeout(() => {
                fabricCanvas.loadFromJSON(sessionData.whiteboard_state, fabricCanvas.renderAll.bind(fabricCanvas));
            }, 200);
        }
        if (sessionData.exercise_document) {
            const documentUrl = sessionData.exercise_document.url;
            if (documentUrl.toLowerCase().endsWith('.pdf')) {
                await loadPdfAsImage(documentUrl, 1); // On charge la première page
            }
            if (sendBtn) sendBtn.disabled = false;

            // Démarrer la sauvegarde automatique
            if (saveInterval) clearInterval(saveInterval);
            saveInterval = setInterval(saveWhiteboardState, 15000); // Sauvegarde toutes les 15 secondes
        }
    }

    // ===================================================================
    // ===            GESTION DE L'EXERCICE (PDF, IMAGE)               ===
    // ===================================================================

    async function loadPdfAsImage(pdfUrl, pageNum) {
        const loadingTask = pdfjsLib.getDocument(pdfUrl);
        currentPdf = await loadingTask.promise;
        totalPages = currentPdf.numPages;
        currentPageNum = pageNum;        
        await renderPdfPage(pageNum);
    }

    async function renderPdfPage(pageNum) {
        if (currentPdf) {
            const page = await currentPdf.getPage(pageNum);
            const viewport = page.getViewport({ scale: 2.0 });
            
            const tempCanvas = document.createElement('canvas');
            tempCanvas.height = viewport.height;
            tempCanvas.width = viewport.width;
            const renderContext = { canvasContext: tempCanvas.getContext('2d'), viewport: viewport };
            await page.render(renderContext).promise;
            
            uploadedImage = tempCanvas.toDataURL('image/png');
            if (questionImageDisplay) questionImageDisplay.src = uploadedImage;
        }
    }

    function updateQuestionZoom(newZoom) {
        questionZoomLevel = Math.max(0.5, Math.min(3, newZoom));
        if (questionImageDisplay) questionImageDisplay.style.transform = `scale(${questionZoomLevel})`;
        if (questionZoomPercent) questionZoomPercent.textContent = `${Math.round(questionZoomLevel * 100)}%`;
    }

    // ===================================================================
    // ===             GESTION DU WHITEBOARD (FABRIC.JS)               ===
    // ===================================================================

    function setupWhiteboard() {
        if (!document.getElementById('whiteboard')) return;

        fabricCanvas = new fabric.Canvas('whiteboard', {
            isDrawingMode: true,
            backgroundColor: 'white',
        });
        
        colorPicker.value = whiteboardState.penColor;
        sizeSlider.value = whiteboardState.penSize;
        setTool(whiteboardState.tool);
        
        fabricCanvas.on('mouse:down', () => { document.body.classList.add('drawing-active'); });
        fabricCanvas.on('mouse:up', () => { document.body.classList.remove('drawing-active'); });
        fabricCanvas.on('mouse:out', () => { document.body.classList.remove('drawing-active'); });
        
        // Gestion de l'historique
        fabricCanvas.on('object:added', saveState);
        fabricCanvas.on('object:modified', saveState);
        fabricCanvas.on('object:removed', saveState);

        // Gestion du dessin de formes
        fabricCanvas.on('mouse:down', startDrawingShape);
        fabricCanvas.on('mouse:move', continueDrawingShape);
        fabricCanvas.on('mouse:up', stopDrawingShape);

        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();
        saveState(); // Sauvegarde l'état initial vide
    }

    function resizeCanvas() {
        if (!fabricCanvas || !canvasContainer) return;
        const { width, height } = canvasContainer.getBoundingClientRect();
        fabricCanvas.setWidth(width);
        fabricCanvas.setHeight(height);
        fabricCanvas.renderAll();
    }
    
    function setTool(tool) {
        if (!fabricCanvas) return;
        
        // Désactiver le mode dessin pour les outils qui ne l'utilisent pas
        fabricCanvas.isDrawingMode = (tool === 'pen' || tool === 'eraser');
        fabricCanvas.selection = (tool === 'select');
        fabricCanvas.defaultCursor = (tool === 'select') ? 'default' : 'crosshair';

        whiteboardState.tool = tool;
        fabricCanvas.freeDrawingBrush = new fabric.PencilBrush(fabricCanvas);

        // Gérer l'état actif des boutons
        document.querySelectorAll('.toolbar .tool').forEach(t => t.classList.remove('active'));
        const activeToolBtn = document.getElementById(`${tool}Tool`);
        if (activeToolBtn) activeToolBtn.classList.add('active');
        if (tool === 'select') selectTool.classList.add('active');

        thicknessIcon.className = tool === 'pen' ? 'fas fa-pen-nib' : 'fas fa-eraser';
        
        if (tool === 'pen') {
            sizeSlider.value = whiteboardState.penSize;
            setColor(whiteboardState.penColor);
            setSize(whiteboardState.penSize);
        } else if (tool === 'eraser') {
            sizeSlider.value = whiteboardState.eraserSize;
            fabricCanvas.freeDrawingBrush.color = '#FFFFFF';
            setSize(whiteboardState.eraserSize);
        }
    }

    function setColor(color) {
        if (!fabricCanvas) return;
        whiteboardState.penColor = color;
        if (whiteboardState.tool !== 'pen') {
            setTool('pen');
        } else {
            fabricCanvas.freeDrawingBrush.color = color;
        }
    }

    function setSize(size) {
        if (!fabricCanvas) return;
        const currentSize = parseInt(size, 10);
        
        if (whiteboardState.tool === 'pen') {
            whiteboardState.penSize = currentSize;
        } else if (whiteboardState.tool === 'eraser') {
            whiteboardState.eraserSize = currentSize;
        }
        fabricCanvas.freeDrawingBrush.width = currentSize;
    }

    function clearCanvas() {
        if (fabricCanvas) {
            fabricCanvas.clear();
            fabricCanvas.backgroundColor = 'white';
            fabricCanvas.renderAll();
            saveState();
        }
    }

    function prepareImageForAI() {
        if (!fabricCanvas || fabricCanvas.isEmpty()) return null;
        return fabricCanvas.toDataURL({ format: 'png', quality: 1.0 });
    }
    
    function toggleFullscreen() {
        if (!document.fullscreenElement) {
            // Déplacer la carte de question dans le conteneur du tableau blanc avant le plein écran
            whiteboardWorkspace.appendChild(questionCard);
            if (whiteboardWorkspace.requestFullscreen) {
                whiteboardWorkspace.requestFullscreen();
            } else if (whiteboardWorkspace.webkitRequestFullscreen) { /* Safari */
                whiteboardWorkspace.webkitRequestFullscreen();
            }
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            }
        }
    }

    function handleFullscreenChange() {
        const icon = fullscreenBtn.querySelector('i');
        if (document.fullscreenElement) {
            // On est en plein écran
            icon.className = 'fas fa-compress';
            questionCard.classList.add('in-fullscreen');
        } else {
            // On a quitté le plein écran, on remet la carte à sa place
            leftPanel.insertBefore(questionCard, leftPanel.firstChild);
            questionCard.classList.remove('in-fullscreen');
            icon.className = 'fas fa-expand';
        }
    }

    // --- LOGIQUE POUR LES NOUVEAUX OUTILS ---

    function startDrawingShape(o) {
        if (['line', 'rect', 'circle'].includes(whiteboardState.tool)) {
            isDrawingShape = true;
            shapeStartPoint = fabricCanvas.getPointer(o.e);
        }
    }

    function continueDrawingShape(o) {
        if (!isDrawingShape) return;
        const pointer = fabricCanvas.getPointer(o.e);
        
        // Supprimer la forme temporaire précédente
        const tempShape = fabricCanvas.getObjects().find(obj => obj.isTemp);
        if (tempShape) fabricCanvas.remove(tempShape);

        let newShape;
        if (whiteboardState.tool === 'line') {
            newShape = new fabric.Line([shapeStartPoint.x, shapeStartPoint.y, pointer.x, pointer.y], {
                stroke: whiteboardState.penColor,
                strokeWidth: whiteboardState.penSize,
            });
        } else if (whiteboardState.tool === 'rect') {
            newShape = new fabric.Rect({
                left: Math.min(shapeStartPoint.x, pointer.x),
                top: Math.min(shapeStartPoint.y, pointer.y),
                width: Math.abs(pointer.x - shapeStartPoint.x),
                height: Math.abs(pointer.y - shapeStartPoint.y),
                fill: 'transparent',
                stroke: whiteboardState.penColor,
                strokeWidth: whiteboardState.penSize,
            });
        } else if (whiteboardState.tool === 'circle') {
            const radius = Math.sqrt(Math.pow(pointer.x - shapeStartPoint.x, 2) + Math.pow(pointer.y - shapeStartPoint.y, 2)) / 2;
            newShape = new fabric.Circle({
                left: shapeStartPoint.x - radius,
                top: shapeStartPoint.y - radius,
                radius: radius,
                fill: 'transparent',
                stroke: whiteboardState.penColor,
                strokeWidth: whiteboardState.penSize,
            });
        }

        if (newShape) {
            newShape.isTemp = true; // Marquer comme temporaire
            fabricCanvas.add(newShape);
            fabricCanvas.renderAll();
        }
    }

    function stopDrawingShape(o) {
        if (isDrawingShape) {
            // Remplacer la forme temporaire par la forme finale
            const tempShape = fabricCanvas.getObjects().find(obj => obj.isTemp);
            if (tempShape) {
                tempShape.isTemp = false;
                fabricCanvas.renderAll();
                // L'événement 'object:added' est déjà déclenché, donc l'état est sauvegardé.
            }
            isDrawingShape = false;
            shapeStartPoint = null;
        }
    }

    function addText() {
        const text = new fabric.IText('Tapez ici', {
            left: 100,
            top: 100,
            fill: whiteboardState.penColor,
            fontSize: 20,
        });
        fabricCanvas.add(text);
        fabricCanvas.setActiveObject(text);
        setTool('select'); // Passer en mode sélection pour éditer le texte
    }

    // --- LOGIQUE ANNULER/RÉTABLIR (UNDO/REDO) ---

    function saveState() {
        redoStack = []; // Vider la pile de rétablissement à chaque nouvelle action
        redoBtn.disabled = true;
        history.push(fabricCanvas.toJSON());
        undoBtn.disabled = history.length <= 1;
    }

    function undo() {
        if (history.length > 1) {
            redoStack.push(history.pop());
            const prevState = history[history.length - 1];
            fabricCanvas.loadFromJSON(prevState, fabricCanvas.renderAll.bind(fabricCanvas));
            redoBtn.disabled = false;
            undoBtn.disabled = history.length <= 1;
        }
    }

    function redo() {
        if (redoStack.length > 0) {
            const nextState = redoStack.pop();
            history.push(nextState);
            fabricCanvas.loadFromJSON(nextState, fabricCanvas.renderAll.bind(fabricCanvas));
            undoBtn.disabled = false;
            redoBtn.disabled = redoStack.length === 0;
        }
    }

    async function saveWhiteboardState() {
        if (!fabricCanvas || !window.APP_CONFIG.saveWhiteboardUrl) return;

        const whiteboardStateJSON = fabricCanvas.toJSON();
        try {
            await fetch(window.APP_CONFIG.saveWhiteboardUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.APP_CONFIG.csrfToken
                },
                body: JSON.stringify({ whiteboard_state: whiteboardStateJSON })
            });
        } catch (error) {
            console.error("Erreur lors de la sauvegarde du tableau blanc:", error);
        }
    }
    // ===================================================================
    // ===                    GESTION DU CHAT                          ===
    // ===================================================================

    async function sendToTutor() {
        const preparedImage = prepareImageForAI();
        const textComment = textInput.value.trim();
        if (!preparedImage && !textComment) {
            alert("Veuillez dessiner une réponse ou écrire un commentaire.");
            return;
        }

        sendBtn.disabled = true;
        let userMessageContent = [];
        if (textComment) userMessageContent.push({ type: 'text', text: textComment });
        if (preparedImage) userMessageContent.push({ type: 'image_url', url: preparedImage });

        chatHistory.push({ role: 'user', content: userMessageContent });
        renderChatHistory();
        displayLoadingIndicator();
        textInput.value = '';
        clearCanvas();

        // Sauvegarder l'état du tableau blanc juste après l'envoi
        await saveWhiteboardState();

        try {
            const res = await fetch(window.APP_CONFIG.tutorInteractUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": window.APP_CONFIG.csrfToken },
                body: JSON.stringify({ messages: chatHistory })
            });
            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(`Erreur API: ${errorData.error || res.statusText}`);
            }
            const replyData = await res.json();
            chatHistory.push({ role: 'assistant', content: replyData.content });
            renderChatHistory();
        } catch (err) {
            console.error(err);
            chatHistory.push({ role: 'assistant', content: [{"type": "text", "text": `Désolé, une erreur est survenue.`}] });
            renderChatHistory();
        } finally {
            sendBtn.disabled = false;
        }
    }
    
    function renderChatHistory() {
        if (!chatbox) return;
        chatbox.innerHTML = '';
        chatHistory.forEach(msg => {
            const messageDiv = document.createElement('div');
            messageDiv.className = `chat-message ${msg.role === 'assistant' ? 'tutor' : 'user'}`;
            let contentHTML = '';
            if (Array.isArray(msg.content)) {
                msg.content.forEach(item => {
                    if (item.type === 'text') {
                        contentHTML += `<div class="comment-text">${item.text}</div>`;
                    }
                    if (item.type === 'image_url') {
                        contentHTML += `<img src="${item.url || item.image_url.url}" alt="Réponse de l'élève">`;
                    }
                });
            } else {
                contentHTML = msg.content;
            }
            messageDiv.innerHTML = contentHTML;
            chatbox.appendChild(messageDiv);
        });
        if (chatbox.parentElement) chatbox.parentElement.scrollTop = chatbox.parentElement.scrollHeight;
        if (window.MathJax) MathJax.typesetPromise([chatbox]);
    }

    function displayLoadingIndicator() {
        if (!chatbox) return;
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'chat-message tutor';
        loadingDiv.innerHTML = `<span>Le tuteur réfléchit...</span>`;
        chatbox.appendChild(loadingDiv);
        if (chatbox.parentElement) chatbox.parentElement.scrollTop = chatbox.parentElement.scrollHeight;
    }

    // ===================================================================
    // ===               ATTACHEMENT DES ÉVÉNEMENTS                    ===
    // ===================================================================

    function attachEventListeners() {
        if (endExerciseBtn) {
            endExerciseBtn.addEventListener('click', async () => {
                if (!confirm("Es-tu sûr de vouloir terminer ?")) return;
                try {
                    const res = await fetch(window.APP_CONFIG.endSessionUrl, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.APP_CONFIG.csrfToken}
                    });
                    if (!res.ok) throw new Error('La réponse du serveur n\'était pas OK');
                    const data = await res.json();
                    window.location.href = data.redirect_url;
                } catch (error) {
                    console.error("Erreur lors de la fin de session:", error);
                    alert("Une erreur est survenue.");
                }
            });
        }
        if (sendBtn) sendBtn.addEventListener('click', sendToTutor);
        
        if (penTool) penTool.addEventListener('click', () => setTool('pen'));
        if (eraserTool) eraserTool.addEventListener('click', () => setTool('eraser'));
        if (lineTool) lineTool.addEventListener('click', () => setTool('line'));
        if (rectTool) rectTool.addEventListener('click', () => setTool('rect'));
        if (circleTool) circleTool.addEventListener('click', () => setTool('circle'));
        if (textTool) textTool.addEventListener('click', addText);
        if (selectTool) selectTool.addEventListener('click', () => setTool('select'));
        if (undoBtn) undoBtn.addEventListener('click', undo);
        if (redoBtn) redoBtn.addEventListener('click', redo);
        if (colorPicker) colorPicker.addEventListener('input', () => setColor(colorPicker.value));
        if (sizeSlider) sizeSlider.addEventListener('input', () => setSize(sizeSlider.value));
        if (clearCanvasBtn) clearCanvasBtn.addEventListener('click', clearCanvas);
        if (fullscreenBtn) fullscreenBtn.addEventListener('click', toggleFullscreen);
        document.addEventListener('fullscreenchange', handleFullscreenChange);
        document.addEventListener('webkitfullscreenchange', handleFullscreenChange); // Pour Safari
        
        if (zoomInBtn) zoomInBtn.addEventListener('click', () => updateQuestionZoom(questionZoomLevel + 0.2));
        if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => updateQuestionZoom(questionZoomLevel - 0.2));
        if (zoomResetBtn) zoomResetBtn.addEventListener('click', () => updateQuestionZoom(1));
        
    }
    
    // --- Lancement de l'application ---
    initialize();
});
