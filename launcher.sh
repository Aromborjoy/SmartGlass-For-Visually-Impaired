#!/bin/bash

# เพิ่มการหน่วงเวลา 10 วินาที เพื่อรอให้ระบบ Desktop พร้อมทำงาน 100%
sleep 10

# ระบุ Path ไปยังโฟลเดอร์ของโปรเจกต์
PROJECT_DIR="/home/bailey/SmartGlass"

# ระบุ Path ไปยังไฟล์ Log ที่เราจะสร้าง
LOG_FILE="$PROJECT_DIR/startup.log"

# เริ่มการบันทึก Log (ล้างไฟล์เก่าทุกครั้งที่เริ่ม)
echo "Starting script at $(date)" > "$LOG_FILE"

# ทำให้ Shell รู้จักคำสั่ง Conda
source /home/bailey/miniconda3/etc/profile.d/conda.sh >> "$LOG_FILE" 2>&1

# Activate Environment
echo "Activating Conda environment: yolo" >> "$LOG_FILE" 2>&1
conda activate yolo >> "$LOG_FILE" 2>&1

# สั่งรันไฟล์ Python และส่ง Output ทั้งหมดไปที่ Log File
echo "Executing Python script..." >> "$LOG_FILE" 2>&1
python "$PROJECT_DIR/main.py" >> "$LOG_FILE" 2>&1
