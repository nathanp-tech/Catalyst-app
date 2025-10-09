document.addEventListener('DOMContentLoaded', () => {

    // --- SÉLECTION DES ÉLÉMENTS DU DOM ---
    const welcomeScreen = document.getElementById('welcomeScreen');
    const workspace = document.getElementById('workspace');
    const documentSelector = document.getElementById('documentSelector');
    const startExerciseBtn = document.getElementById('startExerciseBtn');
    const questionImageDisplay = document.getElementById('questionImageDisplay');
    const changeExerciseBtn = document.getElementById('changeExerciseBtn');
    const endExerciseBtn = document.getElementById('endExerciseBtn');
    const chatbox = document.getElementById('chatbox');
    const textInput = document.getElementById('textInput');
    const sendBtn = document.getElementById('sendBtn');
    const hintBtn = document.getElementById('hintBtn');
    const canvasContainer = document.getElementById('canvas-container');
    const penTool = document.getElementById('penTool');
    const eraserTool = document.getElementById('eraserTool');
    const colorPicker = document.getElementById('colorPicker');
    const sizeSlider = document.getElementById('sizeSlider');
    const clearCanvasBtn = document.getElementById('clearCanvasBtn');
    const thicknessIcon = document.getElementById('thickness-icon');
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const zoomResetBtn = document.getElementById('zoomResetBtn');
    const questionZoomPercent = document.getElementById('questionZoomPercent');
    const pdfNavControls = document.getElementById('pdfNavControls');
    const prevPageBtn = document.getElementById('prevPageBtn');
    const nextPageBtn = document.getElementById('nextPageBtn');
    const pageIndicator = document.getElementById('pageIndicator');
    const startOnPageBtn = document.getElementById('startOnPageBtn');
    

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
    let currentPdf = null;
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
        if (sessionData.exercise_document) {
            const documentUrl = sessionData.exercise_document.url;
            welcomeScreen.classList.add('hidden');
            workspace.classList.remove('hidden');
            if (documentUrl.toLowerCase().endsWith('.pdf')) {
                await loadPdfAsImage(documentUrl);
            } else {
                uploadedImage = documentUrl;
                if (questionImageDisplay) questionImageDisplay.src = uploadedImage;
            }
            if (sendBtn) sendBtn.disabled = false;
            if (hintBtn) hintBtn.disabled = false;
        }
    }

    // ===================================================================
    // ===            GESTION DE L'EXERCICE (PDF, IMAGE)               ===
    // ===================================================================

    async function startExercise() {
        const documentUrl = documentSelector.value;
        if (!documentUrl) return;
        startExerciseBtn.disabled = true;

        try {
            if (documentUrl.toLowerCase().endsWith('.pdf')) {
                await loadPdfAsImage(documentUrl);
                if (totalPages === 1) await analyzeAndSwitchView();
            } else {
                uploadedImage = documentUrl;
                if (questionImageDisplay) questionImageDisplay.src = uploadedImage;
                updateQuestionZoom(1);
                await analyzeAndSwitchView();
            }
        } catch (error) {
            console.error("Erreur lors du chargement:", error);
            alert("Erreur lors du chargement du document.");
            startExerciseBtn.disabled = documentSelector.value === "";
        }
    }
    
    async function loadPdfAsImage(pdfUrl) {
        const loadingTask = pdfjsLib.getDocument(pdfUrl);
        currentPdf = await loadingTask.promise;
        totalPages = currentPdf.numPages;
        currentPageNum = 1;
        if (totalPages > 1) {
            pdfNavControls.classList.remove('hidden');
        }
        await renderPdfPage(1);
    }

    async function renderPdfPage(pageNum) {
        if (!currentPdf) return;
        pageIndicator.textContent = `Page ${pageNum} / ${totalPages}`;
        prevPageBtn.disabled = pageNum <= 1;
        nextPageBtn.disabled = pageNum >= totalPages;
        
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

    async function analyzeAndSwitchView() {
        await analyzeQuestionImage();
        welcomeScreen.classList.add('hidden');
        workspace.classList.remove('hidden');
        resizeCanvas();
    }

    async function analyzeQuestionImage() {
        if (!documentSelector || !uploadedImage) return;
        const imageBase64 = uploadedImage.split(',')[1];
        try {
            const res = await fetch(window.APP_CONFIG.analyzeImageUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": window.APP_CONFIG.csrfToken },
                body: JSON.stringify({ image: imageBase64, document_url: documentSelector.value })
            });
            if (!res.ok) throw new Error(`Erreur API: ${res.status}`);
            const data = await res.json();
            chatHistory = data.initial_history;
            renderChatHistory();
            if (sendBtn) sendBtn.disabled = false;
            if (hintBtn) hintBtn.disabled = false;
        } catch (err) {
            console.error(err);
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

        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();
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
        
        whiteboardState.tool = tool;
        fabricCanvas.freeDrawingBrush = new fabric.PencilBrush(fabricCanvas);

        penTool.classList.toggle('active', tool === 'pen');
        eraserTool.classList.toggle('active', tool === 'eraser');
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
        } else if (tool === 'eraser') {
            whiteboardState.eraserSize = currentSize;
        }
        fabricCanvas.freeDrawingBrush.width = currentSize;
    }

    function clearCanvas() {
        if (fabricCanvas) {
            fabricCanvas.clear();
            fabricCanvas.backgroundColor = 'white';
            fabricCanvas.renderAll();
        }
    }

    function prepareImageForAI() {
        if (!fabricCanvas || fabricCanvas.isEmpty()) return null;
        return fabricCanvas.toDataURL({ format: 'png', quality: 1.0 });
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
        hintBtn.disabled = true;
        let userMessageContent = [];
        if (textComment) userMessageContent.push({ type: 'text', text: textComment });
        if (preparedImage) userMessageContent.push({ type: 'image_url', url: preparedImage });

        chatHistory.push({ role: 'user', content: userMessageContent });
        renderChatHistory();
        displayLoadingIndicator();
        textInput.value = '';
        clearCanvas();

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
            hintBtn.disabled = false;
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
        if (documentSelector) {
            documentSelector.addEventListener('change', () => {
                startExerciseBtn.disabled = !documentSelector.value;
            });
        }
        if (startExerciseBtn) startExerciseBtn.addEventListener('click', startExercise);
        if (changeExerciseBtn) changeExerciseBtn.addEventListener('click', () => window.location.reload());
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
        if (colorPicker) colorPicker.addEventListener('input', () => setColor(colorPicker.value));
        if (sizeSlider) sizeSlider.addEventListener('input', () => setSize(sizeSlider.value));
        if (clearCanvasBtn) clearCanvasBtn.addEventListener('click', clearCanvas);
        
        if (zoomInBtn) zoomInBtn.addEventListener('click', () => updateQuestionZoom(questionZoomLevel + 0.2));
        if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => updateQuestionZoom(questionZoomLevel - 0.2));
        if (zoomResetBtn) zoomResetBtn.addEventListener('click', () => updateQuestionZoom(1));
        
        if (prevPageBtn) prevPageBtn.addEventListener('click', () => {
            if (currentPageNum > 1) {
                currentPageNum--;
                renderPdfPage(currentPageNum);
            }
        });
        if (nextPageBtn) nextPageBtn.addEventListener('click', () => {
            if (currentPageNum < totalPages) {
                currentPageNum++;
                renderPdfPage(currentPageNum);
            }
        });
        if (startOnPageBtn) startOnPageBtn.addEventListener('click', () => {
            startOnPageBtn.disabled = true;
            analyzeAndSwitchView();
        });
    }
    
    // --- Lancement de l'application ---
    initialize();
});
