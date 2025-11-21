import os
import sys
from flask import Flask, render_template, jsonify, url_for, Response
from flask_cors import CORS

# --- 1. IMPORTACIÓN LIMPIA DEL MÓDULO SUPERIOR ---
# Añadimos la carpeta de arriba ("..") a las rutas de Python para poder importar
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(project_root)

# Ahora importamos tu clase directamente. Sin reescribir nada.
from voice_module import VoiceEngine
from reconcoimiento_facial.recognize_smile import SmileDetector


app = Flask(__name__)
CORS(app)

# --- 2. INICIALIZAR TU MOTOR ---
# Definimos la ruta al modelo relativa a la raíz del proyecto
MODEL_PATH = os.path.join(project_root, "vosk-model-small-es-0.42")

print(f"⚙️ Inicializando VoiceEngine desde: {MODEL_PATH}")
# Instanciamos tu clase. Ella se encarga de cargar Vosk, el traductor, etc.
motor_voz = VoiceEngine(MODEL_PATH)


# =========================
#   ESTADO DEL PIPELINE
# =========================

# Flags muy simples por ahora
pipeline_flags = {
    "speech_done": False,   # lo marcaremos a True cuando /api/listen-command tenga éxito
}


# =========================
#   SMILE DETECTOR
# =========================

# Ruta absoluta al static de Flask
STATIC_DIR = os.path.join(current_dir, "static")

# Vamos a guardar la foto en static/img/smile_capture.jpg
CAPTURE_REL = os.path.join("img", "smile_capture.jpg")
CAPTURE_PATH = os.path.join(STATIC_DIR, CAPTURE_REL)

os.makedirs(os.path.dirname(CAPTURE_PATH), exist_ok=True)

print(f"📸 Inicializando SmileDetector. Foto irá a: {CAPTURE_PATH}")
smile_detector = SmileDetector(
    cam_index=0,
    frame_w=1280,          # antes 1920
    frame_h=720,           # antes 1080
    happy_threshold=60.0,
    min_smile_frames=5,
    process_every_n=6,     # antes 2 -> analiza 1 de cada 6 frames
    detector_backend="opencv",  # más ligero que 'retinaface'
    capture_path=CAPTURE_PATH,
)
smile_detector.start()




# =========================
#   RUTAS WEB
# =========================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/listen-command", methods=["POST"])
def listen_command():
    print("🎤 Web pide activar escucha...")
    
    try:
        prompt = motor_voz.escuchar_y_obtener_prompt()
        
        if prompt:
            # ✅ Marcamos que la fase de voz/STT ha terminado correctamente
            pipeline_flags["speech_done"] = True

            return jsonify({
                "ok": True,
                "transcript": prompt
            })
        else:
            return jsonify({
                "ok": False,
                "message": "No se detectó comando o se canceló."
            }), 400

    except Exception as e:
        print(f"❌ Error en el motor de voz: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =========================
#   OTROS ENDPOINTS (ESTADO, IMAGENES...)
# =========================

@app.route("/api/status")
def api_status():
    """
    Devuelve el estado del pipeline para la UI:
      - progress_percent: 0-100
      - current_stage: id del paso actual
      - stages: lista con id y status ('pending' | 'active' | 'done')
    """

    # --- 1) Estado de la cara / sonrisa ---
    smile_state = smile_detector.get_state()
    face_present = smile_state.get("face_present", False)
    photo_taken = smile_state.get("photo_taken", False)

    # Lógica sencilla:
    # - Sin cara: face_detect = active, face_capture = pending
    # - Cara pero sin foto: face_detect = done, face_capture = active
    # - Foto hecha: face_detect = done, face_capture = done
    if photo_taken:
        face_detect_status = "done"
        face_capture_status = "done"
    elif face_present:
        face_detect_status = "done"
        face_capture_status = "active"
    else:
        face_detect_status = "active"
        face_capture_status = "pending"

    # --- 2) Estado de voz ---
    speech_done = pipeline_flags.get("speech_done", False)
    speech_status = "done" if speech_done else "pending"

    # Más adelante podrás cambiar estos cuando añadas IA, contornos, robot...
    ia_edit_status = "pending"
    contours_status = "pending"
    robot_draw_status = "pending"

    stages = [
        {"id": "face_detect",  "status": face_detect_status},
        {"id": "face_capture", "status": face_capture_status},
        {"id": "speech",       "status": speech_status},
        {"id": "ia_edit",      "status": ia_edit_status},
        {"id": "contours",     "status": contours_status},
        {"id": "robot_draw",   "status": robot_draw_status},
    ]

    # --- 3) Progreso global (porcentaje) ---
    done_count = sum(1 for s in stages if s["status"] == "done")
    total = len(stages)
    progress_percent = int(100 * done_count / total) if total > 0 else 0

    # --- 4) Etapa actual (primera que no está 'done') ---
    current_stage = "idle"
    for s in stages:
        if s["status"] != "done":
            current_stage = s["id"]
            break

    return jsonify({
        "progress_percent": progress_percent,
        "current_stage": current_stage,
        "stages": stages
    })

@app.route("/api/ia-image-url")
def ia_image_url():
    return jsonify({"url": url_for("static", filename="img/ia_placeholder.jpg")})


@app.route("/robot_stream")
def robot_stream():
    return url_for('static', filename='img/robot_placeholder.jpg')


@app.route("/api/face-frame")
def api_face_frame():
    """
    Devuelve el último frame de la cámara (con textos/caja) como JPEG.
    El frontend lo usará en el <img> de "Reconocimiento facial".
    """
    jpeg = smile_detector.get_frame_jpeg()
    if jpeg is None:
        # Si aún no hay frame, devolvemos el placeholder estático
        return app.send_static_file("img/face_placeholder.jpg")
    return Response(jpeg, mimetype="image/jpeg")


@app.route("/api/face-status")
def api_face_status():
    """
    Devuelve estado del detector de sonrisas:
    {
      happy, happy_threshold, face_present, photo_taken, capture_path, ...
    }
    """
    return jsonify(smile_detector.get_state())

@app.route("/face_stream")
def face_stream():
    # Por compatibilidad, devolvemos la URL del endpoint de frame
    return url_for("api_face_frame")


if __name__ == "__main__":
    # use_reloader=False es vital para no cargar el modelo Vosk dos veces
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)