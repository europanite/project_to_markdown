# !/bin/bash
SCRIPT_DIR="$(dirname "$(dirname "${BASH_SOURCE[0]}")")"
source ${SCRIPT_DIR}/env/bin/activate
python3 ${SCRIPT_DIR}/make_md.py -r .
deactivate