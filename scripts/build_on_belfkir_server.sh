#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-mohamed@belfkir-server}"
REMOTE_DIR="${REMOTE_DIR:-/home/mohamed/HEP/BSMScanner}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CMAKE_ARGS_VALUE="${CMAKE_ARGS:-}"
ENABLE_DIVER="${ENABLE_DIVER:-auto}"
REMOTE_DIVER_ROOT="${REMOTE_DIVER_ROOT:-/opt/Diver}"
ENABLE_ONELOOP_MICROMEGAS="${ENABLE_ONELOOP_MICROMEGAS:-auto}"
REMOTE_MICROMEGAS_ROOT="${REMOTE_MICROMEGAS_ROOT:-/opt/micromegas/micromegas_6.2.3}"
REMOTE_MICROMEGAS_MODEL_ROOT="${REMOTE_MICROMEGAS_MODEL_ROOT:-${REMOTE_MICROMEGAS_ROOT}/1LRNM-1N1P-New}"
REMOTE_MICROMEGAS_CALCHEP_ROOT="${REMOTE_MICROMEGAS_CALCHEP_ROOT:-${REMOTE_MICROMEGAS_ROOT}/CalcHEP_src}"

ssh "${REMOTE_HOST}" \
  REMOTE_DIR="${REMOTE_DIR}" \
  PYTHON_BIN="${PYTHON_BIN}" \
  CMAKE_ARGS_VALUE="${CMAKE_ARGS_VALUE}" \
  ENABLE_DIVER="${ENABLE_DIVER}" \
  REMOTE_DIVER_ROOT="${REMOTE_DIVER_ROOT}" \
  ENABLE_ONELOOP_MICROMEGAS="${ENABLE_ONELOOP_MICROMEGAS}" \
  REMOTE_MICROMEGAS_ROOT="${REMOTE_MICROMEGAS_ROOT}" \
  REMOTE_MICROMEGAS_MODEL_ROOT="${REMOTE_MICROMEGAS_MODEL_ROOT}" \
  REMOTE_MICROMEGAS_CALCHEP_ROOT="${REMOTE_MICROMEGAS_CALCHEP_ROOT}" \
  'bash -s' <<'EOF'
set -euo pipefail

cd "${REMOTE_DIR}"
resolved_cmake_args="${CMAKE_ARGS_VALUE}"

case "${ENABLE_DIVER}" in
  1|true|TRUE|yes|YES|on|ON)
    if [ -d "${REMOTE_DIVER_ROOT}" ]; then
      if [ -n "${resolved_cmake_args}" ]; then
        resolved_cmake_args="${resolved_cmake_args} -DBSM_SCANNER_BUILD_DIVER=ON -DBSM_SCANNER_DIVER_ROOT=${REMOTE_DIVER_ROOT}"
      else
        resolved_cmake_args="-DBSM_SCANNER_BUILD_DIVER=ON -DBSM_SCANNER_DIVER_ROOT=${REMOTE_DIVER_ROOT}"
      fi
    else
      echo "Requested Diver build, but ${REMOTE_DIVER_ROOT} was not found." >&2
      exit 2
    fi
    ;;
  auto|AUTO)
    if [ -d "${REMOTE_DIVER_ROOT}" ] && [ -z "${resolved_cmake_args}" ]; then
      resolved_cmake_args="-DBSM_SCANNER_BUILD_DIVER=ON -DBSM_SCANNER_DIVER_ROOT=${REMOTE_DIVER_ROOT}"
    fi
    ;;
esac

case "${ENABLE_ONELOOP_MICROMEGAS}" in
  1|true|TRUE|yes|YES|on|ON)
    if [ -d "${REMOTE_MICROMEGAS_ROOT}" ] && [ -d "${REMOTE_MICROMEGAS_MODEL_ROOT}" ] && [ -d "${REMOTE_MICROMEGAS_CALCHEP_ROOT}" ]; then
      if [ -n "${resolved_cmake_args}" ]; then
        resolved_cmake_args="${resolved_cmake_args} -DBSM_SCANNER_BUILD_ONELOOP_MICROMEGAS=ON -DBSM_SCANNER_MICROMEGAS_ROOT=${REMOTE_MICROMEGAS_ROOT} -DBSM_SCANNER_MICROMEGAS_MODEL_ROOT=${REMOTE_MICROMEGAS_MODEL_ROOT} -DBSM_SCANNER_MICROMEGAS_CALCHEP_ROOT=${REMOTE_MICROMEGAS_CALCHEP_ROOT}"
      else
        resolved_cmake_args="-DBSM_SCANNER_BUILD_ONELOOP_MICROMEGAS=ON -DBSM_SCANNER_MICROMEGAS_ROOT=${REMOTE_MICROMEGAS_ROOT} -DBSM_SCANNER_MICROMEGAS_MODEL_ROOT=${REMOTE_MICROMEGAS_MODEL_ROOT} -DBSM_SCANNER_MICROMEGAS_CALCHEP_ROOT=${REMOTE_MICROMEGAS_CALCHEP_ROOT}"
      fi
    else
      echo "Requested oneloop micrOMEGAs build, but one or more required directories were not found." >&2
      exit 2
    fi
    ;;
  auto|AUTO)
    if [ -d "${REMOTE_MICROMEGAS_ROOT}" ] && [ -d "${REMOTE_MICROMEGAS_MODEL_ROOT}" ] && [ -d "${REMOTE_MICROMEGAS_CALCHEP_ROOT}" ]; then
      if [[ "${resolved_cmake_args}" != *"BSM_SCANNER_BUILD_ONELOOP_MICROMEGAS"* ]]; then
        if [ -n "${resolved_cmake_args}" ]; then
          resolved_cmake_args="${resolved_cmake_args} -DBSM_SCANNER_BUILD_ONELOOP_MICROMEGAS=ON -DBSM_SCANNER_MICROMEGAS_ROOT=${REMOTE_MICROMEGAS_ROOT} -DBSM_SCANNER_MICROMEGAS_MODEL_ROOT=${REMOTE_MICROMEGAS_MODEL_ROOT} -DBSM_SCANNER_MICROMEGAS_CALCHEP_ROOT=${REMOTE_MICROMEGAS_CALCHEP_ROOT}"
        else
          resolved_cmake_args="-DBSM_SCANNER_BUILD_ONELOOP_MICROMEGAS=ON -DBSM_SCANNER_MICROMEGAS_ROOT=${REMOTE_MICROMEGAS_ROOT} -DBSM_SCANNER_MICROMEGAS_MODEL_ROOT=${REMOTE_MICROMEGAS_MODEL_ROOT} -DBSM_SCANNER_MICROMEGAS_CALCHEP_ROOT=${REMOTE_MICROMEGAS_CALCHEP_ROOT}"
        fi
      fi
    fi
    ;;
esac

"${PYTHON_BIN}" -m venv .venv
source .venv/bin/activate
export CMAKE_ARGS="${resolved_cmake_args}"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .[dev]
python -m pytest tests
EOF

echo "Remote build and tests completed on ${REMOTE_HOST}:${REMOTE_DIR}"
