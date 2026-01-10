from ultralytics import YOLO
import cv2
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
weights = BASE_DIR / "../models/yolov8n.pt"
model = YOLO(str(weights))  # Trained model


cctv_folder = BASE_DIR / "../cctv"
output_folder = BASE_DIR / "../out"

for image_path in cctv_folder.glob("*.jpg"):
    img = cv2.imread(str(image_path))
    results = model(img, conf=0.02)  # Run inference with a confidence threshold of 0.5

    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = box.conf[0]  # Confidence score
            cls = int(box.cls[0])  # Class ID

            # Draw bounding box and label on the image
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{model.names[cls]}: {conf:.2f}"
            cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        output_path = output_folder / image_path.name
        cv2.imwrite(str(output_path), img)  # Save the output image

