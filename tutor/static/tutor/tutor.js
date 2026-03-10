document.addEventListener('DOMContentLoaded', () => {

    // --- DOM ELEMENT SELECTION ---
    const questionCard = document.getElementById('questionCard');
    const questionImageDisplay = document.getElementById('questionImageDisplay');
    const endExerciseBtn = document.getElementById('endExerciseBtn');
    const chatbox = document.getElementById('chatbox');
    const textInput = document.getElementById('textInput');
    const sendBtn = document.getElementById('sendBtn');
    const attachPhotoBtn = document.getElementById('attachPhotoBtn');
    const photoInput = document.getElementById('photoInput');
    const photoPreviewContainer = document.getElementById('photoPreviewContainer');
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
    const colorMenuBtn = document.getElementById('colorMenuBtn');
    const colorPalette = document.getElementById('colorPalette');
    const sizeSlider = document.getElementById('sizeSlider');
    const restoreLastBtn = document.getElementById('restoreLastBtn');
    const clearCanvasBtn = document.getElementById('clearCanvasBtn');
    const thicknessIcon = document.getElementById('thickness-icon');
    const fullscreenBtn = document.getElementById('fullscreenBtn');
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const zoomResetBtn = document.getElementById('zoomResetBtn');
    const questionZoomPercent = document.getElementById('questionZoomPercent');
    const whiteboardWorkspace = document.querySelector('.workspace-panel') || document.querySelector('.whiteboard-workspace');
    const lightbox = document.getElementById('imageLightbox');
    const lightboxImg = document.getElementById('lightboxImage');
    const resizeHandle = document.getElementById('resizeHandle');
    const workspacePanel = document.querySelector('.workspace-panel');
    const toggleWhiteboardSizeBtn = document.getElementById('toggleWhiteboardSizeBtn');
    const questionFullscreenBtn = document.getElementById('questionFullscreenBtn');
    
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
    let attachedImage = null;
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
    let isResizingWorkspace = false;
    let lastSplitRatio = 50; // Pourcentage par défaut pour le panneau du haut

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
        setupResizer();
        if (sessionData.ongoing_session) {
            restoreSession().then(() => {
                if (chatHistory.length === 0) {
                    initializeAISession();
                }
            });
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

    async function initializeAISession() {
        displayLoadingIndicator();
        const loadingText = chatbox.querySelector('.loading-indicator span');
        if (loadingText) loadingText.textContent = "L'IA prépare la séance...";

        try {
            const res = await fetch(window.APP_CONFIG.initSessionUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.APP_CONFIG.csrfToken
                }
            });

            removeLoadingIndicator();

            if (!res.ok) throw new Error('Erreur lors de l\'initialisation');

            const data = await res.json();
            if (data.initial_history && data.initial_history.length > 0) {
                data.initial_history.forEach(msg => {
                    chatHistory.push(msg);
                    appendMessage(msg);
                });
            }
        } catch (error) {
            console.error("Error initializing session:", error);
            removeLoadingIndicator();
            const errorMsg = { role: 'assistant', content: [{"type": "text", "text": "Une erreur est survenue lors du démarrage. Veuillez rafraîchir la page."}] };
            chatHistory.push(errorMsg);
            appendMessage(errorMsg);
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
    // ===             WORKSPACE RESIZING LOGIC                      ===
    // ===================================================================

    function setupResizer() {
        if (!resizeHandle || !workspacePanel || !questionCard || !document.getElementById('whiteboardContainer')) return;

        const whiteboardContainer = document.getElementById('whiteboardContainer');

        // --- Mouse Events ---
        resizeHandle.addEventListener('mousedown', (e) => {
            e.preventDefault(); // Empêche la sélection de texte
            isResizingWorkspace = true;
            resizeHandle.classList.add('active');
            document.body.style.cursor = 'row-resize';
            
            // Désactiver temporairement les événements de souris sur le canvas et les iframes pour fluidifier le drag
            whiteboardContainer.style.pointerEvents = 'none';
        });

        window.addEventListener('mousemove', (e) => {
            if (!isResizingWorkspace) return;

            const containerRect = workspacePanel.getBoundingClientRect();
            // Calculer la position relative de la souris dans le conteneur
            let relativeY = e.clientY - containerRect.top;
            
            // Convertir en pourcentage
            let percentage = (relativeY / containerRect.height) * 100;

            // Limites (min 0% pour cacher la question, max 90% pour garder un peu de whiteboard)
            percentage = Math.max(0, Math.min(90, percentage));

            applySplitRatio(percentage);
        });

        window.addEventListener('mouseup', () => {
            if (isResizingWorkspace) {
                isResizingWorkspace = false;
                resizeHandle.classList.remove('active');
                document.body.style.cursor = '';
                whiteboardContainer.style.pointerEvents = ''; // Réactiver les événements
                resizeCanvas(); // Ajustement final propre
            }
        });

        // --- Touch Events (iPad/Mobile) ---
        resizeHandle.addEventListener('touchstart', (e) => {
            e.preventDefault(); // Empêche le scroll/zoom natif
            isResizingWorkspace = true;
            resizeHandle.classList.add('active');
            whiteboardContainer.style.pointerEvents = 'none';
        }, { passive: false });

        window.addEventListener('touchmove', (e) => {
            if (!isResizingWorkspace) return;
            if (e.cancelable) e.preventDefault(); // Empêche le scroll de la page

            const containerRect = workspacePanel.getBoundingClientRect();
            const touch = e.touches[0];
            let relativeY = touch.clientY - containerRect.top;
            
            let percentage = (relativeY / containerRect.height) * 100;
            percentage = Math.max(0, Math.min(90, percentage));

            applySplitRatio(percentage);
        }, { passive: false });

        window.addEventListener('touchend', () => {
            if (isResizingWorkspace) {
                isResizingWorkspace = false;
                resizeHandle.classList.remove('active');
                whiteboardContainer.style.pointerEvents = '';
                resizeCanvas();
            }
        });
    }

    function applySplitRatio(percentage) {
        if (!questionCard || !document.getElementById('whiteboardContainer')) return;
        
        lastSplitRatio = percentage;
        
        // Utiliser flex-basis pour un redimensionnement fluide
        questionCard.style.flex = `0 0 ${percentage}%`;
        // Le whiteboard prend le reste
        document.getElementById('whiteboardContainer').style.flex = `1 1 ${100 - percentage}%`;
        
        // Important : Redimensionner le canvas FabricJS car la div a changé de taille
        resizeCanvas();
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
        
        if (colorMenuBtn) {
            colorMenuBtn.style.backgroundColor = whiteboardState.color;
        }
        if (sizeSlider) {
            sizeSlider.value = whiteboardState.penSize;
        }
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
            if (!opt.e) return;
            const evt = opt.e;
            // Only apply palm rejection logic if we are in a drawing mode (Pen or Eraser)
            if (whiteboardState.tool === TOOLS.PEN || whiteboardState.tool === TOOLS.ERASER) {
                if (evt.pointerType === 'touch') {
                    // Disable drawing for touch (finger/palm)
                    fabricCanvas.isDrawingMode = false;
                } else if (evt.pointerType === 'pen' || evt.pointerType === 'mouse') {
                    // Enable drawing for pen or mouse (desktop)
                    // This ensures that if the palm disabled it, the pen re-enables it immediately
                    fabricCanvas.isDrawingMode = true;
                }
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
        document.querySelectorAll('.toolbar .tool-btn').forEach(t => t.classList.remove('active')); // Support new class
        const activeToolBtn = document.getElementById(`${tool}Tool`);
        if (activeToolBtn) activeToolBtn.classList.add('active');
        if (tool === 'select') selectTool.classList.add('active');

        if (!thicknessIcon) return;
        thicknessIcon.className = tool === 'pen' ? 'fas fa-pen-nib' : 'fas fa-eraser';
        
        if (tool === TOOLS.PEN) {
            if (sizeSlider) sizeSlider.value = whiteboardState.penSize;
            setColor(whiteboardState.color);
            setSize(whiteboardState.penSize);
        } else if (tool === TOOLS.ERASER) {
            if (sizeSlider) sizeSlider.value = whiteboardState.eraserSize;
            fabricCanvas.freeDrawingBrush.color = '#FFFFFF';
            setSize(whiteboardState.eraserSize);
        }
    }

    function setColor(color) {
        if (!fabricCanvas) return;
        whiteboardState.color = color;
        if (colorMenuBtn) {
            colorMenuBtn.style.backgroundColor = color;
        }
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
    
    function toggleFullscreen(element) {
        if (!document.fullscreenElement) {
            if (element.requestFullscreen) {
                element.requestFullscreen();
            } else if (element.webkitRequestFullscreen) { /* Safari */
                element.webkitRequestFullscreen();
            }
            
            // Si on met tout le workspace en plein écran, on réapplique le ratio
            if (element === whiteboardWorkspace) {
                setTimeout(() => {
                    applySplitRatio(lastSplitRatio);
                }, 100);
            }
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            }
        }
    }
    
    function handleFullscreenChange() {
        // Gestion icône Workspace (Brouillon + Question)
        if (fullscreenBtn) {
            const icon = fullscreenBtn.querySelector('i');
            if (document.fullscreenElement === whiteboardWorkspace) {
                icon.className = 'fas fa-compress';
            } else {
                icon.className = 'fas fa-expand';
            }
        }
        // Gestion icône Question seule
        if (questionFullscreenBtn) {
            const icon = questionFullscreenBtn.querySelector('i');
            if (document.fullscreenElement === questionCard) {
                icon.className = 'fas fa-compress';
            } else {
                icon.className = 'fas fa-expand';
            }
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
        if (!preparedImage && !textComment && !attachedImage) {
            alert("Veuillez dessiner une réponse, écrire un commentaire ou joindre une photo.");
            return; // Exit if nothing to send
        }

        // Store the current state before sending and clearing it
        lastSentWhiteboardState = fabricCanvas.toJSON(); // Store for potential restore

        sendBtn.disabled = true;
        let userMessageContent = [];
        if (textComment) userMessageContent.push({ type: 'text', text: textComment });
        if (preparedImage) userMessageContent.push({ 
            type: 'image_url', 
            url: preparedImage,
            whiteboard_state: fabricCanvas.toJSON() // Sauvegarde l'état pour restauration future
        });
        if (attachedImage) userMessageContent.push({ type: 'image_url', url: attachedImage });

        const userMsg = { role: 'user', content: userMessageContent };
        chatHistory.push(userMsg);
        appendMessage(userMsg);
        displayLoadingIndicator();
        textInput.value = '';
        clearCanvas();

        // Clear attached image
        attachedImage = null;
        if (photoInput) photoInput.value = '';
        if (photoPreviewContainer) photoPreviewContainer.innerHTML = '';

        // Save whiteboard state right after sending (Non-blocking)
        saveWhiteboardState();

        try {
            const res = await fetch(window.APP_CONFIG.tutorInteractUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": window.APP_CONFIG.csrfToken },
                body: JSON.stringify({ messages: chatHistory })
            });
            
            removeLoadingIndicator();

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(`Erreur API: ${errorData.error || res.statusText}`);
            }
            const replyData = await res.json();
            const aiMsg = { role: 'assistant', content: replyData.content };
            chatHistory.push(aiMsg);
            appendMessage(aiMsg);
        } catch (err) {
            console.error(err);
            removeLoadingIndicator();
            const errorMsg = { role: 'assistant', content: [{"type": "text", "text": `Désolé, une erreur est survenue.`}] };
            chatHistory.push(errorMsg);
            appendMessage(errorMsg);
        } finally {
            sendBtn.disabled = false;
        }
    }
    
    function createMessageElement(msg) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${msg.role === 'assistant' ? 'tutor' : 'user'}`;
        
        if (Array.isArray(msg.content)) {
            msg.content.forEach(item => {
                if (item.type === 'text') {
                    const textDiv = document.createElement('div');
                    textDiv.className = 'comment-text';
                    textDiv.style.whiteSpace = 'pre-wrap';
                    textDiv.textContent = item.text;
                    messageDiv.appendChild(textDiv);
                }
                if (item.type === 'image_url') {
                    const imgUrl = item.url || (item.image_url ? item.image_url.url : '');
                    
                    if (item.whiteboard_state) {
                        // Création du wrapper pour l'image et le bouton de restauration
                        const wrapper = document.createElement('div');
                        wrapper.className = 'whiteboard-wrapper';
                        
                        const img = document.createElement('img');
                        img.src = imgUrl;
                        img.alt = "Image";
                        img.className = "chat-image";
                        
                        const btn = document.createElement('button');
                        btn.className = 'restore-whiteboard-btn';
                        btn.title = "Reprendre ce brouillon";
                        btn.innerHTML = '<i class="fas fa-pen"></i>';
                        btn.onclick = (e) => {
                            e.stopPropagation(); // Empêche l'ouverture de la lightbox
                            if (confirm("Voulez-vous remplacer votre brouillon actuel par celui-ci ?")) {
                                fabricCanvas.loadFromJSON(item.whiteboard_state, fabricCanvas.renderAll.bind(fabricCanvas));
                            }
                        };
                        
                        wrapper.appendChild(img);
                        wrapper.appendChild(btn);
                        messageDiv.appendChild(wrapper);
                    } else {
                        const img = document.createElement('img');
                        img.src = imgUrl;
                        img.alt = "Image";
                        img.className = "chat-image";
                        messageDiv.appendChild(img);
                    }
                }
            });
        } else {
            messageDiv.innerHTML = msg.content;
        }
        return messageDiv;
    }

    function appendMessage(msg) {
        if (!chatbox) return;
        const messageDiv = createMessageElement(msg);
        chatbox.appendChild(messageDiv);
        if (chatbox.parentElement) chatbox.parentElement.scrollTop = chatbox.parentElement.scrollHeight;
        if (window.MathJax) MathJax.typesetPromise([messageDiv]);
    }

    function renderChatHistory() {
        if (!chatbox) return;
        chatbox.innerHTML = '';
        chatHistory.forEach(msg => chatbox.appendChild(createMessageElement(msg)));
        if (chatbox.parentElement) chatbox.parentElement.scrollTop = chatbox.parentElement.scrollHeight; // Scroll to bottom
        if (window.MathJax) MathJax.typesetPromise([chatbox]);
    }

    function displayLoadingIndicator() {
        if (!chatbox) return;
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'chat-message tutor loading-indicator';
        loadingDiv.innerHTML = `<div class="spinner"></div><span>Le tuteur réfléchit...</span>`;
        chatbox.appendChild(loadingDiv);
        if (chatbox.parentElement) chatbox.parentElement.scrollTop = chatbox.parentElement.scrollHeight;
    }

    function removeLoadingIndicator() {
        if (!chatbox) return;
        const loadingDiv = chatbox.querySelector('.loading-indicator');
        if (loadingDiv) loadingDiv.remove();
    }

    // --- SOLUTION MODAL ---
    function showSolutionModal(solutionText) {
        // Create modal elements dynamically
        const modalOverlay = document.createElement('div');
        modalOverlay.style.cssText = 'position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:10000; display:flex; justify-content:center; align-items:center;';
        
        const modalContent = document.createElement('div');
        modalContent.style.cssText = 'background:white; padding:2rem; border-radius:12px; max-width:600px; width:90%; max-height:80vh; overflow-y:auto; box-shadow:0 5px 15px rgba(0,0,0,0.3); position:relative;';
        
        const closeBtn = document.createElement('button');
        closeBtn.innerHTML = '&times;';
        closeBtn.style.cssText = 'position:absolute; top:10px; right:15px; background:none; border:none; font-size:1.5rem; cursor:pointer; color:#666;';
        closeBtn.onclick = () => document.body.removeChild(modalOverlay);
        
        const title = document.createElement('h2');
        title.innerText = 'Correction de l\'exercice';
        title.style.cssText = 'margin-top:0; color:#2c3e50; border-bottom:2px solid #3498db; padding-bottom:0.5rem; margin-bottom:1rem;';
        
        const contentDiv = document.createElement('div');
        // Simple formatting for line breaks
        contentDiv.innerHTML = solutionText.replace(/\n/g, '<br>');
        contentDiv.style.cssText = 'line-height:1.6; color:#34495e; font-size:1rem;';
        
        modalContent.appendChild(closeBtn);
        modalContent.appendChild(title);
        modalContent.appendChild(contentDiv);
        modalOverlay.appendChild(modalContent);
        
        // Close on click outside
        modalOverlay.onclick = (e) => {
            if (e.target === modalOverlay) document.body.removeChild(modalOverlay);
        };
        
        document.body.appendChild(modalOverlay);
        
        // Render MathJax if available
        if (window.MathJax) {
            MathJax.typesetPromise([contentDiv]);
        }
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

            // --- INJECT "SEE SOLUTION" BUTTON ---
            const showSolutionBtn = document.createElement('button');
            showSolutionBtn.id = 'showSolutionBtn';
            showSolutionBtn.innerHTML = '<i class="fas fa-key"></i>';
            showSolutionBtn.title = "Voir la correction";
            // Style similar to other action buttons but distinct
            showSolutionBtn.style.cssText = `
                width: 36px;
                height: 36px;
                background-color: #fff9c4;
                color: #fbc02d;
                border: none;
                border-radius: 50%;
                cursor: pointer;
                display: flex; align-items: center; justify-content: center;
                transition: all 0.2s;
                font-size: 1rem;
            `;
            showSolutionBtn.onmouseover = () => { showSolutionBtn.style.transform = 'scale(1.1)'; showSolutionBtn.style.backgroundColor = '#fff59d'; };
            showSolutionBtn.onmouseout = () => { showSolutionBtn.style.transform = 'scale(1)'; showSolutionBtn.style.backgroundColor = '#fff9c4'; };
            
            showSolutionBtn.addEventListener('click', fetchAndShowSolution);
            
            // Insert before the end button to keep them grouped
            endExerciseBtn.parentNode.insertBefore(showSolutionBtn, endExerciseBtn);
        }
        if (sendBtn) sendBtn.addEventListener('click', sendToTutor);
        
        if (attachPhotoBtn && photoInput) {
            attachPhotoBtn.addEventListener('click', () => photoInput.click());
            photoInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (!file) return;
                
                const reader = new FileReader();
                reader.onload = (event) => {
                    attachedImage = event.target.result;
                    if (photoPreviewContainer) {
                        photoPreviewContainer.innerHTML = `
                            <div style="position: relative; display: inline-block; margin-bottom: 10px;">
                                <img src="${attachedImage}" style="max-height: 100px; border-radius: 8px; border: 1px solid #ddd;">
                                <button id="removePhotoBtn" style="position: absolute; top: -8px; right: -8px; background: #ff4444; color: white; border: none; border-radius: 50%; width: 24px; height: 24px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-weight: bold;">&times;</button>
                            </div>`;
                        document.getElementById('removePhotoBtn').addEventListener('click', () => {
                            attachedImage = null;
                            photoInput.value = '';
                            photoPreviewContainer.innerHTML = '';
                        });
                    }
                };
                reader.readAsDataURL(file);
            });
        }

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
        
        // Nouvelle logique pour le sélecteur de couleur personnalisé
        if (colorMenuBtn && colorPalette) {
            colorMenuBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const isVisible = colorPalette.style.display === 'grid';
                colorPalette.style.display = isVisible ? 'none' : 'grid';
            });
            
            document.querySelectorAll('.color-swatch').forEach(swatch => {
                swatch.addEventListener('click', (e) => {
                    e.stopPropagation();
                    setColor(e.target.dataset.color);
                    colorPalette.style.display = 'none';
                });
            });
            
            // Fermer la palette si on clique ailleurs
            document.addEventListener('click', () => colorPalette.style.display = 'none');
        }

        if (sizeSlider) sizeSlider.addEventListener('input', () => setSize(sizeSlider.value));
        if (clearCanvasBtn) clearCanvasBtn.addEventListener('click', clearCanvas);
        if (fullscreenBtn) fullscreenBtn.addEventListener('click', () => toggleFullscreen(whiteboardWorkspace));
        if (questionFullscreenBtn) questionFullscreenBtn.addEventListener('click', () => toggleFullscreen(questionCard));
        document.addEventListener('fullscreenchange', handleFullscreenChange);
        document.addEventListener('webkitfullscreenchange', handleFullscreenChange); // For Safari
        
        if (zoomInBtn) zoomInBtn.addEventListener('click', () => updateQuestionZoom(questionZoomLevel + 0.2));
        if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => updateQuestionZoom(questionZoomLevel - 0.2));
        if (zoomResetBtn) zoomResetBtn.addEventListener('click', () => updateQuestionZoom(1));
        
        // Lightbox events
        if (chatbox) {
            chatbox.addEventListener('click', (e) => {
                if (e.target.tagName === 'IMG' && e.target.classList.contains('chat-image')) {
                    if (lightbox && lightboxImg) {
                        lightboxImg.src = e.target.src;
                        lightbox.classList.add('active');
                    }
                }
            });
        }
        if (lightbox) {
            lightbox.addEventListener('click', () => lightbox.classList.remove('active'));
        }

        // Logic for Expand/Reduce Whiteboard Button
        if (toggleWhiteboardSizeBtn) {
            toggleWhiteboardSizeBtn.addEventListener('click', () => {
                // Si la question prend moins de 10%, c'est que le whiteboard est déjà agrandi (Max)
                const isExpanded = lastSplitRatio < 10;
                
                if (isExpanded) {
                    applySplitRatio(75); // Réduire : Question 75%, Whiteboard 25% (Min)
                    toggleWhiteboardSizeBtn.innerHTML = '<i class="fas fa-chevron-up"></i> Agrandir';
                } else {
                    applySplitRatio(5); // Agrandir : Question 5%, Whiteboard 95% (Max)
                    toggleWhiteboardSizeBtn.innerHTML = '<i class="fas fa-chevron-down"></i> Réduire';
                }
            });
        }
    }
    
    async function fetchAndShowSolution() {
        if (!confirm("Es-tu sûr de vouloir voir la correction ? Cela peut réduire l'intérêt de l'exercice.")) return;
        
        try {
            const res = await fetch('/tutor/api/get-solution/');
            if (!res.ok) throw new Error('Erreur réseau');
            const data = await res.json();
            showSolutionModal(data.solution);
        } catch (error) {
            console.error("Error fetching solution:", error);
            alert("Impossible de récupérer la correction pour le moment.");
        }
    }

    // --- Application Start ---
    initialize();
});
