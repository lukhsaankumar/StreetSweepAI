from ultralytics import YOLO
import cv2
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
weights = BASE_DIR / "../models/yolov8n.pt"
model = YOLO(str(weights))  # Trained model

src = BASE_DIR / "../cctv/cleanalley.jpg"
img = cv2.imread(str(src))
results = model(img, conf=0.03)  # Run inference with a confidence threshold of 0.5

print(results[0].boxes)  # Print detected boxes

for r in results:
    for box in r.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        conf = box.conf[0]  # Confidence score
        cls = int(box.cls[0])  # Class ID

        # Draw bounding box and label on the image
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"{model.names[cls]}: {conf:.2f}"
        cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
cv2.imwrite("output.jpg", img)  # Save the output image

