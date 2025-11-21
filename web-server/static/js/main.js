// static/js/main.js

document.addEventListener("DOMContentLoaded", () => {
    const recordBtn = document.getElementById("record-btn");
    const audioStatusPill = document.getElementById("audio-status-pill");
    const recordHint = document.getElementById("record-hint");
    const recordingVisual = document.querySelector(".recording-visual");
    const sttText = document.getElementById("stt-text");
    const pipelineProgressBar = document.getElementById("pipeline-progress-bar");
    const pipelineTimeline = document.getElementById("pipeline-timeline");

    let isRecording = false;
    let mediaRecorder = null;
    let audioChunks = [];

    // ==========
    // Grabación
    // ==========
    recordBtn.addEventListener("click", async () => {
        if (!isRecording) {
            // Empezar grabación
            isRecording = true;
            recordBtn.classList.add("recording");
            recordingVisual.classList.add("recording");
            audioStatusPill.textContent = "Grabando…";
            audioStatusPill.className = "status-pill status-active";
            recordHint.textContent = "Pulsa de nuevo para parar y enviar";

            // Si no quieres usar MediaRecorder todavía, comenta todo el bloque try/catch:
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];

                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                };

                mediaRecorder.onstop = async () => {
                    const blob = new Blob(audioChunks, { type: "audio/webm" });
                    await sendAudioToBackend(blob);
                    stream.getTracks().forEach(t => t.stop());
                };

                mediaRecorder.start();
            } catch (err) {
                console.error("Error al acceder al micrófono:", err);
            }
        } else {
            // Parar grabación
            isRecording = false;
            recordBtn.classList.remove("recording");
            recordingVisual.classList.remove("recording");
            audioStatusPill.textContent = "Procesando audio…";
            audioStatusPill.className = "status-pill status-pending";
            recordHint.textContent = "Esperando respuesta del backend…";

            if (mediaRecorder && mediaRecorder.state !== "inactive") {
                mediaRecorder.stop();
            } else {
                // Si no activas MediaRecorder, al menos simula una llamada:
                sendAudioToBackend(null);
            }
        }
    });

    async function sendAudioToBackend(blob) {
        try {
            const formData = new FormData();
            if (blob) {
                formData.append("audio", blob, "audio.webm");
            }

            const response = await fetch("/api/upload-audio", {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            if (data.ok) {
                audioStatusPill.textContent = "Audio enviado";
                audioStatusPill.className = "status-pill status-done";
                sttText.innerHTML = data.transcript || "Transcripción recibida (aquí colocarás el texto STT).";
            } else {
                audioStatusPill.textContent = "Error en el backend";
                audioStatusPill.className = "status-pill status-idle";
            }
        } catch (err) {
            console.error("Error al enviar audio:", err);
            audioStatusPill.textContent = "Error de red";
            audioStatusPill.className = "status-pill status-idle";
        }
    }

    // ==========================
    // Estado del pipeline (UI)
    // ==========================

    async function refreshPipelineStatus() {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();

            const percent = data.progress_percent || 0;
            pipelineProgressBar.style.width = `${percent}%`;
            pipelineProgressBar.setAttribute("aria-valuenow", percent);

            if (!pipelineTimeline) return;

            const stageMap = {};
            (data.stages || []).forEach(s => stageMap[s.id] = s.status);

            pipelineTimeline.querySelectorAll("li").forEach(li => {
                const stageId = li.getAttribute("data-stage");
                const status = stageMap[stageId] || "pending";
                li.classList.remove("completed", "active", "pending");

                if (status === "done") {
                    li.classList.add("completed");
                } else if (status === "in_progress") {
                    li.classList.add("active");
                } else {
                    li.classList.add("pending");
                }
            });
        } catch (err) {
            console.error("Error al obtener estado del pipeline:", err);
        }
    }

    // Actualizar cada 2s (puedes cambiar esta frecuencia)
    setInterval(refreshPipelineStatus, 2000);
    refreshPipelineStatus();
});
