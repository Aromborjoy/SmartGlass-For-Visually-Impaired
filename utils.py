
# utils.py (V18: Blue/Purple Rescue - กู้ชีพสีโทนเย็น)
import cv2
import numpy as np

class Config:
    OBJECT_CONFIDENCE_THRESHOLD = 0.6
    IOU_THRESHOLD = 0.45
    OBJECT_SPEAK_DELAY = 2.5
    COLOR_MATCH_THRESHOLD = 50.0  
    
    UI_COLORS = {
        'BLUE': (255, 0, 0), 'GREEN': (0, 255, 0), 'RED': (0, 0, 255),
        'YELLOW': (0, 255, 255), 'ORANGE': (0, 165, 255), 'WHITE': (255, 255, 255),
        'GRAY': (128, 128, 128), 'BLACK': (50, 50, 50), 'PINK': (147, 20, 255),
        'NAVY': (0, 0, 128), 'CYAN': (255, 255, 0), 'PURPLE': (128, 0, 128),
        'BROWN': (19, 69, 139)
    }

    MODEL_PATH = "/home/bailey/SmartGlass/runs/detect/train4/weights/best.onnx"
    DATA_YAML_PATH = "/home/bailey/SmartGlass/OBD-Smart-Glass-1/data.yaml"
    
    ACCURACY_THRESHOLD = 70.0
    HIGH_ACCURACY_THRESHOLD = 85.0
    MEDIUM_ACCURACY_THRESHOLD = 60.0

class UIRenderer:
    @staticmethod
    def draw_text_with_background(frame, text, org, font=cv2.FONT_HERSHEY_SIMPLEX, font_scale=0.7,
                                  text_color=(255, 255, 255), bg_color=(0, 0, 0), thickness=2):
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        x_end = max(0, org[0] + text_width)
        y_start = max(0, org[1] - text_height - baseline)
        cv2.rectangle(frame, (org[0], org[1] + baseline), (x_end, y_start), bg_color, cv2.FILLED)
        cv2.putText(frame, text, org, font, font_scale, text_color, thickness)

class PerceptualColorAnalyzer: 
    def __init__(self):
        self.gamma = 0.7
        self.lookUpTable = np.empty((1,256), np.uint8)
        for i in range(256):
            self.lookUpTable[0,i] = np.clip(pow(i / 255.0, self.gamma) * 255.0, 0, 255)

    def get_average_color_hsv(self, roi):
        if roi.size == 0: return None
        blurred = cv2.GaussianBlur(roi, (5, 5), 0)
        hsv_roi = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        try:
            h = np.median(hsv_roi[:, :, 0])
            s = np.median(hsv_roi[:, :, 1])
            v = np.median(hsv_roi[:, :, 2])
            return [h, s, v]
        except:
            return None

    def is_focused(self, roi):
        (mean, std) = cv2.meanStdDev(roi)
        avg_std = np.mean(std)
        if avg_std > 40.0: return False
        return True

    def analyze_color(self, roi):
        if not self.is_focused(roi): return "Unknown", 0

        hsv_pixel = self.get_average_color_hsv(roi)
        if hsv_pixel is None: return "Unknown", 0

        H, S, V = hsv_pixel

        # ---------------------------------------------------------
        # SPECIAL CHECK: Cool Color Rescue (น้ำเงิน/ม่วง/ชมพู)
        # สีโทนนี้มักจะจืดกว่าสีร้อน ยอมให้ S ต่ำได้ถึง 20
        # ช่วง Hue: 85 (Blue Start) ถึง 175 (Pink End)
        # ---------------------------------------------------------
        is_cool_tone = (85 <= H <= 175)
        min_saturation = 20 if is_cool_tone else 45

        # ---------------------------------------------------------
        # ZONE 1: ACHROMATIC (ขาว/เทา/ดำ)
        # ---------------------------------------------------------
        if S < min_saturation: 
            if V < 40: return "Black", 95.0
            elif V > 200: return "White", 95.0
            else: return "Gray", 90.0

        if V < 35: return "Black", 92.0

        # ---------------------------------------------------------
        # ZONE 2: HUE ZONES
        # ---------------------------------------------------------
        color_name = "Unknown"
        
        if (0 <= H <= 10) or (170 <= H <= 180):
            if H >= 165 and V > 130: color_name = "Pink" # ปลายแดงสว่าง = ชมพู
            elif V > 90 and S > 70: color_name = "Red"
            else: color_name = "Brown"
                
        elif 11 <= H <= 25:
            color_name = "Orange"
            if V < 130: color_name = "Brown"
            
        elif 26 <= H <= 35:
            color_name = "Yellow"
            
        elif 45 <= H <= 80:
            if S > 60: color_name = "Green"
            else: color_name = "Gray"
            
        elif 86 <= H <= 130:
            if V > 190: color_name = "Cyan"
            # Navy ต้องเข้มจริง และต้องสดพอประมาณ (ไม่งั้นเป็นดำ)
            elif V < 80 and S > 80: color_name = "Navy"
            elif V < 80: return "Black", 90.0
            else: color_name = "Blue"
            
        elif 131 <= H <= 155:
            color_name = "Purple"
            
        elif 156 <= H <= 169:
            color_name = "Pink"

        if color_name == "Unknown": return "Unknown", 0

        # ---------------------------------------------------------
        # ZONE 3: SCORE
        # ---------------------------------------------------------
        base_score = 65.0
        sat_bonus = (S / 255.0) * 25.0 
        val_bonus = (V / 255.0) * 10.0
        
        accuracy = base_score + sat_bonus + val_bonus
        accuracy = min(99.0, accuracy)

        # Boost
        if color_name in ["Black", "Brown", "Navy"]:
            accuracy = max(80.0, accuracy)
        if color_name == "Red": accuracy += 5.0
        
        # Boost พิเศษให้สีที่กู้ชีพมา
        if color_name in ["Blue", "Purple", "Pink"]:
            accuracy = max(78.0, accuracy)

        return color_name, accuracy
