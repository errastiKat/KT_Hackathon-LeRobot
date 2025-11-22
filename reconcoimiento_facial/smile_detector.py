# reconcoimiento_facial/smile_detector.py

import threading
import time
from typing import Optional, Dict, Any, Tuple

import cv2
import numpy as np
from deepface import DeepFace


class SmileDetector:
    """Captura vídeo, mide 'happy' con DeepFace y dispara una foto al sonreír.

    - No abre ventanas de OpenCV.
    - Solo detecta caras dentro del ROI central (el recuadro blanco).
    - Marca únicamente la mejor cara (más grande) dentro del ROI.
    - Usa directamente la caja de DeepFace (sin suavizado de posición).
    - Guarda la foto en disco y expone:
        * último frame anotado (para servirlo por HTTP)
        * estado actual (happy_smooth, si ya hay foto, etc.)
    """

    def __init__(
        self,
        cam_index: int = 0,
        frame_w: int = 1920,
        frame_h: int = 1080,
        happy_threshold: float = 60.0,
        min_smile_frames: int = 5,
        process_every_n: int = 2,
        detector_backend: str = "retinaface",
        capture_path: str = "smile_capture.jpg",
        center_rect: Tuple[float, float, float, float] = (0.2, 0.2, 0.8, 0.8),
        box_smooth_alpha: float = 0.7,      # ya no se usa, pero lo mantengo por compatibilidad
        happy_smooth_alpha: float = 0.7,
        miss_tol_frames: int = 5,
    ) -> None:
        self.cam_index = cam_index
        self.frame_w = frame_w
        self.frame_h = frame_h

        self.happy_threshold = happy_threshold
        self.min_smile_frames = min_smile_frames
        self.process_every_n = process_every_n

        self.detector_backend = detector_backend
        self.capture_path = capture_path

        self.center_rect = center_rect
        self.box_smooth_alpha = box_smooth_alpha
        self.happy_smooth_alpha = happy_smooth_alpha
        self.miss_tol_frames = miss_tol_frames

        # Estado interno
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._lock = threading.Lock()
        self._last_frame: Optional[np.ndarray] = None
        self._happy_smooth: float = 0.0
        self._face_present: bool = False
        self._photo_taken: bool = False

        # Para depurar si hace falta
        self._debug_last_happy_raw: float = 0.0

    # ===========================
    #     API pública (Flask)
    # ===========================

    def start(self) -> None:
        """Arranca el hilo de captura y análisis (no bloqueante)."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Detiene el hilo de captura (por ejemplo al cerrar la app)."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def get_frame_jpeg(self) -> Optional[bytes]:
        """Devuelve el último frame ANOTADO como bytes JPEG."""
        with self._lock:
            if self._last_frame is None:
                return None
            ok, buf = cv2.imencode(".jpg", self._last_frame)
        if not ok:
            return None
        return buf.tobytes()

    def get_state(self) -> Dict[str, Any]:
        """Devuelve un snapshot del estado actual para exponerlo por API."""
        with self._lock:
            state = {
                "happy": float(self._happy_smooth),
                "happy_threshold": float(self.happy_threshold),
                "face_present": bool(self._face_present),
                "photo_taken": bool(self._photo_taken),
                "capture_path": self.capture_path if self._photo_taken else None,
                "debug_last_happy_raw": float(self._debug_last_happy_raw),
            }
        return state

    # ===========================
    #     Bucle interno
    # ===========================

    def _loop(self) -> None:
        cap = cv2.VideoCapture(self.cam_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_h)

        if not cap.isOpened():
            print("[SmileDetector] No se pudo abrir la cámara")
            self._running = False
            return

        frame_idx = 0
        happy_smooth: Optional[float] = None

        last_box: Optional[Tuple[float, float, float, float]] = None
        miss_count = 0
        smile_consec = 0

        print(
            f"[SmileDetector] Iniciado. Umbral happy_smooth > {self.happy_threshold:.0f}% "
            f"durante {self.min_smile_frames} frames."
        )

        cx1_rel, cy1_rel, cx2_rel, cy2_rel = self.center_rect

        try:
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    print("[SmileDetector] Frame no válido, saliendo del bucle.")
                    break

                display = frame.copy()
                h, w = display.shape[:2]

                # Rectángulo central guía (ROI)
                cx1 = int(w * cx1_rel)
                cy1 = int(h * cy1_rel)
                cx2 = int(w * cx2_rel)
                cy2 = int(h * cy2_rel)
                cv2.rectangle(display, (cx1, cy1), (cx2, cy2), (255, 255, 255), 1)

                # Recortamos el ROI: solo detectamos caras dentro del recuadro blanco
                roi = frame[cy1:cy2, cx1:cx2]

                new_happy: Optional[float] = None
                new_box: Optional[Tuple[float, float, float, float]] = None

                # DeepFace cada N frames (sobre el ROI, no sobre toda la imagen)
                if frame_idx % self.process_every_n == 0:
                    try:
                        result = DeepFace.analyze(
                            img_path=roi,
                            actions=["emotion"],
                            detector_backend=self.detector_backend,
                            enforce_detection=False,
                        )

                        # DeepFace puede devolver dict o lista de dicts (varias caras)
                        if isinstance(result, list):
                            candidates = result
                        else:
                            candidates = [result]

                        best_region = None
                        best_emotions = None
                        best_area = 0.0

                        for r in candidates:
                            region = r.get("region", {})
                            if (
                                not region
                                or region.get("w", 0) <= 0
                                or region.get("h", 0) <= 0
                            ):
                                continue

                            w_face = float(region["w"])
                            h_face = float(region["h"])
                            area = w_face * h_face
                            if area <= 0:
                                continue

                            if area > best_area:
                                best_area = area
                                best_region = region
                                best_emotions = r.get("emotion", {})

                        if best_region is not None and best_emotions is not None:
                            # Emociones de la mejor cara
                            new_happy = float(best_emotions.get("happy", 0.0))

                            # Convertimos coords ROI -> coords globales de la imagen
                            x_roi = float(best_region["x"])
                            y_roi = float(best_region["y"])
                            ww = float(best_region["w"])
                            hh = float(best_region["h"])

                            x = x_roi + cx1
                            y = y_roi + cy1
                            new_box = (x, y, ww, hh)

                    except Exception as e:
                        # Si falla DeepFace, no paramos todo
                        print(f"[SmileDetector] Error en DeepFace: {e}")
                        new_happy = None
                        new_box = None

                # Suavizado de happy (mantenemos para que no salte tanto)
                if new_happy is not None:
                    if happy_smooth is None:
                        happy_smooth = new_happy
                    else:
                        happy_smooth = (
                            self.happy_smooth_alpha * happy_smooth
                            + (1.0 - self.happy_smooth_alpha) * new_happy
                        )
                elif happy_smooth is None:
                    happy_smooth = 0.0

                # Gestión de caja SIN suavizado de posición:
                # usamos siempre la última detección directa, solo con tolerancia de pérdida
                if new_box is not None:
                    miss_count = 0
                    last_box = new_box
                else:
                    if last_box is not None:
                        miss_count += 1
                        if miss_count > self.miss_tol_frames:
                            last_box = None
                            miss_count = 0

                # Dibujar caja si la tenemos
                face_present = last_box is not None
                if last_box is not None:
                    x, y, ww, hh = last_box
                    x1 = max(0, int(x))
                    y1 = max(0, int(y))
                    x2 = min(w, int(x + ww))
                    y2 = min(h, int(y + hh))
                    cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Lógica de sonrisa / disparo de foto
                happy_to_show = float(happy_smooth if happy_smooth is not None else 0.0)
                photo_taken_now = False

                if (
                    happy_to_show >= self.happy_threshold
                    and not self._photo_taken
                ):
                    smile_consec += 1
                else:
                    smile_consec = 0

                if not self._photo_taken and smile_consec >= self.min_smile_frames:
                    # Guardamos la foto (frame original, sin overlays)
                    try:
                        cv2.imwrite(self.capture_path, frame)
                        print(
                            f"[SmileDetector] Sonrisa detectada (happy_smooth={happy_to_show:.1f}%). "
                            f"Foto guardada en {self.capture_path}"
                        )
                        photo_taken_now = True
                    except Exception as e:
                        print(f"[SmileDetector] Error guardando la foto: {e}")

                # Texto en el frame
                cv2.putText(
                    display,
                    f"Happy (suavizado): {happy_to_show:.1f}%",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0)
                    if happy_to_show >= self.happy_threshold
                    else (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )

                if self._photo_taken or photo_taken_now:
                    status_text = "Foto capturada. Sonríe de nuevo para reemplazar."
                    status_color = (0, 255, 0)
                else:
                    status_text = "Mete tu cara en el recuadro y SONRIE fuerte."
                    status_color = (255, 255, 255)

                cv2.putText(
                    display,
                    status_text,
                    (20, display.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    status_color,
                    2,
                    cv2.LINE_AA,
                )

                # Actualizamos estado compartido
                with self._lock:
                    self._last_frame = display
                    self._happy_smooth = happy_to_show
                    self._face_present = face_present
                    if photo_taken_now:
                        self._photo_taken = True
                    self._debug_last_happy_raw = float(new_happy or 0.0)

                frame_idx += 1
                # Mini pausa para no saturar CPU
                time.sleep(0.01)

        finally:
            cap.release()
            print("[SmileDetector] Cámara liberada, fin del hilo.")
            self._running = False
