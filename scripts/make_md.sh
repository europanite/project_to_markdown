#!/bin/bash

set -e

SCRIPT_DIR="$(dirname "$(dirname "${BASH_SOURCE[0]}")")"
ENV_DIR="${SCRIPT_DIR}/env"
REQUIREMENTS="${SCRIPT_DIR}/requirement.txt"

if [ ! -d "${ENV_DIR}" ]; then
    echo "Creating virtual environment: ${ENV_DIR}"
    python3 -m venv "${ENV_DIR}"

    echo "Installing requirements..."
    "${ENV_DIR}/bin/python" -m pip install --upgrade pip

    if [ -f "${REQUIREMENTS}" ]; then
        "${ENV_DIR}/bin/python" -m pip install -r "${REQUIREMENTS}"
    else
        echo "Warning: ${REQUIREMENTS} not found."
    fi
fi

source "${ENV_DIR}/bin/activate"

python3 "${SCRIPT_DIR}/make_md.py" -r .

deactivate