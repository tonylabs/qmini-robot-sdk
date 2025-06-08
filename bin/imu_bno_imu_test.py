import serial
import struct
import time

# 设置串口参数
objSerial = serial.Serial(
    port='/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0',
    baudrate=115200,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=1
)

# 设置为配置模式
#objSerial.write(b'\xAA\x00\x3D\x00')
#time.sleep(0.05)

# 设置为 IMU 模式（不使用磁力计）
#objSerial.write(b'\xAA\x00\x3D\x01\x08')
#time.sleep(0.05)

# ---------- Utility Functions ----------
def write_cmd(cmd_bytes, expect_response=True, wait=0.05):
	objSerial.write(cmd_bytes)
	time.sleep(wait)
	if expect_response:
		resp = objSerial.read_all()
		return resp
	return None


def enter_config_mode():
	write_cmd(b'\xAA\x00\x3D\x00')  # Set to CONFIGMODE
	time.sleep(0.05)


def set_ndof_mode():
	write_cmd(b'\xAA\x00\x3D\x01\x0C')  # Set to NDOF mode (0x0C)
	time.sleep(0.05)


def init_bno055():
	enter_config_mode()
	set_ndof_mode()


# ---------- Initialization ----------
print("Initializing BNO055 in NDOF mode...")
init_bno055()
time.sleep(0.2)  # 等待芯片进入稳定状态

print("Reading Euler angles at 100 Hz (Heading, Roll, Pitch):\n")

# ---------- Loop for Euler Reading ----------
try:
	while True:
		start_time = time.time()

		# Request 6 bytes from register 0x1A (Euler H/R/P)
		objSerial.write(b'\xAA\x01\x1A\x06')
		response = objSerial.read(8)

		if len(response) >= 8 and response[0:2] == b'\xBB\x06':
			data_bytes = response[2:8]
			heading_raw = struct.unpack('<H', data_bytes[0:2])[0]
			roll_raw    = struct.unpack('<h', data_bytes[2:4])[0]
			pitch_raw   = struct.unpack('<h', data_bytes[4:6])[0]

			# Convert raw to degrees
			heading = heading_raw / 16.0
			roll = roll_raw / 16.0
			pitch = pitch_raw / 16.0

			timestamp = time.time()
			print(
				f"[{timestamp:.3f}] 航向角: {heading:7.2f}° | 横滚角: {roll:7.2f}° | 俯仰角: {pitch:7.2f}° | Raw: {response.hex()}")
		else:
			print(f"[{time.time():.3f}] Invalid response: {response.hex()}")

		# Maintain 100Hz sampling rate (10ms)
		elapsed = time.time() - start_time
		sleep_time = max(0, 0.1 - elapsed)
		time.sleep(sleep_time)

except KeyboardInterrupt:
	print("Stopped by user.")
finally:
	objSerial.close()