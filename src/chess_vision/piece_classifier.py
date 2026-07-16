"""chess_vision.piece_classifier — M3: detección de piezas usando un
modelo YOLO YA ENTRENADO por la comunidad (sin fine-tuning propio).

v2: se adoptó el modelo pretrained de
https://github.com/siromermer/Dynamic-Chess-Board-Piece-Extraction
(YOLOv8m, 12 clases, nombrado "chess-model-yolov8m.pt"), base también
de la app Chesspector (Google Play). No requiere dataset propio ni
entrenamiento. Ver M2_M3_SPEC.md para instrucciones
de descarga y la advertencia de licencia.

Nota de diseño importante: la detección corre sobre la imagen
ORIGINAL (sin deformar), no sobre una vista cenital. Deformar la
imagen antes de detectar distorsiona la apariencia 3D de piezas
altas (rey, dama) de forma que no está representada en los datos de
entrenamiento del modelo. La corrección de perspectiva se aplica solo
a la GEOMETRÍA de las casillas (ver board_detector.compute_square_grid),
no a los píxeles que ve el detector.
"""

from __future__ import annotations

from chess_vision.vision_types import PieceDetection

# Alfabeto de nombres de clase del modelo comunitario -> alfabeto de
# chess_brain ("wP", "bN", ...). Si se cambia de modelo, este mapa
# debe actualizarse (o pasarse uno distinto por parámetro).
COMMUNITY_YOLOV8M_CLASS_MAP: dict[str, str] = {
    "black-bishop": "bB",
    "black-king": "bK",
    "black-knight": "bN",
    "black-pawn": "bP",
    "black-queen": "bQ",
    "black-rook": "bR",
    "white-bishop": "wB",
    "white-king": "wK",
    "white-knight": "wN",
    "white-pawn": "wP",
    "white-queen": "wQ",
    "white-rook": "wR",
}


def detect_pieces(
    image,
    model,  # ultralytics.YOLO ya cargado (ej. chess-model-yolov8m.pt)
    conf_threshold: float = 0.25,
    class_name_map: dict[str, str] | None = None,
) -> list[PieceDetection]:
    """Corre el modelo de piezas sobre `image` (la imagen ORIGINAL,
    sin deformar — ver nota de diseño arriba). Retorna detecciones
    crudas con su bbox en coordenadas de esa misma imagen; no asigna
    a casillas todavía (responsabilidad de square_mapper.py).

    `class_name_map` traduce el nombre de clase crudo del modelo
    (ej. "white-pawn") al alfabeto de chess_brain (ej. "wP"). Por
    defecto usa COMMUNITY_YOLOV8M_CLASS_MAP; si el nombre no está en
    el mapa, se deja sin traducir (asume que ya viene en el alfabeto
    correcto — útil si en el futuro se reemplaza por un modelo propio
    entrenado directamente con esos nombres de clase).

    Nota de diseño (heredada de v1, sigue vigente): `conf_threshold`
    aquí es un filtro de uso directo del módulo. El pipeline
    (pipeline.py) lo usa con un umbral más bajo a propósito, dejando
    la decisión real de "esta casilla es confiable" para
    square_mapper.check_confidence.
    """
    name_map = class_name_map or COMMUNITY_YOLOV8M_CLASS_MAP
    results = model.predict(image, verbose=False)[0]

    detections: list[PieceDetection] = []
    for box in results.boxes:
        conf = float(box.conf[0])
        if conf < conf_threshold:
            continue
        class_id = int(box.cls[0])
        raw_name = model.names[class_id]
        piece_code = name_map.get(raw_name, raw_name)

        x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
        detections.append(
            PieceDetection(
                piece_code=piece_code,
                bbox_px=(x1, y1, x2, y2),
                confidence=conf,
            )
        )

    return detections
