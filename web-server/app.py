import os
import sys
from flask import Flask, render_template, jsonify, url_for
from flask_cors import CORS

# --- 1. IMPORTACIÓN LIMPIA DEL MÓDULO SUPERIOR ---
# Añadimos la carpeta de arriba ("..") a las rutas de Python para poder importar
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(project_root)

# Ahora importamos tu clase directamente. Sin reescribir nada.
from voice_module import VoiceEngine

app = Flask(__name__)
CORS(app)

# --- 2. INICIALIZAR TU MOTOR ---
# Definimos la ruta al modelo relativa a la raíz del proyecto
MODEL_PATH = os.path.join(project_root, "vosk-model-small-es-0.42")

print(f"⚙️ Inicializando VoiceEngine desde: {MODEL_PATH}")
# Instanciamos tu clase. Ella se encarga de cargar Vosk, el traductor, etc.
motor_voz = VoiceEngine(MODEL_PATH)


# =========================
#   RUTAS WEB
# =========================

@app.route("/")
def index():
    return render_template("index.html")

# --- ENDPOINT CLAVE: USA TU SCRIPT ---
@app.route("/api/listen-command", methods=["POST"])
def listen_command():
    print("🎤 Web pide activar escucha...")
    
    try:
        # USAMOS TU MÉTODO DIRECTAMENTE
        # Esto bloqueará la ejecución hasta que tu script 'voice_module.py'
        # detecte la frase, la valide como navideña, la traduzca y devuelva el prompt.
        prompt = motor_voz.escuchar_y_obtener_prompt()
        
        if prompt:
            return jsonify({
                "ok": True,
                "transcript": prompt  # Devolvemos exactamente lo que generó tu script
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
    # Demo status
    return jsonify({
        "progress_percent": 0,
        "current_stage": "idle",
        "stages": [] # Puedes rellenar esto si quieres mostrar el timeline
    })

@app.route("/api/ia-image-url")
def ia_image_url():
    return jsonify({"url": url_for("static", filename="img/ia_placeholder.jpg")})

@app.route("/face_stream")
def face_stream():
    return url_for('static', filename='img/face_placeholder.jpg')

@app.route("/robot_stream")
def robot_stream():
    return url_for('static', filename='img/robot_placeholder.jpg')


if __name__ == "__main__":
    # use_reloader=False es vital para no cargar el modelo Vosk dos veces
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)