#!/bin/bash
set -ex

LOG_FILE="/home/ubuntu/logfile.log"

exec > "$LOG_FILE" 2>&1

export HOME=/home/ubuntu
export PATH="/usr/local/bin:/usr/bin:$PATH"

WORK_DIR="/home/ubuntu/ssle_test"
export CONFIG_URL=http://74.120.175.74:5000/p256_config.txt
export PROGRAM_URL=http://74.120.175.74:5000/share_benchmark

export NETWORK_MODE="lan"
# export NETWORK_MODE="wan"

sudo rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

wget -O network_config.sh http://74.120.175.74:5000/network_config.sh
chmod +x network_config.sh

wget -O run.py http://74.120.175.74:5000/run.py
sudo apt update > /dev/null 2>&1
sudo apt install python3-pip  python3-venv -y > /dev/null 2>&1

python3 -m venv venv > /dev/null 2>&1
source venv/bin/activate > /dev/null 2>&1

pip3 install requests > /dev/null 2>&1
python run.py
