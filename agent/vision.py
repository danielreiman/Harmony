from ultralytics import YOLO
import os, json, cv2
from PIL import Image
import pyautogui

class ScreenParser:
    def __init__(self, model_path="./models/weights/icon_detect/model.pt"):
        if not os.path.exists(model_path):
            raise FileNotFoundError("Missing YOLO model weights at weights/icon_detect/model.pt")
        self.model = YOLO(model_path)

    def extract(self, screenshot_path="./runtime/screenshot.png", detected_path="./runtime/detected.png", draw=True):
        results = self.model.predict(
            screenshot_path,
            conf=0.1,  # lower threshold: catch small or faint icons
            iou=0.45,  # standard overlap tolerance
            imgsz=1280,  # larger image improves small-object detection
            verbose=False
        )
        image = cv2.imread(screenshot_path)
        data = []

        colors = [
            (255, 0, 0), (0, 255, 0), (0, 200, 255),
            (255, 255, 0), (255, 0, 255), (180, 105, 255),
            (0, 128, 255), (255, 128, 0), (128, 255, 128)
        ]

        used_positions = []  # store (x, y, h) of drawn labels

        for i, box in enumerate(results[0].boxes):
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            label = self.model.names[int(box.cls[0])]
            coords = [x1, y1, x2, y2]
            color = colors[i % len(colors)]

            data.append({
                "id": i,
                "label": label,
                "coordinates": coords
            })

            if not draw:
                continue

            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

            text = f"ID:{i}"
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)

            # Stick the label to the top border, with 1–2px gap inside the frame
            label_x = x1 + 4
            label_y = y1 + th + 2

            # Background box slightly overlapping the border
            bg_x1 = label_x - 3
            bg_y1 = y1 - 2
            bg_x2 = label_x + tw + 4
            bg_y2 = y1 + th + 6

            cv2.rectangle(image, (bg_x1, bg_y1), (bg_x2, bg_y2), color, -1)

            cv2.putText(
                image,
                text,
                (label_x, y1 + th + 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 0),
                2
            )

        if draw:
            cv2.imwrite(detected_path, image)

        return json.dumps(data, indent=2, ensure_ascii=False)

class Vision:
    def __init__(self):
        self.screen_parser = ScreenParser()

    def look(self):
        screenshot_path = "./runtime/screenshot.png"
        detected_path = "./runtime/detected.png"

        # pyautogui.screenshot(screenshot_path)
        img = pyautogui.screenshot()
        img.save(screenshot_path)

        content = json.loads(self.screen_parser.extract(screenshot_path, detected_path))
        return content, screenshot_path, detected_path

    def locate(self, box_id, elements):
        # find the box by ID
        box = None
        for item in elements:
            current_id = str(item.get("id"))
            if current_id == str(box_id):
                box = item
                break

        # get coordinates center if available
        if box:
            return box["coordinates"]

        return None

    def focus(self, box_id, elements, screenshot_path):
        coords = self.locate(box_id, elements)
        if not coords:
            return None

        x1, y1, x2, y2 = coords
        img = Image.open(screenshot_path)

        cropped_path = f"./runtime/focus_{box_id}.png"
        img.crop((x1, y1, x2, y2)).save(cropped_path)

        return cropped_path




