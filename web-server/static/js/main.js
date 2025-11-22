document.addEventListener("DOMContentLoaded", () => {
    console.log("🚀 LeRobot Frontend Cargado");

    // --- Referencias DOM ---
    // Cámara
    const btnStartCam = document.getElementById("btn-start-cam");
    const localVideo = document.getElementById("local-video");
    const startCamOverlay = document.getElementById("start-cam-overlay");
    const captureCanvas = document.getElementById("capture-canvas");
    const ctx = captureCanvas ? captureCanvas.getContext("2d") : null;
    const finalCaptureImg = document.getElementById("final-capture-img");
    
    const faceStatusPill = document.getElementById("face-status-pill");
    const smileDebugText = document.getElementById("smile-debug-text");

    // Audio / IA
    const recordBtn = document.getElementById("record-btn");
    const audioStatusPill = document.getElementById("audio-status-pill");
    const sttText = document.getElementById("stt-text");
    const iaStatusPill = document.getElementById("ia-status-pill");
    const iaImage = document.getElementById("ia-image");
    const pipelineProgressBar = document.getElementById("pipeline-progress-bar");

    // --- Estado Local ---
    let streaming = false;
    let photoTakenLocal = false;
    let sendFrameInterval = null;
    let iaRequested = false;

    // ==================================================
    // 1. ACTIVAR CÁMARA DEL IPHONE (Navegador)
    // ==================================================
    if (btnStartCam) {
        btnStartCam.addEventListener("click", async () => {
            try {
                console.log("Solicitando cámara...");
                // Pide cámara frontal (user) y sin audio (para evitar feedback)
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: "user", width: { ideal: 640 } },
                    audio: false
                });
                
                localVideo.srcObject = stream;
                localVideo.style.display = "block";
                startCamOverlay.style.display = "none";
                
                // Cuando el video esté listo, empezamos a enviar frames
                localVideo.onloadedmetadata = () => {
                    localVideo.play();
                    streaming = true;
                    smileDebugText.innerText = "Cámara activa. Buscando cara...";
                    startSendingFrames();
                };

            } catch (err) {
                alert("Error: No se pudo acceder a la cámara. Asegúrate de usar HTTPS (Ngrok). " + err);
                console.error(err);
            }
        });
    }

    // ==================================================
    // 2. ENVIAR FRAMES AL SERVIDOR (Loop)
    // ==================================================
    function startSendingFrames() {
        if (sendFrameInterval) clearInterval(sendFrameInterval);

        // Intervalo de 400ms (aprox 2.5 fps) para no saturar la red
        sendFrameInterval = setInterval(async () => {
            if (!streaming || photoTakenLocal) return;

            // A. Dibujar frame actual en el canvas oculto
            // Reducimos resolución a 400px de ancho para envío rápido
            const width = 400;
            const height = (localVideo.videoHeight / localVideo.videoWidth) * width;
            
            captureCanvas.width = width;
            captureCanvas.height = height;
            ctx.drawImage(localVideo, 0, 0, width, height);

            // B. Convertir a JPG Base64
            const dataURL = captureCanvas.toDataURL("image/jpeg", 0.6);

            // C. Enviar a Flask
            try {
                const res = await fetch("/api/process-frame", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ image: dataURL })
                });
                
                const data = await res.json();
                if (data.ok) {
                    updateFaceUI(data);
                }

            } catch (err) {
                console.error("Error enviando frame:", err);
            }

        }, 400);
    }

    function updateFaceUI(data) {
        // 1. ¿Foto tomada?
        if (data.taken) {
            if (!photoTakenLocal) {
                photoTakenLocal = true;
                
                // Mostrar la foto congelada en la UI
                finalCaptureImg.src = captureCanvas.toDataURL("image/jpeg");
                finalCaptureImg.classList.remove("d-none");
                
                // Parar video para ahorrar batería
                localVideo.pause();
                streaming = false;
                
                faceStatusPill.textContent = "Foto Capturada";
                faceStatusPill.className = "status-pill status-done";
                smileDebugText.innerHTML = '<i class="bi bi-check-circle-fill text-success"></i> Foto lista. Ahora usa la voz.';
                
                markStageAsDone("face_capture");
                markStageAsDone("face_detect");
            }
            return;
        }

        // 2. Estado en tiempo real
        if (data.smile) {
            faceStatusPill.textContent = "¡Sonrisa!";
            faceStatusPill.className = "status-pill status-active";
            smileDebugText.innerText = "Manten la sonrisa...";
        } else if (data.face) {
            faceStatusPill.textContent = "Cara detectada";
            faceStatusPill.className = "status-pill status-idle";
            smileDebugText.innerText = "Te veo. ¡Sonríe!";
        } else {
            faceStatusPill.textContent = "Buscando...";
            faceStatusPill.className = "status-pill status-pending";
            smileDebugText.innerText = "Encuadra tu cara";
        }
    }

    // ==================================================
    // 3. GRABACIÓN DE VOZ (Botón Servidor)
    // ==================================================
    if (recordBtn) {
        recordBtn.addEventListener("click", async () => {
            if (recordBtn.classList.contains("recording")) return;

            recordBtn.classList.add("recording");
            audioStatusPill.textContent = "Escuchando...";
            audioStatusPill.className = "status-pill status-active";
            sttText.innerHTML = '<span class="placeholder-text">...Escuchando en servidor...</span>';

            try {
                const res = await fetch("/api/listen-command", { method: "POST" });
                const data = await res.json();
                
                recordBtn.classList.remove("recording");

                if (data.ok) {
                    sttText.innerText = data.transcript;
                    audioStatusPill.textContent = "Completado";
                    audioStatusPill.className = "status-pill status-done";
                    markStageAsDone("speech");
                    iaRequested = false; // Permitir nueva llamada a IA
                } else {
                    sttText.innerText = "No entendido.";
                    audioStatusPill.textContent = "Reintentar";
                    audioStatusPill.className = "status-pill status-pending";
                }
            } catch (e) {
                recordBtn.classList.remove("recording");
                console.error("Error audio:", e);
                sttText.innerText = "Error conexión servidor.";
            }
        });
    }

    // ==================================================
    // 4. POLLING DE ESTADO GENERAL (Cada 1.5s)
    // ==================================================
    setInterval(async () => {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();

            // Barra de progreso global
            if (pipelineProgressBar) {
                pipelineProgressBar.style.width = `${data.progress_percent}%`;
            }

            // Actualizar Timeline visual
            if (data.stages) {
                data.stages.forEach(s => {
                    const el = document.querySelector(`li[data-stage="${s.id}"]`);
                    if (el) el.setAttribute("data-status", s.status);
                    
                    // Actualizar UI de IA especificamente
                    if (s.id === "ia_edit") {
                        if (s.status === "done") {
                            iaStatusPill.textContent = "Completado";
                            iaStatusPill.className = "status-pill status-done";
                            updateIAImage(); // Refrescar imagen si ya terminó
                        } else if (s.status === "active") {
                            iaStatusPill.textContent = "Generando...";
                            iaStatusPill.className = "status-pill status-active";
                        }
                    }
                });
            }

            // Trigger Automático de IA: Si hay foto + voz + no IA
            if (data.photo_taken && checkStageDone("speech") && !checkStageDone("ia_edit") && !iaRequested) {
                console.log("🚀 Lanzando IA Automáticamente...");
                iaRequested = true;
                triggerIA();
            }

        } catch (e) {
            console.error("Error polling status:", e);
        }
    }, 1500);


    // --- Funciones Auxiliares IA ---
    async function triggerIA() {
        try {
            const res = await fetch("/api/run-ia", { method: "POST" });
            const data = await res.json();
            if (data.ok) {
                updateIAImage(data.url);
            } else {
                console.warn("IA Error:", data.error);
                iaRequested = false; // Permitir reintento
            }
        } catch (e) { console.error(e); iaRequested = false; }
    }

    async function updateIAImage(forceUrl) {
        let url = forceUrl;
        if (!url) {
            const res = await fetch("/api/ia-image-url");
            const data = await res.json();
            url = data.url;
        }
        if (iaImage && url) {
            // Truco del timestamp para evitar caché del navegador
            iaImage.src = `${url}?t=${Date.now()}`;
        }
    }

    function markStageAsDone(id) {
        const el = document.querySelector(`li[data-stage="${id}"]`);
        if (el) el.setAttribute("data-status", "done");
    }

    function checkStageDone(id) {
        const el = document.querySelector(`li[data-stage="${id}"]`);
        return el && el.getAttribute("data-status") === "done";
    }

    // --- RESET GLOBAL (Expuesto a window para el botón HTML) ---
    window.resetPipeline = async function() {
        if(confirm("¿Borrar todo y empezar de nuevo?")) {
            await fetch("/api/reset");
            location.reload();
        }
    };
});