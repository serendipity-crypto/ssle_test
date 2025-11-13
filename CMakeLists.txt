cmake_minimum_required(VERSION 3.10)
project(share_benchmark)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

find_package(emp-tool REQUIRED)

include_directories(${EMP-TOOL_INCLUDE_DIR})

add_executable(share_benchmark main.cpp)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    set(OPTIMIZATION_FLAGS -O3 -march=native -ffast-math -funroll-loops -flto)
    
    target_compile_options(share_benchmark PRIVATE
        $<$<CONFIG:RELEASE>:${OPTIMIZATION_FLAGS}>
        -Wall -Wextra -Wpedantic
    )
    target_link_options(share_benchmark PRIVATE
        $<$<CONFIG:RELEASE>:-flto>
    )
elseif(MSVC)
    set(OPTIMIZATION_FLAGS /O2 /fp:fast /arch:AVX2)
    
    target_compile_options(share_benchmark PRIVATE
        $<$<CONFIG:RELEASE>:${OPTIMIZATION_FLAGS}>
    )
endif()

target_link_libraries(share_benchmark 
    ${EMP-TOOL_LIBRARIES} 
)
