import os
import sys
import json
import base64
import cv2
import numpy as np
from flask import Flask, render_template, jsonify, request, url_for
from flask_cors import CORS
from google import genai
from PIL import Image
import io

# --- Configuración de directorios ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(project_root)
STATIC_DIR = os.path.join(current_dir, "static")
CAPTURE_REL = os.path.join("img", "smile_capture.jpg")
CAPTURE_PATH = os.path.join(STATIC_DIR, CAPTURE_REL)
IA_OUTPUT_REL = os.path.join("img", "ia_result.png")
IA_OUTPUT_PATH = os.path.join(STATIC_DIR, IA_OUTPUT_REL)

os.makedirs(os.path.dirname(CAPTURE_PATH), exist_ok=True)

# --- Importamos tu motor de voz (se ejecuta en el servidor) ---
# NOTA: Si usas el iPhone, el micrófono que grabará será el del PORTÁTIL
# a menos que cambies la lógica de voz al navegador también.
from voice_module import VoiceEngine
MODEL_PATH = os.path.join(project_root, "vosk-model-small-es-0.42")
try:
    motor_voz = VoiceEngine(MODEL_PATH)
except:
    print("⚠️ No se pudo cargar el motor de voz (¿falta el modelo?).")
    motor_voz = None

app = Flask(__name__)
CORS(app)

# =========================
#  VARIABLES DE ESTADO
# =========================
pipeline_flags = {
    "face_detected": False,
    "smile_detected": False,
    "photo_taken": False,
    "happy_score": 0,
    "speech_done": False,
    "last_prompt": None,
    "ia_in_progress": False,
    "ia_done": False,
}

# Detección de rostro (usamos Haar Cascades por rapidez en HTTP)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
smile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_smile.xml')

# =========================
#  NUEVA RUTA: PROCESAR FRAMES DEL IPHONE
# =========================
@app.route("/api/process-frame", methods=["POST"])
def process_frame():
    """
    Recibe un frame en base64 desde el navegador (iPhone),
    detecta sonrisa y actualiza el estado.
    """
    try:
        data = request.json
        image_data = data['image']
        
        # 1. Decodificar Base64 a Imagen OpenCV
        # Quitamos el header "data:image/jpeg;base64,"
        header, encoded = image_data.split(",", 1)
        nparr = np.frombuffer(base64.b64decode(encoded), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # 2. Procesamiento de Visión (Detección Básica de Sonrisa)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        is_smiling = False
        happy_score = 0
        face_present = len(faces) > 0

        for (x, y, w, h) in faces:
            roi_gray = gray[y:y+h, x:x+w]
            # Ajustar parámetros de smile según luz/cámara (scaleFactor, minNeighbors)
            smiles = smile_cascade.detectMultiScale(roi_gray, 1.8, 20)
            
            if len(smiles) > 0:
                is_smiling = True
                happy_score = 100 # Simplificado para demo
            
            # Dibujar rectángulo (opcional, solo si devolvemos la imagen procesada)
            # cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)

        # 3. Lógica de Captura Automática
        # Si sonríe y no hemos tomado la foto aún
        if is_smiling and not pipeline_flags["photo_taken"]:
            cv2.imwrite(CAPTURE_PATH, frame)
            pipeline_flags["photo_taken"] = True
            print("📸 Foto capturada desde iPhone!")

        # 4. Actualizar estado global
        pipeline_flags["face_detected"] = face_present
        pipeline_flags["smile_detected"] = is_smiling
        pipeline_flags["happy_score"] = happy_score

        return jsonify({
            "ok": True,
            "face": face_present,
            "smile": is_smiling,
            "taken": pipeline_flags["photo_taken"]
        })

    except Exception as e:
        print(f"Error procesando frame: {e}")
        return jsonify({"ok": False}), 500

# =========================
#  RUTAS DE ESTADO (IGUAL QUE ANTES)
# =========================
@app.route("/api/status")
def api_status():
    # Mapeamos las flags simples al formato que espera tu frontend
    face_status = "done" if pipeline_flags["photo_taken"] else ("active" if pipeline_flags["face_detected"] else "active")
    capture_status = "done" if pipeline_flags["photo_taken"] else "pending"
    
    stages = [
        {"id": "face_detect", "status": face_status},
        {"id": "face_capture", "status": capture_status},
        {"id": "speech", "status": "done" if pipeline_flags["speech_done"] else "pending"},
        {"id": "ia_edit", "status": "done" if pipeline_flags["ia_done"] else ("active" if pipeline_flags["ia_in_progress"] else "pending")},
    ]
    
    # Calcular progreso simple
    done = sum(1 for s in stages if s["status"] == "done")
    progress = int((done / 4) * 100)

    return jsonify({
        "progress_percent": progress,
        "stages": stages,
        # Datos extra para los pills
        "happy": pipeline_flags["happy_score"],
        "happy_threshold": 50,
        "photo_taken": pipeline_flags["photo_taken"],
        "face_present": pipeline_flags["face_detected"]
    })

# =========================
#  RUTAS RESTANTES (VOZ / IA)
# =========================

@app.route("/")
def index():
    return render_template("index_mobile.html") # Usaremos un template nuevo

@app.route("/api/listen-command", methods=["POST"])
def listen_command():
    # Tu lógica existente de voz
    if not motor_voz: return jsonify({"ok": False, "message": "Motor voz no cargado"}), 500
    prompt = motor_voz.escuchar_y_obtener_prompt()
    if prompt:
        pipeline_flags["speech_done"] = True
        pipeline_flags["last_prompt"] = prompt
        return jsonify({"ok": True, "transcript": prompt})
    return jsonify({"ok": False, "message": "No entendido"}), 400

@app.route("/api/run-ia", methods=["POST"])
def api_run_ia():
    # Tu lógica existente de IA (Gemini)
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY: return jsonify({"error": "No Key"}), 500
    
    pipeline_flags["ia_in_progress"] = True
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        img = Image.open(CAPTURE_PATH)
        response = client.models.generate_content(
            model="gemini-2.0-flash", # O el modelo que uses
            contents=[pipeline_flags["last_prompt"], img]
        )
        # ... (Lógica de guardar imagen igual que tu código original) ...
        # SIMULACION DE GUARDADO PARA QUE FUNCIONE EL EJEMPLO:
        # En tu código real pega aquí tu bloque de decodificación de gemini
        pipeline_flags["ia_done"] = True
        pipeline_flags["ia_in_progress"] = False
        return jsonify({"ok": True, "url": url_for("static", filename=IA_OUTPUT_REL)})
    except Exception as e:
        pipeline_flags["ia_in_progress"] = False
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/ia-image-url")
def ia_image_url():
    if pipeline_flags["ia_done"]:
        return jsonify({"url": url_for("static", filename=IA_OUTPUT_REL)})
    return jsonify({"url": url_for("static", filename="img/ia_placeholder.jpg")})

# Reset para pruebas
@app.route("/api/reset")
def reset():
    pipeline_flags["photo_taken"] = False
    pipeline_flags["smile_detected"] = False
    pipeline_flags["speech_done"] = False
    pipeline_flags["ia_done"] = False
    return jsonify({"ok": True})

if __name__ == "__main__":
    # Importante: 0.0.0.0 para que sea visible en la red
    # SSL context='adhoc' es OBLIGATORIO para que el iPhone permita usar la cámara web
    # Sin SSL, iOS bloquea el acceso a la cámara en redes que no sean localhost.
    app.run(host="0.0.0.0", port=5000, debug=True, ssl_context=('cert.pem', 'key.pem'))
