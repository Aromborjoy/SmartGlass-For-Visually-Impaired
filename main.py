# main.py
import cv2
from detectors import DualModeDetector 

def main():
    """
    """
    try:
        print("🚀 Starting Smart Glass Detection System...")
        detector_system = DualModeDetector()
        detector_system.run()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("System shutting down.")
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()