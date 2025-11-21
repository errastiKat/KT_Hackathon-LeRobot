# Módulo de Voz – Generador de Prompts (Hackathon LeRobot)

Este módulo gestiona la **interacción por voz** con el usuario para el proyecto del robot dibujante.

**Funcionalidades principales:**

1. **Reconocimiento de voz offline** (español) usando **Vosk**.  
2. **Filtro temático:** asegura que las peticiones sean **navideñas** o relacionadas con la **cara**.  
3. **Traducción automática:** convierte la petición de **español a inglés**.  
4. **Ingeniería de prompt:** genera un prompt técnico optimizado para **Stable Diffusion / ControlNet** (estilo *line art*, B/N, sin sombras).

---

## Requisitos del sistema (Linux/Ubuntu)

IMPORTANTE: Antes de instalar las librerías de Python, necesitas instalar primero las herramientas de audio del sistema operativo.  
Si no haces esto, la instalación de `pyaudio` puede fallar.

Abre una terminal y ejecuta:

```bash
sudo apt-get update
sudo apt-get install python3-venv portaudio19-dev unzip
````

---

## Instalación

Sigue estos pasos para configurar el entorno aislado y descargar el modelo.

### 1. Configurar el entorno virtual

Sitúate en la carpeta raíz de este módulo (`hackathon_voz`):

```bash
# Crear el entorno virtual llamado 'env'
python3 -m venv env

# Activar el entorno
source env/bin/activate
```

### 2. Instalar dependencias

Con el entorno activado (`env`), instala las librerías necesarias:

```bash
pip install vosk pyaudio deep-translator
```

O, si tienes un `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 3. Descargar el modelo de voz

El sistema necesita el modelo neuronal en la carpeta del proyecto.

1. Descarga el modelo ligero en español (≈40 MB):
   `vosk-model-small-es-0.42.zip`
2. Descomprímelo en la raíz de esta carpeta.
3. Asegúrate de que la carpeta descomprimida se llama exactamente:

```text
vosk-model-small-es-0.42
```

### Estructura final de carpetas

```text
hackathon_voz/
├── env/                      # Entorno virtual
├── vosk-model-small-es-0.42/ # Carpeta del modelo
├── main.py                   # Script de prueba
├── voice_module.py           # Librería principal
└── README.md
```

---

## Cómo probarlo

Para verificar que el micrófono escucha y la lógica funciona:

1. Activa el entorno virtual (si no lo está):

   ```bash
   source env/bin/activate
   ```

2. Ejecuta la prueba:

   ```bash
   python main.py
   ```

---

## Guía de interacción

El sistema tiene un filtro estricto: solo acepta peticiones navideñas o relacionadas con adornos navideños sobre la cara.

Ejemplos:

* Incorrecto:
  "Ponme unas gafas de sol."
  (Te rechazará porque no es navideño).

* Correcto:
  "Quiero unas gafas de navidad."

* Correcto:
  "Ponme barba de Papá Noel."

* Correcto:
  "Dibújame con cuernos de reno."

---

## Integración (código Python)

Para usar este módulo dentro del código principal del robot, impórtalo así:

```python
from voice_module import VoiceEngine
import os

# 1. Configurar ruta al modelo (relativa al script)
current_dir = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(current_dir, "vosk-model-small-es-0.42")

# 2. Inicializar el motor (hacerlo solo una vez al inicio)
#    Si tu micro no es el por defecto, pasa device_index=X
engine = VoiceEngine(MODEL_PATH, device_index=None)

# 3. Escuchar (esta función bloquea el código hasta tener un prompt válido)
print("Esperando comando de voz...")
prompt_final = engine.escuchar_y_obtener_prompt()

if prompt_final:
    print(f"Prompt generado para la IA: {prompt_final}")
    # Aquí envías 'prompt_final' a tu generador de imágenes
```

---

## Solución de problemas

### Error: `fatal error: portaudio.h: No such file or directory`

Te falta la librería de desarrollo de PortAudio.

Solución:

```bash
sudo apt-get install portaudio19-dev
pip install --force-reinstall pyaudio
```

---

### Error: `Input Overflow`

A veces ocurre si el ordenador va lento o hay mucho lag.

* Suele poder ignorarse si no es continuo.
* Si persiste, revisa la tasa de muestreo (sample rate) en `voice_module.py`.

---

### Advertencias `ALSA lib ...` en la terminal

Son avisos de Linux sobre la tarjeta de sonido.

* No afectan al funcionamiento del programa.
* Puedes ignorarlos sin problema.
