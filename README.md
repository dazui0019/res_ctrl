# 程控电阻控制工具 (Programmable Resistor Control Tools)

本工具集用于控制程控电阻设备(`RM550`)，主要应用场景为车载测试，支持模拟 BIN 档位电阻以及 NTC 温度电阻特性。本项目使用 `uv` 进行环境和依赖管理。

项目包含三个主要脚本：
1. **`resistance_cli.py`**: 通用电阻控制 CLI 工具，支持直接设置阻值、控制继电器通断及短路状态。
2. **`temp_resistance_cli.py`**: 基于温度的电阻设置 CLI 工具，通过查表将温度转换为对应的电阻值并设置。
3. **`resistance_gui.py`**: 图形界面工具 (GUI)，提供可视化的电阻控制界面，支持设置阻值、控制继电器状态。

## 环境准备

本项目使用 [uv](https://github.com/astral-sh/uv) 管理 Python 环境。

1. 确保已安装 `uv`。
2. 安装项目依赖：
   ```bash
   uv sync
   # 或者手动添加依赖
   uv add pyserial dearpygui
   ```

## 1. 通用电阻控制 (`resistance_cli.py`)

专为自动化集成设计，支持直接控制电阻值和继电器状态。执行单一指令后会**断开串口连接**，但**保持电阻器的物理状态**（闭合/断开/设定值）。

### 使用方法

**注意：必须使用 `-p` 参数指定串口号。**

#### 设置电阻值
```bash
# 设置电阻为 1000 欧姆
uv run resistance_cli.py -p COM3 -v 1000

# 设置电阻为开路 (OPEN)
uv run resistance_cli.py -p COM3 -v OPEN
```

#### 控制状态
```bash
# 闭合继电器 (Connect)
uv run resistance_cli.py -p COM3 --action connect

# 断开继电器 (Disconnect)
uv run resistance_cli.py -p COM3 --action disconnect

# 短路输出 (Short)
uv run resistance_cli.py -p COM3 --action short

# 取消短路 (Unshort)
uv run resistance_cli.py -p COM3 --action unshort
```

#### 参数说明
- `-p`, `--port`: **(必填)** 串口号。
  - Windows: `COMx` (如 `COM3`)
  - Linux: `/dev/ttyUSBx` (如 `/dev/ttyUSB0`)

- `-b`, `--baudrate`: 串口波特率，默认为 9600。
- `-v`, `--value`: 设置电阻值，支持数字或 "OPEN"（最大支持 7MΩ）。
- `--action`: 执行特定动作，可选值: `connect`, `disconnect`, `short`, `unshort`。
- `--verbose`: 显示详细的执行过程和日志信息（默认只输出结果）。

## 2. 基于温度的电阻设置 (`temp_resistance_cli.py`)

通过读取电阻-温度对照表文件，根据输入的目标温度自动查找并设置对应的电阻值。

### 使用方法

```bash
# 设置 -40度 对应的电阻，使用 ntc_res.txt 文件
uv run temp_resistance_cli.py -p COM3 -t -40 -f ntc_res.txt

# 设置 25度 对应的电阻
uv run temp_resistance_cli.py -p COM3 -t 25 -f ntc_res.txt
```

### 参数说明
- `-p`, `--port`: **(必填)** 串口号。
  - Windows: `COMx` (如 `COM3`)
  - Linux: `/dev/ttyUSBx` (如 `/dev/ttyUSB0`)

- `-b`, `--baudrate`: 串口波特率，默认为 9600。
- `-t`, `--temp`: **(必填)** 目标温度 (例如: 25, -40, 25C)。
- `-f`, `--file`: **(必填)** 电阻值对应文件路径 (例如: ntc_res.txt)。
- `--verbose`: 显示详细的执行过程和日志信息（默认只输出结果）。

## 3. 图形界面工具 (`resistance_gui.py`)

提供可视化的图形界面，用于控制程控电阻设备。

### 使用方法

```bash
# 启动 GUI
uv run resistance_gui.py
```

### 配置文件

GUI 使用 `resistance_gui_config.json` 配置文件，可配置以下参数：
- `port`: 默认串口号 (如 `COM3`)
- `baudrate`: 串口波特率，默认为 9600
- `default_resistance`: 默认电阻值 (欧姆)
- `max_resistance`: 最大电阻值 (欧姆)

### 界面功能

- 设置电阻值 (通过滑块或输入框)
- 控制继电器状态 (连接/断开)
- 短路/取消短路
- 实时显示当前设置状态

## 配置文件说明

- **`ntc_res.txt`**: NTC 热敏电阻温度对照表 (格式: `电阻值 ;温度注释`)。
- **`hb_lb_res.txt`, `lh_res.txt`, `signal_res.txt`**: 用于不同测试场景的 BIN 档位或信号电阻定义文件。