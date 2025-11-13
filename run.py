#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EMP Share Benchmark 自动化部署脚本 (Python版本)
功能：下载配置文件，自动识别本机IP并确定party_id，然后运行基准测试

使用方法：
1. 设置环境变量：
   export CONFIG_URL=http://your-server.com/config.txt
   export PROGRAM_URL=http://your-server.com/share_benchmark  # 可选

2. 运行脚本：
   python3 run_practical.py

作者：Assistant
"""

import os
import sys
import subprocess
import requests
import socket
import re
import glob
from pathlib import Path
from datetime import datetime


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


def get_env_var(var_name, default_value=None):
    """获取环境变量，如果不存在则使用默认值"""
    value = os.environ.get(var_name)
    if value is None:
        if default_value is not None:
            print_warning(f"环境变量 {var_name} 未设置，使用默认值: {default_value}")
            return default_value
        else:
            print_error(f"请设置环境变量 {var_name}")
            return None
    return value


def check_dependencies():
    """检查依赖工具"""
    print_info("检查系统依赖...")

    # 检查Python版本
    if sys.version_info < (3, 6):
        print_error("需要Python 3.6或更高版本")
        return False

    # 检查requests库
    try:
        import requests
    except ImportError:
        print_error("缺少requests库，请安装: pip install requests")
        return False

    print_success("依赖检查通过")
    return True


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

    # 如果都失败，返回默认值
    print_warning("无法自动获取IP地址，使用默认值127.0.0.1")
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


def download_file(url, output_path):
    """下载文件"""
    print_info(f"下载文件: {url}")

    try:
        # 确保目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 下载文件
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # 保存文件
        with open(output_path, "wb") as f:
            f.write(response.content)

        print_success(f"文件下载成功: {output_path}")
        return True
    except Exception as e:
        print_error(f"文件下载失败: {e}")
        return False


def validate_config(config_path):
    """验证配置文件格式"""
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
                print_success(f"找到匹配的IP，party_id: {i}")
                return i

        print_warning("未找到匹配的IP地址")
        print_info("配置文件中的IP列表:")
        for i in range(min(num_parties, len(lines) - 1)):
            print_info(f"  [{i}] {lines[i + 1]}")

        # 如果没找到，询问是否使用第一个
        print_warning("将使用默认party_id: 0")
        return 0
    except Exception as e:
        print_error(f"查找party_id失败: {e}")
        return None


def set_executable_permission(file_path):
    """设置文件执行权限"""
    if os.path.exists(file_path):
        try:
            os.chmod(file_path, 0o755)
            print_success("设置执行权限成功")
            return True
        except Exception as e:
            print_warning(f"设置执行权限失败: {e}")
            return False
    else:
        print_warning(f"文件不存在: {file_path}")
        return False


def check_remote_file_exists(dufs_server, remote_path):
    """检查远程文件是否存在"""
    check_url = f"{dufs_server}/{remote_path}"
    try:
        response = requests.head(check_url, timeout=10)
        return response.status_code == 200
    except Exception:
        return False


def compare_file_sizes(local_file, dufs_server, remote_path):
    """比较本地和远程文件大小"""
    if not os.path.exists(local_file):
        return False

    check_url = f"{dufs_server}/{remote_path}"
    try:
        response = requests.head(check_url, timeout=10)
        remote_size = int(response.headers.get("content-length", 0))
        local_size = os.path.getsize(local_file)

        print_info(f"文件大小匹配: 本地={local_size}, 远程={remote_size}")
        return local_size == remote_size
    except Exception:
        return False


def upload_to_dufs(local_file, remote_path, dufs_server):
    """上传文件到dufs服务器"""
    if not os.path.exists(local_file):
        print_error(f"要上传的文件不存在: {local_file}")
        return False

    upload_url = f"{dufs_server}/{remote_path}"
    print_info(f"上传文件到dufs: {local_file} -> {upload_url}")

    # 检查远程文件是否已存在
    if check_remote_file_exists(dufs_server, remote_path):
        # 比较文件大小
        if compare_file_sizes(local_file, dufs_server, remote_path):
            print_info(
                f"文件已存在且大小一致，跳过上传: {os.path.basename(local_file)}"
            )
            return True
        else:
            print_warning(
                f"文件已存在但大小不同，将覆盖上传: {os.path.basename(local_file)}"
            )
    else:
        print_info(f"远程文件不存在，准备上传: {os.path.basename(local_file)}")

    try:
        with open(local_file, "rb") as f:
            response = requests.put(upload_url, data=f, timeout=60)
            if response.status_code in [200, 201, 204]:
                print_success(f"上传成功: {os.path.basename(local_file)}")
                return True
            else:
                print_error(f"上传失败: {local_file} - HTTP {response.status_code}")
                return False
    except Exception as e:
        print_error(f"上传失败: {local_file} - {str(e)}")
        return False


def upload_results(dufs_server, num_parties, party_id, network_mode):
    """上传结果文件到dufs服务器"""
    print_info("查找并上传结果文件...")

    # 根据C++代码的命名规则生成文件名模式
    filename_pattern = (
        f"benchmark_results_p{num_parties}_id{party_id}_{network_mode}.csv"
    )
    print_info(f"查找结果文件: {filename_pattern}")

    # 查找匹配的文件
    files = glob.glob(filename_pattern)

    if not files:
        print_warning(f"未找到匹配的结果文件: {filename_pattern}")
        # 尝试查找类似的文件
        alternative_pattern = f"benchmark_results_p*_id{party_id}_*.csv"
        alternative_files = glob.glob(alternative_pattern)
        if alternative_files:
            print_info(f"找到类似文件: {alternative_files}")
            files = alternative_files
        else:
            print_warning("未找到任何结果文件")
            return True

    success_count = 0
    fail_count = 0

    # 创建基于时间戳的目录
    upload_dir = f"{network_mode}_results"

    for file in files:
        remote_path = f"{upload_dir}/{os.path.basename(file)}"
        if upload_to_dufs(file, remote_path, dufs_server):
            success_count += 1
        else:
            fail_count += 1

    print_info(f"上传完成: {success_count} 个文件成功, {fail_count} 个文件失败")
    return fail_count == 0


def run_benchmark(program_path, party_id, config_path, network_mode):
    """运行基准测试"""
    print_info("运行基准测试...")
    print_info(f"  Program: {program_path}")
    print_info(f"  Party ID: {party_id}")
    print_info(f"  Config: {config_path}")
    print_info(f"  Network Mode: {network_mode}")

    # 检查程序文件
    if not os.path.exists(program_path):
        print_error(f"程序文件不存在: {program_path}")
        return False

    # 设置执行权限
    set_executable_permission(program_path)

    # 构建命令
    cmd = [program_path, str(party_id), config_path, network_mode]
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
    """主函数"""
    print_info("EMP Share Benchmark 自动化部署脚本 (Python版本)")

    # 检查依赖
    if not check_dependencies():
        return False

    # 获取配置（从环境变量或使用默认值）
    config_url = get_env_var("CONFIG_URL")
    if not config_url:
        print_error("请设置CONFIG_URL环境变量")
        print("示例: export CONFIG_URL=http://example.com/config.txt")
        return False

    program_url = os.environ.get("PROGRAM_URL")
    dufs_server = os.environ.get("DUFS_SERVER", "http://74.120.175.74:5000/")

    # 配置路径
    local_program = os.environ.get("LOCAL_PROGRAM", "./share_benchmark")
    local_config = os.environ.get("LOCAL_CONFIG", "./config.txt")
    network_mode = os.environ.get("NETWORK_MODE", "wan")

    # 下载程序文件（如果提供了URL）
    if program_url:
        print_info(f"从 {program_url} 下载程序文件")
        if not download_file(program_url, local_program):
            print_warning("程序文件下载失败")
    else:
        print_info("未提供PROGRAM_URL，跳过程序文件下载")

    # 下载配置文件
    print_info(f"从 {config_url} 下载配置文件")
    if not download_file(config_url, local_config):
        print_error("配置文件下载失败")
        return False

    # 验证配置文件并获取参与方数量
    config_valid, num_parties = validate_config(local_config)
    if not config_valid:
        print_error("配置文件验证失败")
        return False

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

    # 运行基准测试
    success = run_benchmark(local_program, party_id, local_config, network_mode)

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
            dufs_server, num_parties, party_id, network_mode
        )
        if upload_success:
            print_success("所有操作完成")
        else:
            print_warning("基准测试完成，但部分文件上传失败")
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
