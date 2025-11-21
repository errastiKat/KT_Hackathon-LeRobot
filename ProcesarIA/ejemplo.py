# ==========================================
#  CÓDIGO CLIENTE (TU ORDENADOR LOCAL)
# ==========================================
import requests
import os
import cv2 # Solo para mostrar el resultado si quieres, no esencial para el envío

# --- CONFIGURACIÓN ---
# 🔴 IMPORTANTE: Cada vez que inicies Colab, esta URL cambia. ¡Actualízala!
URL_COLAB = "https://johnsie-presumptive-undeprecatively.ngrok-free.dev"  # <-- PEGA LA URL DE COLAB AQUÍ

def obtener_lineart_ia(ruta_imagen_local, estilo_deseado):
    """
    Envía la foto al servidor Colab y guarda la respuesta procesada.
    """
    endpoint = f"{URL_COLAB}/dibujame"
    
    print(f"📡 Conectando con el cerebro IA en: {URL_COLAB}")
    print(f"🎨 Solicitando estilo: '{estilo_deseado}'...")

    try:
        # Preparamos los archivos y datos
        files = {'image': open(ruta_imagen_local, 'rb')}
        data = {'estilo': estilo_deseado}
        
        # Hacemos la petición POST
        response = requests.post(endpoint, files=files, data=data)
        
        # Verificamos si todo fue bien (Código 200 = OK)
        if response.status_code == 200:
            nombre_salida = "resultado_para_robot.png"
            
            # Guardamos la imagen recibida
            with open(nombre_salida, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ ¡ÉXITO! Imagen guardada como: {nombre_salida}")
            return nombre_salida
        else:
            print(f"❌ Error del servidor (Código {response.status_code}):")
            print(response.text)
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se puede conectar. ¿Está corriendo el Colab? ¿La URL es correcta?")
        return None
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return None

# --- BLOQUE PRINCIPAL (Para probarlo) ---
if __name__ == "__main__":
    # 1. Pon la ruta COMPLETA a tu archivo
    # Python maneja bien los espacios y acentos si la cadena está entre comillas
    foto_test = "/home/errastikat/Imágenes/Cámara web/2025-11-21-192708.jpg" 
    
# Verificación de seguridad
    if not os.path.exists(foto_test):
        print(f"⚠️ NO ENCUENTRO LA FOTO EN: {foto_test}")
    else:
        # 2. Llamada a la función
        print("🚀 Iniciando prueba...")
        resultado = obtener_lineart_ia(foto_test, "christmas elf")
        
        # 3. Resultado
        if resultado:
            print("--> ¡Todo listo! Imagen guardada.")