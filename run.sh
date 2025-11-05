#!/bin/bash

# 自动部署和运行EMP Share Benchmark脚本
# 功能：下载程序文件、配置文件，自动识别本机IP并确定party_id，然后运行基准测试

set -e  # 遇到错误立即退出

# 配置变量
LOCAL_PROGRAM="share_benchmark"                      # 本地程序文件名
LOCAL_CONFIG="config.txt"                                 # 本地配置文件名

# 网络配置脚本路径
NETWORK_SCRIPT="./network_config.sh"

# 检查网络配置脚本是否存在
check_network_script() {
    if [ ! -f "$NETWORK_SCRIPT" ]; then
        echo "❌ 网络配置脚本不存在: $NETWORK_SCRIPT"
        return 1
    fi
    
    if [ ! -x "$NETWORK_SCRIPT" ]; then
        chmod +x "$NETWORK_SCRIPT"
    fi
    
    return 0
}

# 非交互式网络配置
configure_network_auto() {
    local mode=$1
    local choice
    
    case "$mode" in
        "lan") choice="1" ;;
        "wan") choice="2" ;;
        *) echo "❌ 未知网络模式: $mode"; return 1 ;;
    esac
    
    echo "$choice" | sudo "$NETWORK_SCRIPT"
}

# 颜色输出函数
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖工具
check_dependencies() {
    local deps=("wget" "curl")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            print_error "缺少依赖工具: $dep"
            print_info "在Ubuntu/Debian上可以运行: sudo apt-get install $dep"
            print_info "在CentOS/RHEL上可以运行: sudo yum install $dep"
            exit 1
        fi
    done
}

# 获取本机IP地址
get_local_ip() {
    local ip
    # 尝试多种方法获取IP
    ip=$(hostname -I 2>/dev/null | awk '{print $1}' | head -1)
    
    if [ -z "$ip" ]; then
        ip=$(ip route get 1 2>/dev/null | awk '{print $7}' | head -1)
    fi
    
    if [ -z "$ip" ]; then
        ip=$(curl -s http://checkip.amazonaws.com 2>/dev/null)
    fi
    
    if [ -z "$ip" ]; then
        print_error "无法获取本机IP地址"
        exit 1
    fi
    
    echo "$ip"
}

# 下载文件
download_file() {
    local url="$1"
    local output="$2"
    
    print_info "下载文件: $url -> $output"
    
    if wget -O "$output" "$url" 2>/dev/null; then
        print_success "下载成功: $output"
    elif curl -o "$output" "$url" 2>/dev/null; then
        print_success "下载成功: $output"
    else
        print_error "下载失败: $url"
        return 1
    fi
}

# 验证配置文件格式
validate_config() {
    local config_file="$1"
    
    if [ ! -f "$config_file" ]; then
        print_error "配置文件不存在: $config_file"
        return 1
    fi
    
    # 检查文件是否为空
    if [ ! -s "$config_file" ]; then
        print_error "配置文件为空"
        return 1
    fi
    
    # 读取参与方数量
    local num_parties
    num_parties=$(head -1 "$config_file" 2>/dev/null)
    
    if ! [[ "$num_parties" =~ ^[0-9]+$ ]]; then
        print_error "配置文件格式错误: 第一行应该是数字（参与方数量）"
        return 1
    fi
    
    # 检查IP地址行数
    local ip_lines
    ip_lines=$(sed -n "2,$((num_parties+1))p" "$config_file" | grep -c .)
    
    if [ "$ip_lines" -ne "$num_parties" ]; then
        print_error "配置文件格式错误: IP地址数量与参与方数量不匹配"
        return 1
    fi
    
    # 检查数据大小行
    local data_sizes_line
    data_sizes_line=$((num_parties + 2))
    if ! sed -n "${data_sizes_line}p" "$config_file" | grep -qE "^[0-9]+ [0-9]+$"; then
        print_error "配置文件格式错误: 数据大小行格式不正确"
        return 1
    fi
    
    print_success "配置文件验证通过"
    return 0
}

# 确定本机的party_id
determine_party_id() {
    local config_file="$1"
    local local_ip="$2"
    
    local num_parties
    num_parties=$(head -1 "$config_file")
    
    print_info "在配置文件中查找本机IP: $local_ip"
    print_info "参与方数量: $num_parties"
    
    # 读取IP列表
    local party_id=-1
    local line_num=2
    
    for ((i=0; i<num_parties; i++)); do
        local config_ip
        config_ip=$(sed -n "${line_num}p" "$config_file")
        
        print_info "配置文件中第$i个IP: $config_ip"
        
        if [ "$config_ip" = "$local_ip" ]; then
            party_id=$i
            print_success "找到匹配的IP，party_id: $party_id"
            break
        fi
        
        ((line_num++))
    done
    
    if [ "$party_id" -eq -1 ]; then
        print_error "在配置文件中找不到本机IP: $local_ip"
        print_info "配置文件中的IP列表:"
        sed -n "2,$((num_parties+1))p" "$config_file"
        return 1
    fi
    
    echo "$party_id"
}

# 设置文件权限
set_permissions() {
    chmod +x "$LOCAL_PROGRAM"
    print_success "设置程序执行权限"
}

# 运行基准测试
run_benchmark() {
    local party_id="$1"
    local config_file="$2"
    local network_mode="$3"
    
    print_info "启动基准测试..."
    print_info "Party ID: $party_id"
    print_info "Network Mode: $network_mode"
    print_info "配置文件: $config_file"
    
    # 检查程序文件是否存在且可执行
    if [ ! -x "$LOCAL_PROGRAM" ]; then
        print_error "程序文件不存在或不可执行: $LOCAL_PROGRAM"
        return 1
    fi
    
    # 运行程序
    if ./"$LOCAL_PROGRAM" "$party_id" "$config_file" "$network_mode"; then
        print_success "基准测试完成"
    else
        print_error "基准测试运行失败"
        return 1
    fi
}

# 主函数
main() {
    print_info "开始自动部署EMP Share Benchmark"

    # 检查依赖
    print_info "检查系统依赖..."
    check_dependencies

    # 获取本机IP
    print_info "获取本机IP地址..."
    local local_ip
    local_ip=$(get_local_ip)
    print_info "本机IP: $local_ip"
    
    # 下载文件
    # print_info "下载程序文件和配置文件..."
    # download_file "$PROGRAM_URL" "$LOCAL_PROGRAM" || exit 1
    # download_file "$CONFIG_URL" "$LOCAL_CONFIG" || exit 1

    # 检查网络配置脚本
    if ! check_network_script; then
        exit 1
    fi

    # 设置网络模式
    NETWORK_MODE="lan"  # 或 "wan"
    
    echo "📡 配置网络为 $NETWORK_MODE 模式..."
    if ! configure_network_auto "$NETWORK_MODE"; then
        echo "❌ 网络配置失败"
        exit 1
    fi

    # 验证配置文件
    print_info "验证配置文件..."
    validate_config "$LOCAL_CONFIG" || exit 1
    
    # 确定party_id
    print_info "确定本机的party_id..."
    local party_id
    party_id=$(determine_party_id "$LOCAL_CONFIG" "$local_ip") || exit 1
    
    # 设置权限
    print_info "设置文件权限..."
    set_permissions
    
    # 运行基准测试
    run_benchmark "$party_id" "$LOCAL_CONFIG" "$NETWORK_MODE"

    sudo "$NETWORK_SCRIPT" 5

    if ! command -v aws &> /dev/null; then
        sudo apt install awscli
    fi

    upload_files
    
    print_success "自动部署和运行完成"
}

upload_files() {
    local file_pattern="benchmark_results_p*.csv"
    local success_count=0
    local fail_count=0
    
    # 查找匹配的文件
    local files=$(find . -maxdepth 1 -name "$file_pattern" -type f | sort)
    
    for file in $files; do
        [ -z "$file" ] && continue
        
        # 执行上传
        if aws s3 cp "$file" "s3://dont-delete-ssle/ssle/" --no-progress; then
            success_count=$((success_count + 1))
        else
            fail_count=$((fail_count + 1))
        fi
    done
    
    return $fail_count
}

main
