#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

REPO_DIR="${REPO_DIR:-${ROOT_DIR}}"
VENV_PATH="${VENV_PATH:-${REPO_DIR}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python}"

MODEL_PATH="${MODEL_PATH:-examples/oneloop_master/model_normal_full.yaml}"
RUN_DIR="${RUN_DIR:-examples/oneloop_master/runs/normal_full_run}"

JOB_NAME="${JOB_NAME:-oneloop_nf}"
PARTITION="${PARTITION:-}"
ACCOUNT="${ACCOUNT:-}"
QOS="${QOS:-}"
TIME_LIMIT="${TIME_LIMIT:-24:00:00}"
CPUS_PER_TASK="${CPUS_PER_TASK:-1}"
MEMORY="${MEMORY:-8G}"
OMP_THREADS="${OMP_THREADS:-${CPUS_PER_TASK}}"

LOG_DIR="${LOG_DIR:-${REPO_DIR}/slurm_logs}"
SBATCH_DIR="${SBATCH_DIR:-${LOG_DIR}/jobs}"

mkdir -p "${LOG_DIR}" "${SBATCH_DIR}"

if ! command -v sbatch >/dev/null 2>&1; then
  echo "sbatch was not found in PATH. Run this script on the Slurm-enabled server." >&2
  exit 2
fi

if [ ! -d "${REPO_DIR}" ]; then
  echo "Repository directory does not exist: ${REPO_DIR}" >&2
  exit 2
fi

if [ ! -f "${VENV_PATH}/bin/activate" ]; then
  echo "Virtual environment not found at ${VENV_PATH}." >&2
  echo "Build/install the project on the server first so .venv exists." >&2
  exit 2
fi

timestamp="$(date +%Y%m%d_%H%M%S)"
job_script="${SBATCH_DIR}/${JOB_NAME}_${timestamp}.sbatch"
stdout_log="${LOG_DIR}/${JOB_NAME}-%j.out"
stderr_log="${LOG_DIR}/${JOB_NAME}-%j.err"

cat > "${job_script}" <<EOF
#!/usr/bin/env bash
set -euo pipefail

cd "${REPO_DIR}"
source "${VENV_PATH}/bin/activate"

export OMP_NUM_THREADS="${OMP_THREADS}"
export OPENBLAS_NUM_THREADS="${OMP_THREADS}"
export MKL_NUM_THREADS="${OMP_THREADS}"
export NUMEXPR_NUM_THREADS="${OMP_THREADS}"

"${PYTHON_BIN}" examples/oneloop_master/run_scan.py \\
  --model "${MODEL_PATH}" \\
  --run-dir "${RUN_DIR}"
EOF

chmod +x "${job_script}"

sbatch_args=(
  "--job-name=${JOB_NAME}"
  "--output=${stdout_log}"
  "--error=${stderr_log}"
  "--time=${TIME_LIMIT}"
  "--cpus-per-task=${CPUS_PER_TASK}"
  "--mem=${MEMORY}"
)

if [ -n "${PARTITION}" ]; then
  sbatch_args+=("--partition=${PARTITION}")
fi

if [ -n "${ACCOUNT}" ]; then
  sbatch_args+=("--account=${ACCOUNT}")
fi

if [ -n "${QOS}" ]; then
  sbatch_args+=("--qos=${QOS}")
fi

submit_output="$(sbatch "${sbatch_args[@]}" "${job_script}")"

echo "${submit_output}"
echo "Job script: ${job_script}"
echo "Stdout log: ${stdout_log}"
echo "Stderr log: ${stderr_log}"
echo "Run directory: ${RUN_DIR}"
