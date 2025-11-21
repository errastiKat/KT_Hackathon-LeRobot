document.addEventListener("DOMContentLoaded", () => {
    console.log("🚀 LeRobot Frontend cargado");

    // --- ELEMENTOS DEL DOM ---
    const recordBtn = document.getElementById("record-btn");
    const audioStatusPill = document.getElementById("audio-status-pill");
    const recordHint = document.getElementById("record-hint");
    const recordingVisual = document.querySelector(".recording-visual");
    const sttText = document.getElementById("stt-text");

    // Elementos del módulo de cara
    const faceStatusPill = document.getElementById("face-status-pill");
    const faceImage = document.getElementById("face-image");

    // Elementos de la barra de progreso (Pipeline)
    const pipelineProgressBar = document.getElementById("pipeline-progress-bar");
    const pipelineTimeline = document.getElementById("pipeline-timeline");

    // ==================================================
    // 1. LÓGICA DEL BOTÓN (ACTIVAR ESCUCHA DEL ROBOT)
    // ==================================================
    if (recordBtn) {
        recordBtn.addEventListener("click", async () => {

            // Evitar pulsar dos veces si ya está escuchando
            if (recordBtn.classList.contains("recording")) return;

            // --- A. CAMBIAR UI A MODO "ESCUCHANDO" ---
            console.log("🎤 Enviando orden de escuchar al robot...");

            // Activar animaciones CSS
            recordBtn.classList.add("recording");
            if (recordingVisual) recordingVisual.classList.add("recording");

            // Actualizar textos y etiquetas
            if (audioStatusPill) {
                audioStatusPill.textContent = "Robot escuchando...";
                audioStatusPill.className = "status-pill status-active"; // Verde/Activo
            }
            if (recordHint) {
                recordHint.textContent = "Habla alto y claro al micrófono del robot";
            }
            if (sttText) {
                sttText.innerHTML = '<span class="placeholder-text">🤖 Escuchando... (Di "Ponme un gorro", "gafas"...)</span>';
            }

            try {
                // --- B. LLAMADA AL BACKEND (TRIGGER) ---
                // Esto le dice a Python: "Ejecuta voice_engine.escuchar_y_obtener_prompt()"
                const response = await fetch("/api/listen-command", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    }
                });

                const data = await response.json();

                // --- C. RESPUESTA RECIBIDA (FIN DE ESCUCHA) ---
                // Desactivar animaciones
                recordBtn.classList.remove("recording");
                if (recordingVisual) recordingVisual.classList.remove("recording");

                if (data.ok) {
                    // ÉXITO: El robot entendió y generó el prompt
                    console.log("✅ Prompt recibido:", data.transcript);

                    if (audioStatusPill) {
                        audioStatusPill.textContent = "Completado";
                        audioStatusPill.className = "status-pill status-done";
                    }
                    if (recordHint) {
                        recordHint.textContent = "Pulsa para grabar otra vez";
                    }

                    // Mostrar el prompt en inglés en la caja
                    if (sttText) {
                        sttText.innerText = data.transcript;
                    }

                    // Actualizar visualmente el paso en la timeline
                    markStageAsDone("speech");

                } else {
                    // ERROR LÓGICO: El robot escuchó pero no entendió o se canceló
                    console.warn("⚠️", data.message);
                    if (audioStatusPill) {
                        audioStatusPill.textContent = "No entendido";
                        audioStatusPill.className = "status-pill status-pending"; // Naranja
                    }
                    if (recordHint) {
                        recordHint.textContent = "Inténtalo de nuevo";
                    }
                    if (sttText) {
                        sttText.innerHTML = `<span style="color: var(--accent-danger)">❌ ${data.message}</span>`;
                    }
                }

            } catch (err) {
                // --- D. ERROR DE RED/SERVIDOR ---
                console.error("❌ Error de conexión:", err);

                recordBtn.classList.remove("recording");
                if (recordingVisual) recordingVisual.classList.remove("recording");

                if (audioStatusPill) {
                    audioStatusPill.textContent = "Error de Conexión";
                    audioStatusPill.className = "status-pill status-pending";
                }
                if (sttText) {
                    sttText.innerText = "Error: El servidor Python no responde o el micrófono falló.";
                }
            }
        });
    }

    // ==================================================
    // 2. ESTADO DEL PIPELINE (Polling cada 2s)
    // ==================================================
    async function refreshPipelineStatus() {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();

            // Actualizar barra superior
            const percent = data.progress_percent || 0;
            if (pipelineProgressBar) {
                pipelineProgressBar.style.width = `${percent}%`;
                pipelineProgressBar.setAttribute("aria-valuenow", percent);
            }

            // Actualizar lista lateral (Timeline)
            if (!pipelineTimeline) return;

            const stageMap = {};
            (data.stages || []).forEach(s => {
                stageMap[s.id] = s.status;
            });

            pipelineTimeline.querySelectorAll("li").forEach(li => {
                const stageId = li.getAttribute("data-stage");
                const status = stageMap[stageId] || "pending";

                // Resetear clases si tu CSS las usa, pero principalmente usamos data-status
                li.classList.remove("done", "active", "pending");
                li.setAttribute("data-status", status);
            });

        } catch (err) {
            console.error("Error polling status:", err);
        }
    }

    // Función auxiliar para forzar visualmente un paso completado (Feedback inmediato)
    function markStageAsDone(stageId) {
        if (!pipelineTimeline) return;
        const li = pipelineTimeline.querySelector(`li[data-stage="${stageId}"]`);
        if (li) {
            li.setAttribute("data-status", "done");
        }
    }

    // Iniciar el bucle de estado
    setInterval(refreshPipelineStatus, 2000);
    refreshPipelineStatus();

    // ==================================================
    // 3. MÓDULO DE CARA: STREAM + ESTADO
    // ==================================================
    async function refreshFaceModule() {
        try {
            // 1) Actualizar imagen de la cámara
            if (faceImage) {
                // Añadimos timestamp para evitar caché del navegador
                faceImage.src = `/api/face-frame?t=${Date.now()}`;
            }

            // 2) Actualizar pill de estado (cara / sonrisa / captura)
            if (faceStatusPill) {
                const res = await fetch("/api/face-status");
                if (!res.ok) return;

                const data = await res.json();
                const happy = data.happy || 0;
                const threshold = data.happy_threshold || 60;

                if (data.photo_taken) {
                    faceStatusPill.textContent = "Foto capturada";
                    faceStatusPill.className = "status-pill status-done";

                    // Marcamos también la etapa de captura en la timeline
                    markStageAsDone("face_capture");

                } else if (data.face_present) {
                    faceStatusPill.textContent =
                        `Rostro detectado (${happy.toFixed(0)}% feliz)`;

                    if (happy >= threshold) {
                        faceStatusPill.className = "status-pill status-active";
                    } else {
                        faceStatusPill.className = "status-pill status-idle";
                    }

                    // Marcamos la etapa de detección cuando haya rostro
                    markStageAsDone("face_detect");

                } else {
                    faceStatusPill.textContent = "Esperando rostro";
                    faceStatusPill.className = "status-pill status-idle";
                }
            }
        } catch (err) {
            console.error("Error refrescando módulo de cara:", err);
        }
    }

    // Refrescar cara cada 500 ms
    setInterval(refreshFaceModule, 800);
    refreshFaceModule();
});
