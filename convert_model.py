# convert_model.py
# (ลบ 'nx' ที่ผิดพลาดจากบรรทัดแรกแล้ว)
from onnx import version_converter
import os
import onnx # เพิ่ม import ที่จำเป็น
import onnx.checker # เพิ่ม import ที่ขาดหายไป

def convert_onnx_opset(input_file, output_file, target_opset=11):
    """Converts an ONNX model from opset 19 to 11."""
    
    print(f"🔄 Converting {input_file} from opset 19 to opset {target_opset}...")
    
    try:
        # Load the model
        print("📥 Loading model...")
        model = onnx.load(input_file)
        
        print(f"📊 Original Model:")
        print(f"    - Opset version: {model.opset_import[0].version}")
        print(f"    - IR version: {model.ir_version}")
        print(f"    - Producer: {model.producer_name}")
        
        # Convert to the desired opset
        print(f"🔧 Converting to opset {target_opset}...")
        converted_model = version_converter.convert_version(model, target_opset)
        
        # Save the new model
        print(f"💾 Saving to {output_file}...")
        onnx.save(converted_model, output_file)
        
        # Check model validity
        print("✅ Checking new model...")
        onnx.checker.check_model(converted_model)
        
        # Display new model info
        new_model = onnx.load(output_file)
        print(f"📊 New Model:")
        print(f"    - Opset version: {new_model.opset_import[0].version}")
        print(f"    - IR version: {new_model.ir_version}")
        
        # Compare file sizes
        old_size = os.path.getsize(input_file) / 1024 / 1024
        new_size = os.path.getsize(output_file) / 1024 / 1024
        print(f"📏 File Size:")
        print(f"    - Old: {old_size:.2f} MB")
        print(f"    - New: {new_size:.2f} MB")
        
        print(f"🎉 Conversion successful! Use file: {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        return False

def backup_original_model(model_path):
    """Backs up the original model."""
    backup_path = model_path.replace('.onnx', '_backup.onnx')
    
    if not os.path.exists(backup_path):
        print(f"💾 Backing up original model to: {backup_path}")
        import shutil
        shutil.copy2(model_path, backup_path)
        print("✅ Backup complete")
    else:
        print("✅ Backup file already exists")

def test_converted_model(model_path):
    """Tests the converted model."""
    try:
        import onnxruntime as ort
        
        print(f"🧪 Testing model: {model_path}")
        
        # Create a session
        session = ort.InferenceSession(model_path)
        
        # Get input/output info
        input_info = session.get_inputs()[0]
        output_info = session.get_outputs()[0]
        
        print(f"✅ Model is functional!")
        print(f"    - Input: {input_info.name} {input_info.shape}")
        print(f"    - Output: {output_info.name} {output_info.shape}")
        
        return True
        
    except Exception as e:
        print(f"❌ Model test failed: {e}")
        return False

def main():
    """Main function for model conversion."""
    
    original_model = "runs/detect/train4/weights/best.onnx"
    converted_model = "runs/detect/train4/weights/best_opset11.onnx"
    
    print("🎯 ONNX Model Converter - Opset 19 → 11")
    print("=" * 50)
    
    # Check if the original file exists
    if not os.path.exists(original_model):
        print(f"❌ File not found: {original_model}")
        print("Please check the MODEL_PATH in convert_model.py")
        return False
    
    # Backup the original model
    backup_original_model(original_model)
    
    # Convert the model
    if convert_onnx_opset(original_model, converted_model, target_opset=11):
        # Test the new model
        if test_converted_model(converted_model):
            print("\n🎉 All conversions successful!")
            print(f"📝 How to use:")
            print(f"    1. Edit the utils.py file")
            print(f"    2. Change MODEL_PATH from 'best.onnx' to 'best_opset11.onnx'")
            print(f"    3. Or rename the new file to 'best.onnx'")
            
            # Offer to rename the file
            choice = input("\n❓ Do you want to rename the new file to 'best.onnx' now? (y/n): ")
            if choice.lower() == 'y':
                import shutil
                # เปลี่ยนชื่อตัวเก่าไปเป็น _opset19
                shutil.move(original_model, original_model.replace('.onnx', '_opset19.onnx'))
                # เปลี่ยนชื่อตัวใหม่ (opset11) ให้เป็น best.onnx
                shutil.move(converted_model, original_model)
                print("✅ File renamed successfully!")
                print(f"    - Original model (old): {original_model.replace('.onnx', '_opset19.onnx')}")
                print(f"    - New model (in use): {original_model}")
                
                # ถ้า rename แล้ว ไม่ต้องอัปเดต config
                return True
            
            # ถ้าไม่ rename ให้อัปเดต config
            return update_config_file()
        else:
            print("\n❌ Converted model is not functional")
            return False
    else:
        print("\n❌ Conversion failed")
        return False

# Manual fix instructions
def manual_fix_instructions():
    """Instructions for a manual fix."""
    
    print("\n📋 Alternative Fixes:")
    print("=" * 30)
    
    print("\n1️⃣ Re-export from the original machine:")
    print("    yolo export model=runs/detect/train4/weights/best.pt format=onnx opset=11 simplify=True")
    
    print("\n2️⃣ Use the PyTorch model instead (recommended):")
    print("    - Edit detectors.py")
    print("    - Change from onnxruntime to ultralytics YOLO")
    print("    - Use the .pt file instead of .onnx")
    
    print("\n3️⃣ Upgrade ONNX Runtime:")
    print("    pip3 install --upgrade onnxruntime")
    print("    # or for Jetson Nano:")
    print("    pip3 install onnxruntime-gpu")
    
    print("\n4️⃣ Download a compatible model:")
    print("    wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.onnx")

# Script to automatically update utils.py
def update_config_file():
    """Updates config to use the new model."""
    
    config_file = "utils.py"
    
    if not os.path.exists(config_file):
        print(f"❌ File not found: {config_file}")
        return False
    
    try:
        # Read the file
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace the path
        old_path = 'MODEL_PATH = "runs/detect/train4/weights/best.onnx"'
        new_path = 'MODEL_PATH = "runs/detect/train4/weights/best_opset11.onnx"'
        
        if old_path in content:
            content = content.replace(old_path, new_path)
            
            # Save the file
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ Successfully updated {config_file} to use new opset 11 model.")
            return True
        else:
            print(f"⚠️ MODEL_PATH not found in {config_file} or already updated.")
            return False
            
    except Exception as e:
        print(f"❌ Could not update {config_file}: {e}")
        return False

if __name__ == "__main__":
    # Install dependencies if necessary
    try:
        # import onnx (ย้ายไปไว้ข้างบนแล้ว)
        # from onnx import version_converter (ย้ายไปไว้ข้างบนแล้ว)
        pass # Imports are now global
    except ImportError:
        print("❌ Please install ONNX tools first:")
        print("pip3 install onnx onnx-tools")
        exit(1)
    
    # Run the conversion
    success = main()
    
    if not success:
        # Show alternative fixes if main conversion fails
        manual_fix_instructions()
