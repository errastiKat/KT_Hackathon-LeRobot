from voice_module import VoiceEngine
import os

# Configuración automática: busca el modelo en la carpeta actual
current_dir = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(current_dir, "vosk-model-small-es-0.42")

# Pon None para usar el micro por defecto. Si falla, probaremos otra cosa.
MIC_INDEX = None 

def main():
    print("--- INICIO PRUEBA DE VOZ ---")
    
    # Inicializamos motor
    engine = VoiceEngine(MODEL_PATH, MIC_INDEX)
    
    print("📸 (Simulando que ya sacamos la foto...)")
    print("❓ Hola usuario, ¿qué quieres añadir a tu dibujo? (Gorro, elfo, gafas...)")
    
    # Llamada bloqueante
    prompt = engine.escuchar_y_obtener_prompt()
    
    if prompt:
        print("\n" + "="*40)
        print("✅ ÉXITO. ESTE ES EL PROMPT PARA LA IA:")
        print(prompt)
        print("="*40 + "\n")

if __name__ == "__main__":
    main()