# tts_handler.py
import os
import re
import threading
import subprocess 

class CachedTTS:
    def __init__(self, cache_dir="tts_cache"):
        self.speaking_lock = threading.Lock()
        self.speaking_flag = False
        print("✅ Offline TTS (espeak-ng) initialized.")
        
        try:
            subprocess.run(['espeak-ng', '--version'], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except FileNotFoundError:
            print("="*50)
            print("❌ ERROR: 'espeak-ng' not found.")
            print("Please install it with: sudo apt install espeak-ng")
            print("="*50)
            raise
        except Exception as e:
            print(f"espeak-ng test failed: {e}")

    def _speak_task(self, text):
        with self.speaking_lock:
            self.speaking_flag = True
            try:
                subprocess.run(['espeak-ng', '-a', '150', '-s', '160', text], 
                               check=True, 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"espeak-ng error: {e}")
            finally:
                self.speaking_flag = False

    def speak(self, text):
        if self.is_currently_speaking():
            return
        threading.Thread(target=self._speak_task, args=(text,), daemon=True).start()

    def is_currently_speaking(self):
        return self.speaking_flag
