import os
import sys
import json
import base64
import cv2
import numpy as np
from flask import Flask, render_template, jsonify, url_for, Response, request
from flask_cors import CORS
from google import genai
from PIL import Image
import io

# --- 1. IMPORTACIÓN DEL MÓDULO SUPERIOR (VOZ) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(project_root)

from voice_module import VoiceEngine

app = Flask(__name__)
CORS(app)

# =========================
#  CONFIGURACIÓN: VOZ (VOSK)
# =========================
MODEL_PATH = os.path.join(project_root, "vosk-model-small-es-0.42")
print(f"⚙️ Inicializando VoiceEngine desde: {MODEL_PATH}")

try:
    # Inicializamos el motor de voz (Micrófono del SERVIDOR/PC)
    motor_voz = VoiceEngine(MODEL_PATH)
except Exception as e:
    print(f"⚠️ Error cargando voz (¿falta modelo?): {e}")
    motor_voz = None

# =========================
#  CONFIGURACIÓN: VISIÓN (OPENCV)
# =========================
# Usamos Haar Cascades porque son rápidos para procesar peticiones HTTP
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
smile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_smile.xml')

# Directorios de imágenes
STATIC_DIR = os.path.join(current_dir, "static")
CAPTURE_REL = os.path.join("img", "smile_capture.jpg")
CAPTURE_PATH = os.path.join(STATIC_DIR, CAPTURE_REL)
IA_OUTPUT_REL = os.path.join("img", "ia_result.png")
IA_OUTPUT_PATH = os.path.join(STATIC_DIR, IA_OUTPUT_REL)

os.makedirs(os.path.dirname(CAPTURE_PATH), exist_ok=True)

# =========================
#  ESTADO GLOBAL DEL PIPELINE
# =========================
pipeline_flags = {
    "face_detected": False,
    "smile_detected": False,
    "happy_score": 0,
    "photo_taken": False,
    
    "speech_done": False,
    "last_prompt": None,
    
    "ia_in_progress": False,
    "ia_done": False,
}

# =========================
#  CONFIGURACIÓN: GEMINI API
# =========================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL_NAME = "gemini-1.5-flash" # Ajusta según tu disponibilidad (o 2.5-flash si tienes acceso)

# =========================
#  RUTAS FLASK
# =========================

@app.route("/")
def index():
    return render_template("index.html")

# --- 1. PROCESAR FRAME DEL IPHONE (VISIÓN) ---
@app.route("/api/process-frame", methods=["POST"])
def process_frame():
    """
    Recibe una imagen en Base64 desde el navegador (iPhone),
    detecta si hay cara/sonrisa y guarda la foto si corresponde.
    """
    try:
        data = request.json
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({"ok": False, "error": "No image data"}), 400

        # 1. Decodificar Base64 a imagen OpenCV
        # Formato data:image/jpeg;base64,/9j/4AAQSk...
        header, encoded = image_data.split(",", 1)
        nparr = np.frombuffer(base64.b64decode(encoded), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # 2. Detección de Rostro y Sonrisa
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        face_present = len(faces) > 0
        is_smiling = False
        current_score = 0

        for (x, y, w, h) in faces:
            roi_gray = gray[y:y+h, x:x+w]
            # Ajustar parámetros (1.8, 20) si detecta muchas falsas sonrisas
            smiles = smile_cascade.detectMultiScale(roi_gray, 1.8, 20)
            
            if len(smiles) > 0:
                is_smiling = True
                current_score = 90  # Valor simulado alto
            else:
                current_score = 10  # Valor simulado bajo

        # 3. Lógica de Captura Automática
        if is_smiling and not pipeline_flags["photo_taken"]:
            cv2.imwrite(CAPTURE_PATH, frame)
            pipeline_flags["photo_taken"] = True
            print("📸 ¡Sonrisa detectada en iPhone y guardada en servidor!")

        # 4. Actualizar flags globales
        pipeline_flags["face_detected"] = face_present
        pipeline_flags["smile_detected"] = is_smiling
        pipeline_flags["happy_score"] = current_score

        return jsonify({
            "ok": True,
            "face": face_present,
            "smile": is_smiling,
            "taken": pipeline_flags["photo_taken"]
        })

    except Exception as e:
        print(f"❌ Error procesando frame: {e}")
        return jsonify({"ok": False}), 500


# --- 2. PROCESAR VOZ (AUDIO) ---
@app.route("/api/listen-command", methods=["POST"])
def listen_command():
    print("🎤 Web pide activar escucha (Micrófono del SERVIDOR)...")
    
    if not motor_voz:
        return jsonify({"ok": False, "message": "Motor de voz no disponible"}), 500

    try:
        # Escucha por el micro del PC Ubuntu
        prompt = motor_voz.escuchar_y_obtener_prompt()
        
        if prompt:
            pipeline_flags["speech_done"] = True
            pipeline_flags["last_prompt"] = prompt
            
            # Si cambiamos el prompt, reseteamos la IA para permitir generar de nuevo
            pipeline_flags["ia_done"] = False
            pipeline_flags["ia_in_progress"] = False
            
            return jsonify({"ok": True, "transcript": prompt})
        else:
            return jsonify({"ok": False, "message": "No se detectó comando o se canceló."}), 400

    except Exception as e:
        print(f"❌ Error voz: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# --- 3. ESTADO GLOBAL (STATUS) ---
@app.route("/api/status")
def api_status():
    """Devuelve el estado de todo el sistema para que el JS actualice la UI"""
    
    photo_taken = pipeline_flags["photo_taken"]
    face_present = pipeline_flags["face_detected"]
    
    # Lógica de estados para el Timeline
    face_status = "done" if photo_taken else ("active" if face_present else "active")
    capture_status = "done" if photo_taken else "pending"
    speech_status = "done" if pipeline_flags["speech_done"] else "pending"
    
    ia_status = "pending"
    if pipeline_flags["ia_done"]: 
        ia_status = "done"
    elif pipeline_flags["ia_in_progress"]: 
        ia_status = "active"
    elif photo_taken and pipeline_flags["speech_done"]: 
        # Si hay foto y voz, la IA está lista (aunque pendiente de disparar)
        ia_status = "pending"

    stages = [
        {"id": "face_detect",  "status": face_status},
        {"id": "face_capture", "status": capture_status},
        {"id": "speech",       "status": speech_status},
        {"id": "ia_edit",      "status": ia_status},
        {"id": "robot_draw",   "status": "pending"},
    ]

    # Calcular porcentaje
    done_count = sum(1 for s in stages if s["status"] == "done")
    progress_percent = int(100 * done_count / len(stages))

    return jsonify({
        "progress_percent": progress_percent,
        "stages": stages,
        # Extras para las píldoras de estado
        "happy": pipeline_flags["happy_score"],
        "happy_threshold": 50,
        "face_present": face_present,
        "photo_taken": photo_taken
    })


# --- 4. GENERAR IMAGEN (IA) ---
@app.route("/api/run-ia", methods=["POST"])
def api_run_ia():
    if not GEMINI_API_KEY:
        return jsonify({"ok": False, "error": "Falta GEMINI_API_KEY"}), 500
    
    # Validaciones previas
    if not pipeline_flags["photo_taken"]:
        return jsonify({"ok": False, "error": "Falta la foto"}), 400
    if not pipeline_flags["last_prompt"]:
        return jsonify({"ok": False, "error": "Falta el comando de voz"}), 400
    if pipeline_flags["ia_in_progress"]:
        return jsonify({"ok": False, "error": "IA ocupada"}), 409

    pipeline_flags["ia_in_progress"] = True
    print("✨ Ejecutando Gemini...")

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        if not os.path.exists(CAPTURE_PATH):
            raise Exception("No encuentro el archivo smile_capture.jpg")
            
        img = Image.open(CAPTURE_PATH)
        
        # Llamada a Gemini
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=[pipeline_flags["last_prompt"], img]
        )
        
        # Procesar respuesta (Buscar imagen dentro)
        found_image = False
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if getattr(part, "inline_data", None):
                    image_bytes = part.inline_data.data
                    image_output = Image.open(io.BytesIO(image_bytes))
                    image_output.save(IA_OUTPUT_PATH)
                    found_image = True
                    break
        
        pipeline_flags["ia_in_progress"] = False
        
        if found_image:
            pipeline_flags["ia_done"] = True
            return jsonify({"ok": True, "url": url_for("static", filename=IA_OUTPUT_REL)})
        else:
            return jsonify({"ok": False, "error": "La IA no devolvió una imagen"}), 500

    except Exception as e:
        pipeline_flags["ia_in_progress"] = False
        print(f"❌ Error IA: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# Helper para obtener la URL actual de la imagen IA
@app.route("/api/ia-image-url")
def ia_image_url():
    if pipeline_flags["ia_done"]:
        return jsonify({"url": url_for("static", filename=IA_OUTPUT_REL)})
    return jsonify({"url": url_for("static", filename="img/ia_placeholder.jpg")})

# --- 5. RESET ---
@app.route("/api/reset")
def api_reset():
    pipeline_flags["photo_taken"] = False
    pipeline_flags["face_detected"] = False
    pipeline_flags["smile_detected"] = False
    pipeline_flags["speech_done"] = False
    pipeline_flags["ia_done"] = False
    pipeline_flags["ia_in_progress"] = False
    print("🔄 Sistema reseteado")
    return jsonify({"ok": True})

# --- ROBOT STREAM (Placeholder) ---
@app.route("/robot_stream")
def robot_stream():
    return url_for('static', filename='img/robot_placeholder.jpg')


if __name__ == "__main__":
    # Recuerda usar NGROK para acceder desde iPhone con HTTPS:
    # ngrok http 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
