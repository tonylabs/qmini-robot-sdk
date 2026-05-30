# RoboTamerSdk4Qmini_v1.0
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
![C++](https://img.shields.io/badge/Code%20Language-C++-blue.svg) 
![ONNX](https://img.shields.io/badge/Framework-ONNX-orange.svg)
![Version](https://img.shields.io/badge/Version-1.0-blue.svg)  

## Code Structure
   ```
RoboTamerSdk4Qmini/
   ├── bin/                    # The pre-trained onnx model, the config file, and the executable files
   ├── include/                # Tne header files
   ├── lib/                    # Tne dependency libraries 
   ├── source/                 # The source files
   ├── thirdparty/             # The thirdparty files
   ├── CMakeLists.txt          # Configuration file for building the executable files
   └── README.md
   ```
### Notes
* Some params are hard-coded in _Motor_thread.hpp_, _run_interface.cpp_, and _test_interface.cpp_. Be careful about them.
* This repository is not maintained anymore. If you have any question, please send emails to info@vsislab.com.
* The project can only be run after successful installation.

## Installation
### Prerequisites
* [Ubuntu](https://cn.ubuntu.com/)(version 20.04 or higher)
* [Unitree_sdk2](https://github.com/unitreerobotics/unitree_sdk2)
* [unitree_actuator_sdk](https://github.com/unitreerobotics/unitree_actuator_sdk)
* [CMake](http://www.cmake.org) (version 2.8.3 or higher)
* [Yaml-cpp](https://github.com/jbeder/yaml-cpp) (version 0.6.0 or higher)
* [Eigen](https://gitlab.com/libeigen/eigen/-/releases) (version 3.3.7 or higher)
* [OnnxRuntime](https://onnxruntime.ai/docs/install/) (version 1.17.1 or higher)
* [JsonCpp](https://github.com/open-source-parsers/jsoncpp)
* [Python3](version 3.8.12 or higher)
* [pygame](https://pypi.org/project/pygame/)(version 2.6.1 or higher)

### Steps
1. Install cmake:

```bash
sudo apt-get install cmake
```

2. Install yaml-cpp/eigen:

```bash
cd yaml-cpp-xxx/eigen-x.x.x
mkdir build
cd build
cmake ..
make
sudo make install
```

3. Install OnnxRuntime

```bash
sudo cp -r libonnxruntime.so libonnxruntime.so.1.17.1 /usr/lib
sudo cp -r libonnxruntime.so libonnxruntime.so.1.17.1 /usr/local/lib
sudo ldconfig
```

4. Load Unitree Motor SDK Lib:
```bash
sudo cp lib/m8010motor/libUnitreeMotorSDK_Linux64.so /usr/local/lib/
sudo cp lib/m8010motor/libUnitreeMotorSDK_Linux64.so /usr/lib/
sudo ldconfig

#or
sudo cp lib/m8010motor/libUnitreeMotorSDK_Arm64.so /usr/local/lib/
sudo cp lib/m8010motor/libUnitreeMotorSDK_Arm64.so /usr/lib/
sudo ldconfig
```

## Full steps of operating RoboTamerSdk4Qmini on the real Qmini robot

#### Before start

```bash
cd ~/qmini_sdk/build
cmake -DPLATFORM=arm64 .. && make && cd ../bin
```

```bash
cd ~/qmini_sdk/bin
./run_interface
```