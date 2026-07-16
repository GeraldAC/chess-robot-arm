"""chess_vision.camera_capture — lado receptor (laptop) de M1.

El firmware/lado-emisor de la ESP32-CAM queda fuera de alcance; este
módulo solo asume que existe un endpoint HTTP que devuelve un JPEG.
"""

from __future__ import annotations

import cv2
import numpy as np
import requests

from chess_vision.vision_types import RawFrame, VisionError


def fetch_frame(esp32_cam_url: str, timeout: float = 5.0) -> RawFrame:
    """Descarga un frame JPEG desde el endpoint HTTP de la ESP32-CAM y
    lo decodifica a RawFrame (BGR, cv2.imdecode).

    Lanza VisionError si falla la conexión o la decodificación.
    """
    try:
        response = requests.get(esp32_cam_url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise VisionError(
            f"No se pudo obtener el frame de {esp32_cam_url}: {exc}"
        ) from exc

    image_array = np.frombuffer(response.content, dtype=np.uint8)
    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if frame is None:
        raise VisionError(
            f"No se pudo decodificar la imagen recibida de {esp32_cam_url}"
        )

    return frame
