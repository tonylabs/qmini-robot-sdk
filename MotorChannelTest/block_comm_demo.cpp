/**
 * 多通道电机控制与监控系统 (阻塞I/O版本)
 *
 * 本程序实现了对4个通道，每个通道3个电机的并行控制和数据采集。
 * 通过串口进行通信，实现电机的实时控制和状态监控。
 * 电机的减速比为 6.33:1。在实际应用中，需要对数据进行相应的处理：
 *   - 输出端转速 = 转子端转速 / 6.33
 *   - 输出端位置 = 转子端位置 / 6.33
 *   - 输出端转矩 = 转子端转矩 * 6.33 * 效率（效率需要根据实际情况确定）
 */

#include <iostream>
#include <vector>
#include <thread>
#include <chrono>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <cstring>
#include <atomic>
#include "motor.h"

// 定义系统常量
#define NUM_CHANNELS 4         // 通道数量
#define MOTORS_PER_CHANNEL 3   // 每个通道的电机数量
#define MAX_BUFFER_SIZE 1024   // 最大缓冲区大小
#define GEAR_RATIO 6.33f       // 减速比

// 全局变量
// 创建一个二维向量来存储所有电机对象
std::vector<std::vector<Motor>> g_motors(NUM_CHANNELS, std::vector<Motor>(MOTORS_PER_CHANNEL));
std::atomic<bool> g_running(true);  // 控制程序运行的原子布尔值


void channel_thread(int channel);
void print_statistics();
int initialize_serial_port(const char* port_name);

// 定义全局控制参数
float g_tor_des = 0.0f;  // 目标转矩
float g_spd_des = 0.0f;  // 目标速度
float g_pos_des = 0.0f;  // 目标位置
float g_k_pos = 0.0f;    // 位置增益
float g_k_spd = 0.0f;    // 速度增益

int main(int argc, char* argv[]) {
    // 检查命令行参数
    if (argc != 2) {
        std::cerr << "Usage: " << argv[0] << " <mode>\n";
        std::cerr << "Modes: stop, tor, speed\n";
        return 1;
    }

    // 根据命令行参数设置控制模式
    if (strcmp(argv[1], "stop") == 0) {
        // 停止模式：所有参数设为0
        g_tor_des = 0.0f;
        g_spd_des = 0.0f;
        g_pos_des = 0.0f;
        g_k_pos = 0.0f;
        g_k_spd = 0.0f;
    } else if (strcmp(argv[1], "tor") == 0) {
        // 转矩模式：设置目标转矩
        g_tor_des = 0.25f;
        g_spd_des = 0.0f;
        g_pos_des = 0.0f;
        g_k_pos = 0.0f;
        g_k_spd = 0.0f;
    } else if (strcmp(argv[1], "speed") == 0) {
        // 速度模式：设置目标速度和速度增益
        g_tor_des = 0.0f;
        g_spd_des = 6.28f;
        g_pos_des = 0.0f;
        g_k_pos = 0.0f;
        g_k_spd = 0.4f;
    } else {
        std::cerr << "Invalid mode. Use 'stop', 'tor', or 'speed'.\n";
        return 1;
    }

    std::vector<std::thread> threads;

    // 初始化电机控制参数
    for (int i = 0; i < NUM_CHANNELS; ++i) {
        for (int j = 0; j < MOTORS_PER_CHANNEL; ++j) {
            g_motors[i][j].setControlParams(0.0f, 0.0f, 0.0f, 0.0f, 0.0f);  // 初始化状态为0
        }
    }

    // 为每个通道创建线程
    for (int i = 0; i < NUM_CHANNELS; ++i) {
        threads.emplace_back(channel_thread, i);
    }

    // 主循环
    while (g_running) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
        
        for (int i = 0; i < NUM_CHANNELS; ++i) {
            for (int j = 0; j < MOTORS_PER_CHANNEL; ++j) {
                // 更新电机控制参数，考虑减速比
                g_motors[i][j].setControlParams(
                    g_tor_des / GEAR_RATIO,     // 转子端转矩 = 输出端转矩 / 减速比
                    g_spd_des * GEAR_RATIO,     // 转子端速度 = 输出端速度 * 减速比
                    g_pos_des * GEAR_RATIO,     // 转子端位置 = 输出端位置 * 减速比
                    g_k_pos / GEAR_RATIO / GEAR_RATIO,  // 位置增益需要考虑两次减速比
                    g_k_spd / GEAR_RATIO / GEAR_RATIO   // 速度增益需要考虑两次减速比
                );
                
                // 获取电机状态并转换为输出端数据
                float tor = g_motors[i][j].getTorque() * GEAR_RATIO;  // 转换为输出端转矩
                float spd = g_motors[i][j].getSpeed() / GEAR_RATIO;   // 转换为输出端速度
                float pos = g_motors[i][j].getPosition() / GEAR_RATIO;// 转换为输出端位置
                float temp = g_motors[i][j].getTemperature();
                uint16_t err = g_motors[i][j].getError();
                
                // 打印电机状态（输出端的值）
                std::cout << "Channel " << i << ", Motor " << j 
                          << " - Output Torque: " << tor 
                          << ", Output Speed: " << spd 
                          << ", Output Position: " << pos 
                          << ", Temp: " << temp 
                          << ", Error: " << err << std::endl;
            }
        }
        
        // 打印统计信息
        print_statistics();
    }

    // 清理资源
    g_running = false;  // 停止所有线程
    for (auto& thread : threads) {
        thread.join();  // 等待所有线程结束
    }

    return 0;
}


/**
 * 初始化串口
 * @param port_name 串口设备名
 * @return 成功返回文件描述符，失败返回-1
 */
int initialize_serial_port(const char* port_name) {
    // 以读写方式打开串口设备
    int fd = open(port_name, O_RDWR | O_NOCTTY);
    if (fd < 0) {
        std::cerr << "Error opening " << port_name << ": " << strerror(errno) << std::endl;
        return -1;
    }

    struct termios tty;
    memset(&tty, 0, sizeof(tty));
    // 获取当前串口设置
    if (tcgetattr(fd, &tty) != 0) {
        std::cerr << "Error from tcgetattr: " << strerror(errno) << std::endl;
        close(fd);
        return -1;
    }

    // 设置波特率
    cfsetospeed(&tty, B4000000);
    cfsetispeed(&tty, B4000000);
    
    // 设置其他串口参数
    tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;  // 8位数据位
    tty.c_iflag &= ~(IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | ICRNL | IXON);
    tty.c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);
    tty.c_oflag &= ~OPOST;
    tty.c_cc[VMIN] = 0;
    tty.c_cc[VTIME] = 1;  // 0.1秒读取超时

    // 应用新的串口设置
    if (tcsetattr(fd, TCSANOW, &tty) != 0) {
        std::cerr << "Error from tcsetattr: " << strerror(errno) << std::endl;
        close(fd);
        return -1;
    }

    return fd;
}

/**
 * 通道线程函数
 * @param channel 通道号
 */
void channel_thread(int channel) {
    // 构造串口设备名
    char port_name[20];
    snprintf(port_name, sizeof(port_name), "/dev/ttyUSB%d", channel);
    
    // 初始化串口
    int fd = initialize_serial_port(port_name);
    if (fd < 0) {
        std::cerr << "Failed to initialize port " << port_name << std::endl;
        return;
    }

    uint8_t recv_buffer[MAX_BUFFER_SIZE];
    int current_motor = 0;

    while (g_running) {
        // 创建并发送控制数据包
        Motor::ControlData_t packet = g_motors[channel][current_motor].createControlPacket(current_motor);
        ssize_t bytes_written = write(fd, &packet, sizeof(Motor::ControlData_t));
        if (bytes_written == sizeof(Motor::ControlData_t)) {
            g_motors[channel][current_motor].incrementSendCount();
        } else {
            std::cerr << "Channel " << channel << ", Motor " << current_motor 
                      << ": Send failed. Bytes written: " << bytes_written 
                      << ", Error: " << strerror(errno) << std::endl;
        }

        // 接收数据
        ssize_t bytes_read = read(fd, recv_buffer, MAX_BUFFER_SIZE);
        if (bytes_read >= sizeof(Motor::RecvData_t)) {
            Motor::RecvData_t* recv_packet = reinterpret_cast<Motor::RecvData_t*>(recv_buffer);
            
            // 检查数据包头
            if (recv_packet->head[0] == 0xFD && recv_packet->head[1] == 0xEE) {
                // 验证CRC
                uint16_t calculated_crc = crc_ccitt(0, reinterpret_cast<uint8_t*>(recv_packet), sizeof(Motor::RecvData_t) - 2);
                if (calculated_crc == recv_packet->CRC16) {
                    // 更新电机反馈数据
                    g_motors[channel][recv_packet->mode.id].updateFeedback(*recv_packet);
                }
            }
        }

        // 切换到下一个电机
        current_motor = (current_motor + 1) % MOTORS_PER_CHANNEL;
        std::this_thread::sleep_for(std::chrono::microseconds(100));
    }

    // 关闭串口
    close(fd);
}

/**
 * 打印统计信息
 */
void print_statistics() {
    std::cout << "Channel | Motor | Sent | Received | Lost | Loss Rate\n";
    std::cout << "--------|-------|------|----------|------|----------\n";
    
    for (int i = 0; i < NUM_CHANNELS; ++i) {
        for (int j = 0; j < MOTORS_PER_CHANNEL; ++j) {
            uint64_t sent = g_motors[i][j].getSendCount();
            uint64_t received = g_motors[i][j].getReceiveCount();
            int64_t lost = sent > received ? sent - received : 0;
            double loss_rate = sent > 0 ? (double)lost / sent * 100 : 0;

            printf("%7d | %5d | %4lu | %8lu | %4ld | %8.2f%%\n",
                   i, j, sent, received, lost, loss_rate);

            g_motors[i][j].resetStats();
        }
    }
    std::cout << std::endl;
}