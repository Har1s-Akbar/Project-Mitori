cmake_minimum_required(VERSION 3.15)
project(mitori_engine_cpp)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_BUILD_TYPE Release)

find_package(Python 3.14 REQUIRED COMPONENTS Interpreter Development)

include(FetchContent)
FetchContent_Declare(
    pybind11
    URL https://github.com/pybind/pybind11/archive/refs/tags/v2.11.1.tar.gz
)
FetchContent_MakeAvailable(pybind11)
set(SOURCES 
    ${CMAKE_CURRENT_SOURCE_DIR}/bindings.cpp   
    ${CMAKE_CURRENT_SOURCE_DIR}/src/engine.cpp 
)

pybind11_add_module(mitori_engine_cpp ${SOURCES})

target_include_directories(mitori_engine_cpp PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)

if(WIN32 OR MINGW)
    message(FATAL_ERROR "Benchmarking requires a container-native Linux environment. Host-level Windows/MSYS2 builds are strictly forbidden.")
endif()

target_compile_options(mitori_engine_cpp PRIVATE -O3 -march=native)