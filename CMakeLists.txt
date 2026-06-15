cmake_minimum_required(VERSION 3.20)
project(BSMScanner LANGUAGES CXX)

option(BSM_SCANNER_BUILD_DIVER "Build optional Diver bridge" OFF)
option(BSM_SCANNER_BUILD_FORTRAN "Build optional Fortran kernels" OFF)
option(BSM_SCANNER_ALLOW_PYBIND11_PYTHON_DISCOVERY
       "Find pybind11 through the active Python interpreter if CMake config lookup fails"
       ON)
set(BSM_SCANNER_DIVER_ROOT "" CACHE PATH "Optional Diver installation prefix")
set(BSM_SCANNER_DIVER_INCLUDE_DIR "" CACHE PATH "Directory containing diver.hpp")
set(BSM_SCANNER_DIVER_LIBRARY "" CACHE FILEPATH "Path to the Diver library")

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Python3 COMPONENTS Interpreter Development.Module REQUIRED)

find_package(pybind11 CONFIG QUIET)
if(NOT pybind11_FOUND AND BSM_SCANNER_ALLOW_PYBIND11_PYTHON_DISCOVERY)
  execute_process(
    COMMAND "${Python3_EXECUTABLE}" -c "import pybind11; print(pybind11.get_cmake_dir())"
    OUTPUT_VARIABLE pybind11_cmake_dir
    RESULT_VARIABLE pybind11_python_status
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
  if(pybind11_python_status EQUAL 0 AND pybind11_cmake_dir)
    list(PREPEND CMAKE_PREFIX_PATH "${pybind11_cmake_dir}")
    find_package(pybind11 CONFIG REQUIRED)
  endif()
endif()
if(NOT pybind11_FOUND)
  message(FATAL_ERROR
    "pybind11 was not found. Install it into the active Python environment, "
    "for example with 'python3 -m pip install pybind11'.")
endif()

find_package(Eigen3 3.4 CONFIG QUIET)
if(NOT Eigen3_FOUND)
  find_path(EIGEN3_INCLUDE_DIR Eigen/Core
    PATH_SUFFIXES eigen3
    PATHS
      /usr/include
      /usr/local/include
      /opt/homebrew/include
  )
  if(EIGEN3_INCLUDE_DIR)
    add_library(Eigen3::Eigen INTERFACE IMPORTED)
    set_target_properties(Eigen3::Eigen PROPERTIES
      INTERFACE_INCLUDE_DIRECTORIES "${EIGEN3_INCLUDE_DIR}"
    )
    set(Eigen3_FOUND TRUE)
  endif()
endif()
if(NOT Eigen3_FOUND)
  message(FATAL_ERROR
    "Eigen3 was not found. Install the system package (e.g. libeigen3-dev) "
    "or provide Eigen3_DIR.")
endif()

set(BSM_SCANNER_CORE_SOURCES
  src/constraints.cpp
  src/evaluator.cpp
  src/functions.cpp
  src/plugins.cpp
  src/status.cpp
  src/scan/adapter.cpp
  src/scan/config.cpp
  src/scan/mapper.cpp
  src/scan/result_writer.cpp
  src/scan/runner.cpp
  src/pybind_module.cpp
)
file(GLOB BSM_SCANNER_PLUGIN_SOURCES CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/src/plugins/*.cpp"
)

pybind11_add_module(_core
  ${BSM_SCANNER_CORE_SOURCES}
  ${BSM_SCANNER_PLUGIN_SOURCES}
)

target_include_directories(_core PRIVATE include)
target_link_libraries(_core PRIVATE Eigen3::Eigen)

if(BSM_SCANNER_BUILD_DIVER)
  if(BSM_SCANNER_DIVER_ROOT)
    if(NOT BSM_SCANNER_DIVER_INCLUDE_DIR AND EXISTS "${BSM_SCANNER_DIVER_ROOT}/include/diver.hpp")
      set(BSM_SCANNER_DIVER_INCLUDE_DIR "${BSM_SCANNER_DIVER_ROOT}/include" CACHE PATH
          "Directory containing diver.hpp" FORCE)
    endif()
    if(NOT BSM_SCANNER_DIVER_LIBRARY)
      if(EXISTS "${BSM_SCANNER_DIVER_ROOT}/lib/libdiver.so")
        set(BSM_SCANNER_DIVER_LIBRARY "${BSM_SCANNER_DIVER_ROOT}/lib/libdiver.so" CACHE FILEPATH
            "Path to the Diver library" FORCE)
      elseif(EXISTS "${BSM_SCANNER_DIVER_ROOT}/lib/libdiver.a")
        set(BSM_SCANNER_DIVER_LIBRARY "${BSM_SCANNER_DIVER_ROOT}/lib/libdiver.a" CACHE FILEPATH
            "Path to the Diver library" FORCE)
      elseif(EXISTS "${BSM_SCANNER_DIVER_ROOT}/lib64/libdiver.so")
        set(BSM_SCANNER_DIVER_LIBRARY "${BSM_SCANNER_DIVER_ROOT}/lib64/libdiver.so" CACHE FILEPATH
            "Path to the Diver library" FORCE)
      elseif(EXISTS "${BSM_SCANNER_DIVER_ROOT}/lib64/libdiver.a")
        set(BSM_SCANNER_DIVER_LIBRARY "${BSM_SCANNER_DIVER_ROOT}/lib64/libdiver.a" CACHE FILEPATH
            "Path to the Diver library" FORCE)
      endif()
    endif()
  endif()
  if(NOT BSM_SCANNER_DIVER_INCLUDE_DIR)
    find_path(BSM_SCANNER_DIVER_INCLUDE_DIR diver.hpp
      HINTS
        /opt/Diver
        /opt/Diver/include
        ${BSM_SCANNER_DIVER_ROOT}
        ${BSM_SCANNER_DIVER_ROOT}/include
        $ENV{DIVER_ROOT}
        $ENV{DIVER_ROOT}/include
    )
  endif()
  if(NOT BSM_SCANNER_DIVER_LIBRARY)
    find_library(BSM_SCANNER_DIVER_LIBRARY
      NAMES diver Diver
      HINTS
        /opt/Diver
        /opt/Diver/lib
        /opt/Diver/lib64
        ${BSM_SCANNER_DIVER_ROOT}
        ${BSM_SCANNER_DIVER_ROOT}/lib
        ${BSM_SCANNER_DIVER_ROOT}/lib64
        $ENV{DIVER_ROOT}
        $ENV{DIVER_ROOT}/lib
        $ENV{DIVER_ROOT}/lib64
    )
  endif()
  if(NOT BSM_SCANNER_DIVER_INCLUDE_DIR OR NOT BSM_SCANNER_DIVER_LIBRARY)
    message(FATAL_ERROR
      "BSM_SCANNER_BUILD_DIVER=ON requires Diver. Set BSM_SCANNER_DIVER_ROOT, "
      "or provide both BSM_SCANNER_DIVER_INCLUDE_DIR and BSM_SCANNER_DIVER_LIBRARY.")
  endif()
  target_compile_definitions(_core PRIVATE BSM_SCANNER_ENABLE_DIVER=1)
  target_include_directories(_core PRIVATE "${BSM_SCANNER_DIVER_INCLUDE_DIR}")
  target_link_libraries(_core PRIVATE "${BSM_SCANNER_DIVER_LIBRARY}")
  get_filename_component(BSM_SCANNER_DIVER_LIBRARY_DIR "${BSM_SCANNER_DIVER_LIBRARY}" DIRECTORY)
  set_property(TARGET _core APPEND PROPERTY BUILD_RPATH "${BSM_SCANNER_DIVER_LIBRARY_DIR}")
  set_property(TARGET _core APPEND PROPERTY INSTALL_RPATH "${BSM_SCANNER_DIVER_LIBRARY_DIR}")

  # Diver is a Fortran library.  Static Diver builds do not always propagate the
  # Fortran runtime dependencies to CMake, so link the common GCC runtimes when
  # they are available.
  find_library(BSM_SCANNER_DIVER_GFORTRAN_LIBRARY
    NAMES gfortran
    HINTS
      /opt/homebrew/opt/gcc/lib/gcc/current
      /opt/homebrew/lib/gcc/current
      /usr/local/opt/gcc/lib/gcc/current
      /usr/local/lib/gcc/current
  )
  if(BSM_SCANNER_DIVER_GFORTRAN_LIBRARY)
    target_link_libraries(_core PRIVATE "${BSM_SCANNER_DIVER_GFORTRAN_LIBRARY}")
    get_filename_component(BSM_SCANNER_DIVER_GFORTRAN_LIBRARY_DIR
                           "${BSM_SCANNER_DIVER_GFORTRAN_LIBRARY}" DIRECTORY)
    set_property(TARGET _core APPEND PROPERTY BUILD_RPATH
                 "${BSM_SCANNER_DIVER_GFORTRAN_LIBRARY_DIR}")
    set_property(TARGET _core APPEND PROPERTY INSTALL_RPATH
                 "${BSM_SCANNER_DIVER_GFORTRAN_LIBRARY_DIR}")
  endif()
  find_library(BSM_SCANNER_DIVER_QUADMATH_LIBRARY
    NAMES quadmath
    HINTS
      /opt/homebrew/opt/gcc/lib/gcc/current
      /opt/homebrew/lib/gcc/current
      /usr/local/opt/gcc/lib/gcc/current
      /usr/local/lib/gcc/current
  )
  if(BSM_SCANNER_DIVER_QUADMATH_LIBRARY)
    target_link_libraries(_core PRIVATE "${BSM_SCANNER_DIVER_QUADMATH_LIBRARY}")
    get_filename_component(BSM_SCANNER_DIVER_QUADMATH_LIBRARY_DIR
                           "${BSM_SCANNER_DIVER_QUADMATH_LIBRARY}" DIRECTORY)
    set_property(TARGET _core APPEND PROPERTY BUILD_RPATH
                 "${BSM_SCANNER_DIVER_QUADMATH_LIBRARY_DIR}")
    set_property(TARGET _core APPEND PROPERTY INSTALL_RPATH
                 "${BSM_SCANNER_DIVER_QUADMATH_LIBRARY_DIR}")
  endif()

  foreach(BSM_SCANNER_DIVER_MPI_LIBRARY_NAME
          mpi_usempif08 mpi_usempi_ignore_tkr mpi_mpifh mpi)
    find_library(BSM_SCANNER_DIVER_MPI_${BSM_SCANNER_DIVER_MPI_LIBRARY_NAME}_LIBRARY
      NAMES ${BSM_SCANNER_DIVER_MPI_LIBRARY_NAME}
      HINTS
        /opt/homebrew/lib
        /opt/homebrew/opt/open-mpi/lib
        /opt/homebrew/Cellar/open-mpi/5.0.8/lib
        /usr/local/lib
        /usr/local/opt/open-mpi/lib
    )
    if(BSM_SCANNER_DIVER_MPI_${BSM_SCANNER_DIVER_MPI_LIBRARY_NAME}_LIBRARY)
      target_link_libraries(_core PRIVATE
        "${BSM_SCANNER_DIVER_MPI_${BSM_SCANNER_DIVER_MPI_LIBRARY_NAME}_LIBRARY}")
      get_filename_component(BSM_SCANNER_DIVER_MPI_LIBRARY_DIR
        "${BSM_SCANNER_DIVER_MPI_${BSM_SCANNER_DIVER_MPI_LIBRARY_NAME}_LIBRARY}" DIRECTORY)
      set_property(TARGET _core APPEND PROPERTY BUILD_RPATH
                   "${BSM_SCANNER_DIVER_MPI_LIBRARY_DIR}")
      set_property(TARGET _core APPEND PROPERTY INSTALL_RPATH
                   "${BSM_SCANNER_DIVER_MPI_LIBRARY_DIR}")
    endif()
  endforeach()
endif()

if(BSM_SCANNER_BUILD_FORTRAN)
  enable_language(Fortran)
endif()

file(GLOB BSM_SCANNER_PLUGIN_CMAKE CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/plugins/*.cmake"
)
foreach(BSM_SCANNER_PLUGIN_CMAKE_FILE IN LISTS BSM_SCANNER_PLUGIN_CMAKE)
  include("${BSM_SCANNER_PLUGIN_CMAKE_FILE}")
endforeach()

install(TARGETS _core LIBRARY DESTINATION bsm_scanner)
