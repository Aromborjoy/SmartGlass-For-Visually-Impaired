# jetson_adapter.py (V30: YUYV 640x480 - High Accuracy Color)
import os
import sys
import time
import threading
import subprocess
import cv2
import psutil
import queue
import numpy as np

GPIO_AVAILABLE = False 

# --- [WORKER CLASS] ---
class DetectionWorker(threading.Thread):
    def __init__(self, detector_system, input_q, output_q):
        super().__init__(daemon=True)
        self.detector = detector_system
        self.input_q = input_q
        self.output_q = output_q
        self.stop_signal = False
        print("✅ DetectionWorker initialized.")

    def run(self):
        print("🚀 DetectionWorker thread started.")
        while not self.stop_signal:
            try:
                frame = self.input_q.get(timeout=1)
            except queue.Empty:
                continue
            try:
                processed_frame = self.detector.process_frame(frame)
                try:
                    self.output_q.put_nowait(processed_frame)
                except queue.Full:
                    pass
            except Exception as e:
                print(f"❌ Error in Worker Thread: {e}")
        print("🛑 DetectionWorker thread stopped.")

# --- [CAMERA MANAGER] ---
class JetsonCameraManager:
    def __init__(self):
        self.camera_type = None
        self.camera_index = 0

    def create_optimized_capture(self, preferred_type=None):
        # =========================================================
        # 📷 USB CAMERA FIX (YUYV Mode for Better Color)
        # =========================================================
        print("🔍 Scanning for USB Cameras (Force YUYV 640x480)...")
        
        for i in range(4):
            print(f"   Testing /dev/video{i} ...")
            try:
                # 1. เปิดด้วย V4L2 (มาตรฐาน Linux)
                cap = cv2.VideoCapture(i, cv2.CAP_V4L2)

                if not cap or not cap.isOpened():
                    if cap: cap.release()
                    continue

                # 2. [IMPORTANT] บังคับใช้ YUYV (ภาพดิบ สีสด ไม่เพี้ยน)
                # ต้องตั้งค่า FourCC ก่อนอ่านภาพเสมอ
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))
                
                # 3. [CRITICAL] ต้องใช้ความละเอียดนี้เท่านั้น (ตามสเปกกล้อง)
                # ถ้าตั้งผิด Bandwidth จะเต็มและภาพจะดำ
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 30)
                
                # ลองอ่านภาพจริง 1 เฟรม
                ret, frame = cap.read()
                if not ret or frame is None:
                    print(f"   ❌ Index {i} opened but no frame (Bandwidth limit?).")
                    cap.release()
                    continue

                print(f"✅ FOUND USB Camera at index {i} (Mode: YUYV 640x480)")
                
                # 4. พยายามปิด Auto Exposure (ถ้าทำได้) เพื่อให้สีนิ่งที่สุด
                try:
                    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25) # Manual Mode
                    # cap.set(cv2.CAP_PROP_EXPOSURE, -5) # ปลดบรรทัดนี้ถ้าต้องการปรับแสงเอง
                except:
                    pass

                return cap

            except Exception as e:
                print(f"   ❌ Error checking index {i}: {e}")
                
        print("❌ No working USB Camera found on any index!")
        return None

# --- [AUDIO MANAGER] ---
class JetsonAudioManager:
    """
    Enhanced Audio Manager with Auto-Recovery
    ตรวจสอบและซ่อมแซม Bluetooth audio อัตโนมัติ
    """
    def __init__(self):
        self.target_speaker_mac = "72_79_CF_D7_11_C3"
        self.sink_name = f"bluez_sink.{self.target_speaker_mac}.a2dp_sink"
        self.monitoring = False
        self.monitor_thread = None
        self.last_check_time = 0
        self.check_interval = 15  # ตรวจทุก 15 วินาที

    def setup_audio(self):
        """Initial audio setup"""
        try:
            os.environ['SDL_AUDIODRIVER'] = 'pulse'
            pulse_path = '/run/user/1000/pulse'
            if os.path.exists(pulse_path):
                os.environ['PULSE_RUNTIME_PATH'] = pulse_path
            
            print("✅ Audio setup complete.")
            
            # เริ่ม monitor
            self.start_monitoring()
            
        except Exception as e:
            print(f"⚠️  Audio setup warning: {e}")

    def is_bluetooth_connected(self):
        """ตรวจสอบว่า Bluetooth Sink ยังเชื่อมต่ออยู่หรือไม่"""
        try:
            # วิธีที่ 1: เช็ค PulseAudio Sink (เร็วที่สุด)
            result = subprocess.run(
                ['pactl', 'list', 'sinks', 'short'],
                capture_output=True,
                text=True,
                timeout=3
            )
            if self.target_speaker_mac in result.stdout:
                return True
            
            # วิธีที่ 2: เช็คผ่าน bluetoothctl (สำรอง)
            mac_address = self.target_speaker_mac.replace('_', ':')
            result = subprocess.run(
                ['bluetoothctl', 'info', mac_address],
                capture_output=True,
                text=True,
                timeout=3
            )
            return "Connected: yes" in result.stdout
            
        except:
            return False

    def reconnect_bluetooth(self):
        """พยายามเชื่อมต่อ Bluetooth ใหม่"""
        print(f"[{time.strftime('%H:%M:%S')}] 🔄 Attempting Bluetooth reconnect...")
        
        try:
            # แปลง MAC address กลับเป็นรูปแบบปกติ
            mac_address = self.target_speaker_mac.replace('_', ':')
            
            # ใช้ bluetoothctl เชื่อมต่อ
            connect_cmd = f"echo 'connect {mac_address}' | bluetoothctl"
            subprocess.run(
                connect_cmd,
                shell=True,
                timeout=10,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # รอให้ PulseAudio รับรู้
            time.sleep(3)
            
            # ตั้งค่าใหม่
            if self.is_bluetooth_connected():
                subprocess.run(['pactl', 'set-default-sink', self.sink_name],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(['pactl', 'set-sink-volume', self.sink_name, '100%'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"[{time.strftime('%H:%M:%S')}] ✅ Bluetooth reconnected!")
                return True
            else:
                print(f"[{time.strftime('%H:%M:%S')}] ❌ Reconnection failed")
                return False
                
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️  Reconnect error: {e}")
            return False

    def _monitor_loop(self):
        """Background thread สำหรับ monitor Bluetooth"""
        print("🛡️  Audio monitor started")
        consecutive_failures = 0
        
        while self.monitoring:
            try:
                current_time = time.time()
                
                # ตรวจสอบทุก check_interval วินาที
                if current_time - self.last_check_time < self.check_interval:
                    time.sleep(1)
                    continue
                
                self.last_check_time = current_time
                
                # ตรวจสอบสถานะ
                if not self.is_bluetooth_connected():
                    consecutive_failures += 1
                    print(f"[{time.strftime('%H:%M:%S')}] ⚠️  Bluetooth disconnected! (Attempt {consecutive_failures})")
                    
                    # พยายามเชื่อมต่อใหม่
                    if self.reconnect_bluetooth():
                        consecutive_failures = 0
                    elif consecutive_failures >= 3:
                        print(f"[{time.strftime('%H:%M:%S')}] ❌ Multiple reconnect failures. Resetting Bluetooth...")
                        self._reset_bluetooth_stack()
                        consecutive_failures = 0
                else:
                    # เชื่อมต่ออยู่ปกติ
                    if consecutive_failures > 0:
                        consecutive_failures = 0
                
                time.sleep(1)
                
            except Exception as e:
                print(f"Audio monitor error: {e}")
                time.sleep(5)

    def _reset_bluetooth_stack(self):
        """รีเซ็ต Bluetooth stack ทั้งหมด (กรณีฉุกเฉิน)"""
        try:
            print("🔧 Resetting Bluetooth stack...")
            
            # Restart Bluetooth service
            subprocess.run(['sudo', 'systemctl', 'restart', 'bluetooth'],
                         timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
            
            # Restart PulseAudio
            subprocess.run(['pulseaudio', '-k'], 
                         timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)
            subprocess.run(['pulseaudio', '--start', '--log-target=syslog'],
                         timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)
            
            # โหลดโมดูลใหม่
            subprocess.run(['pactl', 'load-module', 'module-bluetooth-discover'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # พยายามเชื่อมต่อ
            time.sleep(2)
            self.reconnect_bluetooth()
            
        except Exception as e:
            print(f"Bluetooth reset error: {e}")

    def start_monitoring(self):
        """เริ่ม monitoring thread"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()

    def stop_monitoring(self):
        """หยุด monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)

# --- [SYSTEM MONITOR] ---
class JetsonSystemMonitor:
    def __init__(self):
        self.monitoring = False
        self.monitor_thread = None

    def start_monitoring(self):
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            print("✅ System monitoring started.")

    def stop_monitoring(self):
        self.monitoring = False
        if self.monitor_thread: self.monitor_thread.join(timeout=1)

    def _monitor_loop(self):
        while self.monitoring:
            try:
                cpu = psutil.cpu_percent(interval=None)
                if cpu > 95: print(f"⚠️ [MONITOR] CPU Load High: {cpu}%")
                time.sleep(10)
            except Exception:
                time.sleep(10)

# --- [MAIN ADAPTER] ---
class JetsonAdapter:
    def __init__(self):
        self.camera_manager = JetsonCameraManager()
        self.audio_manager = JetsonAudioManager()
        self.system_monitor = JetsonSystemMonitor()
        self.detector_system_instance = None
        self.is_jetson = True

    def setup_environment(self):
        self.audio_manager.setup_audio()
        self.system_monitor.start_monitoring()
        print("✅ Environment setup complete.")

    def run_main_system(self, preferred_camera_type=None):
        worker = None
        cap = None
        try:
            self.setup_environment()
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from detectors import DualModeDetector
            self.detector_system_instance = DualModeDetector()

            input_q = queue.Queue(maxsize=1)
            output_q = queue.Queue(maxsize=1)
            worker = DetectionWorker(self.detector_system_instance, input_q, output_q)
            worker.start()

            # Initial Camera Load
            cap = self.camera_manager.create_optimized_capture(preferred_camera_type)
            if cap is None or not cap.isOpened():
                print("❌ Initial camera fail. Entering recovery loop...")
                cap = None

            print("✅ Headless main loop running...")

            # Settings for Gesture
            DARKNESS_THRESHOLD = 15.0
            DOUBLE_TAP_TIME = 1.5
            first_tap_time = 0.0
            is_covered = False

            # พูดเปิดตัว
            self.detector_system_instance.tts_handler.speak("Color Mode")

            while True:
                # --- Recovery Loop ---
                if cap is None or not cap.isOpened():
                    print("❌ Camera disconnected. Retrying...")
                    if cap: cap.release()
                    time.sleep(2)
                    cap = self.camera_manager.create_optimized_capture(preferred_camera_type)
                    if cap is None or not cap.isOpened():
                        continue 
                    print("✅ Camera recovered!")

                # --- Read Frame ---
                ret, frame = cap.read()
                if not ret:
                    cap.release()
                    continue

                # --- Gesture Logic (Cover Camera to Switch) ---
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                brightness = cv2.mean(gray)[0]
                currently_covered = brightness < DARKNESS_THRESHOLD
                now = time.time()
                
                if currently_covered and not is_covered:
                    is_covered = True
                    if (now - first_tap_time) < DOUBLE_TAP_TIME:
                        print("🖐️ [GESTURE] Switching Mode!")
                        detector = self.detector_system_instance
                        new_mode = 2 if detector.current_mode == 1 else 1
                        detector.current_mode = new_mode
                        
                        announcement = "Object Mode" if new_mode == 2 else "Color Mode"
                        detector.tts_handler.speak(announcement)
                        first_tap_time = 0.0
                    else:
                        first_tap_time = now
                elif not currently_covered and is_covered:
                    is_covered = False

                # ส่งภาพเข้าคิวไปประมวลผล (ถ้าว่าง)
                try: input_q.put_nowait(frame.copy())
                except queue.Full: pass
                
                # รับผลลัพธ์ (ถ้ามี) - จริงๆ ส่วนนี้เอาไว้โชว์ภาพ แต่ Headless ไม่ได้ใช้
                try: output_q.get_nowait()
                except queue.Empty: pass

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("Shutting down...")
            if worker:
                worker.stop_signal = True
                worker.join(timeout=2)
            self.system_monitor.stop_monitoring()
            if cap: cap.release()
            cv2.destroyAllWindows()

def main():
    print("="*60)
    print("🎯 Smart Glass - YUYV Edition (High Accuracy)")
    print("="*60)
    adapter = JetsonAdapter()
    adapter.run_main_system(None)

if __name__ == "__main__":
    main()
