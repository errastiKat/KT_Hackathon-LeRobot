import os
import sys
import json
import pyaudio
from vosk import Model, KaldiRecognizer
from deep_translator import GoogleTranslator

class VoiceEngine:
    def __init__(self, model_path, device_index=None):
        self.device_index = device_index
        self.sample_rate = 16000
        
        # --- 1. CARGA DEL MODELO ---
        if not os.path.exists(model_path):
            print(f"[ERROR] No encuentro el modelo en: {model_path}")
            sys.exit(1)
            
        print(f"[INFO] Cargando modelo Vosk...")
        try:
            self.model = Model(model_path)
            self.translator = GoogleTranslator(source='es', target='en')
            print("[INFO] Motor de voz listo (Modo Modificacion de Cara).")
        except Exception as e:
            print(f"[ERROR CRITICO] {e}")
            sys.exit(1)

        # --- 2. TRIGGERS (Intencion de pedir) ---
        self.triggers = [
            "quiero", "ponme", "dame", "añade", "dibuja", "dibújame", 
            "generame", "hazme", "pon", "crea", "me gustaría", "tengo"
        ]

        # --- 3. FILTRO NAVIDENO (Keywords obligatorias) ---
        self.christmas_keywords = [
            "navidad", "navideño", "navideña", "pascua",
            "santa", "claus", "papá noel", "papa noel",
            "reno", "rudolph", "cuernos", "trineo",
            "elfo", "duende", "gnomo",
            "nieve", "invierno", "copo", "hielo",
            "regalo", "lazo", 
            "árbol", "abeto", "pino", "luces", "guirnalda",
            "gorro", "bufanda", "muérdago", "campana",
            "barba", "bigote", "gafas" # Anadimos rasgos faciales tipicos aunque no sean 100% navidad
        ]

        # --- 4. ESTILO ROBOT + PRESERVACION DE CARA ---
        # prompt_prefix: Fuerza a la IA a saber que hay una persona base
        self.prompt_prefix = "portrait of the person in the input image modified to have "
        
        # tech_prompt: El estilo de dibujo final
        self.tech_prompt = (
            ", high quality line art, thick black contours, minimalist sketch, "
            "vector style, white background, no shading, no gray scales, "
            "clean strokes, coloring book style, sharp edges, christmas atmosphere."
        )

    def escuchar_y_obtener_prompt(self):
        """
        Escucha -> Valida -> Traduce -> Retorna prompt enfocado en la cara.
        """
        rec = KaldiRecognizer(self.model, self.sample_rate)
        p = pyaudio.PyAudio()
        
        try:
            stream = p.open(format=pyaudio.paInt16,
                            channels=1,
                            rate=self.sample_rate,
                            input=True,
                            input_device_index=self.device_index,
                            frames_per_buffer=8000)
            stream.start_stream()
            
            # EJEMPLOS CORRECTOS PARA EL USUARIO
            print("\n[ESCUCHANDO] Di que quieres cambiar en tu cara. Ej: 'Ponme barba de Santa Claus', 'Quiero cuernos de reno'...")

            while True:
                data = stream.read(4000, exception_on_overflow=False)
                if len(data) == 0: continue

                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = res.get("text", "").lower()
                    
                    if text and len(text) > 3:
                        print(f"   [Texto oido]: '{text}'")
                        
                        # 1. Verificar trigger
                        has_trigger = any(trigger in text for trigger in self.triggers)
                        
                        if has_trigger:
                            # 2. VERIFICACION NAVIDENA
                            is_christmas = any(word in text for word in self.christmas_keywords)
                            
                            if is_christmas:
                                print("   [OK] Peticion valida. Procesando...")
                                try:
                                    # Traduccion
                                    translated_text = self.translator.translate(text)
                                    print(f"   [Traducido]: '{translated_text}'")
                                    
                                    # CONSTRUCCION DEL PROMPT FINAL (La clave del exito)
                                    # Estructura: [RETRATO DE ESTA PERSONA MODIFICADO CON...] + [LO QUE PIDE EL USUARIO] + [ESTILO]
                                    final_prompt = (
                                        f"{self.prompt_prefix} {translated_text}{self.tech_prompt}"
                                    )
                                    
                                    stream.stop_stream()
                                    stream.close()
                                    p.terminate()
                                    return final_prompt

                                except Exception as e:
                                    print(f"   [WARN] Error traduciendo: {e}. Reintentando...")
                            else:
                                print("   [RECHAZADO] No es una peticion navidena valida.")
                                print("   -> Pide cosas como: 'gorro de navidad', 'barba de santa', 'cuernos de reno'...")
                        
                        else:
                            pass

        except KeyboardInterrupt:
            print("\n[STOP] Interrumpido por usuario.")
            if 'stream' in locals():
                stream.stop_stream()
                stream.close()
            p.terminate()
            return None
        except Exception as e:
            print(f"\n[ERROR] {e}")
            return None