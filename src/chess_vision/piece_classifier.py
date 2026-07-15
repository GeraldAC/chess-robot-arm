"""chess_vision.piece_classifier — M3: detección de piezas sobre la
imagen ya rectificada por M2 (vista cenital).
"""

from __future__ import annotations

from chess_vision.types import PieceDetection


def detect_pieces(
    topdown_image,
    model,  # ultralytics.YOLO cargado (12 clases de pieza)
    conf_threshold: float = 0.4,
) -> list[PieceDetection]:
    """Corre el modelo de piezas sobre la imagen ya rectificada.
    Retorna detecciones crudas con su bbox — no asigna a casillas
    todavía (responsabilidad de square_mapper.py).

    Se asume que `model.names` mapea el índice de clase al código de
    pieza en el alfabeto de chess_brain (ej. {0: "wP", 1: "wN", ...}).

    Nota de diseño: este `conf_threshold` es un filtro de ruido
    genérico para uso directo del módulo. El pipeline (pipeline.py)
    lo usa con un umbral más bajo ("piso de ruido") a propósito,
    dejando que la decisión real de "esta casilla es confiable"
    ocurra después, en square_mapper.check_confidence — de lo
    contrario, una pieza detectada con baja confianza simplemente
    desaparecería y la casilla se reportaría como vacía con
    confianza 1.0, ocultando justo la incertidumbre que se quiere
    exponer.
    """
    results = model.predict(topdown_image, verbose=False)[0]

    detections: list[PieceDetection] = []
    for box in results.boxes:
        conf = float(box.conf[0])
        if conf < conf_threshold:
            continue
        class_id = int(box.cls[0])
        piece_code = model.names[class_id]
        x1, y1, x2, y2 = box.xyxy[0]
        detections.append(
            PieceDetection(
                piece_code=piece_code,
                bbox_px=(x1, y1, x2, y2),
                confidence=conf,
            )
        )

    return detections
