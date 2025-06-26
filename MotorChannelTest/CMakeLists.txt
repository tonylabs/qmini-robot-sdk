cmake_minimum_required(VERSION 3.10)

# 设置项目名称
project(CommDemo)

# 设置 C++ 标准
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED True)

add_executable(block_comm_test block_comm_demo.cpp motor.cpp)
# add_executable(no_block_comm_test no_block_comm_demo.cpp motor.cpp)
