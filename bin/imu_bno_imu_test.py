import serial
import struct
import time
import math
import argparse

# Constants
PI = 3.141592653589793
DEG_TO_RAD = 0.017453292519943295

# 获取命令行输入参数
def parse_opt(known=False):
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=str, default='/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0', help='serial port receive data')
    parser.add_argument('--bps', type=int, default=115200, help='the models baud rate set; default: 115200')
    parser.add_argument('--timeout', type=int, default=1, help='set the serial port timeout; default: 1')
    
    receive_params = parser.parse_known_args()[0] if known else parser.parse_args()
    return receive_params

def write_cmd(serial_obj, cmd_bytes, expect_response=True, wait=0.05):
    serial_obj.write(cmd_bytes)
    time.sleep(wait)
    if expect_response:
        resp = serial_obj.read_all()
        return resp
    return None

def enter_config_mode(serial_obj):
    write_cmd(serial_obj, b'\xAA\x00\x3D\x00')  # Set to CONFIGMODE
    time.sleep(0.05)

def set_ndof_mode(serial_obj):
    write_cmd(serial_obj, b'\xAA\x00\x3D\x01\x0C')  # Set to NDOF mode (0x0C)
    time.sleep(0.05)

def init_bno055(serial_obj):
    enter_config_mode(serial_obj)
    set_ndof_mode(serial_obj)

def read_imu_data(port="/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0", baudrate=115200, timeout=1):
    try:
        objSerial = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout
        )
    except:
        print("error: unable to open port.")
        exit(1)
    
    # Initialize BNO055
    print("Initializing BNO055 in NDOF mode...")
    init_bno055(objSerial)
    time.sleep(0.2)  # 等待芯片进入稳定状态
    
    result = {
        "Accelerometer_X": 0,
        "Accelerometer_Y": 0,
        "Accelerometer_Z": 0,
        "RollSpeed": 0,
        "PitchSpeed": 0,
        "HeadingSpeed": 0,
        "Roll": 0,
        "Pitch": 0,
        "Heading": 0,
        "qw": 0,
        "qx": 0,
        "qy": 0,
        "qz": 0,
    }
    
    accel_ready = False
    gyro_ready = False
    euler_ready = False
    quat_ready = False
    
    while objSerial.isOpen():
        try:
            # Read accelerometer data (register 0x08, 6 bytes)
            objSerial.write(b'\xAA\x01\x08\x06')
            response = objSerial.read(8)
            if len(response) >= 8 and response[0:2] == b'\xBB\x06':
                data_bytes = response[2:8]
                accel_x_raw = struct.unpack('<h', data_bytes[0:2])[0]
                accel_y_raw = struct.unpack('<h', data_bytes[2:4])[0]
                accel_z_raw = struct.unpack('<h', data_bytes[4:6])[0]
                
                # Convert to m/s^2 (BNO055 accelerometer scale: 1 m/s^2 = 100 LSB)
                result["Accelerometer_X"] = accel_x_raw / 100.0
                result["Accelerometer_Y"] = accel_y_raw / 100.0
                result["Accelerometer_Z"] = accel_z_raw / 100.0
                accel_ready = True
            
            time.sleep(0.01)
            
            # Read gyroscope data (register 0x14, 6 bytes)
            objSerial.write(b'\xAA\x01\x14\x06')
            response = objSerial.read(8)
            if len(response) >= 8 and response[0:2] == b'\xBB\x06':
                data_bytes = response[2:8]
                gyro_x_raw = struct.unpack('<h', data_bytes[0:2])[0]
                gyro_y_raw = struct.unpack('<h', data_bytes[2:4])[0]
                gyro_z_raw = struct.unpack('<h', data_bytes[4:6])[0]
                
                # Convert to rad/s (BNO055 gyroscope scale: 1 dps = 16 LSB, then convert to rad/s)
                result["RollSpeed"] = (gyro_y_raw / 16.0) * DEG_TO_RAD
                result["PitchSpeed"] = -(gyro_x_raw / 16.0) * DEG_TO_RAD  # Inverted to match N100
                result["HeadingSpeed"] = (gyro_z_raw / 16.0) * DEG_TO_RAD
                gyro_ready = True
            
            time.sleep(0.01)
            
            # Read Euler angles (register 0x1A, 6 bytes)
            objSerial.write(b'\xAA\x01\x1A\x06')
            response = objSerial.read(8)
            if len(response) >= 8 and response[0:2] == b'\xBB\x06':
                data_bytes = response[2:8]
                heading_raw = struct.unpack('<H', data_bytes[0:2])[0]
                roll_raw = struct.unpack('<h', data_bytes[2:4])[0]
                pitch_raw = struct.unpack('<h', data_bytes[4:6])[0]
                
                # Convert to radians (BNO055 Euler scale: 1 degree = 16 LSB)
                heading_deg = heading_raw / 16.0
                roll_deg = roll_raw / 16.0
                pitch_deg = pitch_raw / 16.0
                
                result["Roll"] = roll_deg * DEG_TO_RAD
                result["Pitch"] = -pitch_deg * DEG_TO_RAD  # Inverted to match N100
                result["Heading"] = heading_deg * DEG_TO_RAD
                euler_ready = True
            
            time.sleep(0.01)
            
            # Read quaternion data (register 0x20, 8 bytes)
            objSerial.write(b'\xAA\x01\x20\x08')
            response = objSerial.read(10)
            if len(response) >= 10 and response[0:2] == b'\xBB\x08':
                data_bytes = response[2:10]
                qw_raw = struct.unpack('<h', data_bytes[0:2])[0]
                qx_raw = struct.unpack('<h', data_bytes[2:4])[0]
                qy_raw = struct.unpack('<h', data_bytes[4:6])[0]
                qz_raw = struct.unpack('<h', data_bytes[6:8])[0]
                
                # Convert to unit quaternion (BNO055 quaternion scale: 1 = 16384 LSB)
                result["qw"] = qw_raw / 16384.0
                result["qx"] = qx_raw / 16384.0
                result["qy"] = qy_raw / 16384.0
                result["qz"] = qz_raw / 16384.0
                quat_ready = True
            
            # Return result when all data is ready
            if accel_ready and gyro_ready and euler_ready and quat_ready:
                objSerial.close()
                return result
                
        except Exception as e:
            print(f"Error reading data: {e}")
            continue
    
    objSerial.close()
    return result

if __name__ == "__main__":
    # Test the function
    data = read_imu_data()
    print("IMU Data:")
    for key, value in data.items():
        print(f"{key}: {value}")