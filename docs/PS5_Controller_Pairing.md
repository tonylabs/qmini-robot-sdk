# Pairing a PS5 (DualSense) Controller to the Qmini Robot

This guide explains how to pair a Sony **PS5 DualSense** (or **PS4 DualShock 4**)
controller to the Qmini robot over Bluetooth so that:

* a gamepad node `/dev/input/js0` is created, and
* the controller **auto-reconnects whenever it is powered on** — including after
  a robot reboot — with no re-pairing.

A helper script, [`scripts/pair_ps5_controller.sh`](../scripts/pair_ps5_controller.sh),
automates the whole process. This document also explains what it does so you can
do it by hand or debug it.

> Tested on a Jetson Orin Nano (`5.15-tegra`, BlueZ 5.64, Ubuntu). The steps are
> generic to any Linux host using BlueZ.

---

## Quick start (recommended)

Run **on the robot** (it needs the robot's local Bluetooth adapter and root):

```bash
cd ~/Documents/GitHub/qmini-robot-sdk
sudo ./scripts/pair_ps5_controller.sh --install-service
```

Then follow the prompt:

1. With the controller **off**, put it in **pairing mode**:
   * **PS5 DualSense** — hold **Create** (small button left of the touchpad) **+ PS**
     until the light bar **double-flashes** rapidly.
   * **PS4 DualShock** — hold **Share + PS** until the light bar double-flashes.
2. Press **Enter** in the terminal.
3. Wait for `Done.` Then power-cycle the controller (hold **PS** ~10 s until it
   turns off, then a single **PS** press) — it should reconnect on its own and
   the light bar goes solid.

Verify:

```bash
ls /dev/input/js0                # gamepad node exists
bluetoothctl info <MAC> | grep Connected
```

### Command variants

| Command | What it does |
|---|---|
| `sudo ./scripts/pair_ps5_controller.sh` | Host setup + pair + persist link key |
| `sudo ./scripts/pair_ps5_controller.sh --install-service` | Same, **plus** install the boot auto-connect service |
| `sudo ./scripts/pair_ps5_controller.sh --service-only` | Only (re)install the service for an already-paired pad |
| `sudo ./scripts/pair_ps5_controller.sh --mac AA:BB:CC:DD:EE:FF` | Skip scanning, use a known MAC |

---

## Do you even need the systemd service?

**Usually no.** Once the controller is paired, *trusted*, and its link key is
persisted, BlueZ reconnects it automatically when you power it on — that is the
controller-initiated path and it already survives reboots (`AutoEnable=true`
powers the adapter at boot and BlueZ reloads the stored link key).

The optional service only helps one edge case: the controller was **already
powered on before the robot finished booting** and stopped paging before BlueZ
was ready. The service then nudges a connection. It is intentionally **gentle**
(one attempt every ~20 s, only while disconnected) so it does not collide with
the controller's own reconnect attempts.

---

## What the script does (and how to do it by hand)

If you prefer to understand or reproduce each step manually:

### 1. Kernel modules for a gamepad node

```bash
sudo modprobe uhid joydev
echo -e "uhid\njoydev" | sudo tee /etc/modules-load.d/qmini-controller.conf
```

* `joydev` creates `/dev/input/jsX`.
* `uhid` is used by BlueZ's HID path.
* The controller binds to the built-in `hid-generic` driver (there is no
  `hid_sony`/`hid_playstation` module on the Tegra kernel — that's fine; buttons
  and sticks work as a standard HID gamepad).

### 2. Allow HID input from the pad

`/etc/bluetooth/input.conf`:

```ini
[General]
ClassicBondedOnly=false
```

Without this, BlueZ logs `Refusing input device connect` / `Rejected connection
from !bonded device` — the pad "connects" but **no `js0` is ever created**,
because DualSense/DualShock use an *unauthenticated* ("Just Works") pairing that
fails the default `ClassicBondedOnly=true` check.

### 3. Power the adapter on at boot

`/etc/bluetooth/main.conf`:

```ini
[Policy]
AutoEnable=true
```

Then restart Bluetooth: `sudo systemctl restart bluetooth`.

### 4. Pair the controller

Put the pad in pairing mode, then:

```bash
bluetoothctl --timeout 20 scan on
bluetoothctl pair  <MAC>
bluetoothctl trust <MAC>
bluetoothctl connect <MAC>
```

At this point `/dev/input/js0` should appear and the pad works — **but it will
fail to reconnect after a power-cycle.** See the next step.

### 5. Persist the link key (the crucial fix)

DualSense/DualShock send their link key with **`store_hint=0`**, which tells
BlueZ *not* to save it. So the bond works once, then every later reconnect fails
with `bonding ... status 0x5` (Authentication Failure) because the host has no
stored key. Confirm the problem:

```bash
sudo cat /var/lib/bluetooth/<ADAPTER_MAC>/<CONTROLLER_MAC>/info
# ...notice there is NO [LinkKey] section
```

Capture the key that was negotiated during pairing with `btmon`, then write it
into the info file yourself:

```bash
# run btmon in one terminal WHILE pairing in another:
sudo btmon | grep -A2 "Link Key Notification"
#   Link key: 8ec411b0a291b8ffe125b5474bd2992a
#   Key type: Unauthenticated Combination key from P-192 (0x04)

sudo systemctl stop bluetooth
sudo tee -a /var/lib/bluetooth/<ADAPTER_MAC>/<CONTROLLER_MAC>/info >/dev/null <<'EOF'

[LinkKey]
Key=8EC411B0A291B8FFE125B5474BD2992A
Type=4
PINLength=0
EOF
sudo systemctl start bluetooth
```

(The script does exactly this automatically — capture, uppercase, write, restart.)

Now the bond is permanent: power-cycle the pad and it reconnects cleanly, no
`status 0x5`.

### 6. (Optional) Boot auto-connect service

Installed by `--install-service` as `qmini-ds-autoconnect.service`:

```bash
systemctl status qmini-ds-autoconnect     # check
sudo systemctl disable --now qmini-ds-autoconnect   # remove if unwanted
```

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Pad connects but **no `/dev/input/js0`** | `ClassicBondedOnly` not `false`, or `uhid`/`joydev` not loaded. Re-run the script; check `lsmod \| grep -E 'uhid\|joydev'`. |
| Reconnect fails, log shows **`status 0x5`** / `bonding failed` | No persistent link key (`store_hint=0`). Re-run pairing so the key is captured and written; verify a `[LinkKey]` section exists in the device `info` file. |
| Log shows `br-connection-create-socket` on host-initiated `connect` | The pad is asleep/idle — a host `connect` can't wake it. Press **PS** so the controller initiates instead. |
| Pad blinks then turns off | It tried its last host and failed (stale/one-sided bond). Remove it (`bluetoothctl remove <MAC>`) and pair fresh. |
| `Wireless Controller` shows an old/stale pairing | `bluetoothctl remove <MAC>`, then re-pair. |
| Which driver bound? | `sudo dmesg \| grep -i "Gamepad"` → `hid-generic ... BLUETOOTH HID ... Gamepad`. |

## Useful commands

```bash
bluetoothctl paired-devices                 # list paired controllers
bluetoothctl info <MAC>                      # Paired/Trusted/Connected state
sudo journalctl -u bluetooth -f              # live Bluetooth daemon log
jstest /dev/input/js0                        # test buttons/axes (apt install joystick)
```
