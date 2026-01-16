#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import argparse
import serial
import time
import logging
from pathlib import Path
from serial.tools import list_ports

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class ResistanceTester:
    def __init__(self, port="COM1", baudrate=9600):
        """初始化电阻测试器"""
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.is_connected = False  # 跟踪电阻连接状态
        
    def connect_serial(self):
        """连接串口"""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            logging.info(f"成功连接到串口 {self.port}")
            return True
        except Exception as e:
            logging.error(f"连接串口失败: {e}")
            return False
    
    def disconnect_serial(self):
        """断开串口连接"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            logging.info("串口连接已关闭")
    
    def send_command(self, command):
        """发送AT指令"""
        if not self.ser or not self.ser.is_open:
            logging.error("串口未连接")
            return False
        
        try:
            self.ser.write(command.encode())
            time.sleep(0.5)  # 等待响应
            response = self.ser.read_all().decode(errors='ignore')
            logging.info(f"发送: {command.strip()}, 响应: {response.strip()}")
            return True
        except Exception as e:
            logging.error(f"发送指令失败: {e}")
            return False

    def disconnect_resistance(self):
        """将电阻设置为开路状态"""
        logging.info("正在将电阻设置为开路状态...")
        result = self.send_command("AT+RES.DISCONNECT\r\n")
        if result:
            logging.info("电阻已成功设置为开路状态")
            self.is_connected = False
        return result
        
    def connect_resistance(self):
        """将电阻设置为连接状态"""
        logging.info("正在将电阻设置为连接状态...")
        result = self.send_command("AT+RES.CONNECT\r\n")
        if result:
            logging.info("电阻已成功设置为连接状态")
            self.is_connected = True
        return result
        
    def short_resistance(self):
        """将电阻设置为短路状态"""
        logging.info("正在将电阻设置为短路状态...")
        result = self.send_command("AT+RES.SHORT\r\n")
        if result:
            logging.info("电阻已成功设置为短路状态")
            self.is_connected = True
        return result
    
    def unshort_resistance(self):
        """取消电阻短路状态"""
        logging.info("正在取消电阻短路状态...")
        result = self.send_command("AT+RES.UNSHORTEN\r\n")
        if result:
            logging.info("电阻短路状态已取消")
            self.is_connected = True
        return result

    def set_custom_resistance(self, resistance_value):
        """设置自定义电阻值"""
        try:
            # 验证输入值
            if resistance_value.upper() == "OPEN":
                return self.disconnect_resistance()
            
            # 转换为浮点数验证
            value = float(resistance_value)
            
            # 检查合理范围
            if value < 0:
                print(f"电阻值不能为负数")
                return False
            
            if value > 1000000:  # 1MΩ 上限
                print(f"电阻值过大（最大支持1MΩ）")
                return False
            
            # 先连接电阻
            if not self.connect_resistance():
                return False
            
            # 设置电阻值
            success = self.send_command(f"AT+RES.SP={value}\r\n")
            if success:
                print(f"已设置自定义电阻值: {value}Ω")
                return True
            else:
                print(f"设置电阻值失败")
                return False
                
        except ValueError:
            print(f"无效的电阻值，请输入数字或 OPEN")
            return False
        except Exception as e:
            print(f"设置电阻值时出错: {e}")
            return False

def list_available_com_ports():
    """列出所有可用的COM端口"""
    ports = list_ports.comports()
    available_ports = []
    
    print("\n===== 可用的COM端口 =====")
    if not ports:
        print("未检测到任何COM端口")
        return available_ports
    
    for i, port in enumerate(ports):
        print(f"{i+1}. {port.device} - {port.description}")
        available_ports.append(port.device)
    
    return available_ports

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
    
    # 初始化测试器
    tester = ResistanceTester(port=port)
    
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