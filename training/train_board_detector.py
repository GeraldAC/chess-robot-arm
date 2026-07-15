"""training/train_board_detector.py

Fine-tuning de YOLO11n para detección de las 4 esquinas del tablero
(M2), partiendo de un checkpoint COCO-preentrenado (no desde cero).

Pensado para ejecutarse en Google Colab:

    !pip install ultralytics
    !python train_board_detector.py --data /content/datasets/board_corners/data.yaml

El dataset debe estar en formato YOLO (imágenes + labels .txt), con
una sola clase: "corner". Ver M2_M3_SPEC.md (base strategy with model training with fine-tuning) para cómo
generarlo y etiquetarlo.
"""

from __future__ import annotations

import argparse

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", required=True, help="Ruta al data.yaml del dataset de esquinas"
    )
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument(
        "--base-model",
        default="yolo11n.pt",
        help="Checkpoint COCO-preentrenado de partida (se descarga solo la primera vez)",
    )
    parser.add_argument("--output-name", default="board_corners")
    args = parser.parse_args()

    model = YOLO(args.base_model)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        name=args.output_name,
    )

    print(
        f"\nEntrenamiento terminado. Copiar el mejor checkpoint:\n"
        f"  runs/detect/{args.output_name}/weights/best.pt\n"
        f"  -> src/chess_vision/models/board_corners.pt\n"
    )


if __name__ == "__main__":
    main()
