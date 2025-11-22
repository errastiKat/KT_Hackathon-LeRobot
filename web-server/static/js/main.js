document.addEventListener("DOMContentLoaded", () => {
    console.log("🚀 LeRobot Frontend cargado");

    // --- ELEMENTOS DEL DOM ---
    const recordBtn = document.getElementById("record-btn");
    const audioStatusPill = document.getElementById("audio-status-pill");
    const recordHint = document.getElementById("record-hint");
    const recordingVisual = document.querySelector(".recording-visual");
    const sttText = document.getElementById("stt-text");

    // Módulo de cara
    const faceStatusPill = document.getElementById("face-status-pill");
    const faceImage = document.getElementById("face-image");

    // Módulo IA
    const iaStatusPill = document.getElementById("ia-status-pill");
    const iaImage = document.getElementById("ia-image");

    // Pipeline
    const pipelineProgressBar = document.getElementById("pipeline-progress-bar");
    const pipelineTimeline = document.getElementById("pipeline-timeline");

    // Flag local para no spamear /api/run-ia
    let iaRequested = false;

    // ==================================================
    // 1. LÓGICA DEL BOTÓN (ACTIVAR ESCUCHA)
    // ==================================================
    if (recordBtn) {
        recordBtn.addEventListener("click", async () => {

            if (recordBtn.classList.contains("recording")) return;

            console.log("🎤 Enviando orden de escuchar al robot...");

            recordBtn.classList.add("recording");
            if (recordingVisual) recordingVisual.classList.add("recording");

            if (audioStatusPill) {
                audioStatusPill.textContent = "Robot escuchando...";
                audioStatusPill.className = "status-pill status-active";
            }
            if (recordHint) {
                recordHint.textContent = "Habla alto y claro al micrófono del robot";
            }
            if (sttText) {
                sttText.innerHTML =
                    '<span class="placeholder-text">🤖 Escuchando... (Di "Ponme un gorro", "gafas"...)</span>';
            }

            try {
                const response = await fetch("/api/listen-command", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    }
                });

                const data = await response.json();

                recordBtn.classList.remove("recording");
                if (recordingVisual) recordingVisual.classList.remove("recording");

                if (data.ok) {
                    console.log("✅ Prompt recibido:", data.transcript);

                    if (audioStatusPill) {
                        audioStatusPill.textContent = "Completado";
                        audioStatusPill.className = "status-pill status-done";
                    }
                    if (recordHint) {
                        recordHint.textContent = "Pulsa para grabar otra vez";
                    }
                    if (sttText) {
                        sttText.innerText = data.transcript;
                    }

                    markStageAsDone("speech");
                    // Nuevo prompt => permitimos volver a pedir IA
                    iaRequested = false;

                } else {
                    console.warn("⚠️", data.message);
                    if (audioStatusPill) {
                        audioStatusPill.textContent = "No entendido";
                        audioStatusPill.className = "status-pill status-pending";
                    }
                    if (recordHint) {
                        recordHint.textContent = "Inténtalo de nuevo";
                    }
                    if (sttText) {
                        sttText.innerHTML =
                            `<span style="color: var(--accent-danger)">❌ ${data.message}</span>`;
                    }
                }

            } catch (err) {
                console.error("❌ Error de conexión:", err);

                recordBtn.classList.remove("recording");
                if (recordingVisual) recordingVisual.classList.remove("recording");

                if (audioStatusPill) {
                    audioStatusPill.textContent = "Error de Conexión";
                    audioStatusPill.className = "status-pill status-pending";
                }
                if (sttText) {
                    sttText.innerText =
                        "Error: El servidor Python no responde o el micrófono falló.";
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

            const percent = data.progress_percent || 0;
            if (pipelineProgressBar) {
                pipelineProgressBar.style.width = `${percent}%`;
                pipelineProgressBar.setAttribute("aria-valuenow", percent);
            }

            if (!pipelineTimeline) return;

            const stageMap = {};
            (data.stages || []).forEach(s => {
                stageMap[s.id] = s.status;
            });

            pipelineTimeline.querySelectorAll("li").forEach(li => {
                const stageId = li.getAttribute("data-stage");
                const status = stageMap[stageId] || "pending";
                li.classList.remove("done", "active", "pending");
                li.setAttribute("data-status", status);
            });

            // ---- Actualizar pill de IA en función del estado ----
            const iaStatus = stageMap["ia_edit"] || "pending";
            if (iaStatusPill) {
                if (iaStatus === "done") {
                    iaStatusPill.textContent = "Completado";
                    iaStatusPill.className = "status-pill status-done";
                } else if (iaStatus === "active") {
                    iaStatusPill.textContent = "Procesando IA...";
                    iaStatusPill.className = "status-pill status-active";
                } else {
                    iaStatusPill.textContent = "Pendiente";
                    iaStatusPill.className = "status-pill status-pending";
                }
            }

            // ---- Lógica para lanzar automáticamente la IA ----
            const faceCaptureStatus = stageMap["face_capture"];
            const speechStatus = stageMap["speech"];

            if (
                faceCaptureStatus === "done" &&
                speechStatus === "done" &&
                iaStatus !== "done" &&
                !iaRequested
            ) {
                console.log("🧠 Lanzando IA generativa automáticamente...");
                iaRequested = true;
                triggerIAProcess();
            }

            // Si la IA ya está done, aseguramos que la imagen que se ve es la buena
            if (iaStatus === "done") {
                updateIAImage();
            }

        } catch (err) {
            console.error("Error polling status:", err);
        }
    }

    function markStageAsDone(stageId) {
        if (!pipelineTimeline) return;
        const li = pipelineTimeline.querySelector(`li[data-stage="${stageId}"]`);
        if (li) {
            li.setAttribute("data-status", "done");
        }
    }

    setInterval(refreshPipelineStatus, 2000);
    refreshPipelineStatus();

    // ==================================================
    // 3. MÓDULO DE CARA: STREAM + ESTADO
    // ==================================================
    async function refreshFaceModule() {
        try {
            if (faceImage) {
                faceImage.src = `/api/face-frame?t=${Date.now()}`;
            }

            if (faceStatusPill) {
                const res = await fetch("/api/face-status");
                if (!res.ok) return;

                const data = await res.json();
                const happy = data.happy || 0;
                const threshold = data.happy_threshold || 60;

                if (data.photo_taken) {
                    faceStatusPill.textContent = "Foto capturada";
                    faceStatusPill.className = "status-pill status-done";
                    markStageAsDone("face_capture");

                } else if (data.face_present) {
                    faceStatusPill.textContent =
                        `Rostro detectado (${happy.toFixed(0)}% feliz)`;

                    if (happy >= threshold) {
                        faceStatusPill.className = "status-pill status-active";
                    } else {
                        faceStatusPill.className = "status-pill status-idle";
                    }

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

    setInterval(refreshFaceModule, 800);
    refreshFaceModule();

    // ==================================================
    // 4. MÓDULO IA: LLAMADA AL BACKEND
    // ==================================================

    async function triggerIAProcess() {
        try {
            if (iaStatusPill) {
                iaStatusPill.textContent = "Procesando IA...";
                iaStatusPill.className = "status-pill status-active";
            }

            const res = await fetch("/api/run-ia", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                }
            });

            const data = await res.json();

            if (res.ok && data.ok) {
                console.log("✅ IA completada. Imagen en:", data.url);
                markStageAsDone("ia_edit");
                updateIAImage(data.url);

                if (iaStatusPill) {
                    iaStatusPill.textContent = "Completado";
                    iaStatusPill.className = "status-pill status-done";
                }
            } else {
                console.warn("⚠️ Error en IA:", data.error || res.statusText);
                iaRequested = false; // Permitimos reintentar si hace falta
                if (iaStatusPill) {
                    iaStatusPill.textContent = "Error IA";
                    iaStatusPill.className = "status-pill status-pending";
                }
            }
        } catch (err) {
            console.error("❌ Error llamando a /api/run-ia:", err);
            iaRequested = false;
            if (iaStatusPill) {
                iaStatusPill.textContent = "Error IA";
                iaStatusPill.className = "status-pill status-pending";
            }
        }
    }

    async function updateIAImage(forceUrl) {
        try {
            let url = forceUrl;
            if (!url) {
                const res = await fetch("/api/ia-image-url");
                const data = await res.json();
                url = data.url;
            }
            if (iaImage && url) {
                iaImage.src = `${url}?t=${Date.now()}`;
            }
        } catch (err) {
            console.error("Error refrescando imagen IA:", err);
        }
    }
});
