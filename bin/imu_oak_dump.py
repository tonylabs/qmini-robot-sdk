import argparse
import sys
import time
import json
import depthai as dai
import math
import numpy as np

# Constants
PI = 3.141592653589793
DEG_TO_RAD = 0.017453292519943295

def parse_opt(known=False):
    parser = argparse.ArgumentParser(description='OAK-D-Pro W IMU Data Dumper')
    parser.add_argument('--output', type=str, default='oak_imu_data.txt', help='output file to dump IMU data')
    parser.add_argument('--duration', type=int, default=60, help='duration to collect data in seconds; default: 60')
    parser.add_argument('--frequency', type=int, default=100, help='IMU sampling frequency; default: 100Hz')
    parser.add_argument('--format', type=str, choices=['json', 'csv'], default='json', help='output format: json or csv')
    parser.add_argument('--verbose', action='store_true', help='print data to console as well')
    
    receive_params = parser.parse_known_args()[0] if known else parser.parse_args()
    return receive_params

class MadgwickFilter:
    """Madgwick AHRS filter for quaternion estimation from accelerometer and gyroscope"""
    def __init__(self, beta=0.1, sample_freq=100):
        self.beta = beta
        self.sample_freq = sample_freq
        self.q = [1.0, 0.0, 0.0, 0.0]  # quaternion [w, x, y, z]
        
    def update(self, gx, gy, gz, ax, ay, az):
        """Update quaternion with gyroscope and accelerometer data"""
        q1, q2, q3, q4 = self.q
        
        # Normalise accelerometer measurement
        norm = math.sqrt(ax * ax + ay * ay + az * az)
        if norm == 0:
            return
        ax /= norm
        ay /= norm
        az /= norm
        
        # Auxiliary variables to avoid repeated arithmetic
        _2q1 = 2 * q1
        _2q2 = 2 * q2
        _2q3 = 2 * q3
        _2q4 = 2 * q4
        _4q1 = 4 * q1
        _4q2 = 4 * q2
        _4q3 = 4 * q3
        _8q2 = 8 * q2
        _8q3 = 8 * q3
        q1q1 = q1 * q1
        q2q2 = q2 * q2
        q3q3 = q3 * q3
        q4q4 = q4 * q4
        
        # Gradient decent algorithm corrective step
        s1 = _4q1 * q3q3 + _2q3 * ax + _4q1 * q2q2 - _2q2 * ay
        s2 = _4q2 * q4q4 - _2q4 * ax + 4 * q1q1 * q2 - _2q1 * ay - _4q2 + _8q2 * q2q2 + _8q2 * q3q3 + _4q2 * az
        s3 = 4 * q1q1 * q3 + _2q1 * ax + _4q3 * q4q4 - _2q4 * ay - _4q3 + _8q3 * q2q2 + _8q3 * q3q3 + _4q3 * az
        s4 = 4 * q2q2 * q4 - _2q2 * ax + 4 * q3q3 * q4 - _2q3 * ay
        
        # Normalise step magnitude
        norm = math.sqrt(s1 * s1 + s2 * s2 + s3 * s3 + s4 * s4)
        if norm != 0:
            s1 /= norm
            s2 /= norm
            s3 /= norm
            s4 /= norm
        
        # Apply feedback step
        qDot1 = 0.5 * (-q2 * gx - q3 * gy - q4 * gz) - self.beta * s1
        qDot2 = 0.5 * (q1 * gx + q3 * gz - q4 * gy) - self.beta * s2
        qDot3 = 0.5 * (q1 * gy - q2 * gz + q4 * gx) - self.beta * s3
        qDot4 = 0.5 * (q1 * gz + q2 * gy - q3 * gx) - self.beta * s4
        
        # Integrate rate of change of quaternion
        q1 += qDot1 * (1.0 / self.sample_freq)
        q2 += qDot2 * (1.0 / self.sample_freq)
        q3 += qDot3 * (1.0 / self.sample_freq)
        q4 += qDot4 * (1.0 / self.sample_freq)
        
        # Normalise quaternion
        norm = math.sqrt(q1 * q1 + q2 * q2 + q3 * q3 + q4 * q4)
        if norm != 0:
            self.q = [q1/norm, q2/norm, q3/norm, q4/norm]
        
        return self.q

def quaternion_to_euler(qw, qx, qy, qz):
    """Convert quaternion to Euler angles (roll, pitch, yaw)"""
    # Roll (x-axis rotation)
    sinr_cosp = 2 * (qw * qx + qy * qz)
    cosr_cosp = 1 - 2 * (qx * qx + qy * qy)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    
    # Pitch (y-axis rotation)
    sinp = 2 * (qw * qy - qz * qx)
    if abs(sinp) >= 1:
        pitch = math.copysign(PI / 2, sinp)  # use 90 degrees if out of range
    else:
        pitch = math.asin(sinp)
    
    # Yaw (z-axis rotation)
    siny_cosp = 2 * (qw * qz + qx * qy)
    cosy_cosp = 1 - 2 * (qy * qy + qz * qz)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    
    return roll, pitch, yaw

def read_oak_imu_data(frequency=100):
    """Read IMU data from OAK-D-Pro W device (BMI270 sensor)"""
    try:
        # Create pipeline
        pipeline = dai.Pipeline()
        
        # Create IMU node - BMI270 only supports ACCELEROMETER_RAW and GYROSCOPE_RAW
        imu = pipeline.create(dai.node.IMU)
        imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, frequency)
        imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, frequency)
        imu.setBatchReportThreshold(1)
        imu.setMaxBatchReports(10)
        
        # Create output
        imuOut = pipeline.create(dai.node.XLinkOut)
        imuOut.setStreamName("imu")
        imu.out.link(imuOut.input)
        
        # Initialize Madgwick filter for quaternion estimation
        madgwick = MadgwickFilter(beta=0.1, sample_freq=frequency)
        
        # Connect to device and start pipeline
        with dai.Device(pipeline) as device:
            q = device.getOutputQueue(name="imu", maxSize=50, blocking=False)
            
            print(f"Connected to OAK-D-Pro W device with BMI270 IMU sensor")
            
            while True:
                inIMU = q.get()
                if inIMU is None:
                    continue
                    
                imuData = inIMU.packets[-1]
                
                # Get raw accelerometer and gyroscope data
                ax = imuData.acceleroMeter.x
                ay = imuData.acceleroMeter.y
                az = imuData.acceleroMeter.z
                
                gx = imuData.gyroscope.x
                gy = imuData.gyroscope.y
                gz = imuData.gyroscope.z
                
                # Update Madgwick filter to get quaternion
                quaternion = madgwick.update(gx, gy, gz, ax, ay, az)
                qw, qx, qy, qz = quaternion
                
                # Calculate Euler angles from quaternion
                roll, pitch, yaw = quaternion_to_euler(qw, qx, qy, qz)
                
                result = {
                    "timestamp": time.time(),
                    "Accelerometer_X": ax,
                    "Accelerometer_Y": ay,
                    "Accelerometer_Z": az,
                    "RollSpeed": gx,
                    "PitchSpeed": gy,
                    "HeadingSpeed": gz,
                    "Roll": roll,
                    "Pitch": pitch,
                    "Heading": yaw,
                    "qw": qw,
                    "qx": qx,
                    "qy": qy,
                    "qz": qz,
                }
                
                yield result
                
    except Exception as e:
        print(f"Error reading OAK-D-Pro W IMU data: {e}")
        return None

def dump_imu_data():
    """Main function to dump IMU data"""
    args = parse_opt()
    
    print(f"Starting OAK-D-Pro W IMU data collection...")
    print(f"Duration: {args.duration} seconds")
    print(f"Frequency: {args.frequency} Hz")
    print(f"Output file: {args.output}")
    print(f"Format: {args.format}")
    print("Note: Using BMI270 sensor (ACCELEROMETER_RAW + GYROSCOPE_RAW only)")
    print("Quaternions calculated using Madgwick AHRS filter")
    print("Press Ctrl+C to stop early\n")
    
    start_time = time.time()
    data_count = 0
    
    try:
        with open(args.output, 'w') as f:
            # Write CSV header if needed
            if args.format == 'csv':
                header = "timestamp,Accelerometer_X,Accelerometer_Y,Accelerometer_Z,RollSpeed,PitchSpeed,HeadingSpeed,Roll,Pitch,Heading,qw,qx,qy,qz\n"
                f.write(header)
            
            for imu_data in read_oak_imu_data(args.frequency):
                if imu_data is None:
                    break
                    
                # Check if duration exceeded
                if time.time() - start_time > args.duration:
                    break
                
                # Write data to file
                if args.format == 'json':
                    f.write(json.dumps(imu_data) + '\n')
                elif args.format == 'csv':
                    csv_line = f"{imu_data['timestamp']},{imu_data['Accelerometer_X']},{imu_data['Accelerometer_Y']},{imu_data['Accelerometer_Z']},{imu_data['RollSpeed']},{imu_data['PitchSpeed']},{imu_data['HeadingSpeed']},{imu_data['Roll']},{imu_data['Pitch']},{imu_data['Heading']},{imu_data['qw']},{imu_data['qx']},{imu_data['qy']},{imu_data['qz']}\n"
                    f.write(csv_line)
                
                f.flush()  # Ensure data is written immediately
                
                # Print to console if verbose
                if args.verbose:
                    print(f"Sample {data_count + 1}: {json.dumps(imu_data, indent=2)}")
                
                data_count += 1
                
                # Small delay to prevent overwhelming the system
                time.sleep(0.001)
                
    except KeyboardInterrupt:
        print("\nData collection stopped by user.")
    except Exception as e:
        print(f"Error during data collection: {e}")
    
    elapsed_time = time.time() - start_time
    print(f"\nData collection completed!")
    print(f"Total samples collected: {data_count}")
    print(f"Elapsed time: {elapsed_time:.2f} seconds")
    print(f"Average sampling rate: {data_count/elapsed_time:.2f} Hz")
    print(f"Data saved to: {args.output}")

if __name__ == "__main__":
    dump_imu_data()