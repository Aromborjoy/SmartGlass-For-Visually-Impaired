# detectors.py (V8: Adaptive Streak - สีพื้นหลังต้องรอนานกว่า)
import cv2
import numpy as np
import time
import torch
import yaml
import os
import onnxruntime as ort
from ultralytics.utils.ops import non_max_suppression, scale_boxes
from collections import deque
import math

from utils import Config, UIRenderer, PerceptualColorAnalyzer
from tts_handler import CachedTTS

class ColorOnlyDetector:
    def __init__(self, tts_handler, color_analyzer):
        self.color_analyzer = color_analyzer
        self.tts = tts_handler
        self.last_announced_color = None
        self.last_announce_time = 0
        
        self.speak_delay = 4.0
        self.detection_box_size = 150
        self.last_log_time = 0
        
        # ตัวแปรนับ Combo
        self.current_streak_color = "Unknown"
        self.current_streak_count = 0
        self.score_history = deque(maxlen=15)

    def get_detection_box_coords(self, frame_width, frame_height):
        center_x, center_y = frame_width // 2, frame_height // 2
        half_size = self.detection_box_size // 2
        x1 = max(0, center_x - half_size); y1 = max(0, center_y - half_size)
        x2 = min(frame_width, center_x + half_size); y2 = min(frame_height, center_y + half_size)
        return x1, y1, x2, y2

    def detect_and_announce_color(self, frame):
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = self.get_detection_box_coords(width, height)
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0: return

        # 1. วิเคราะห์สี
        raw_color, raw_accuracy = self.color_analyzer.analyze_color(roi)

        # 2. [ADAPTIVE STREAK] กำหนดความยากง่ายตามสี
        # สีกลุ่มเสี่ยง (Background/Noise) ต้องถือนิ่งๆ นานๆ (20-25 เฟรม)
        if raw_color in ["White", "Black", "Gray", "Purple", "Yellow", "Brown"]:
            streak_threshold = 25
        # สีชัดเจน (Vivid) ให้พูดเร็วหน่อย (10-12 เฟรม)
        else:
            streak_threshold = 12

        # 3. นับคอมโบ
        if raw_color == self.current_streak_color and raw_color != "Unknown":
            self.current_streak_count += 1
        else:
            # รีเซ็ต
            self.current_streak_color = raw_color
            self.current_streak_count = 1
            self.score_history.clear()

        self.score_history.append(raw_accuracy)

        # 4. ตรวจสอบสถานะ (ใช้ Threshold แบบยืดหยุ่น)
        is_stable = False
        stable_acc = 0.0
        
        if self.current_streak_count >= streak_threshold:
            is_stable = True
            stable_acc = np.mean(self.score_history)

        # --- Log Output ---
        current_time = time.time()
        if current_time - self.last_log_time > 1.0:
            if is_stable:
                print(f"🎨 STABLE: {self.current_streak_color} | Acc: {stable_acc:.1f}% | Streak: {self.current_streak_count}")
            else:
                if self.current_streak_color != "Unknown":
                    # โชว์ว่าต้องการเท่าไหร่ (เช่น 5/25)
                    print(f"⏳ Verifying: {self.current_streak_color} ({self.current_streak_count}/{streak_threshold})")
            self.last_log_time = current_time

        # --- UI Drawing ---
        if is_stable:
            result_text = f"Color: {self.current_streak_color}"
            confidence_text = f"Acc: {stable_acc:.0f}%"
            box_color = Config.UI_COLORS['GREEN']
        else:
            result_text = "Scanning..."
            confidence_text = ""
            box_color = Config.UI_COLORS['GRAY']

        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 3)
        UIRenderer.draw_text_with_background(frame, result_text, (x1, y1 - 40), font_scale=0.7)
        UIRenderer.draw_text_with_background(frame, confidence_text, (x1, y1 - 15), font_scale=0.6)

        # --- Speech Logic ---
        if is_stable and stable_acc > Config.ACCURACY_THRESHOLD:
            if (self.last_announced_color != self.current_streak_color) or \
               (current_time - self.last_announce_time > self.speak_delay):
                
                # กรองครั้งสุดท้าย: ถ้าเป็น White/Black/Gray ต้องมั่นใจจริงๆ (Acc > 85)
                if self.current_streak_color in ["White", "Black", "Gray"]:
                     if stable_acc < 85: return 

                print(f"🗣️ SPEAKING: {self.current_streak_color}")
                self.tts.speak(f"{self.current_streak_color}")
                
                self.last_announced_color = self.current_streak_color
                self.last_announce_time = current_time

# --- Object Detector (เหมือนเดิม) ---
class ObjectOnlyDetector:
    def __init__(self, tts_handler, color_analyzer):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        if self.device == 'cuda':
            self.providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        else:
            self.providers = ['CPUExecutionProvider']
            
        self.model_path = Config.MODEL_PATH
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"❌ ONNX Model file not found: {self.model_path}")
            
        try:
            self.session = ort.InferenceSession(self.model_path, providers=self.providers)
            self.input_name = self.session.get_inputs()[0].name
            self.input_shape = self.session.get_inputs()[0].shape
            self.output_names = [output.name for output in self.session.get_outputs()]
            print(f"✅ ONNX model loaded! (Input: {self.input_shape})")
            
            self.custom_classes = self._load_class_names_from_yaml(Config.DATA_YAML_PATH)
            if not self.custom_classes:
                self.custom_classes = {0: 'Object'}
            print(f"✅ Loaded {len(self.custom_classes)} classes.")
        except Exception as e:
            print(f"❌ Error loading ONNX model: {e}")
            raise

        self.tts = tts_handler
        self.color_analyzer = color_analyzer
        self.last_announced_objects = {}
        self.tracked_objects = {}
        self.last_log_time = 0

    def _load_class_names_from_yaml(self, yaml_path):
        if not os.path.exists(yaml_path): return None
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            names = data.get('names')
            if isinstance(names, list): return {i: name for i, name in enumerate(names)}
            elif isinstance(names, dict): return names
            return None
        except: return None

    def _preprocess(self, frame):
        input_height, input_width = self.input_shape[2], self.input_shape[3]
        input_img = cv2.resize(frame, (input_width, input_height))
        input_img = cv2.cvtColor(input_img, cv2.COLOR_BGR2RGB)
        input_img = input_img.astype(np.float32) / 255.0
        input_img = np.transpose(input_img, (2, 0, 1))
        input_img = np.expand_dims(input_img, axis=0)
        return input_img

    def detect_objects(self, frame):
        original_h, original_w = frame.shape[:2]
        input_tensor = self._preprocess(frame)
        try:
            outputs = self.session.run(self.output_names, {self.input_name: input_tensor})
            predictions = outputs[0]
            if predictions.shape[1] > predictions.shape[2]: predictions = np.transpose(predictions, (0, 2, 1))
            predictions_tensor = torch.from_numpy(predictions)
            nms_results = non_max_suppression(predictions_tensor, conf_thres=Config.OBJECT_CONFIDENCE_THRESHOLD, iou_thres=Config.IOU_THRESHOLD, max_det=10)
            
            detections = []
            if nms_results and nms_results[0] is not None and len(nms_results[0]) > 0:
                detections_tensor = nms_results[0]
                detections_tensor[:, :4] = scale_boxes((self.input_shape[2], self.input_shape[3]), detections_tensor[:, :4], (original_h, original_w)).round()
                current_detections_np = detections_tensor.cpu().numpy()
                self._update_tracked_objects(current_detections_np)
                stable_detections = self._get_stable_detections()
                detections.extend(stable_detections)
            self._cleanup_old_tracks()
            return detections
        except Exception:
            return []

    def draw_and_announce_fused(self, frame, detections):
        height, width = frame.shape[:2]
        current_time = time.time()
        should_log = (current_time - self.last_log_time > 1.0)
        if should_log: self.last_log_time = current_time

        for det in detections:
            x1, y1, x2, y2 = det['bbox']; name = det['name']; accuracy = det['accuracy']
            
            if should_log:
                print(f"📦 Object: {name} | Confidence: {accuracy:.1f}%")

            roi = frame[y1:y2, x1:x2]
            if roi.size == 0: continue
            color, delta_e = self.color_analyzer.analyze_color(roi)
            color_accuracy = max(0, 100 - delta_e)
            
            if color != "Unknown" and color_accuracy > 60:
                label = f"{color} {name} ({accuracy:.0f}%)"; announcement = f"I see a {color} {name}"; box_color = Config.UI_COLORS['GREEN']
            else:
                label = f"{name} ({accuracy:.0f}%)"; announcement = f"I see a {name}"; box_color = Config.UI_COLORS['YELLOW']
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
            UIRenderer.draw_text_with_background(frame, label, (x1, y1 - 5), font_scale=0.6)
            
            if (accuracy >= Config.ACCURACY_THRESHOLD and (name not in self.last_announced_objects or current_time - self.last_announced_objects.get(name, 0) > Config.OBJECT_SPEAK_DELAY)):
                if not self.tts.is_currently_speaking():
                    self.tts.speak(announcement); self.last_announced_objects[name] = current_time

    def _get_centroid(self, bbox): return (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    def _update_tracked_objects(self, current_detections_np):
        current_time = time.time()
        for class_id in self.tracked_objects:
            for track in self.tracked_objects[class_id]: track['updated_this_frame'] = False
        for det in current_detections_np:
            x1, y1, x2, y2, conf, cls_id_float = det
            class_id = int(cls_id_float); bbox = [int(x1), int(y1), int(x2), int(y2)]; centroid = self._get_centroid(bbox)
            if class_id not in self.tracked_objects: self.tracked_objects[class_id] = []
            best_match_track = None; min_dist = float('inf')
            for track in self.tracked_objects[class_id]:
                dist = math.hypot(centroid[0] - track['centroid'][0], centroid[1] - track['centroid'][1])
                if dist < 50 and dist < min_dist: min_dist = dist; best_match_track = track
            if best_match_track:
                best_match_track['history'].append(conf); best_match_track['bbox'] = bbox; best_match_track['centroid'] = centroid
                best_match_track['last_seen'] = current_time; best_match_track['updated_this_frame'] = True
            else:
                self.tracked_objects[class_id].append({'history': deque([conf], maxlen=5), 'bbox': bbox, 'centroid': centroid, 'last_seen': current_time, 'updated_this_frame': True, 'name': self.custom_classes.get(class_id, f"unknown_{class_id}")})
        for class_id in self.tracked_objects:
            for track in self.tracked_objects[class_id]:
                if not track['updated_this_frame']: track['history'].append(None)
    def _get_stable_detections(self):
        stable_detections = []
        for class_id, tracks in self.tracked_objects.items():
            for track in tracks:
                if sum(1 for conf in track['history'] if conf is not None) >= 3:
                    valid_confs = [conf for conf in track['history'] if conf is not None]
                    avg_conf = sum(valid_confs) / len(valid_confs)
                    stable_detections.append({'name': track['name'], 'bbox': track['bbox'], 'confidence': float(avg_conf), 'accuracy': float(avg_conf) * 100, 'class_id': class_id})
        return stable_detections
    def _cleanup_old_tracks(self):
        current_time = time.time(); keys_to_delete = []
        for class_id, tracks in self.tracked_objects.items():
            self.tracked_objects[class_id] = [track for track in tracks if current_time - track['last_seen'] < 1.0]
            if not self.tracked_objects[class_id]: keys_to_delete.append(class_id)
        for key in keys_to_delete: del self.tracked_objects[key]

class DualModeDetector:
    def __init__(self):
        print("🔄 Initializing detection systems...")
        self.tts_handler = CachedTTS()
        self.color_analyzer = PerceptualColorAnalyzer()
        self.color_detector = ColorOnlyDetector(self.tts_handler, self.color_analyzer)
        try:
            self.object_detector = ObjectOnlyDetector(self.tts_handler, self.color_analyzer)
            print("✅ Object Detection initialized successfully")
        except Exception as e:
            print(f"❌ Could not initialize Object Detector: {e}"); self.object_detector = None
        self.current_mode = 1; print("✅ Dual Mode initialized. Starting in SAFE (Color) mode.")
    def run(self): pass
    def process_frame(self, frame):
        if self.current_mode == 1: self.color_detector.detect_and_announce_color(frame); mode_info = "MODE 1: COLOR"
        elif self.current_mode == 2 and self.object_detector: detections = self.object_detector.detect_objects(frame); self.object_detector.draw_and_announce_fused(frame, detections); mode_info = "MODE 2: OBJECT"
        else: self.color_detector.detect_and_announce_color(frame); mode_info = "FALLBACK"
        cv2.putText(frame, mode_info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        return frame
