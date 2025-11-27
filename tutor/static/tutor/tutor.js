document.addEventListener('DOMContentLoaded', () => {

    // --- DOM ELEMENT SELECTION ---
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
    const restoreLastBtn = document.getElementById('restoreLastBtn');
    const clearCanvasBtn = document.getElementById('clearCanvasBtn');
    const thicknessIcon = document.getElementById('thickness-icon');
    const fullscreenBtn = document.getElementById('fullscreenBtn');
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const zoomResetBtn = document.getElementById('zoomResetBtn');
    const questionZoomPercent = document.getElementById('questionZoomPercent');
    const leftPanel = document.querySelector('.left-panel');
    const whiteboardWorkspace = document.querySelector('.whiteboard-workspace');
    
    // --- CONSTANTS ---
    const TOOLS = {
        PEN: 'pen',
        ERASER: 'eraser',
        LINE: 'line',
        RECT: 'rect',
        CIRCLE: 'circle',
        TEXT: 'text',
        SELECT: 'select',
    };

    // --- STATE VARIABLES ---
    let chatHistory = [];
    let uploadedImage = null;
    let fabricCanvas = null;
    const whiteboardState = {
        color: '#000000',
        penSize: 5, eraserSize: 20,
        tool: 'pen',
    };
    let history = [];
    let redoStack = [];
    let isDrawingShape = false;
    let shapeStartPoint = null;
    let lastSentWhiteboardState = null;
    let currentPdf = null;
    let currentPageNum = 1;
    let totalPages = 1;
    let questionZoomLevel = 1;
    let saveInterval = null;

    // --- CONFIGURATION ---
    if (typeof pdfjsLib !== 'undefined') {
        pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.11.338/pdf.worker.min.js`;
    }
    const sessionData = JSON.parse(document.getElementById('session-data').textContent);

    // --- UTILITIES ---
    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }

    // ===================================================================
    // ===                  APP INITIALIZATION                       ===
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
            renderChatHistory(); // Render chat history on session restore
        }
        if (sessionData.whiteboard_state) {
            // Wait for the canvas to be ready
            setTimeout(() => {
                fabricCanvas.loadFromJSON(sessionData.whiteboard_state, fabricCanvas.renderAll.bind(fabricCanvas));
            }, 200);
        }
        if (sessionData.exercise_document) {
            const documentUrl = sessionData.exercise_document.url;
            if (documentUrl.toLowerCase().endsWith('.pdf')) {
                await loadPdfAsImage(documentUrl, 1); // Load the first page
            }
            if (sendBtn) sendBtn.disabled = false;

            // Start automatic saving
            if (saveInterval) clearInterval(saveInterval);
            saveInterval = setInterval(saveWhiteboardState, 15000); // Save every 15 seconds
        }
    }
    
    function restoreLastWhiteboard() {
        if (lastSentWhiteboardState) {
            fabricCanvas.loadFromJSON(lastSentWhiteboardState, () => {
                fabricCanvas.renderAll();
                saveState(); // Save the restored state to history
            });
        } else {
            alert("No previous submission to restore.");
        }
    }

    // ===================================================================
    // ===            EXERCISE MANAGEMENT (PDF, IMAGE)               ===
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
    // ===             WHITEBOARD MANAGEMENT (FABRIC.JS)             ===
    // ===================================================================

    function setupWhiteboard() {
        if (!document.getElementById('whiteboard')) return;

        fabricCanvas = new fabric.Canvas('whiteboard', {
            isDrawingMode: true,
            backgroundColor: 'white',
        });
        
        colorPicker.value = whiteboardState.color;
        sizeSlider.value = whiteboardState.penSize;
        setTool(whiteboardState.tool);
        
        fabricCanvas.on('mouse:down', () => { document.body.classList.add('drawing-active'); });
        fabricCanvas.on('mouse:up', () => { document.body.classList.remove('drawing-active'); });
        fabricCanvas.on('mouse:out', () => { document.body.classList.remove('drawing-active'); });
        
        // History management
        fabricCanvas.on('object:added', saveState);
        fabricCanvas.on('object:modified', saveState);
        fabricCanvas.on('object:removed', saveState);

        // --- Palm Rejection ---
        fabricCanvas.on('mouse:down:before', function(opt) {
            // If the tool is a drawing tool and the event is a touch event,
            // temporarily disable drawing mode.
            if (fabricCanvas.isDrawingMode && opt.e.pointerType === 'touch') {
                fabricCanvas.isDrawingMode = false;
            }
        });
        fabricCanvas.on('mouse:up', () => setTool(whiteboardState.tool));
        
        // Shape drawing management
        fabricCanvas.on('mouse:down', startDrawingShape);
        fabricCanvas.on('mouse:move', continueDrawingShape);
        fabricCanvas.on('mouse:up', stopDrawingShape);

        window.addEventListener('resize', debounce(resizeCanvas, 150));
        resizeCanvas();
        saveState(); // Save the initial empty state
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
        
        // Disable drawing mode for tools that don't use it
        fabricCanvas.isDrawingMode = [TOOLS.PEN, TOOLS.ERASER].includes(tool);
        fabricCanvas.selection = (tool === TOOLS.SELECT);
        fabricCanvas.defaultCursor = (tool === TOOLS.SELECT) ? 'default' : 'crosshair';

        whiteboardState.tool = tool;
        fabricCanvas.freeDrawingBrush = new fabric.PencilBrush(fabricCanvas); // Re-instantiate brush
        
        // Manage active state of buttons
        document.querySelectorAll('.toolbar .tool').forEach(t => t.classList.remove('active'));
        const activeToolBtn = document.getElementById(`${tool}Tool`);
        if (activeToolBtn) activeToolBtn.classList.add('active');
        if (tool === 'select') selectTool.classList.add('active');

        thicknessIcon.className = tool === 'pen' ? 'fas fa-pen-nib' : 'fas fa-eraser';
        
        if (tool === TOOLS.PEN) {
            sizeSlider.value = whiteboardState.penSize;
            setColor(whiteboardState.color);
            setSize(whiteboardState.penSize);
        } else if (tool === TOOLS.ERASER) {
            sizeSlider.value = whiteboardState.eraserSize;
            fabricCanvas.freeDrawingBrush.color = '#FFFFFF';
            setSize(whiteboardState.eraserSize);
        }
    }

    function setColor(color) {
        if (!fabricCanvas) return;
        whiteboardState.color = color;
        if (whiteboardState.tool !== TOOLS.PEN) {
            setTool(TOOLS.PEN);
        } else {
            fabricCanvas.freeDrawingBrush.color = color;
        }
    }

    function setSize(size) {
        if (!fabricCanvas) return;
        const currentSize = parseInt(size, 10);
        
        if (whiteboardState.tool === TOOLS.PEN) {
            whiteboardState.penSize = currentSize;
        } else if (whiteboardState.tool === TOOLS.ERASER) {
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
            // Move the question card into the whiteboard container before fullscreen
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
            // We are in fullscreen
            icon.className = 'fas fa-compress';
            questionCard.classList.add('in-fullscreen');
        } else {
            // Exited fullscreen, move card back to its original place
            leftPanel.insertBefore(questionCard, leftPanel.firstChild);
            questionCard.classList.remove('in-fullscreen');
            icon.className = 'fas fa-expand';
        }
    }

    // --- LOGIC FOR NEW TOOLS ---
    const shapePainters = {
        [TOOLS.LINE]: (start, end) => new fabric.Line([start.x, start.y, end.x, end.y], {
            stroke: whiteboardState.color,
            strokeWidth: whiteboardState.penSize,
        }),
        [TOOLS.RECT]: (start, end) => new fabric.Rect({
            left: Math.min(start.x, end.x),
            top: Math.min(start.y, end.y),
            width: Math.abs(end.x - start.x),
            height: Math.abs(end.y - start.y),
            fill: 'transparent',
            stroke: whiteboardState.color,
            strokeWidth: whiteboardState.penSize,
        }),
        [TOOLS.CIRCLE]: (start, end) => {
            const radius = Math.sqrt(Math.pow(end.x - start.x, 2) + Math.pow(end.y - start.y, 2)) / 2;
            return new fabric.Circle({
                left: start.x - radius,
                top: start.y - radius,
                radius: radius,
                fill: 'transparent',
                stroke: whiteboardState.color,
                strokeWidth: whiteboardState.penSize,
            });
        }
    };

    function startDrawingShape(o) {
        if (Object.keys(shapePainters).includes(whiteboardState.tool)) {
            isDrawingShape = true;
            shapeStartPoint = fabricCanvas.getPointer(o.e);
        }
    }

    function continueDrawingShape(o) {
        if (!isDrawingShape || !shapeStartPoint) return;

        const painter = shapePainters[whiteboardState.tool];
        if (!painter) return;

        const pointer = fabricCanvas.getPointer(o.e);
        const tempShape = fabricCanvas.getObjects().find(obj => obj.isTemp);
        if (tempShape) fabricCanvas.remove(tempShape);

        const newShape = painter(shapeStartPoint, pointer);
        if (newShape) {
            newShape.isTemp = true; // Mark as temporary
            fabricCanvas.add(newShape);
            fabricCanvas.renderAll();
        }
    }

    function stopDrawingShape(o) {
        if (isDrawingShape) {
            const tempShape = fabricCanvas.getObjects().find(obj => obj.isTemp);
            if (tempShape) {
                tempShape.isTemp = false;
                fabricCanvas.renderAll();
            }
            isDrawingShape = false;
            shapeStartPoint = null;
        }
    }

    function addText() {
        const text = new fabric.IText('Tapez ici', {
            left: 100,
            top: 100,
            fill: whiteboardState.color,
            fontSize: 20,
        });
        fabricCanvas.add(text); // Add text to canvas
        fabricCanvas.setActiveObject(text);
        setTool(TOOLS.SELECT); // Switch to select mode to edit text
    }

    // --- UNDO/REDO LOGIC ---
    
    function saveState() {
        redoStack = []; // Clear redo stack on new action
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
            console.error("Error saving whiteboard state:", error);
        }
    }

    // ===================================================================
    // ===                    CHAT MANAGEMENT                          ===
    // ===================================================================

    async function sendToTutor() {
        const preparedImage = prepareImageForAI();
        const textComment = textInput.value.trim();
        if (!preparedImage && !textComment) {
            alert("Veuillez dessiner une réponse ou écrire un commentaire.");
            return; // Exit if nothing to send
        }

        // Store the current state before sending and clearing it
        lastSentWhiteboardState = fabricCanvas.toJSON(); // Store for potential restore

        sendBtn.disabled = true;
        let userMessageContent = [];
        if (textComment) userMessageContent.push({ type: 'text', text: textComment });
        if (preparedImage) userMessageContent.push({ type: 'image_url', url: preparedImage });

        chatHistory.push({ role: 'user', content: userMessageContent });
        renderChatHistory();
        displayLoadingIndicator();
        textInput.value = '';
        clearCanvas();

        // Save whiteboard state right after sending
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
            chatHistory.push({ role: 'assistant', content: [{"type": "text", "text": `Sorry, an error occurred.`}] });
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
        if (chatbox.parentElement) chatbox.parentElement.scrollTop = chatbox.parentElement.scrollHeight; // Scroll to bottom
        if (window.MathJax) MathJax.typesetPromise([chatbox]);
    }

    function displayLoadingIndicator() {
        if (!chatbox) return;
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'chat-message tutor loading-indicator';
        loadingDiv.innerHTML = `<span>Le tuteur réfléchit...</span>`;
        chatbox.appendChild(loadingDiv);
        if (chatbox.parentElement) chatbox.parentElement.scrollTop = chatbox.parentElement.scrollHeight;
    }

    // ===================================================================
    // ===               EVENT LISTENERS ATTACHMENT                  ===
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
                    console.error("Error ending session:", error);
                    alert("Une erreur est survenue.");
                }
            });
        }
        if (sendBtn) sendBtn.addEventListener('click', sendToTutor);
        
        if (penTool) penTool.addEventListener('click', () => setTool(TOOLS.PEN));
        if (eraserTool) eraserTool.addEventListener('click', () => setTool(TOOLS.ERASER));
        if (lineTool) lineTool.addEventListener('click', () => setTool(TOOLS.LINE));
        if (rectTool) rectTool.addEventListener('click', () => setTool(TOOLS.RECT));
        if (circleTool) circleTool.addEventListener('click', () => setTool(TOOLS.CIRCLE));
        if (textTool) textTool.addEventListener('click', addText);
        if (selectTool) selectTool.addEventListener('click', () => setTool(TOOLS.SELECT));
        if (undoBtn) undoBtn.addEventListener('click', undo);
        if (redoBtn) redoBtn.addEventListener('click', redo);
        if (restoreLastBtn) restoreLastBtn.addEventListener('click', restoreLastWhiteboard);
        if (colorPicker) colorPicker.addEventListener('input', () => setColor(colorPicker.value));
        if (sizeSlider) sizeSlider.addEventListener('input', () => setSize(sizeSlider.value));
        if (clearCanvasBtn) clearCanvasBtn.addEventListener('click', clearCanvas);
        if (fullscreenBtn) fullscreenBtn.addEventListener('click', toggleFullscreen);
        document.addEventListener('fullscreenchange', handleFullscreenChange);
        document.addEventListener('webkitfullscreenchange', handleFullscreenChange); // For Safari
        
        if (zoomInBtn) zoomInBtn.addEventListener('click', () => updateQuestionZoom(questionZoomLevel + 0.2));
        if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => updateQuestionZoom(questionZoomLevel - 0.2));
        if (zoomResetBtn) zoomResetBtn.addEventListener('click', () => updateQuestionZoom(1));
        
    }
    
    // --- Application Start ---
    initialize();
});
