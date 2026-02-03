#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import argparse
import serial
import time
from pathlib import Path
from serial.tools import list_ports


class ResistanceTester:
    def __init__(self, port="COM1", baudrate=9600, verbose=False):
        """初始化电阻测试器"""
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.resistance_values = []
        self.verbose = verbose
        
    def log(self, message):
        """根据verbose设置打印日志"""
        if self.verbose:
            print(message)
        
    def connect_serial(self):
        """连接串口"""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.log(f"成功连接到串口 {self.port}")
            return True
        except Exception as e:
            # 错误信息始终打印
            print(f"连接串口失败: {e}")
            return False
    
    def disconnect_serial(self):
        """断开串口连接"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.log("串口连接已关闭")
    
    def send_command(self, command):
        """发送AT指令"""
        if not self.ser or not self.ser.is_open:
            print("串口未连接")
            return False
        
        try:
            self.ser.write(command.encode())
            time.sleep(0.5)  # 等待响应
            response = self.ser.read_all().decode(errors='ignore')
            self.log(f"发送: {command.strip()}, 响应: {response.strip()}")
            return True
        except Exception as e:
            print(f"发送指令失败: {e}")
            return False

    def connect_resistance(self):
        """将电阻设置为连接状态"""
        self.log("正在将电阻设置为连接状态...")
        result = self.send_command("AT+RES.CONNECT\r\n")
        if result:
            self.log("电阻已成功设置为连接状态")
        return result

    def disconnect_resistance(self):
        """将电阻设置为开路状态"""
        self.log("正在将电阻设置为开路状态...")
        result = self.send_command("AT+RES.DISCONNECT\r\n")
        if result:
            self.log("电阻已成功设置为开路状态")
        return result

    def set_resistance_value(self, value):
        """设置电阻值"""
        try:
             # 验证输入值
            if str(value).upper() == "OPEN":
                return self.disconnect_resistance()
            
            # 转换为浮点数验证
            res_value = float(value)
            
            # 检查合理范围
            if res_value < 0:
                print(f"电阻值不能为负数")
                return False
            
            if res_value > 1000000:  # 1MΩ 上限
                print(f"电阻值过大（最大支持1MΩ）")
                return False
            
            # 先连接电阻
            if not self.connect_resistance():
                return False
            
            # 设置电阻值
            success = self.send_command(f"AT+RES.SP={res_value}\r\n")
            if success:
                self.log(f"已设置电阻值: {res_value}Ω")
                return True
            else:
                print(f"设置电阻值失败")
                return False
        except ValueError:
            print(f"无效的电阻值: {value}")
            return False
        except Exception as e:
            print(f"设置电阻值时出错: {e}")
            return False

    def load_resistance_values(self, resistance_file):
        """从文件加载电阻值和注释"""
        try:
            file_path = Path(resistance_file)
            if not file_path.exists():
                print(f"文件不存在: {resistance_file}")
                return False

            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            self.resistance_values = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 分离注释
                if ';' in line:
                    parts = line.split(';')
                    value = parts[0].strip()
                    comment = parts[1].strip()
                else:
                    value = line
                    comment = ""
                
                self.resistance_values.append((value, comment))
                
            self.log(f"成功加载 {len(self.resistance_values)} 组电阻值")
            return True
        except Exception as e:
            print(f"加载电阻值文件失败: {e}")
            return False

    def find_resistance_by_temperature(self, temperature):
        """根据温度值查找对应的电阻值"""
        # 移除温度单位，只保留数字部分
        temp_str = str(temperature).replace('C', '').replace('°', '').strip()
        try:
            target_temp = float(temp_str)
        except ValueError:
            print(f"无效的温度值: {temperature}")
            return None, None
        
        # 遍历所有电阻值，查找匹配的温度
        for resistance, comment in self.resistance_values:
            if comment:
                # 解析注释中的温度值
                comment_temp = comment.replace('C', '').replace('°', '').strip()
                try:
                    temp_value = float(comment_temp)
                    if abs(temp_value - target_temp) < 0.1:  # 允许0.1度的误差
                        return resistance, comment
                except ValueError:
                    continue
        
        return None, None

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
    parser = argparse.ArgumentParser(description='根据温度设置电阻值 CLI 工具')
    parser.add_argument('-t', '--temp', type=str, required=True, help='目标温度 (例如: 25, -40)')
    parser.add_argument('-f', '--file', type=str, required=True, help='电阻值对应文件路径 (例如: ntc_res.txt)')
    parser.add_argument('-p', '--port', type=str, help='串口号 (例如: COM1)')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细执行过程')
    
    args = parser.parse_args()

    # 确定串口
    port = args.port
    if not port:
        print("错误: 未指定串口。请使用 -p 或 --port 指定串口。")
        list_available_com_ports()
        sys.exit(1)
    
    # 初始化测试器
    tester = ResistanceTester(port=port, verbose=args.verbose)
    
    # 加载电阻文件
    if not tester.load_resistance_values(args.file):
        sys.exit(1)
        
    # 查找温度对应的电阻
    resistance, comment = tester.find_resistance_by_temperature(args.temp)
    if not resistance:
        print(f"未找到温度 {args.temp} 对应的电阻值")
        sys.exit(1)
        
    if args.verbose:
        print(f"找到温度 {args.temp} 对应的电阻值: {resistance} ({comment})")
    
    # 连接串口并设置电阻
    if not tester.connect_serial():
        sys.exit(1)

    try:
        if tester.set_resistance_value(resistance):
            # 成功设置后，打印总结信息
            if not args.verbose:
                # 简化输出
                print(f"已设置电阻值: {resistance}Ω ({comment})")
            else:
                # 详细模式下已经在set_resistance_value中打印了，这里可以再补充或不补充
                pass
    finally:
        tester.disconnect_serial()

if __name__ == "__main__":
    main()