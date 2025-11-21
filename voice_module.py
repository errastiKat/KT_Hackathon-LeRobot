import os
import sys
import json
import pyaudio
from vosk import Model, KaldiRecognizer

class VoiceEngine:
    def __init__(self, model_path, device_index=None):
        self.device_index = device_index
        self.sample_rate = 16000
        
        if not os.path.exists(model_path):
            print(f"❌ ERROR: No encuentro el modelo en: {model_path}")
            sys.exit(1)
            
        print(f"⏳ Cargando modelo Vosk...")
        try:
            self.model = Model(model_path)
            print("✅ Modelo cargado.")
        except Exception as e:
            print(f"❌ Error cargando modelo: {e}")
            sys.exit(1)

        # Diccionario: Palabra clave -> Prompt técnico
        self.keywords = {
            "gorro": "wearing a christmas santa hat",
            "navidad": "wearing a christmas santa hat",
            "elfo": "wearing elf ears and fantasy hat",
            "duende": "wearing elf ears and fantasy hat",
            "cuernos": "wearing reindeer antlers headband",
            "reno": "wearing reindeer antlers headband",
            "barba": "wearing a big white fake santa beard",
            "gafas": "wearing funny christmas star glasses",
            "bigote": "wearing a funny mustache",
            "nariz": "wearing a red clown nose"
        }
        
        self.style_suffix = ", line art, black and white, simple sketch, minimalist, clean lines, white background, no shading, vector style."

    def escuchar_y_obtener_prompt(self):
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
            
            print("\n🎙️  ESCUCHANDO... (Di: 'gorro', 'elfo', 'cuernos'...)")

            while True:
                data = stream.read(4000, exception_on_overflow=False)
                if len(data) == 0: continue

                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = res.get("text", "").lower()
                    
                    if text:
                        print(f"   🗣️  He oído: '{text}'")
                        for word, prompt_part in self.keywords.items():
                            if word in text:
                                print(f"   ✨ ¡Detectado!: '{word}'")
                                final_prompt = f"portrait of a person {prompt_part}{self.style_suffix}"
                                stream.stop_stream()
                                stream.close()
                                p.terminate()
                                return final_prompt
                        # print("   ⚠️  No entendí el adorno.") # Descomentar si quieres mucho log

        except KeyboardInterrupt:
            print("\n🛑 Interrumpido.")
            return None
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return None