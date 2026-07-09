#!/bin/bash
#
# pair_ps5_controller.sh
# -----------------------------------------------------------------------------
# One-shot helper to pair a Sony PS5 DualSense (or PS4 DualShock 4) controller
# to a Qmini robot over Bluetooth, and make it reliably auto-reconnect whenever
# the controller is powered on again -- including after a reboot.
#
# Run this ON the robot (e.g. the Jetson), as it needs local Bluetooth + root:
#
#     sudo ./scripts/pair_ps5_controller.sh                 # pair + persist
#     sudo ./scripts/pair_ps5_controller.sh --install-service   # also install the boot service
#     sudo ./scripts/pair_ps5_controller.sh --service-only      # only (re)install the service
#     sudo ./scripts/pair_ps5_controller.sh --mac AA:BB:..      # skip scan, use this MAC
#
# Why this script exists (three gotchas it works around):
#   1. BlueZ refuses HID input from the controller unless ClassicBondedOnly is
#      disabled -> the pad connects but no /dev/input/js0 is ever created.
#   2. The kernel needs the `uhid` and `joydev` modules for a gamepad node.
#   3. DualSense/DualShock send their link key with store_hint=0, so BlueZ never
#      saves it -> the pad authenticates once, then fails ("status 0x5") on every
#      later reconnect. We capture the key with btmon and write it to disk so the
#      bond is permanent.
# -----------------------------------------------------------------------------
set -u

SERVICE_NAME="qmini-ds-autoconnect"
CONTROLLER_NAME_RE="DualSense Wireless Controller|Wireless Controller"  # PS5 | PS4
MAC=""
DO_PAIR=1
DO_SERVICE=0

log()  { printf '\033[1;36m[pair]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[err ]\033[0m %s\n' "$*" >&2; }

# ---- args -------------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --install-service) DO_SERVICE=1 ;;
        --service-only)    DO_SERVICE=1; DO_PAIR=0 ;;
        --mac)             shift; MAC="$1" ;;
        -h|--help)         grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) err "unknown arg: $1"; exit 1 ;;
    esac
    shift
done

if [ "$(id -u)" -ne 0 ]; then
    err "please run as root (sudo $0 ...)"; exit 1
fi

for tool in bluetoothctl btmon; do
    command -v "$tool" >/dev/null 2>&1 || { err "missing '$tool' (apt install bluez)"; exit 1; }
done

# =============================================================================
# 1. Host-side setup: kernel modules + BlueZ config (idempotent)
# =============================================================================
setup_host() {
    log "Loading and persisting kernel modules (uhid, joydev)..."
    modprobe uhid   2>/dev/null || true
    modprobe joydev 2>/dev/null || true
    printf 'uhid\njoydev\n' > /etc/modules-load.d/qmini-controller.conf

    log "Allowing HID input from non-bonded pads (ClassicBondedOnly=false)..."
    local ic=/etc/bluetooth/input.conf
    if [ -f "$ic" ] && grep -qE '^\s*ClassicBondedOnly' "$ic"; then
        sed -i 's/^\s*#\?\s*ClassicBondedOnly.*/ClassicBondedOnly=false/' "$ic"
    elif [ -f "$ic" ] && grep -q '^\[General\]' "$ic"; then
        sed -i '/^\[General\]/a ClassicBondedOnly=false' "$ic"
    else
        printf '[General]\nClassicBondedOnly=false\n' >> "$ic"
    fi

    log "Ensuring the adapter powers on at boot (AutoEnable=true)..."
    local mc=/etc/bluetooth/main.conf
    if grep -qE '^\s*#?\s*AutoEnable' "$mc" 2>/dev/null; then
        sed -i 's/^\s*#\?\s*AutoEnable.*/AutoEnable=true/' "$mc"
    elif grep -q '^\[Policy\]' "$mc" 2>/dev/null; then
        sed -i '/^\[Policy\]/a AutoEnable=true' "$mc"
    else
        printf '\n[Policy]\nAutoEnable=true\n' >> "$mc"
    fi

    log "Restarting bluetooth so config changes take effect..."
    systemctl restart bluetooth
    sleep 2
    bluetoothctl power on >/dev/null 2>&1
}

# =============================================================================
# 2. Discover the controller MAC (must be in pairing mode)
# =============================================================================
find_controller() {
    log "Put the controller in PAIRING mode now:"
    log "  PS5 DualSense : hold  Create (left of touchpad) + PS  until the bar double-flashes"
    log "  PS4 DualShock : hold  Share  + PS                 until the bar double-flashes"
    read -r -p "Press Enter once the light bar is flashing rapidly... " _

    log "Scanning for the controller (up to ~20s)..."
    bluetoothctl --timeout 20 scan on >/dev/null 2>&1
    MAC=$(bluetoothctl devices 2>/dev/null \
            | grep -iE "$CONTROLLER_NAME_RE" | head -1 | awk '{print $2}')
    [ -n "$MAC" ] || { err "no controller found. Was it flashing? Retry."; exit 1; }
    log "Found controller: $MAC"
}

# =============================================================================
# 3. Pair while capturing the link key with btmon
# =============================================================================
pair_and_capture() {
    local cap=/tmp/qmini_btmon_capture.txt
    rm -f "$cap"
    btmon > "$cap" 2>&1 &
    local mon=$!

    bluetoothctl --timeout 45 scan on >/dev/null 2>&1 &
    local scan=$!

    log "Pairing $MAC (keep it in pairing mode)..."
    local ok=0 i
    for i in $(seq 1 20); do
        if bluetoothctl pair "$MAC" 2>&1 | grep -q "Pairing successful"; then
            ok=1; break
        fi
        sleep 2
    done
    kill "$scan" 2>/dev/null
    sleep 3
    kill "$mon"  2>/dev/null
    sleep 1

    [ "$ok" = 1 ] || { err "pairing failed - retry with the pad freshly in pairing mode"; exit 1; }
    bluetoothctl trust "$MAC" >/dev/null 2>&1
    log "Paired + trusted."

    # Extract the negotiated link key from the btmon capture.
    LINKKEY=$(grep -oiP 'Link key:\s*\K[0-9a-fA-F]{32}' "$cap" | tail -1 | tr 'a-f' 'A-F')
    LINKTYPE=$(grep -oiP 'Key type:.*\(0x\K[0-9a-fA-F]{2}' "$cap" | tail -1)
    LINKTYPE=$((16#${LINKTYPE:-04}))
    [ -n "$LINKKEY" ] || { err "could not capture link key from btmon output ($cap)"; exit 1; }
    log "Captured link key (type $LINKTYPE)."
}

# =============================================================================
# 4. Persist the link key into BlueZ storage (survives reboot)
# =============================================================================
persist_link_key() {
    local adapter info
    adapter=$(bluetoothctl list 2>/dev/null | awk '/Controller/{print $2; exit}')
    info="/var/lib/bluetooth/$adapter/$MAC/info"
    [ -f "$info" ] || { err "info file not found: $info"; exit 1; }

    log "Writing persistent [LinkKey] to $info ..."
    systemctl stop bluetooth
    sleep 1
    # remove any stale [LinkKey] block, then append the captured one
    sed -i '/^\[LinkKey\]/,/^\[/{/^\[LinkKey\]/d;/^Key=/d;/^Type=/d;/^PINLength=/d}' "$info"
    printf '\n[LinkKey]\nKey=%s\nType=%s\nPINLength=0\n' "$LINKKEY" "$LINKTYPE" >> "$info"
    systemctl start bluetooth
    sleep 2
    bluetoothctl power on >/dev/null 2>&1
    log "Link key persisted. The bond now survives reboots."
}

# =============================================================================
# 5. Optional: install the gentle boot-time auto-reconnect service
# =============================================================================
install_service() {
    [ -n "$MAC" ] || MAC=$(bluetoothctl devices 2>/dev/null \
        | grep -iE "$CONTROLLER_NAME_RE" | head -1 | awk '{print $2}')
    [ -n "$MAC" ] || { err "no paired controller MAC known; run pairing first"; exit 1; }

    log "Installing systemd service '$SERVICE_NAME' for $MAC ..."
    cat > /usr/local/bin/${SERVICE_NAME}.sh <<EOF
#!/bin/bash
# Gently keep the trusted controller connected. Controller-initiated reconnect
# (trust + persistent link key) does the real work; this just nudges a connect
# when the pad is on but idle, e.g. if it was already powered on at boot.
MAC="$MAC"
bluetoothctl power on     >/dev/null 2>&1
bluetoothctl trust "\$MAC" >/dev/null 2>&1
while true; do
    if bluetoothctl info "\$MAC" 2>/dev/null | grep -q "Connected: yes"; then
        sleep 15
    else
        bluetoothctl connect "\$MAC" >/dev/null 2>&1
        sleep 20
    fi
done
EOF
    chmod 755 /usr/local/bin/${SERVICE_NAME}.sh

    cat > /etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=Auto-connect trusted PS5/PS4 controller when powered on (Qmini)
After=bluetooth.service
Requires=bluetooth.service

[Service]
Type=simple
ExecStart=/usr/local/bin/${SERVICE_NAME}.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now ${SERVICE_NAME}.service
    log "Service enabled. Check it with: systemctl status ${SERVICE_NAME}"
}

# =============================================================================
# 6. Verify
# =============================================================================
verify() {
    sleep 1
    log "Verifying..."
    bluetoothctl info "$MAC" 2>/dev/null | grep -E "Name|Paired|Trusted|Connected" || true
    if ls /dev/input/js* >/dev/null 2>&1; then
        log "Gamepad node(s): $(ls /dev/input/js* 2>/dev/null | tr '\n' ' ')"
    else
        warn "No /dev/input/js* yet. Press the PS button to connect the pad."
    fi
}

# ---- main -------------------------------------------------------------------
if [ "$DO_PAIR" = 1 ]; then
    setup_host
    [ -n "$MAC" ] || find_controller
    pair_and_capture
    persist_link_key
    verify
    log "Done. Power-cycle the controller: it should reconnect on its own."
fi

if [ "$DO_SERVICE" = 1 ]; then
    install_service
fi
