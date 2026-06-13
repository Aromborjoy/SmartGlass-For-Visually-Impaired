#!/bin/bash
# === fix_pulseaudio_bt.sh - แก้ปัญหา Audio Sink ไม่ขึ้น ===

echo "🔧 Fixing PulseAudio Bluetooth Configuration..."

# ------------------------------------------------------
# 1. แก้ไข PulseAudio Default Config
# ------------------------------------------------------
echo "📝 Step 1: Updating PulseAudio default.pa..."

sudo tee -a /etc/pulse/default.pa > /dev/null << 'EOF'

### Bluetooth Audio Fix (Smart Glass)
.ifexists module-bluetooth-discover.so
load-module module-bluetooth-discover
load-module module-bluetooth-policy
.endif

### Auto-switch to Bluetooth when connected
load-module module-switch-on-connect

### Auto-detect Bluetooth cards
load-module module-udev-detect

### Enable native protocol
load-module module-native-protocol-unix
EOF

echo "   ✅ Updated /etc/pulse/default.pa"

# ------------------------------------------------------
# 2. แก้ไข PulseAudio System Mode (สำคัญมาก!)
# ------------------------------------------------------
echo "📝 Step 2: Enabling PulseAudio system-wide mode..."

# สร้างไฟล์ config สำหรับ system mode
sudo tee /etc/pulse/system.pa > /dev/null << 'EOF'
#!/usr/bin/pulseaudio -nF

# Load core modules
load-module module-device-restore
load-module module-card-restore
load-module module-udev-detect
load-module module-native-protocol-unix auth-anonymous=1

# Bluetooth support
.ifexists module-bluetooth-discover.so
load-module module-bluetooth-discover
load-module module-bluetooth-policy auto_switch=2
.endif

load-module module-switch-on-connect
load-module module-rescue-streams

# Network support (optional)
load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1

# Automatically restore volume
load-module module-default-device-restore
load-module module-always-sink
EOF

echo "   ✅ Created /etc/pulse/system.pa"

# ------------------------------------------------------
# 3. เพิ่ม User ให้อยู่ใน pulse-access group
# ------------------------------------------------------
echo "📝 Step 3: Adding user to pulse-access group..."

sudo usermod -a -G pulse-access bailey
sudo usermod -a -G bluetooth bailey

echo "   ✅ User added to groups"

# ------------------------------------------------------
# 4. สร้าง udev rule สำหรับ Bluetooth Audio
# ------------------------------------------------------
echo "📝 Step 4: Creating udev rule..."

sudo tee /etc/udev/rules.d/99-bluetooth-audio.rules > /dev/null << 'EOF'
# Auto-trust Bluetooth audio devices
SUBSYSTEM=="bluetooth", ATTR{address}=="72:79:CF:D7:11:C3", RUN+="/usr/bin/bluetoothctl trust 72:79:CF:D7:11:C3"

# Reload PulseAudio when Bluetooth device connects
SUBSYSTEM=="bluetooth", ACTION=="add", RUN+="/bin/su bailey -c 'pactl load-module module-bluetooth-discover'"
EOF

sudo udevadm control --reload-rules

echo "   ✅ Created udev rules"

# ------------------------------------------------------
# 5. แก้ไข Bluetooth Main Config
# ------------------------------------------------------
echo "📝 Step 5: Updating Bluetooth configuration..."

sudo tee /etc/bluetooth/main.conf > /dev/null << 'EOF'
[General]
Name = jetson
Class = 0x200414
DiscoverableTimeout = 0
AlwaysPairable = true
PairableTimeout = 0

[Policy]
AutoEnable=true
ReconnectAttempts=7
ReconnectIntervals=1,2,4,8,16,32,64

[LE]
MinConnectionInterval=7
MaxConnectionInterval=9
ConnectionLatency=0
EOF

echo "   ✅ Updated /etc/bluetooth/main.conf"

# ------------------------------------------------------
# 6. Restart Services
# ------------------------------------------------------
echo "🔄 Step 6: Restarting services..."

sudo systemctl restart bluetooth
sleep 2

pulseaudio -k
sleep 2
pulseaudio --start

echo "   ✅ Services restarted"

# ------------------------------------------------------
# 7. Test Connection
# ------------------------------------------------------
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Testing Bluetooth Connection..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SPEAKER_MAC="72:79:CF:D7:11:C3"

# Connect
echo "📡 Connecting to speaker..."
(echo "power on"; sleep 1; echo "trust $SPEAKER_MAC"; sleep 1; echo "connect $SPEAKER_MAC"; sleep 5; echo "exit") | bluetoothctl

sleep 5

# Check connection
if hcitool con | grep -qi "$SPEAKER_MAC"; then
    echo "✅ Bluetooth connected!"
    
    # Force load A2DP profile
    echo "🔊 Loading A2DP profile..."
    pactl load-module module-bluetooth-discover
    sleep 3
    
    # Check sink
    if pactl list sinks short | grep -q "bluez_sink"; then
        echo "✅ Audio sink detected!"
        SINK_NAME=$(pactl list sinks short | grep bluez_sink | awk '{print $2}')
        pactl set-default-sink "$SINK_NAME"
        pactl set-sink-volume "$SINK_NAME" 100%
        echo "✅ Audio configured!"
        
        # Test audio
        espeak-ng "Audio test successful" 2>/dev/null
    else
        echo "⚠️  Still no audio sink. Trying advanced fix..."
        
        # Manual card profile switch
        CARD=$(pactl list cards short | grep bluez | awk '{print $2}')
        if [ ! -z "$CARD" ]; then
            echo "   Found card: $CARD"
            pactl set-card-profile "$CARD" a2dp_sink
            sleep 2
            
            if pactl list sinks short | grep -q "bluez_sink"; then
                echo "✅ Audio sink NOW detected!"
                SINK_NAME=$(pactl list sinks short | grep bluez_sink | awk '{print $2}')
                pactl set-default-sink "$SINK_NAME"
                espeak-ng "Audio working now" 2>/dev/null
            fi
        fi
    fi
else
    echo "❌ Bluetooth not connected"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Configuration complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Next steps:"
echo "   1. Reboot your Jetson: sudo reboot"
echo "   2. After reboot, run: ./connect_bt.sh"
echo ""
