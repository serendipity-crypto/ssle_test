#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EMP Share Benchmark 运行脚本
功能:自动识别本机IP并确定party_id,然后运行基准测试

2. 运行脚本:
   python3 run.py
"""

import os
import sys
import subprocess
import socket
import re
import glob


# 颜色输出
class Color:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"  # No Color


def print_colored(color, message):
    """彩色输出"""
    print(f"{color}{message}{Color.NC}")


def print_info(message):
    print_colored(Color.BLUE, f"[INFO] {message}")


def print_success(message):
    print_colored(Color.GREEN, f"[SUCCESS] {message}")


def print_warning(message):
    print_colored(Color.YELLOW, f"[WARNING] {message}")


def print_error(message):
    print_colored(Color.RED, f"[ERROR] {message}")


def get_local_ip():
    """获取本机IP地址"""
    print_info("获取本机IP地址...")

    # 尝试多种方法获取IP
    methods = [
        # 方法2: 使用hostname
        lambda: _get_ip_by_hostname(),
        # 方法1: 连接外部地址
        lambda: _get_ip_by_connection(),
    ]

    for i, method in enumerate(methods, 1):
        try:
            ip = method()
            if ip and ip != "127.0.0.1":
                print_success(f"成功获取IP地址: {ip} (方法{i})")
                return ip
        except Exception as e:
            print_warning(f"方法{i}失败: {e}")
            continue

    # 如果都失败,返回默认值
    print_warning("无法自动获取IP地址,使用默认值127.0.0.1")
    return "127.0.0.1"


def _get_ip_by_connection():
    """通过连接外部地址获取IP"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


def _get_ip_by_hostname():
    """通过hostname获取IP"""
    hostname = socket.gethostname()
    return socket.gethostbyname(hostname)


def validate_config(config_path):
    print_info(f"验证配置文件: {config_path}")

    if not os.path.exists(config_path):
        print_error("配置文件不存在")
        return False, 0

    try:
        with open(config_path, "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        if not lines:
            print_error("配置文件为空")
            return False, 0

        # 第一行应该是参与方数量
        try:
            num_parties = int(lines[0])
            print_info(f"参与方数量: {num_parties}")
        except ValueError:
            print_error("配置文件第一行应该是数字（参与方数量）")
            return False, 0

        # 检查是否有足够的IP地址行
        if len(lines) < num_parties + 1:
            print_error("配置文件行数不足")
            return False, 0

        # 验证IP地址格式
        for i in range(1, min(num_parties + 1, len(lines))):
            ip = lines[i]
            if not _is_valid_ip(ip):
                print_warning(f"第{i+1}行可能不是有效的IP地址: {ip}")

        print_success("配置文件验证完成")
        return True, num_parties
    except Exception as e:
        print_error(f"配置文件验证失败: {e}")
        return False, 0


def _is_valid_ip(ip):
    """简单验证IP地址格式"""
    pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    if re.match(pattern, ip):
        parts = ip.split(".")
        return all(0 <= int(part) <= 255 for part in parts)
    return False


def find_party_id(config_path, local_ip):
    """在配置文件中查找本机的party_id"""
    print_info(f"在配置文件中查找IP: {local_ip}")

    try:
        with open(config_path, "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        if not lines:
            print_error("配置文件为空")
            return None

        num_parties = int(lines[0])

        # 查找匹配的IP地址
        for i in range(min(num_parties, len(lines) - 1)):
            config_ip = lines[i + 1]
            if config_ip == local_ip:
                print_success(f"找到匹配的IP,party_id: {i}")
                return i

        print_warning("未找到匹配的IP地址")
        print_info("配置文件中的IP列表:")
        for i in range(min(num_parties, len(lines) - 1)):
            print_info(f"  [{i}] {lines[i + 1]}")

        # 如果没找到,询问是否使用第一个
        print_warning("将使用默认party_id: 0")
        return 0
    except Exception as e:
        print_error(f"查找party_id失败: {e}")
        return None


def upload_to_dufs(local_file, remote_path, dufs_server):
    """使用curl上传文件到dufs服务器"""
    if not os.path.exists(local_file):
        print_error(f"要上传的文件不存在: {local_file}")
        return False

    upload_url = f"{dufs_server}/{remote_path}"
    print_info(f"使用curl上传文件到dufs: {local_file} -> {upload_url}")

    # 使用curl上传文件
    cmd = ["curl", "-T", local_file, upload_url]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print_success(f"上传成功: {os.path.basename(local_file)}")
        return True
    else:
        print_error(f"上传失败: {local_file} - curl错误: {result.stderr}")
        return False


def delete_all_csv_files():
    # 遍历目录中的所有文件
    for filename in glob.glob("*.csv"):
        try:
            os.remove(filename)
            print(f"已删除文件: {filename}")
        except Exception as e:
            print(f"删除文件 {filename} 时出错: {str(e)}")


def upload_results(dufs_server, scheme, transport, topology, network_mode):
    """上传结果文件到dufs服务器"""
    print_info("查找并上传结果文件...")

    # 查找匹配的文件
    files = glob.glob("*.csv")

    if not files:
        print_warning("未找到任何结果文件")
        return True

    success_count = 0
    fail_count = 0

    # 创建基于时间戳的目录
    upload_dir = f"{scheme}_{transport}_{topology}_{network_mode}_results"

    for file in files:
        remote_path = f"{upload_dir}/{os.path.basename(file)}"
        if upload_to_dufs(file, remote_path, dufs_server):
            success_count += 1
        else:
            fail_count += 1

    print_info(f"上传完成: {success_count} 个文件成功, {fail_count} 个文件失败")
    return fail_count == 0


def run_benchmark(
    program_path,
    party_id,
    config_path,
    scheme,
    network_mode,
    topology,
):
    """运行基准测试"""
    print_info("运行基准测试...")
    print_info(f"  Program: {program_path}")
    print_info(f"  Party ID: {party_id}")
    print_info(f"  Config: {config_path}")
    print_info(f"  Network Mode: {network_mode}")

    base_port = os.environ.get("BASE_PORT", "12367")

    # 检查程序文件
    if not os.path.exists(program_path):
        print_error(f"程序文件不存在: {program_path}")
        return False

    # 构建命令
    if scheme == "qelect":
        cmd = [
            program_path,
            "-i",
            str(party_id),
            "-c",
            config_path,
            "-s",
            f"{topology}_{network_mode}",
            "-b",
            f"{base_port}",
            "--scheme",
            "qelect",
        ]
    else:
        cmd = [
            program_path,
            "-i",
            str(party_id),
            "-c",
            config_path,
            "-s",
            f"{topology}_{network_mode}",
            "-b",
            f"{base_port}",
        ]
    print_info(f"执行命令: {' '.join(cmd)}")

    try:
        with open("output.log", "w") as log_file:
            # 执行命令
            result = subprocess.run(
                cmd,
                stdout=log_file,  # 标准输出重定向到文件
                stderr=log_file,  # 标准错误也重定向到同一个文件
                text=True,
                timeout=60 * 5,  # 超时
            )

        if result.returncode == 0:
            print_success("基准测试执行成功")
            if result.stdout:
                print("输出:")
                print(result.stdout)
            return True
        else:
            print_error(f"基准测试执行失败 (退出码: {result.returncode})")
            if result.stderr:
                print("错误信息:")
                print(result.stderr)
            return False
    except subprocess.TimeoutExpired:
        print_error("基准测试执行超时")
        return False
    except Exception as e:
        print_error(f"执行基准测试时出错: {e}")
        return False


def main():
    print_info("EMP Share Benchmark 运行脚本")

    dufs_server = os.environ.get("DUFS_SERVER", "http://148.135.88.228:5000")

    # 配置路径
    scheme = os.environ.get("SCHEME", "relect")  # qelect
    transport = os.environ.get("TRANSPORT", "tcp")
    topology = os.environ.get("TOPOLOGY", "tree")  # pairwise
    network_mode = os.environ.get("NETWORK_MODE", "lan")  # wan
    local_config = os.environ.get("LOCAL_CONFIG", "./config.txt")
    local_program = os.environ.get("LOCAL_PROGRAM", f"./{transport}_{topology}")

    # # 验证配置文件并获取参与方数量
    # config_valid, num_parties = validate_config(local_config)
    # if not config_valid:
    #     print_error("配置文件验证失败")
    #     return False

    # 获取本机IP
    local_ip = get_local_ip()

    # 查找party_id
    party_id = find_party_id(local_config, local_ip)
    if party_id is None:
        party_id = 0  # 默认值

    if network_mode == "wan":
        cmd = ["./network_config.sh"]
        subprocess.run(
            cmd,
            input="2\n",
            text=True,
            timeout=30,
        )
    elif network_mode == "lan":
        cmd = ["./network_config.sh"]
        subprocess.run(
            cmd,
            input="5\n",
            text=True,
            timeout=30,
        )

    delete_all_csv_files()

    # 运行基准测试
    success = run_benchmark(
        local_program,
        party_id,
        local_config,
        scheme,
        network_mode,
        topology,
    )

    if network_mode == "wan":
        cmd = ["./network_config.sh"]
        subprocess.run(
            cmd,
            input="5\n",
            text=True,
            timeout=30,
        )

    # 上传结果文件
    if success:
        print_info("开始上传结果文件...")
        upload_success = upload_results(
            dufs_server,
            scheme,
            transport,
            topology,
            network_mode,
        )
        if upload_success:
            print_success("所有操作完成")
        else:
            print_warning("基准测试完成,但部分文件上传失败")
    else:
        print_error("基准测试执行失败")

    return success


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print_info("用户中断执行")
        sys.exit(1)
    except Exception as e:
        print_error(f"程序执行出错: {e}")
        sys.exit(1)
