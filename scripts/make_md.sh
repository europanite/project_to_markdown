# !/bin/bash
source ../env/bin/activate
python3 ../make_md.py -r "$@"
deactivate