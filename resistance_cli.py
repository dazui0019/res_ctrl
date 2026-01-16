#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import argparse
from pathlib import Path

# 添加当前目录到 sys.path 以确保能导入 resistance_test
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

try:
    from resistance_test import ResistanceTester, list_available_com_ports
except ImportError:
    print("错误: 无法导入 resistance_test.py。请确保该文件在同一目录下。")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='电阻控制 CLI 工具')
    parser.add_argument('-p', '--port', type=str, help='串口号 (例如: COM1)')
    parser.add_argument('-v', '--value', type=str, help='设置电阻值 (例如: 100, OPEN)')
    parser.add_argument('--action', type=str, choices=['connect', 'disconnect', 'short', 'unshort'], help='控制电阻状态')
    
    args = parser.parse_args()

    # 如果没有提供任何操作参数，显示帮助
    if not args.value and not args.action:
        parser.print_help()
        sys.exit(0)

    # 确定串口
    port = args.port
    if not port:
        available_ports = list_available_com_ports()
        if available_ports:
            port = available_ports[0]
            print(f"未指定串口，自动选择第一个可用端口: {port}")
        else:
            print("错误: 未找到可用串口且未指定串口。")
            sys.exit(1)
    
    # 初始化测试器 (传入 dummy 文件名，因为 CLI 模式不需要加载文件)
    tester = ResistanceTester("dummy.txt", port=port)
    
    print(f"正在连接串口 {port}...")
    if not tester.connect_serial():
        print(f"连接串口 {port} 失败")
        sys.exit(1)

    try:
        # 处理设置电阻值
        if args.value:
            print(f"正在设置电阻值: {args.value}")
            tester.set_custom_resistance(args.value)

        # 处理状态控制动作
        if args.action:
            print(f"正在执行动作: {args.action}")
            if args.action == 'connect':
                tester.connect_resistance()
            elif args.action == 'disconnect':
                tester.disconnect_resistance()
            elif args.action == 'short':
                tester.short_resistance()
            elif args.action == 'unshort':
                tester.unshort_resistance()
                
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        # 仅断开串口连接，保持电阻状态
        tester.disconnect_serial()
        print("操作完成，串口已断开 (电阻状态保持)")

if __name__ == "__main__":
    main()