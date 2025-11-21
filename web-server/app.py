from flask import Flask, render_template, jsonify, request

app = Flask(__name__)


@app.route("/")
def index():
    # Página principal con todos los bloques:
    # - Vídeo de reconocimiento facial
    # - Grabadora de voz
    # - Resultado de la IA + barra de progreso
    # - Vídeo del robot dibujando
    return render_template("index.html")


# =========================
#   ENDPOINTS ESQUELETO
# =========================

@app.route("/api/status")
def api_status():
    """
    Devuelve el estado del pipeline.
    Aquí luego conectarás tu lógica real (face -> audio -> IA -> contornos -> robot).
    """
    # TODO: sustituir por estados reales
    demo_status = {
        "progress_percent": 40,   # 0-100
        "current_stage": "ia_edit",
        "stages": [
            {"id": "face_detect", "label": "Detección de rostro", "status": "done"},
            {"id": "face_capture", "label": "Captura de foto", "status": "done"},
            {"id": "speech", "label": "Frase grabada", "status": "in_progress"},
            {"id": "ia_edit", "label": "Edición IA", "status": "pending"},
            {"id": "contours", "label": "Extracción de contornos", "status": "pending"},
            {"id": "robot_draw", "label": "Dibujo en LeRobot", "status": "pending"},
        ]
    }
    return jsonify(demo_status)


@app.route("/api/upload-audio", methods=["POST"])
def upload_audio():
    """
    Endpoint al que el front enviará el audio grabado con la frase.
    Aquí conectarás tu biblioteca de Speech-to-Text y la llamada a la IA.
    """
    # audio_file = request.files.get("audio")  # cuando lo conectes de verdad
    # TODO: conectar STT + IA
    # Simulamos una respuesta
    return jsonify({
        "ok": True,
        "message": "Audio recibido. Procesando STT + IA...",
        "transcript": "ponme un gorro de navidad rojo, grande"
    })


@app.route("/api/ia-image-url")
def ia_image_url():
    """
    Devuelve la URL de la imagen editada por la IA (cuando exista).
    Por ahora, devolvemos una imagen estática de ejemplo.
    """
    # TODO: en el futuro podrías devolver una ruta dinámica
    from flask import url_for
    return jsonify({
        "url": url_for("static", filename="img/ia_placeholder.jpg")
    })


if __name__ == "__main__":
    app.run(debug=True)
