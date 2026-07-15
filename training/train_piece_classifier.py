"""training/train_piece_classifier.py

Fine-tuning de YOLO11s para detección de piezas de ajedrez (M3) sobre
imágenes ya rectificadas (vista cenital) por M2, partiendo de un
checkpoint COCO-preentrenado (no desde cero).

Pensado para ejecutarse en Google Colab:

    !pip install ultralytics
    !python train_piece_classifier.py --data /content/datasets/pieces/data.yaml

El dataset debe tener 12 clases, con el mismo alfabeto que
BoardMatrix: wP, wN, wB, wR, wQ, wK, bP, bN, bB, bR, bQ, bK. Puede
partir de un dataset público (ver M2_M3_SPEC.md - base strategy with model training with fine-tuning)
combinado con imágenes propias.
"""

from __future__ import annotations

import argparse

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", required=True, help="Ruta al data.yaml del dataset de piezas"
    )
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--imgsz", type=int, default=800)
    parser.add_argument(
        "--base-model",
        default="yolo11s.pt",
        help="Checkpoint COCO-preentrenado de partida (se descarga solo la primera vez)",
    )
    parser.add_argument("--output-name", default="pieces")
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
        f"  -> src/chess_vision/models/pieces.pt\n"
    )


if __name__ == "__main__":
    main()
