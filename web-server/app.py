from flask import Flask, render_template, jsonify, request, url_for
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# =========================
#   RUTAS PRINCIPALES
# =========================

@app.route("/")
def index():
    return render_template("index.html")

# =========================
#   ENDPOINTS DE LA API
# =========================

@app.route("/api/status")
def api_status():
    """
    Devuelve el estado del pipeline.
    """
    demo_status = {
        "progress_percent": 40,
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
    Endpoint para recibir el audio.
    """
    return jsonify({
        "ok": True,
        "message": "Audio recibido. Procesando STT + IA...",
        "transcript": "ponme un gorro de navidad rojo, grande"
    })

@app.route("/api/ia-image-url")
def ia_image_url():
    """
    Devuelve la URL de la imagen editada.
    """
    return jsonify({
        "url": url_for("static", filename="img/ia_placeholder.jpg")
    })

# =========================
#   ENDPOINTS DE VIDEO (Placeholder)
#   Estos son los que te daban el error BuildError
# =========================

@app.route("/face_stream")
def face_stream():
    """
    Ruta futura para el stream de vídeo MJPEG.
    Por ahora devuelve una imagen estática o un error 404 controlado 
    para que la app no se rompa.
    """
    # Cuando tengas la cámara, aquí iría el 'yield (b--frame...)'
    return url_for('static', filename='img/face_placeholder.jpg')

@app.route("/robot_stream")
def robot_stream():
    """
    Ruta futura para el stream del robot.
    """
    return url_for('static', filename='img/robot_placeholder.jpg')


if __name__ == "__main__":
    # 3. CAMBIO IMPORTANTE: host="0.0.0.0"
    # Esto le dice a Flask: "Escucha en la red, no solo en mi PC"
    app.run(host="0.0.0.0", port=5000, debug=True)