cmake_minimum_required(VERSION 3.16)
project(baekjoonhub_migrator VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(baekjoonhub-migrator src/migrator.cpp)

if(MSVC)
    target_compile_options(baekjoonhub-migrator PRIVATE /W4 /utf-8)
else()
    target_compile_options(baekjoonhub-migrator PRIVATE -Wall -Wextra -Wpedantic)
endif()
