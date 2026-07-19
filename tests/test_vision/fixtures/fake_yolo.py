"""Stub de ultralytics.YOLO para tests: permite probar
board_detector.py y piece_classifier.py sin pesos reales ni la
dependencia de ultralytics.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _FakeBox:
    _conf: float
    _cls: int
    _xyxy: tuple[float, float, float, float]

    @property
    def conf(self):
        return [self._conf]

    @property
    def cls(self):
        return [self._cls]

    @property
    def xyxy(self):
        return [list(self._xyxy)]


@dataclass
class _FakeResult:
    boxes: list[_FakeBox] = field(default_factory=list)


class FakeYOLOModel:
    """Simula la interfaz mínima de ultralytics.YOLO usada por
    chess_vision: `model.predict(frame)` y `model.names`.

    Se le precargan las detecciones que debe devolver.
    """

    def __init__(
        self,
        detections: list[tuple[float, int, tuple[float, float, float, float]]],
        names: dict[int, str] | None = None,
    ):
        """detections: lista de (confidence, class_id, (x1,y1,x2,y2))"""
        self._boxes = [
            _FakeBox(conf, cls_id, bbox) for conf, cls_id, bbox in detections
        ]
        self.names = names or {}

    def predict(self, _frame, verbose: bool = False):
        return [_FakeResult(boxes=self._boxes)]
