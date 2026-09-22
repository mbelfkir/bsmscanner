# Generic micrOMEGAs plugin build fragment. Auto-included by the root
# CMakeLists.txt (cmake/plugins/*.cmake globbing) alongside src/plugins/micromegas.cpp.
#
# Only one micrOMEGAs-backed CalcHEP model can be linked into a given
# BSMScanner build: micrOMEGAs is a C library with global state, so these
# paths select the model at CONFIGURE time, not at scan time. Switching
# models means reconfiguring and rebuilding, not passing a different YAML.
# Point these at whichever project `bsm-scanner generate-dm-config`'s
# --calchep-model-root / --micromegas-root generated a cache script for.

option(BSM_SCANNER_BUILD_MICROMEGAS
       "Build the generic micromegas plugin against a compiled micrOMEGAs project"
       OFF)
set(BSM_SCANNER_MICROMEGAS_ROOT "" CACHE PATH "micrOMEGAs installation prefix")
set(BSM_SCANNER_MICROMEGAS_MODEL_ROOT "" CACHE PATH
    "Compiled micrOMEGAs CalcHEP model directory for the target physics model")
set(BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT "" CACHE PATH
    "CalcHEP_src directory inside the micrOMEGAs installation")

if(NOT BSM_SCANNER_BUILD_MICROMEGAS)
  return()
endif()

if(NOT BSM_SCANNER_MICROMEGAS_ROOT AND DEFINED ENV{MICROMEGAS_PATH} AND EXISTS "$ENV{MICROMEGAS_PATH}")
  set(BSM_SCANNER_MICROMEGAS_ROOT "$ENV{MICROMEGAS_PATH}" CACHE PATH
      "micrOMEGAs installation prefix" FORCE)
endif()
if(NOT BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT AND BSM_SCANNER_MICROMEGAS_ROOT)
  if(EXISTS "${BSM_SCANNER_MICROMEGAS_ROOT}/CalcHEP_src")
    set(BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT
        "${BSM_SCANNER_MICROMEGAS_ROOT}/CalcHEP_src" CACHE PATH
        "CalcHEP_src directory inside the micrOMEGAs installation" FORCE)
  endif()
endif()

if(NOT EXISTS "${BSM_SCANNER_MICROMEGAS_ROOT}/include/micromegas.h")
  message(FATAL_ERROR
    "BSM_SCANNER_BUILD_MICROMEGAS=ON requires micrOMEGAs headers under "
    "BSM_SCANNER_MICROMEGAS_ROOT/include.")
endif()
if(NOT EXISTS "${BSM_SCANNER_MICROMEGAS_MODEL_ROOT}/lib/aLib.a")
  message(FATAL_ERROR
    "BSM_SCANNER_BUILD_MICROMEGAS=ON requires a compiled micrOMEGAs CalcHEP "
    "model under BSM_SCANNER_MICROMEGAS_MODEL_ROOT.")
endif()
if(NOT EXISTS "${BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT}/lib/dynamic_me.a")
  message(FATAL_ERROR
    "BSM_SCANNER_BUILD_MICROMEGAS=ON requires CalcHEP_src under "
    "BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT.")
endif()

file(GLOB BSM_SCANNER_MICROMEGAS_MODEL_STATIC_LIBS
     "${BSM_SCANNER_MICROMEGAS_MODEL_ROOT}/lib/*.a")

set(BSM_SCANNER_MICROMEGAS_SERVICE_LIB
    "${BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT}/lib/servNoX11.a")
if(APPLE AND EXISTS "${BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT}/lib/serv.a")
  set(BSM_SCANNER_MICROMEGAS_SERVICE_LIB
      "${BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT}/lib/serv.a")
  find_package(X11 REQUIRED)
endif()
if(NOT EXISTS "${BSM_SCANNER_MICROMEGAS_SERVICE_LIB}")
  set(BSM_SCANNER_MICROMEGAS_SERVICE_LIB
      "${BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT}/lib/serv.a")
endif()

if(NOT EXISTS "${BSM_SCANNER_MICROMEGAS_ROOT}/lib/micromegas.a")
  message(FATAL_ERROR "Could not find micromegas.a under ${BSM_SCANNER_MICROMEGAS_ROOT}/lib.")
endif()

find_package(Threads REQUIRED)
find_library(BSM_SCANNER_GFORTRAN_LIBRARY gfortran)
find_library(BSM_SCANNER_QUADMATH_LIBRARY quadmath)

set(BSM_SCANNER_MICROMEGAS_SQME_AUX "${BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT}/lib/sqme_aux.so")
set(BSM_SCANNER_MICROMEGAS_MAXGAP "${BSM_SCANNER_MICROMEGAS_ROOT}/lib/maxGap.so")
set(BSM_SCANNER_MICROMEGAS_LHAPDF "${BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT}/lib/lhapdf.so")

add_library(bsm_sqme_aux SHARED IMPORTED)
set_target_properties(bsm_sqme_aux PROPERTIES IMPORTED_LOCATION "${BSM_SCANNER_MICROMEGAS_SQME_AUX}")
add_library(bsm_maxGap SHARED IMPORTED)
set_target_properties(bsm_maxGap PROPERTIES IMPORTED_LOCATION "${BSM_SCANNER_MICROMEGAS_MAXGAP}")
add_library(bsm_lhapdf SHARED IMPORTED)
set_target_properties(bsm_lhapdf PROPERTIES IMPORTED_LOCATION "${BSM_SCANNER_MICROMEGAS_LHAPDF}")

target_compile_definitions(_core PRIVATE BSM_SCANNER_ENABLE_MICROMEGAS=1)
target_include_directories(_core PRIVATE
  "${BSM_SCANNER_MICROMEGAS_ROOT}/include"
  "${BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT}/include"
  "${BSM_SCANNER_MICROMEGAS_MODEL_ROOT}/lib"
)

target_link_libraries(_core PRIVATE
  ${BSM_SCANNER_MICROMEGAS_MODEL_STATIC_LIBS}
  "${BSM_SCANNER_MICROMEGAS_ROOT}/lib/micromegas.a"
  "${BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT}/lib/dynamic_me.a"
  "${BSM_SCANNER_MICROMEGAS_MODEL_ROOT}/work/work_aux.a"
  bsm_sqme_aux
  "${BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT}/lib/libSLHAplus.a"
  "${BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT}/lib/num_c.a"
  "${BSM_SCANNER_MICROMEGAS_SERVICE_LIB}"
  "${BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT}/lib/ntools.a"
  bsm_maxGap
  bsm_lhapdf
  "${BSM_SCANNER_MICROMEGAS_ROOT}/lib/dummy.a"
  "${BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT}/lib/dummy.a"
  Threads::Threads
  ${CMAKE_DL_LIBS}
  m
)

if(APPLE)
  target_link_libraries(_core PRIVATE X11::X11)
endif()
if(BSM_SCANNER_GFORTRAN_LIBRARY)
  target_link_libraries(_core PRIVATE "${BSM_SCANNER_GFORTRAN_LIBRARY}")
endif()
if(BSM_SCANNER_QUADMATH_LIBRARY)
  target_link_libraries(_core PRIVATE "${BSM_SCANNER_QUADMATH_LIBRARY}")
endif()

set(BSM_SCANNER_MICROMEGAS_RPATHS
    "${BSM_SCANNER_MICROMEGAS_ROOT}/lib"
    "${BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT}/lib"
    "${BSM_SCANNER_MICROMEGAS_MODEL_ROOT}/lib"
    "${BSM_SCANNER_MICROMEGAS_MODEL_ROOT}/work")
set_property(TARGET _core APPEND PROPERTY BUILD_RPATH "${BSM_SCANNER_MICROMEGAS_RPATHS}")
set_property(TARGET _core APPEND PROPERTY INSTALL_RPATH "${BSM_SCANNER_MICROMEGAS_RPATHS}")
