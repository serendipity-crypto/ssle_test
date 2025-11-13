# EMP Share Benchmark Python 脚本使用说明

## 概述

本项目将原始的Shell脚本 `run.sh` 转换为Python版本，提供了更好的跨平台兼容性和错误处理能力。

## 文件说明

1. `run.py` - 完整功能版本，与原始Shell脚本功能对应
2. `run_practical.py` - 实用版本，更适合实际使用场景
3. `run.sh` - 原始Shell脚本（参考）

## 环境要求

- Python 3.6 或更高版本
- requests 库 (`pip install requests`)

## 使用方法

### 1. 设置环境变量

```bash
# 必需环境变量
export CONFIG_URL=http://your-server.com/config.txt

# 可选环境变量
export PROGRAM_URL=http://your-server.com/share_benchmark
export LOCAL_PROGRAM=/path/to/share_benchmark
export LOCAL_CONFIG=/path/to/config.txt
export NETWORK_MODE=lan  # 或 wan
```

### 2. 运行脚本

```bash
# 运行实用版本（推荐）
python3 run_practical.py

# 或运行完整版本
python3 run.py
```

## 功能特性

### 自动化流程
1. **环境检查** - 自动检查所需环境变量和依赖
2. **IP识别** - 自动获取本机IP地址
3. **文件下载** - 自动下载程序和配置文件
4. **配置验证** - 验证配置文件格式
5. **ID匹配** - 自动匹配本机IP与配置中的party_id
6. **权限设置** - 自动设置程序执行权限
7. **基准测试** - 运行基准测试程序
8. **结果处理** - 处理测试结果（待实现）

### 错误处理
- 彩色输出便于识别不同类型的信息
- 详细的错误信息和解决建议
- 优雅的异常处理和程序退出

## 配置文件格式

配置文件应遵循以下格式：

```
<number_of_parties>
<party_0_ip>
<party_1_ip>
...
<party_n_ip>
<data_size_1> <data_size_2>
```

示例：
```
3
192.168.1.10
192.168.1.11
192.168.1.12
1000 2000
```

## 常见问题

### 1. 如何安装依赖？

```bash
pip install requests
```

### 2. 如何设置环境变量？

临时设置（当前会话有效）：
```bash
export CONFIG_URL=http://example.com/config.txt
```

永久设置（添加到 ~/.bashrc 或 ~/.zshrc）：
```bash
echo 'export CONFIG_URL=http://example.com/config.txt' >> ~/.bashrc
source ~/.bashrc
```

### 3. 脚本执行失败怎么办？

1. 检查环境变量是否正确设置
2. 检查网络连接是否正常
3. 检查配置文件格式是否正确
4. 查看错误信息中的具体提示

## 开发说明

### 代码结构

- `main()` - 主函数，控制整体流程
- `check_dependencies()` - 检查依赖
- `get_local_ip()` - 获取本机IP
- `download_file()` - 下载文件
- `validate_config()` - 验证配置文件
- `find_party_id()` - 查找party_id
- `run_benchmark()` - 运行基准测试

### 自定义修改

可以根据实际需求修改以下配置变量：
- `LOCAL_PROGRAM` - 程序文件路径
- `LOCAL_CONFIG` - 配置文件路径
- `NETWORK_MODE` - 网络模式（lan/wan）
