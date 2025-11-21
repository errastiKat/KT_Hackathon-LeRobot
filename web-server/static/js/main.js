document.addEventListener("DOMContentLoaded", () => {
    console.log("🚀 LeRobot Frontend cargado");

    // --- ELEMENTOS DEL DOM ---
    const recordBtn = document.getElementById("record-btn");
    const audioStatusPill = document.getElementById("audio-status-pill");
    const recordHint = document.getElementById("record-hint");
    const recordingVisual = document.querySelector(".recording-visual");
    const sttText = document.getElementById("stt-text");
    
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
            audioStatusPill.textContent = "Robot escuchando...";
            audioStatusPill.className = "status-pill status-active"; // Verde/Activo
            recordHint.textContent = "Habla alto y claro al micrófono del robot";
            sttText.innerHTML = '<span class="placeholder-text">🤖 Escuchando... (Di "Ponme un gorro", "gafas"...)</span>';

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
                    
                    audioStatusPill.textContent = "Completado";
                    audioStatusPill.className = "status-pill status-done"; 
                    recordHint.textContent = "Pulsa para grabar otra vez";
                    
                    // Mostrar el prompt en inglés en la caja
                    sttText.innerText = data.transcript;
                    
                    // Actualizar visualmente el paso en la timeline
                    markStageAsDone('speech');

                } else {
                    // ERROR LÓGICO: El robot escuchó pero no entendió o se canceló
                    console.warn("⚠️", data.message);
                    audioStatusPill.textContent = "No entendido";
                    audioStatusPill.className = "status-pill status-pending"; // Naranja
                    recordHint.textContent = "Inténtalo de nuevo";
                    sttText.innerHTML = `<span style="color: var(--accent-danger)">❌ ${data.message}</span>`;
                }

            } catch (err) {
                // --- D. ERROR DE RED/SERVIDOR ---
                console.error("❌ Error de conexión:", err);
                
                recordBtn.classList.remove("recording");
                if (recordingVisual) recordingVisual.classList.remove("recording");
                
                audioStatusPill.textContent = "Error de Conexión";
                audioStatusPill.className = "status-pill status-pending";
                sttText.innerText = "Error: El servidor Python no responde o el micrófono falló.";
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
            (data.stages || []).forEach(s => stageMap[s.id] = s.status);

            pipelineTimeline.querySelectorAll("li").forEach(li => {
                const stageId = li.getAttribute("data-stage");
                const status = stageMap[stageId] || "pending";
                
                // Resetear clases
                li.classList.remove("done", "active", "pending"); // Ajusta según tu CSS
                li.setAttribute("data-status", status); // Para que el CSS nuevo funcione
            });

        } catch (err) {
            console.error("Error polling status:", err);
        }
    }

    // Función auxiliar para forzar visualmente un paso completado (Feedback inmediato)
    function markStageAsDone(stageId) {
        if (!pipelineTimeline) return;
        const li = pipelineTimeline.querySelector(`li[data-stage="${stageId}"]`);
        if (li) li.setAttribute("data-status", "done");
    }

    // Iniciar el bucle de estado
    setInterval(refreshPipelineStatus, 2000);
    refreshPipelineStatus();
});