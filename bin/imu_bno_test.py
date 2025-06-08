import serial
import time

'''
1 Byte = 8 bits
Byte 1 - Start Byte:		0xAA
Byte 2 - Read:				0x01
Byte 2 - Write:				0x00
Byte 3 - Reg Address:		<..>
Byte 4 - Length				<..>
Byte 5 - Data 1				<..>
Byte n						<..>
'''

objSerial = serial.Serial('/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0', 115200, timeout=1)
objSerial.write(b'\xAA\x01\x00\x01')
response = objSerial.read(4)
print('Reading IMU Response: ' + response.hex())
if response.hex() == 'bb01a0':
	print("IMU OK")

objSerial.write(b'\xAA\x01\x3D\x01')
response = objSerial.read(4)
print('Reading IMU mode response: ' + response.hex())
if response.hex() == 'bb0100':
	print("IMU is in CONFIG mode")
elif response.hex() == 'bb0101':
	print("IMU is in ACCONLY mode")
elif response.hex() == 'bb0102':
	print("IMU is in MAGONLY mode")
elif response.hex() == 'bb0103':
	print("IMU is in GYROONLY mode")
elif response.hex() == 'bb0104':
	print("IMU is in ACCMAG mode")
elif response.hex() == 'bb0105':
	print("IMU is in ACCGYRO mode")
elif response.hex() == 'bb0106':
	print("IMU is in MAGGYRO mode")
elif response.hex() == 'bb0107':
	print("IMU is in AMG mode")
elif response.hex() == 'bb0108':
	print("IMU is in IMU mode")
elif response.hex() == 'bb0109':
	print("IMU is in COMPASS mode")
elif response.hex() == 'bb010a':
	print("IMU is in M4G mode")
elif response.hex() == 'bb010b':
	print("IMU is in NDOF_FMC_OFF mode")
elif response.hex() == 'bb010c':
	print("IMU is in NDOF mode")
else:
	print("IMU mode unknown")

print("\nStarting continuous Euler angle reading at 100Hz...")
print("Press Ctrl+C to stop\n")

# Continuous reading loop at 100Hz
try:
    while True:
        start_time = time.time()
        # Read Euler Angles (Heading, Roll, Pitch)
        objSerial.write(b'\xAA\x01\x1A\x06')
        response = objSerial.read(8)  # Read 8 bytes instead of 4 to get complete response
        
        # Parse the Euler angle data if we have a complete response
        if len(response) >= 8 and response[0:2] == b'\xbb\x06':
            # Extract the 6 data bytes (skip the first 2 bytes: 0xBB and 0x06)
            data_bytes = response[2:8]
            
            # Parse according to BNO055 format: [Heading LSB, Heading MSB, Roll LSB, Roll MSB, Pitch LSB, Pitch MSB]
            heading_raw = (data_bytes[1] << 8) | data_bytes[0]  # MSB << 8 | LSB
            roll_raw = (data_bytes[3] << 8) | data_bytes[2]
            pitch_raw = (data_bytes[5] << 8) | data_bytes[4]
            
            # Convert to degrees (BNO055 uses 1 degree = 16 LSB)
            heading_degrees = heading_raw / 16.0
            roll_degrees = roll_raw / 16.0
            pitch_degrees = pitch_raw / 16.0
            
            # Print with timestamp for serial dump format
            timestamp = time.time()
            print(f"[{timestamp:.3f}] 航向角: {heading_degrees:7.2f}° | 横滚角: {roll_degrees:7.2f}° | 俯仰角: {pitch_degrees:7.2f}° | Raw: {response.hex()}")
        else:
            print(f"[{time.time():.3f}] Invalid response: {response.hex()}")
        
        # Calculate sleep time to maintain 100Hz (10ms period)
        elapsed_time = time.time() - start_time
        sleep_time = max(0, 0.1 - elapsed_time)  # 0.01s = 10ms for 100Hz
        time.sleep(sleep_time)
        
except KeyboardInterrupt:
    print("\nStopping continuous reading...")
    objSerial.close()
    print("Serial connection closed.")