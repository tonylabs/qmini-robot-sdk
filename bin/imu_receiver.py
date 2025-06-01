import argparse
import depthai as dai
import math
import time

# Constants
PI = 3.141592653589793
DEG_TO_RAD = 0.017453292519943295
isrun = True

# Global variables for persistent connection
device = None
queue = None
madgwick = None

def parse_opt(known=False):
    parser = argparse.ArgumentParser()
    parser.add_argument('--frequency', type=int, default=100, help='IMU sampling frequency; default: 100Hz')
    parser.add_argument('--timeout', type=int, default=20, help='set the timeout; default: 20')

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
            return self.q
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

def initialize_imu_connection(frequency=100):
    """Initialize a persistent connection to the OAK-D-Pro W device"""
    global device, queue, madgwick

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
        device = dai.Device(pipeline)
        queue = device.getOutputQueue(name="imu", maxSize=50, blocking=False)
        print(f"Connected to OAK-D-Pro W device with BMI270 IMU sensor")
        return True
    except Exception as e:
        print(f"Error initializing OAK-D-Pro W IMU connection: {e}")
        return False

def read_imu_data(frequency=100, timeout=1):
    """Read IMU data from OAK-D-Pro W device (BMI270 sensor)"""
    global device, queue, madgwick

    # Initialize connection if not already done
    if device is None or queue is None or madgwick is None:
        if not initialize_imu_connection(frequency):
            return {
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

    try:
        # Get data from the queue
        inIMU = queue.get()
        if inIMU is None:
            return None

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

        # Apply the same coordinate transformations as the original code
        result = {
            "Accelerometer_X": ax,
            "Accelerometer_Y": ay,
            "Accelerometer_Z": az,
            "RollSpeed": gy,  # Swapped as in original
            "PitchSpeed": gx * -1,  # Inverted as in original
            "HeadingSpeed": gz,
            "Roll": pitch,  # Swapped as in original
            "Pitch": roll * -1,  # Inverted as in original
            "Heading": yaw,
            "qw": qw,
            "qx": qx,
            "qy": qy,
            "qz": qz,
        }
        return result

    except Exception as e:
        print(f"Error reading OAK-D-Pro W IMU data: {e}")
        # Try to reinitialize the connection
        if initialize_imu_connection(frequency):
            return read_imu_data(frequency, timeout)  # Try again
        return {
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

def cleanup_imu_connection():
    """Clean up the IMU connection when done"""
    global device
    if device is not None:
        device.close()
        device = None

if __name__ == "__main__":
    args = parse_opt()
    try:
        initialize_imu_connection(frequency=args.frequency)
        while True:
            imu_data = read_imu_data(frequency=args.frequency, timeout=args.timeout)
            print(f"IMU Data: {imu_data}")
            time.sleep(0.01)  # Small delay to prevent overwhelming output
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        cleanup_imu_connection()