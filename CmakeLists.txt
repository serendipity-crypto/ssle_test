cmake_minimum_required(VERSION 3.10)
project(emp_share_benchmark)

set(CMAKE_CXX_STANDARD 14)

# 查找emp-toolkit
find_package(emp-tool REQUIRED)
# find_package(emp-ot REQUIRED)

# 包含目录
include_directories(include)
include_directories(${EMP-TOOL_INCLUDE_DIR})

# 可执行文件
add_executable(share_benchmark 
    main.cpp 
)

# 链接库
target_link_libraries(share_benchmark 
    ${EMP-TOOL_LIBRARIES} 
    pthread
    ssl
    crypto
)