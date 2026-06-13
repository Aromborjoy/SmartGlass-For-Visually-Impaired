#!/bin/bash
# === connect_bt.sh (V55: CARD ENFORCER) ===

# รอระบบบูต
sleep 10

SPEAKER_MAC="72:79:CF:D7:11:C3"
# แปลง MAC Address เป็นรูปแบบที่ PulseAudio ใช้ (เปลี่ยน : เป็น _)
MAC_UNDERSCORE="${SPEAKER_MAC//:/_}"
CARD_NAME="bluez_card.$MAC_UNDERSCORE"
SINK_NAME="bluez_sink.$MAC_UNDERSCORE.a2dp_sink"

echo "=========================================="
echo "🎧 SMART GLASS: CONNECTION FIX"
echo "=========================================="

# 1. 🔧 CONFIG ENV
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export PULSE_RUNTIME_PATH="/run/user/$(id -u)/pulse"

# 2. ⏳ WAITING FOR PULSEAUDIO
echo "⏳ Waiting for PulseAudio..."
while ! pactl info > /dev/null 2>&1; do
    sleep 2
done
echo "✅ PulseAudio is READY!"

# โหลด Module จำเป็น (กันเหนียว)
pactl load-module module-bluetooth-discover >/dev/null 2>&1 || true
pactl load-module module-switch-on-connect >/dev/null 2>&1 || true

# 3. 🔵 SMART CONNECTION LOOP
echo "🔵 Connecting Bluetooth..."

# วนลูปจนกว่าจะเจอ SINK (ท่อเสียง)
while ! pactl list sinks short | grep -q "$MAC_UNDERSCORE"; do
    
    # เช็คก่อนว่า "เชื่อม Hardware ติดหรือยัง?" (เช็ค Card)
    if pactl list cards short | grep -q "$MAC_UNDERSCORE"; then
        echo "🃏 Bluetooth connected! Forcing Audio Profile..."
        
        # นี่คือจุดสำคัญ! บังคับเปิดโหมด A2DP เดี๋ยวนี้!
        pactl set-card-profile "$CARD_NAME" a2dp_sink 2>/dev/null
        pactl set-card-profile "$CARD_NAME" a2dp_sink 2>/dev/null
        
        sleep 2
    else
        # ถ้ายังไม่เชื่อม Hardware เลย ให้สั่ง Connect
        echo "📡 Attempting to connect via bluetoothctl..."
        bluetoothctl <<EOF
trust $SPEAKER_MAC
connect $SPEAKER_MAC
exit
EOF
        # รอให้มันจับคู่
        sleep 5
    fi
done

echo "✅ SUCCESS: Audio Sink Found!"

# 4. 🔊 SET VOLUME & TEST
pactl set-default-sink "$SINK_NAME" 2>/dev/null
pactl set-sink-volume "$SINK_NAME" 100% 2>/dev/null

# ส่งเสียงเตือนว่าพร้อมแล้ว (ใช้ paplay หรือ espeak-ng)
nice -n -20 espeak-ng "System Online" 2>/dev/null

# 5. 🚀 LAUNCH PYTHON
echo "🚀 Launching Python..."
cd /home/bailey/SmartGlass
exec /home/bailey/miniconda3/envs/yolo/bin/python3 -u jetson_adapter.py
