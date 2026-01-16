# 程控电阻控制工具 (Programmable Resistor Control Tools)

本工具集用于控制程控电阻设备(`RM550`)，主要应用场景为车载测试，支持模拟 BIN 档位电阻以及 NTC 温度电阻特性。本项目使用 `uv` 进行环境和依赖管理。

项目包含两个主要脚本：
1. **`resistance_test.py`**: 交互式测试工具，适合手动调试、循环测试和自动递增测试。
2. **`resistance_cli.py`**: 命令行(CLI)工具，适合集成到自动化脚本中，支持单次指令执行。

## 环境准备

本项目使用 [uv](https://github.com/astral-sh/uv) 管理 Python 环境。

1. 确保已安装 `uv`。
2. 安装项目依赖：
   ```bash
   uv sync
   # 或者手动添加依赖
   uv add pyserial
   ```

## 1. 交互式测试工具 (`resistance_test.py`)

用于手动调试和长时间的压力测试。

### 启动方式
```bash
# 使用默认电阻文件 (resistance_values.txt)
uv run resistance_test.py -p COMx

# 指定电阻文件 (例如 NTC 温度表)
uv run resistance_test.py -p COMx -f ntc_res.txt
```

### 主要功能与指令
启动后进入交互界面，支持以下指令：
- **导航**: 
  - `n`: 下一个电阻值 (Next)
  - `p`: 上一个电阻值 (Previous)
  - `j<行号>`: 跳转到指定行 (例如 `j5`)
  - `f`: 重置到第一组 (First)
- **温度模拟** (配合 ntc_res.txt):
  - `t<温度>`: 跳转到指定温度对应的电阻值 (例如 `t25`, `t-10`)
- **控制**:
  - `o`: 切换继电器连接/断开 (Open/Close)
  - `s`: 切换短路状态 (Short)
  - `c<值>`: 设置自定义电阻值 (例如 `c1000`, `cOPEN`)
- **自动化**:
  - `a`: 开启/停止自动递增遍历
  - `a<间隔>`: 指定间隔自动递增 (例如 `a0.5` 为 0.5秒)
  - `z` / `x`: 暂停/继续自动递增

## 2. 命令行工具 (`resistance_cli.py`)

专为自动化集成设计。执行单一指令后会**断开串口连接**，但**保持电阻器的物理状态**（闭合/断开/设定值），不会像交互脚本那样在退出时自动复位。

### 使用方法

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
- `-p`, `--port`: 串口号 (如 COM1, COM3)。如果不指定，脚本会尝试自动探测第一个可用端口。
- `-v`, `--value`: 设置电阻值，支持数字或 "OPEN"。
- `--action`: 执行特定动作，可选值: `connect`, `disconnect`, `short`, `unshort`。

## 配置文件说明

- **`ntc_res.txt`**: NTC 热敏电阻温度对照表 (格式: `电阻值 ;温度注释`)。
- **`hb_lb_res.txt`, `lh_res.txt`, `signal_res.txt`**: 用于不同测试场景的 BIN 档位或信号电阻定义文件。