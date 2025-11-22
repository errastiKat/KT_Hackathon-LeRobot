import os
from google import genai
from google.genai import types
from PIL import Image
import io

# --- TU CLAVE DE API (Cuidado: cámbiala o bórrala del chat después) ---
API_KEY = "AIzaSyBX29lNKrRmVi1P-WJfLZwyf7TiNJTAzg8"

# Configuración de archivos
INPUT_IMAGE_PATH = "/home/errastikat/Descargas/2025-11-21-192708.jpg" 
OUTPUT_IMAGE_PATH = "mi_foto_navidad.png"
PROMPT = "Ponme un gorro de navidad."
MODEL_NAME = "gemini-2.5-flash-image" 

def editar_imagen_definitivo():
    print(f"🔹 Iniciando proceso con imagen: {INPUT_IMAGE_PATH}")

    # 1. Cliente
    client = genai.Client(api_key=API_KEY)

    # 2. Cargar imagen
    try:
        img = Image.open(INPUT_IMAGE_PATH)
        print(f"🔹 Imagen cargada. Tamaño: {img.size}")
    except FileNotFoundError:
        print(f"❌ ERROR: No existe el archivo {INPUT_IMAGE_PATH}")
        return

    # 3. Llamada a la API (Usando generate_content)
    # Usamos generate_content porque estamos enviando una imagen + texto
    print(f"🔹 Enviando a {MODEL_NAME}...")
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[PROMPT, img]
        )
    except Exception as e:
        print(f"❌ ERROR CRÍTICO DE API: {e}")
        return

    # 4. Procesar la respuesta MANUALMENTE
    # Buscamos en las 'partes' de la respuesta si hay una imagen
    image_found = False
    
    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            
            # Caso A: La API devuelve una imagen en bytes (inline_data)
            if part.inline_data:
                print("✅ ¡La API devolvió datos de imagen!")
                try:
                    # Convertir bytes a imagen
                    image_bytes = part.inline_data.data
                    image_output = Image.open(io.BytesIO(image_bytes))
                    image_output.save(OUTPUT_IMAGE_PATH)
                    print(f"🎉 ¡ÉXITO! Imagen guardada en: {OUTPUT_IMAGE_PATH}")
                    image_found = True
                except Exception as e:
                    print(f"⚠️ Error al guardar la imagen recibida: {e}")

            # Caso B: La API devuelve texto (A veces se niega a editar o describe la imagen)
            if part.text:
                print(f"\n📝 La API respondió con texto: '{part.text}'")
                if "sorry" in part.text.lower() or "cannot" in part.text.lower() or "no puedo" in part.text.lower():
                    print("⚠️ AVISO: Es posible que este modelo se niegue a editar personas reales o imágenes por políticas de seguridad.")

    if not image_found:
        print("\n❌ El script terminó sin guardar ninguna imagen nueva.")
        print("Posibles causas:")
        print("1. El modelo respondió solo con texto (mira arriba).")
        print("2. El modelo 'gemini-2.5-flash-image' aún no soporta salida de imagen en esta versión.")

if __name__ == "__main__":
    editar_imagen_definitivo()