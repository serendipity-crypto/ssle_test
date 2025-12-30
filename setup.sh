#!/bin/bash
set -ex

if [ $# -eq 0 ]; then
    echo "Usage: $0 <Party Count>"
    exit 1
fi

LOG_FILE="/home/ubuntu/logfile.log"

exec > "$LOG_FILE" 2>&1

export HOME=/home/ubuntu
export PATH="/usr/local/bin:/usr/bin:$PATH"
export DUFS_SERVER="http://148.135.88.228:5000"

N=$1

WORK_DIR="/home/ubuntu/ssle_test"
export CONFIG_URL="${DUFS_SERVER}/p${N}_config.txt"
export TCP_TREE_PROGRAM_URL="${DUFS_SERVER}/tcp_tree"
export TCP_PAIRWISE_PROGRAM_URL="${DUFS_SERVER}/tcp_pairwise"

mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

sudo apt update
sudo apt install curl -y

if ! curl -s --head "$DUFS_SERVER" > /dev/null; then
    echo "Error: Cannot reach server $DUFS_SERVER"
    exit 1
fi

wget -O config.txt "${CONFIG_URL}"

# wget -O share_benchmark "${PROGRAM_URL}"
# chmod +x share_benchmark

wget -O tcp_tree "${TCP_TREE_PROGRAM_URL}"
chmod +x tcp_tree

wget -O tcp_pairwise "${TCP_PAIRWISE_PROGRAM_URL}"
chmod +x tcp_pairwise

wget -O network_config.sh "${DUFS_SERVER}/network_config.sh"
chmod +x network_config.sh

wget -O run.py "${DUFS_SERVER}/run.py"
