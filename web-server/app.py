import os
import sys
import json
from flask import Flask, render_template, jsonify, url_for, Response, request
from flask_cors import CORS

from google import genai
from PIL import Image
import io

# --- 1. IMPORTACIÓN LIMPIA DEL MÓDULO SUPERIOR ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(project_root)

from voice_module import VoiceEngine
from reconcoimiento_facial.smile_detector import SmileDetector


app = Flask(__name__)
CORS(app)

# =========================
#   VOICE ENGINE (VOSK)
# =========================

MODEL_PATH = os.path.join(project_root, "vosk-model-small-es-0.42")

print(f"⚙️ Inicializando VoiceEngine desde: {MODEL_PATH}")
motor_voz = VoiceEngine(MODEL_PATH)

# =========================
#   ESTADO DEL PIPELINE
# =========================

pipeline_flags = {
    "speech_done": False,      # /api/listen-command OK
    "last_prompt": None,       # prompt final en inglés
    "ia_in_progress": False,   # IA generativa en marcha
    "ia_done": False,          # IA generativa terminada
}

# =========================
#   SMILE DETECTOR
# =========================

STATIC_DIR = os.path.join(current_dir, "static")

# Foto de la cara (entrada a la IA)
CAPTURE_REL = os.path.join("img", "smile_capture.jpg")
CAPTURE_PATH = os.path.join(STATIC_DIR, CAPTURE_REL)
os.makedirs(os.path.dirname(CAPTURE_PATH), exist_ok=True)

print(f"📸 Inicializando SmileDetector. Foto irá a: {CAPTURE_PATH}")
smile_detector = SmileDetector(
    cam_index=0,
    frame_w=1280,
    frame_h=720,
    happy_threshold=60.0,
    min_smile_frames=5,
    process_every_n=6,
    detector_backend="opencv",
    capture_path=CAPTURE_PATH,
)
smile_detector.start()

# =========================
#   CONFIG IA (GEMINI)
# =========================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL_NAME = "gemini-2.5-flash-image"

# Imagen salida IA
IA_OUTPUT_REL = os.path.join("img", "ia_result.png")
IA_OUTPUT_PATH = os.path.join(STATIC_DIR, IA_OUTPUT_REL)


# =========================
#   RUTAS WEB
# =========================

@app.route("/")
def index():
    return render_template("index.html")


# -------------------------
#   VOZ → PROMPT
# -------------------------
@app.route("/api/listen-command", methods=["POST"])
def listen_command():
    print("🎤 Web pide activar escucha...")
    
    try:
        prompt = motor_voz.escuchar_y_obtener_prompt()
        
        if prompt:
            # ✅ Marcamos que la fase de voz/STT ha terminado correctamente
            pipeline_flags["speech_done"] = True
            pipeline_flags["last_prompt"] = prompt

            # Cuando hay prompt nuevo, reseteamos la IA generativa
            pipeline_flags["ia_done"] = False
            pipeline_flags["ia_in_progress"] = False
            # (opcional: podrías borrar la imagen anterior ia_result.png)

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


# -------------------------
#   ESTADO GLOBAL PIPELINE
# -------------------------
@app.route("/api/status")
def api_status():
    """
    Devuelve el estado del pipeline para la UI:
      - progress_percent: 0-100
      - current_stage: id del paso actual
      - stages: lista con id y status ('pending' | 'active' | 'done')
    """

    # 1) Cara / sonrisa / captura
    smile_state = smile_detector.get_state()
    face_present = smile_state.get("face_present", False)
    photo_taken = smile_state.get("photo_taken", False)

    if photo_taken:
        face_detect_status = "done"
        face_capture_status = "done"
    elif face_present:
        face_detect_status = "done"
        face_capture_status = "active"
    else:
        face_detect_status = "active"
        face_capture_status = "pending"

    # 2) Voz
    speech_done = pipeline_flags.get("speech_done", False)
    speech_status = "done" if speech_done else "pending"

    # 3) IA generativa
    ia_done = pipeline_flags.get("ia_done", False)
    ia_in_progress = pipeline_flags.get("ia_in_progress", False)

    if ia_done:
        ia_edit_status = "done"
    elif ia_in_progress:
        ia_edit_status = "active"
    else:
        # Solo tiene sentido activar IA cuando cara y voz están listas
        if photo_taken and speech_done:
            ia_edit_status = "active"  # el frontend puede usar esto para mostrar "listo para IA"
        else:
            ia_edit_status = "pending"

    # 4) Contornos / robot (por ahora pendientes)
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

    done_count = sum(1 for s in stages if s["status"] == "done")
    total = len(stages)
    progress_percent = int(100 * done_count / total) if total > 0 else 0

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


# -------------------------
#   IA: LANZAR PROCESO
# -------------------------
@app.route("/api/run-ia", methods=["POST"])
def api_run_ia():
    """
    Lanza el procesado IA:
      - Usa la foto de SmileDetector (smile_capture.jpg)
      - Usa el último prompt de VoiceEngine
      - Llama al modelo Gemini y guarda ia_result.png
    """
    if GEMINI_API_KEY is None:
        return jsonify({
            "ok": False,
            "error": "GEMINI_API_KEY no está definida en el entorno"
        }), 500

    # Comprobamos que haya foto
    smile_state = smile_detector.get_state()
    if not smile_state.get("photo_taken", False):
        return jsonify({
            "ok": False,
            "error": "Todavía no hay foto capturada."
        }), 400

    # Comprobamos que haya prompt
    prompt = pipeline_flags.get("last_prompt")
    if not prompt:
        return jsonify({
            "ok": False,
            "error": "Todavía no hay prompt de voz válido."
        }), 400

    # Evitar dobles ejecuciones simultáneas
    if pipeline_flags.get("ia_in_progress", False):
        return jsonify({
            "ok": False,
            "error": "La IA ya está procesando."
        }), 409

    print("✨ Lanzando IA generativa con Gemini...")
    pipeline_flags["ia_in_progress"] = True

    try:
        # 1) Cliente
        client = genai.Client(api_key=GEMINI_API_KEY)

        # 2) Cargar la imagen capturada
        if not os.path.exists(CAPTURE_PATH):
            pipeline_flags["ia_in_progress"] = False
            return jsonify({
                "ok": False,
                "error": f"No se encuentra la imagen de entrada en {CAPTURE_PATH}"
            }), 500

        img = Image.open(CAPTURE_PATH)

        # 3) Llamada al modelo
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=[prompt, img]
        )

        # 4) Buscar imagen en la respuesta
        image_found = False
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if getattr(part, "inline_data", None):
                    try:
                        image_bytes = part.inline_data.data
                        image_output = Image.open(io.BytesIO(image_bytes))
                        os.makedirs(os.path.dirname(IA_OUTPUT_PATH), exist_ok=True)
                        image_output.save(IA_OUTPUT_PATH)
                        image_found = True
                        print(f"🎉 IA: imagen guardada en {IA_OUTPUT_PATH}")
                        break
                    except Exception as e:
                        print(f"⚠️ Error guardando la imagen devuelta por la IA: {e}")

                if getattr(part, "text", None):
                    print(f"📝 Respuesta IA (texto): {part.text}")

        if not image_found:
            pipeline_flags["ia_in_progress"] = False
            return jsonify({
                "ok": False,
                "error": "La IA no devolvió ninguna imagen nueva."
            }), 500

        # Éxito
        pipeline_flags["ia_in_progress"] = False
        pipeline_flags["ia_done"] = True

        return jsonify({
            "ok": True,
            "url": url_for("static", filename=IA_OUTPUT_REL)
        })

    except Exception as e:
        pipeline_flags["ia_in_progress"] = False
        print(f"❌ Error crítico en IA: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# -------------------------
#   IA: URL DE LA IMAGEN
# -------------------------
@app.route("/api/ia-image-url")
def ia_image_url():
    """
    Devuelve la URL de la imagen IA:
      - Si hay resultado: ia_result.png
      - Si no, el placeholder original.
    """
    if pipeline_flags.get("ia_done", False) and os.path.exists(IA_OUTPUT_PATH):
        return jsonify({"url": url_for("static", filename=IA_OUTPUT_REL)})
    else:
        return jsonify({"url": url_for("static", filename="img/ia_placeholder.jpg")})


# -------------------------
#   ROBOT CAM (placeholder)
# -------------------------
@app.route("/robot_stream")
def robot_stream():
    return url_for('static', filename='img/robot_placeholder.jpg')


# -------------------------
#   FACE: FRAME + ESTADO
# -------------------------
@app.route("/api/face-frame")
def api_face_frame():
    jpeg = smile_detector.get_frame_jpeg()
    if jpeg is None:
        return app.send_static_file("img/face_placeholder.jpg")
    return Response(jpeg, mimetype="image/jpeg")


@app.route("/api/face-status")
def api_face_status():
    return jsonify(smile_detector.get_state())


@app.route("/face_stream")
def face_stream():
    return url_for("api_face_frame")


if __name__ == "__main__":
    # use_reloader=False es vital para no cargar el modelo Vosk dos veces
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
