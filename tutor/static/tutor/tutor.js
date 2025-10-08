// --- Éléments d'interface ---
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

// --- Éléments du tableau blanc (Whiteboard) ---
const canvas = document.getElementById('whiteboard');
const ctx = canvas ? canvas.getContext('2d', { willReadFrequently: true }) : null;
const scrollContainer = document.getElementById('scrollContainer');
const whiteboardContainer = document.getElementById('whiteboardContainer');
const whiteboardWorkspace = document.querySelector('.whiteboard-workspace');
const zoomPercentEl = document.getElementById('zoomPercent');

// Éléments de zoom/pan pour l'image de la question
const zoomInBtn = document.getElementById('zoomInBtn');
const zoomOutBtn = document.getElementById('zoomOutBtn');
const zoomResetBtn = document.getElementById('zoomResetBtn');
const questionZoomPercent = document.getElementById('questionZoomPercent');
const questionImageContainer = document.getElementById('questionImageContainer');
const pdfNavControls = document.getElementById('pdfNavControls');
const prevPageBtn = document.getElementById('prevPageBtn');
const nextPageBtn = document.getElementById('nextPageBtn');
const pageIndicator = document.getElementById('pageIndicator');
const startOnPageBtn = document.getElementById('startOnPageBtn');

// --- Variables d'état ---
let chatHistory = [];
let uploadedImage = null;

// Variables pour le tableau blanc
let isDrawing = false;
let currentTool = 'pen';
let strokes = []; // Stocke tous les tracés terminés
let currentPoints = []; // Le tracé en cours de dessin
let whiteboardZoomLevel = 1;

// Variables pour la navigation PDF
let currentPdf = null;
let currentPageNum = 1;
let totalPages = 1;

// Variables pour le zoom/pan de l'image de la question
let questionZoomLevel = 1;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 3;
let isPanning = false;
let panStartX, panStartY, startScrollLeft, startScrollTop;


// Configuration de PDF.js
if (typeof pdfjsLib !== 'undefined') {
    pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.11.338/pdf.worker.min.js`;
}

// --- Récupération des données de session depuis le HTML ---
const sessionDataElement = document.getElementById('session-data');
let ongoing_session, initial_chat_history, exercise_document;

if (sessionDataElement) {
    const sessionData = JSON.parse(sessionDataElement.textContent);
    ongoing_session = sessionData.ongoing_session;
    initial_chat_history = sessionData.initial_chat_history;
    exercise_document = sessionData.exercise_document;
}

// === INITIALISATION DE LA PAGE ===

window.addEventListener('load', () => {
    if (ongoing_session) {
        console.log("Reprise d'une session en cours...");
        restoreSession();
    } else {
        console.log("Démarrage d'une nouvelle session.");
    }
    if (canvas) {
      resizeCanvas();
      setTool('pen'); // Initialise l'outil
    }
});

async function restoreSession() {
    if (initial_chat_history) {
        chatHistory = initial_chat_history;
        renderChatHistory();
    }
    if (exercise_document) {
        const documentUrl = exercise_document.url;
        if (documentUrl.toLowerCase().endsWith('.pdf')) {
            await loadPdfAsImage(documentUrl);
        } else {
            uploadedImage = documentUrl;
            if(questionImageDisplay) questionImageDisplay.src = uploadedImage;
        }
        if(sendBtn) sendBtn.disabled = false;
        if(hintBtn) hintBtn.disabled = false;
    }
}

// === GESTION DE L'INTERFACE ET DU DÉMARRAGE ===

if (documentSelector) {
    documentSelector.addEventListener('change', (e) => {
        if(startExerciseBtn) startExerciseBtn.disabled = !e.target.value;
    });
}
if (startExerciseBtn) {
    startExerciseBtn.addEventListener('click', startExercise);
}

if (changeExerciseBtn) {
    changeExerciseBtn.addEventListener('click', () => {
        window.location.reload();
    });
}

if (endExerciseBtn) {
    endExerciseBtn.addEventListener('click', async () => {
        if (!confirm("Es-tu sûr de vouloir terminer cet exercice ?")) {
            return;
        }
        try {
            const res = await fetch(endSessionUrl, {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken}
            });
            if (!res.ok) throw new Error('La réponse du serveur n\'était pas OK');
            const data = await res.json();
            window.location.href = data.redirect_url;
        } catch (error) {
            console.error("Erreur lors de la fin de session:", error);
            alert("Une erreur est survenue. Impossible de terminer la session correctement.");
        }
    });
}

if (prevPageBtn) {
    prevPageBtn.addEventListener('click', () => {
        if (currentPageNum > 1) {
            currentPageNum--;
            renderPdfPage(currentPageNum);
        }
    });
}

if (nextPageBtn) {
    nextPageBtn.addEventListener('click', () => {
        if (currentPageNum < totalPages) {
            currentPageNum++;
            renderPdfPage(currentPageNum);
        }
    });
}

async function analyzeAndSwitchView() {
    await analyzeQuestionImage();
    if(welcomeScreen) welcomeScreen.classList.add('hidden');
    if(workspace) workspace.classList.remove('hidden');
    resizeCanvas();
}

async function startExercise() {
    if (!documentSelector) return;
    const documentUrl = documentSelector.value;
    if (!documentUrl) return;

    if(startExerciseBtn) {
        startExerciseBtn.innerHTML = `<div class="spinner"></div>`;
        startExerciseBtn.disabled = true;
    }

    try {
        if (documentUrl.toLowerCase().endsWith('.pdf')) {
            await loadPdfAsImage(documentUrl);
            if (totalPages === 1) {
                await analyzeAndSwitchView();
            }
        } else {
            uploadedImage = documentUrl;
            if(questionImageDisplay) questionImageDisplay.src = uploadedImage;
            updateQuestionZoom(1);
            await analyzeAndSwitchView();
        }
        
    } catch (error) {
        console.error("Erreur détaillée lors du chargement du document:", error);
        alert("Une erreur est survenue lors du chargement du document.");
        if(startExerciseBtn) {
            startExerciseBtn.innerHTML = `<i class="fas fa-play"></i> Commencer`;
            startExerciseBtn.disabled = documentSelector.value === "";
        }
    }
}

async function loadPdfAsImage(pdfUrl) {
    const loadingTask = pdfjsLib.getDocument(pdfUrl);
    currentPdf = await loadingTask.promise;
    totalPages = currentPdf.numPages;
    currentPageNum = 1;
    if (totalPages > 1) {
        if(pdfNavControls) pdfNavControls.classList.remove('hidden');
        if(startOnPageBtn) startOnPageBtn.classList.remove('hidden');
    }
    await renderPdfPage(1);
}

async function renderPdfPage(pageNum) {
    if (!currentPdf) return;
    
    if(pageIndicator) pageIndicator.textContent = `Page ${pageNum} / ${totalPages}`;
    if(prevPageBtn) prevPageBtn.disabled = pageNum <= 1;
    if(nextPageBtn) nextPageBtn.disabled = pageNum >= totalPages;
    
    const page = await currentPdf.getPage(pageNum);
    const viewport = page.getViewport({ scale: 2.0 });
    
    const tempCanvas = document.createElement('canvas');
    tempCanvas.height = viewport.height;
    tempCanvas.width = viewport.width;
    const renderContext = {
        canvasContext: tempCanvas.getContext('2d'),
        viewport: viewport
    };
    await page.render(renderContext).promise;
    
    uploadedImage = tempCanvas.toDataURL('image/png');
    if (questionImageDisplay) questionImageDisplay.src = uploadedImage;
    
    if(startOnPageBtn) {
        startOnPageBtn.onclick = async () => {
            startOnPageBtn.innerHTML = `<div class="spinner"></div>`;
            startOnPageBtn.disabled = true;
            await analyzeAndSwitchView();
        };
    }
}

async function analyzeQuestionImage() {
    if (!documentSelector || !uploadedImage) return;
    const documentUrl = documentSelector.value;
    const imageBase64 = uploadedImage.split(',')[1];
    try {
        const res = await fetch(analyzeImageUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
            body: JSON.stringify({ image: imageBase64, document_url: documentUrl })
        });
        if (!res.ok) throw new Error(`Erreur API: ${res.status}`);
        const data = await res.json();
        chatHistory = data.initial_history;
        renderChatHistory();
        if(sendBtn) sendBtn.disabled = false;
        if(hintBtn) hintBtn.disabled = false;
    } catch (err) {
        console.error(err);
        if(chatbox) chatbox.innerHTML = `<div class="chat-message tutor" style="background-color: var(--accent-color); color: white;">Erreur lors de l'analyse de l'image: ${err.message}</div>`;
    }
}

// === GESTION DU ZOOM ET PAN DE L'IMAGE DE LA QUESTION ===

function updateQuestionZoom(newZoom) {
    questionZoomLevel = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, newZoom));
    if(questionImageDisplay) questionImageDisplay.style.transform = `scale(${questionZoomLevel})`;
    if(questionZoomPercent) questionZoomPercent.textContent = `${Math.round(questionZoomLevel * 100)}%`;
    if(zoomOutBtn) zoomOutBtn.disabled = questionZoomLevel <= MIN_ZOOM;
    if(zoomInBtn) zoomInBtn.disabled = questionZoomLevel >= MAX_ZOOM;
}

if (zoomInBtn) zoomInBtn.addEventListener('click', () => updateQuestionZoom(questionZoomLevel + 0.2));
if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => updateQuestionZoom(questionZoomLevel - 0.2));
if (zoomResetBtn) zoomResetBtn.addEventListener('click', () => updateQuestionZoom(1));

if (questionImageContainer) {
    questionImageContainer.addEventListener('mousedown', (e) => {
        isPanning = true;
        panStartX = e.pageX - questionImageContainer.offsetLeft;
        panStartY = e.pageY - questionImageContainer.offsetTop;
        startScrollLeft = questionImageContainer.scrollLeft;
        startScrollTop = questionImageContainer.scrollTop;
        questionImageContainer.style.cursor = 'grabbing';
    });
    questionImageContainer.addEventListener('mouseleave', () => { isPanning = false; questionImageContainer.style.cursor = 'grab'; });
    questionImageContainer.addEventListener('mouseup', () => { isPanning = false; questionImageContainer.style.cursor = 'grab'; });
    questionImageContainer.addEventListener('mousemove', (e) => {
        if (!isPanning) return;
        e.preventDefault();
        const x = e.pageX - questionImageContainer.offsetLeft;
        const y = e.pageY - questionImageContainer.offsetTop;
        const walkX = (x - panStartX);
        const walkY = (y - panStartY);
        questionImageContainer.scrollLeft = startScrollLeft - walkX;
        questionImageContainer.scrollTop = startScrollTop - walkY;
    });
}

// === GESTION DU CHAT ===

function renderChatHistory() {
    if (!chatbox) return;
    chatbox.innerHTML = '';
    chatHistory.forEach(msg => {
        const messageDiv = document.createElement('div');
        if (msg.role === 'assistant') {
            messageDiv.className = 'chat-message tutor';
            messageDiv.innerHTML = msg.content;
        } else {
            messageDiv.className = 'chat-message user';
            let contentHTML = '';
            if (Array.isArray(msg.content)) {
                msg.content.forEach(item => {
                    if (item.type === 'text' && item.text) {
                        contentHTML += `<div class="comment-text">${item.text}</div>`;
                    }
                    if (item.type === 'image_url') {
                        contentHTML += `<img src="${item.image_url.url}" alt="Réponse de l'élève">`;
                    }
                });
            }
            messageDiv.innerHTML = contentHTML;
        }
        chatbox.appendChild(messageDiv);
    });
    if(chatbox.parentElement) chatbox.parentElement.scrollTop = chatbox.parentElement.scrollHeight;
    if (window.MathJax) {
        MathJax.typesetPromise([chatbox]);
    }
}

function displayLoadingIndicator() {
    if (!chatbox) return;
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'chat-message tutor';
    loadingDiv.innerHTML = `<div class="loading"><div class="spinner"></div><span>Le tuteur réfléchit...</span></div>`;
    chatbox.appendChild(loadingDiv);
    if (chatbox.parentElement) chatbox.parentElement.scrollTop = chatbox.parentElement.scrollHeight;
}

async function sendToTutor() {
    const preparedImage = await prepareImageForAI();
    const textComment = textInput ? textInput.value.trim() : "";

    if (!preparedImage && !textComment) {
        alert("Veuillez dessiner une réponse ou écrire un commentaire.");
        return;
    }

    if(sendBtn) sendBtn.disabled = true;
    if(hintBtn) hintBtn.disabled = true;
    let userMessageContent = [];

    if (textComment) userMessageContent.push({ type: 'text', text: textComment });
    if (preparedImage) userMessageContent.push({ type: 'image_url', image_url: { url: preparedImage } });

    chatHistory.push({ role: 'user', content: userMessageContent });
    renderChatHistory();
    displayLoadingIndicator();
    
    if(textInput) textInput.value = '';
    clearCanvas();

    try {
        const res = await fetch(tutorInteractUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
            body: JSON.stringify({ messages: chatHistory })
        });
        if (!res.ok) throw new Error(`Erreur API: ${res.statusText}`);
        const replyData = await res.json();
        chatHistory.push({ role: 'assistant', content: replyData.content });
        renderChatHistory();
    } catch (err) {
        console.error(err);
        chatHistory.push({ role: 'assistant', content: `Désolé, une erreur est survenue: ${err.message}` });
        renderChatHistory();
    } finally {
        if(sendBtn) sendBtn.disabled = false;
        if(hintBtn) hintBtn.disabled = false;
    }
}

if (hintBtn) {
    hintBtn.addEventListener('click', async () => {
        hintBtn.disabled = true;
        if(sendBtn) sendBtn.disabled = true;
        displayLoadingIndicator();
        try {
            const res = await fetch(getHintUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({ messages: chatHistory })
            });
            if (!res.ok) throw new Error(`Erreur API: ${res.statusText}`);
            const hintData = await res.json();
            chatHistory.push({ role: 'assistant', content: hintData.content });
            renderChatHistory();
        } catch (err) {
            console.error("Erreur lors de la demande d'indice:", err);
            chatHistory.push({ role: 'assistant', content: `Désolé, une erreur est survenue lors de la génération de l'indice: ${err.message}` });
            renderChatHistory();
        } finally {
            if (chatbox) {
                const lastMessage = chatbox.lastElementChild;
                if (lastMessage && lastMessage.querySelector('.loading')) {
                    lastMessage.remove();
                }
            }
            hintBtn.disabled = false;
            if(sendBtn) sendBtn.disabled = false;
        }
    });
}

function prepareImageForAI() {
    return new Promise((resolve) => {
        if (strokes.length === 0 || !canvas) {
            resolve(null);
            return;
        }
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = canvas.width;
        tempCanvas.height = canvas.height;
        const tempCtx = tempCanvas.getContext('2d');
        
        tempCtx.fillStyle = 'white';
        tempCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
        
        redrawAllStrokes(tempCtx);

        resolve(tempCanvas.toDataURL('image/png'));
    });
}


// === GESTION DU TABLEAU BLANC (WHITEBOARD) AVEC PERFECT-FREEHAND ===

// --- Fonctions utilitaires pour le dessin ---

/**
 * Récupère les options de dessin actuelles depuis l'interface.
 * @returns {object} Options pour perfect-freehand.
 */
function getStrokeOptions() {
    const sizeEl = document.getElementById('size');
    const size = sizeEl ? parseInt(sizeEl.value, 10) : 5;

    return {
        size: currentTool === 'eraser' ? size * 2 : size,
        thinning: 0.6,
        smoothing: 0.5,
        streamline: 0.5,
        start: { taper: 0, cap: true },
        end: { taper: 0, cap: true },
    };
}

/**
 * Dessine un seul tracé (stroke) sur le contexte de canvas fourni.
 * @param {CanvasRenderingContext2D} context - Le contexte sur lequel dessiner.
 * @param {object} stroke - L'objet de tracé contenant les points et les options.
 */
function drawStroke(context, stroke) {
    const strokePoints = PerfectFreehand.getStroke(stroke.points, stroke.options);
    if (!strokePoints.length) {
        return;
    }

    context.beginPath();
    context.moveTo(strokePoints[0][0], strokePoints[0][1]);
    for (let i = 1; i < strokePoints.length; i++) {
        context.lineTo(strokePoints[i][0], strokePoints[i][1]);
    }
    
    context.fillStyle = stroke.isEraser ? 'white' : stroke.color;
    context.globalCompositeOperation = stroke.isEraser ? 'destination-out' : 'source-over';
    
    context.fill();
    context.closePath();
    
    // Rétablit l'opération par défaut
    context.globalCompositeOperation = 'source-over';
}

/**
 * Redessine tous les tracés stockés.
 * @param {CanvasRenderingContext2D} context - Le contexte sur lequel dessiner.
 */
function redrawAllStrokes(context = ctx) {
    if (!context) return;
    context.clearRect(0, 0, context.canvas.width, context.canvas.height);
    context.fillStyle = 'white';
    context.fillRect(0, 0, context.canvas.width, context.canvas.height);
    
    strokes.forEach(stroke => drawStroke(context, stroke));
}


// --- Fonctions de gestion du canvas ---

window.addEventListener('resize', () => resizeCanvas());

function resizeCanvas() {
    if (!canvas || !scrollContainer || !workspace || workspace.classList.contains('hidden')) return;
    const containerRect = scrollContainer.getBoundingClientRect();
    canvas.width = containerRect.width;
    canvas.height = containerRect.height;
    redrawAllStrokes();
    applyWhiteboardZoom();
}

function clearCanvas() {
    if (!ctx || !canvas) return;
    strokes = [];
    currentPoints = [];
    redrawAllStrokes();
}

function setTool(tool) {
    if (!document.getElementById('penTool')) return;
    currentTool = tool;
    document.getElementById('penTool').classList.toggle('active', tool === 'pen');
    document.getElementById('eraserTool').classList.toggle('active', tool === 'eraser');
    if (canvas) canvas.style.cursor = tool === 'pen' ? 'crosshair' : 'cell';
}

function getPointerPosition(e) {
    if (!canvas) return { x: 0, y: 0, pressure: 0.5 };
    const rect = canvas.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    // La pression est disponible sur les événements de pointeur pour les stylets
    const pressure = e.pressure !== undefined ? e.pressure : 0.5;
    
    return {
        x: clientX - rect.left,
        y: clientY - rect.top,
        pressure: pressure
    };
}


// --- Fonctions de gestion des événements de dessin ---

function startDrawing(e) {
    if (e.buttons !== 1 && e.type !== 'pointerdown') return;
    e.preventDefault();
    document.body.classList.add('drawing-active'); // <-- LIGNE AJOUTÉE ICI

    isDrawing = true;
    
    const { x, y, pressure } = getPointerPosition(e);
    currentPoints = [[x, y, pressure]];
}

function draw(e) {
    if (!isDrawing) return;
    e.preventDefault();

    const { x, y, pressure } = getPointerPosition(e);
    currentPoints.push([x, y, pressure]);
    
    // Redessine tout pour un aperçu en temps réel
    redrawAllStrokes();
    
    // Dessine le tracé en cours
    const colorEl = document.getElementById('color');
    drawStroke(ctx, {
        points: currentPoints,
        options: getStrokeOptions(),
        color: colorEl ? colorEl.value : '#000000',
        isEraser: currentTool === 'eraser'
    });
}

function stopDrawing() {
    if (!isDrawing) return;
    document.body.classList.remove('drawing-active'); // <-- LIGNE AJOUTÉE ICI
    
    isDrawing = false;
    
    if (currentPoints.length > 1) {
        const colorEl = document.getElementById('color');
        strokes.push({
            points: currentPoints,
            options: getStrokeOptions(),
            color: colorEl ? colorEl.value : '#000000',
            isEraser: currentTool === 'eraser'
        });
    }
    currentPoints = [];
    // Redessine une dernière fois pour "fixer" le trait
    redrawAllStrokes();
}


if (canvas) {
    // J'ai aussi un peu modifié la condition dans startDrawing pour mieux gérer les appareils tactiles
    canvas.addEventListener('pointerdown', startDrawing);
    canvas.addEventListener('pointermove', draw);
    canvas.addEventListener('pointerup', stopDrawing);
    canvas.addEventListener('pointerleave', stopDrawing);
}

function changeZoom(delta) {
    whiteboardZoomLevel = Math.max(0.5, Math.min(3, whiteboardZoomLevel + delta));
    if(zoomPercentEl) zoomPercentEl.textContent = `${Math.round(whiteboardZoomLevel * 100)}%`;
    applyWhiteboardZoom();
}

function applyWhiteboardZoom() {
    if (canvas) {
        canvas.style.transformOrigin = 'top left'; // Important pour que le zoom se fasse depuis le coin
        canvas.style.transform = `scale(${whiteboardZoomLevel})`;
    }
}

// --- GESTION DU PLEIN ÉCRAN DU WHITEBOARD ---
const fullscreenBtn = document.getElementById('fullscreenBtn');
if (fullscreenBtn && whiteboardWorkspace) {
    fullscreenBtn.addEventListener('click', () => {
        whiteboardWorkspace.classList.toggle('fullscreen');
        document.body.classList.toggle('no-scroll');
        
        setTimeout(() => {
            resizeCanvas();
        }, 50);

        const icon = fullscreenBtn.querySelector('i');
        if (whiteboardWorkspace.classList.contains('fullscreen')) {
            icon.classList.replace('fa-expand-arrows-alt', 'fa-compress-arrows-alt');
        } else {
            icon.classList.replace('fa-compress-arrows-alt', 'fa-expand-arrows-alt');
        }
    });
}