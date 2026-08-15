cmake_minimum_required(VERSION 3.15)
project(mitori_engine_cpp)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_BUILD_TYPE Release)

find_package(Python 3.14 REQUIRED COMPONENTS Interpreter Development)
execute_process(
    COMMAND python -c "import pybind11; print(pybind11.get_cmake_dir())"
    OUTPUT_VARIABLE PYBIND_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
set(pybind11_DIR "${PYBIND_DIR}")
find_package(pybind11 REQUIRED)

set(SOURCES 
    ${CMAKE_CURRENT_SOURCE_DIR}/bindings.cpp   
    ${CMAKE_CURRENT_SOURCE_DIR}/src/engine.cpp 
)

pybind11_add_module(mitori_engine_cpp ${SOURCES})

target_include_directories(mitori_engine_cpp PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)

if(MINGW)
    target_link_options(mitori_engine_cpp PRIVATE "-static-libstdc++" "-static-libgcc")
endif()