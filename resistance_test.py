#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import signal
import sys
import serial
import logging
import argparse
import threading
from pathlib import Path
from serial.tools import list_ports
import msvcrt  # Windows only

# 终端颜色代码
class TermColors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("resistance_test.log"),
        logging.StreamHandler()
    ]
)

class ResistanceTester:
    def __init__(self, resistance_file, port="COM1", baudrate=9600):
        """初始化电阻测试器"""
        self.resistance_file = resistance_file
        self.port = port
        self.baudrate = baudrate
        self.resistance_values = []
        self.current_index = 0
        self.current_sub_index = 0  # 添加子索引，用于跟踪逗号分隔的值
        self.ser = None
        self.test_started = False  # 添加测试是否已开始的标志
        self.is_connected = False  # 添加电阻连接状态跟踪变量
        self.auto_increment_active = False  # 自动递增活动状态
        self.auto_increment_thread = None  # 自动递增线程
        self.auto_increment_interval = 1.0  # 默认时间间隔（秒）
        self.auto_increment_start_index = 0  # 自动递增起始索引
        self.auto_increment_end_index = -1  # 自动递增结束索引（-1表示到最后）
        self.auto_increment_paused = False  # 自动递增暂停状态
        self.auto_increment_pause_event = threading.Event()  # 暂停控制事件
        
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
        
    def toggle_resistance_connection(self):
        """切换电阻连接状态"""
        if self.is_connected:
            return self.disconnect_resistance()
        else:
            return self.connect_resistance()
    
    def short_resistance(self):
        """将电阻设置为短路状态"""
        logging.info("正在将电阻设置为短路状态...")
        result = self.send_command("AT+RES.SHORT\r\n")
        if result:
            logging.info("电阻已成功设置为短路状态")
            self.is_connected = True  # 短路状态也算作连接状态
        return result
    
    def unshort_resistance(self):
        """取消电阻短路状态"""
        logging.info("正在取消电阻短路状态...")
        result = self.send_command("AT+RES.UNSHORTEN\r\n")
        if result:
            logging.info("电阻短路状态已取消")
            self.is_connected = True
        return result
    
    def toggle_resistance_short(self):
        """切换电阻短路状态"""
        # 这里需要一个状态变量来跟踪当前是否短路
        if not hasattr(self, 'is_short_circuited'):
            self.is_short_circuited = False
            
        if self.is_short_circuited:
            success = self.unshort_resistance()
            if success:
                self.is_short_circuited = False
            return success
        else:
            success = self.short_resistance()
            if success:
                self.is_short_circuited = True
            return success
        
    def load_resistance_values(self):
        """从文件加载电阻值和注释"""
        try:
            with open(self.resistance_file, 'r') as f:
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
                
            logging.info(f"成功加载 {len(self.resistance_values)} 组电阻值")
            return True
        except Exception as e:
            logging.error(f"加载电阻值文件失败: {e}")
            return False
    
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
    
    def set_resistance(self, value):
        """设置电阻值"""
        if isinstance(value, tuple):
            value, _ = value
        
        if value.upper() == "OPEN":
            return self.disconnect_resistance()
        else:
            # 先连接电阻
            if not self.connect_resistance():
                return False
            
            # 如果是逗号分隔的多个值，使用当前子索引选择值
            if ',' in value:
                values = [float(v) for v in value.split(',')]
                if self.current_sub_index < len(values):
                    value = values[self.current_sub_index]
                else:
                    value = values[0]  # 默认使用第一个值
            
            # 设置电阻值
            return self.send_command(f"AT+RES.SP={value}\r\n")
    
    def set_custom_resistance(self, resistance_value):
        """设置自定义电阻值"""
        try:
            # 验证输入值
            if resistance_value.upper() == "OPEN":
                return self.disconnect_resistance()
            
            # 转换为浮点数验证
            value = float(resistance_value)
            
            # 检查合理范围（可根据实际需求调整）
            if value < 0:
                print(f"\n{TermColors.RED}电阻值不能为负数{TermColors.RESET}")
                return False
            
            if value > 1000000:  # 1MΩ 上限
                print(f"\n{TermColors.RED}电阻值过大（最大支持1MΩ）{TermColors.RESET}")
                return False
            
            # 先连接电阻
            if not self.connect_resistance():
                return False
            
            # 设置电阻值
            success = self.send_command(f"AT+RES.SP={value}\r\n")
            if success:
                print(f"\n{TermColors.GREEN}已设置自定义电阻值: {value}Ω{TermColors.RESET}")
                return True
            else:
                print(f"\n{TermColors.RED}设置电阻值失败{TermColors.RESET}")
                return False
                
        except ValueError:
            print(f"\n{TermColors.RED}无效的电阻值，请输入数字或 OPEN{TermColors.RESET}")
            return False
        except Exception as e:
            print(f"\n{TermColors.RED}设置电阻值时出错: {e}{TermColors.RESET}")
            return False
    
    def get_current_resistance(self):
        """获取当前电阻值和注释"""
        if self.current_index < len(self.resistance_values):
            return self.resistance_values[self.current_index]
        return None, None
    
    def get_current_resistance_value(self):
        """获取当前实际设置的电阻值（考虑子索引）"""
        resistance, _ = self.get_current_resistance()
        if not resistance or resistance.upper() == "OPEN":
            return resistance
            
        if ',' in resistance:
            values = resistance.split(',')
            if self.current_sub_index < len(values):
                return values[self.current_sub_index]
            return values[0]
        return resistance
    
    def next_resistance(self):
        """切换到下一个电阻值"""
        current, _ = self.get_current_resistance()
        
        # 如果当前是逗号分隔的值，先尝试增加子索引
        if current and ',' in current:
            values = current.split(',')
            if self.current_sub_index < len(values) - 1:
                self.current_sub_index += 1
                return True
        
        # 如果不是逗号分隔的值或已经是最后一个子值，则移动到下一个主索引
        self.current_sub_index = 0  # 重置子索引
        if self.current_index < len(self.resistance_values) - 1:
            self.current_index += 1
            return True
        else:
            logging.info("已经是最后一个电阻值")
            return False
    
    def previous_resistance(self):
        """切换到上一个电阻值"""
        current, _ = self.get_current_resistance()
        
        # 如果当前是逗号分隔的值，先尝试减少子索引
        if current and ',' in current and self.current_sub_index > 0:
            self.current_sub_index -= 1
            return True
        
        # 如果不是逗号分隔的值或已经是第一个子值，则移动到上一个主索引
        if self.current_index > 0:
            self.current_index -= 1
            # 如果上一个是逗号分隔的值，将子索引设置为最后一个
            prev, _ = self.get_current_resistance()
            if prev and ',' in prev:
                values = prev.split(',')
                self.current_sub_index = len(values) - 1
            else:
                self.current_sub_index = 0
            return True
        else:
            logging.info("已经是第一个电阻值")
            return False
    
    def reset_to_first_group(self):
        """重置到第一组电阻值"""
        self.current_index = 0
        self.current_sub_index = 0
        return True
    
    def start_auto_increment(self, interval=None, start_line=None, end_line=None):
        """开始自动递增电阻值"""
        if self.auto_increment_active:
            print("\n自动递增已在运行中")
            return False
        
        # 处理时间间隔参数
        if interval:
            try:
                self.auto_increment_interval = float(interval)
                if self.auto_increment_interval < 0.1:
                    print("\n时间间隔不能小于0.1秒")
                    return False
            except ValueError:
                print("\n无效的时间间隔")
                return False
        
        # 处理范围参数
        if start_line is not None:
            try:
                start_line = int(start_line)
                if start_line < 1 or start_line > len(self.resistance_values):
                    print(f"\n起始行号必须在 1-{len(self.resistance_values)} 范围内")
                    return False
                self.auto_increment_start_index = start_line - 1
            except ValueError:
                print("\n无效的起始行号")
                return False
        else:
            self.auto_increment_start_index = 0  # 默认从第一个开始
        
        if end_line is not None:
            try:
                end_line = int(end_line)
                if end_line < 1 or end_line > len(self.resistance_values):
                    print(f"\n结束行号必须在 1-{len(self.resistance_values)} 范围内")
                    return False
                if end_line < start_line if start_line else 1:
                    print("\n结束行号不能小于起始行号")
                    return False
                self.auto_increment_end_index = end_line - 1
            except ValueError:
                print("\n无效的结束行号")
                return False
        else:
            self.auto_increment_end_index = -1  # 默认到最后一个
        
        # 设置当前位置到起始位置
        self.current_index = self.auto_increment_start_index
        self.current_sub_index = 0
        
        self.auto_increment_active = True
        self.auto_increment_thread = threading.Thread(target=self._auto_increment_loop)
        self.auto_increment_thread.daemon = True
        self.auto_increment_thread.start()
        
        range_info = ""
        if start_line or end_line:
            start_display = start_line if start_line else 1
            end_display = end_line if end_line else len(self.resistance_values)
            range_info = f"，范围: 第{start_display}行到第{end_display}行"
        
        print(f"\n开始自动递增，时间间隔: {self.auto_increment_interval}秒{range_info}")
        return True
    
    def stop_auto_increment(self):
        """停止自动递增电阻值"""
        if not self.auto_increment_active:
            print("\n自动递增未运行")
            return False
        
        self.auto_increment_active = False
        self.auto_increment_paused = False
        self.auto_increment_pause_event.set()  # 确保线程可以继续执行
        if self.auto_increment_thread:
            self.auto_increment_thread.join(timeout=2.0)  # 等待最多2秒
        print("\n停止自动递增")
        return True
    
    def pause_auto_increment(self):
        """暂停自动递增"""
        if not self.auto_increment_active:
            print("\n自动递增未运行")
            return False
        
        if self.auto_increment_paused:
            print("\n自动递增已在暂停状态")
            return False
        
        self.auto_increment_paused = True
        self.auto_increment_pause_event.clear()  # 清除事件，使线程等待
        print("\n自动递增已暂停")
        return True
    
    def resume_auto_increment(self):
        """继续自动递增"""
        if not self.auto_increment_active:
            print("\n自动递增未运行")
            return False
        
        if not self.auto_increment_paused:
            print("\n自动递增未在暂停状态")
            return False
        
        self.auto_increment_paused = False
        self.auto_increment_pause_event.set()  # 设置事件，使线程继续执行
        print("\n自动递增已继续")
        return True
    
    def _auto_increment_loop(self):
        """自动递增循环"""
        while self.auto_increment_active:
            # 检查暂停状态
            if self.auto_increment_paused:
                print(f"\n{TermColors.BRIGHT_YELLOW}自动递增已暂停，输入 'x' 继续...{TermColors.RESET}")
                self.auto_increment_pause_event.wait()  # 等待继续信号
                if not self.auto_increment_active:  # 检查是否在暂停时停止了
                    break
                print(f"\n{TermColors.BRIGHT_GREEN}自动递增继续...{TermColors.RESET}")
            
            # 检查是否超出指定范围
            end_index = self.auto_increment_end_index if self.auto_increment_end_index != -1 else len(self.resistance_values) - 1
            if self.current_index > end_index:
                print(f"\n已到达指定范围末尾（第{end_index + 1}行），停止自动递增")
                self.auto_increment_active = False
                break
            
            # 获取当前电阻值并显示
            current, comment = self.get_current_resistance()
            if current:
                current_value = self.get_current_resistance_value()
                comment_display = f"{TermColors.BRIGHT_BLACK}[{comment}]{TermColors.RESET}" if comment else ""
                
                # 计算范围内的进度
                start_display = self.auto_increment_start_index + 1
                end_display = end_index + 1
                range_progress = f"[{self.current_index + 1 - self.auto_increment_start_index}/{end_display - start_display + 1}]"
                
                if ',' in current:
                    values = current.split(',')
                    print(f"\n自动递增 - 当前电阻值 ({self.current_index + 1}/{len(self.resistance_values)}) {range_progress}: {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} (组: {current}) {comment_display}")
                else:
                    print(f"\n自动递增 - 当前电阻值 ({self.current_index + 1}/{len(self.resistance_values)}) {range_progress}: {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} {comment_display}")
                
                self.set_resistance(current)
            
            # 尝试下一个电阻值
            if not self.next_resistance():
                print("\n已到达最后一个电阻值，停止自动递增")
                self.auto_increment_active = False
                break
            
            # 检查是否即将超出范围
            end_index = self.auto_increment_end_index if self.auto_increment_end_index != -1 else len(self.resistance_values) - 1
            if self.current_index > end_index:
                print(f"\n已到达指定范围末尾（第{end_index + 1}行），停止自动递增")
                self.auto_increment_active = False
                break
            
            # 等待指定的时间间隔
            time.sleep(self.auto_increment_interval)
    
    def find_resistance_by_temperature(self, temperature):
        """根据温度值查找对应的电阻值"""
        # 移除温度单位，只保留数字部分
        temp_str = str(temperature).replace('C', '').replace('°', '').strip()
        try:
            target_temp = float(temp_str)
        except ValueError:
            return None, None, None
        
        # 遍历所有电阻值，查找匹配的温度
        for i, (resistance, comment) in enumerate(self.resistance_values):
            if comment:
                # 解析注释中的温度值
                comment_temp = comment.replace('C', '').replace('°', '').strip()
                try:
                    temp_value = float(comment_temp)
                    if abs(temp_value - target_temp) < 0.1:  # 允许0.1度的误差
                        return i, resistance, comment
                except ValueError:
                    continue
        
        return None, None, None
    
    def get_user_input(self, prompt):
        """获取用户输入，保持输入区域整洁"""
        try:
            # 清空输入行并显示提示
            sys.stdout.write('\r' + ' ' * 80 + '\r')  # 清空当前行
            sys.stdout.write(prompt)
            sys.stdout.flush()
            
            # 获取用户输入
            user_input = input().strip().lower()
            
            return user_input
        except (KeyboardInterrupt, EOFError):
            return 'q'  # 中断时返回退出命令
    
    def show_help(self):
        """显示所有指令的使用方法"""
        help_text = f"""
{TermColors.BRIGHT_CYAN}{TermColors.BOLD}========== 电阻测试程序 - 指令帮助 =========={TermColors.RESET}

{TermColors.BRIGHT_YELLOW}基本控制指令：{TermColors.RESET}
  {TermColors.BRIGHT_GREEN}s{TermColors.RESET} - 开始测试
  {TermColors.BRIGHT_GREEN}q{TermColors.RESET} - 退出程序

{TermColors.BRIGHT_YELLOW}电阻值导航指令：{TermColors.RESET}
  {TermColors.BRIGHT_GREEN}n{TermColors.RESET} - 下一个电阻值
  {TermColors.BRIGHT_GREEN}p{TermColors.RESET} - 上一个电阻值
  {TermColors.BRIGHT_GREEN}f{TermColors.RESET} - 重置到第一组电阻值
  {TermColors.BRIGHT_GREEN}j<行号>{TermColors.RESET} - 跳转到指定行号，如：j5
  {TermColors.BRIGHT_GREEN}t<温度>{TermColors.RESET} - 根据温度跳转到对应电阻值，如：t25 或 t-10

{TermColors.BRIGHT_YELLOW}电阻设置指令：{TermColors.RESET}
  {TermColors.BRIGHT_GREEN}r{TermColors.RESET} - 重新设置当前电阻值
  {TermColors.BRIGHT_GREEN}o{TermColors.RESET} - 切换电阻连接状态（连接/断开）
  {TermColors.BRIGHT_GREEN}s{TermColors.RESET} - 切换电阻短路状态（短路/正常）
  {TermColors.BRIGHT_GREEN}c{TermColors.RESET} - 设置自定义电阻值（支持数字或 OPEN）

{TermColors.BRIGHT_YELLOW}自动递增指令：{TermColors.RESET}
  {TermColors.BRIGHT_GREEN}a{TermColors.RESET} - 开始/停止自动递增（默认间隔1秒）
  {TermColors.BRIGHT_GREEN}a<间隔>{TermColors.RESET} - 设置时间间隔并开始递增，如：a0.5
  {TermColors.BRIGHT_GREEN}a<起始>-<结束>{TermColors.RESET} - 指定递增范围，如：a5-20
  {TermColors.BRIGHT_GREEN}a<间隔>:<起始>-<结束>{TermColors.RESET} - 同时设置间隔和范围，如：a0.2:10-30
  {TermColors.BRIGHT_GREEN}z{TermColors.RESET} - 暂停自动递增（仅在自动递增运行时有效）
  {TermColors.BRIGHT_GREEN}x{TermColors.RESET} - 继续自动递增（仅在暂停时有效）

{TermColors.BRIGHT_YELLOW}帮助指令：{TermColors.RESET}
  {TermColors.BRIGHT_GREEN}h{TermColors.RESET} - 显示此帮助信息

{TermColors.BRIGHT_CYAN}示例用法：{TermColors.RESET}
  j10         - 跳转到第10行
  t25         - 跳转到25°C对应的电阻值
  a0.5:5-15   - 0.5秒间隔，从第5行到第15行自动递增
  a3-25       - 默认间隔，从第3行到第25行自动递增
  c100        - 设置自定义电阻值为100Ω
  c 1000      - 设置自定义电阻值为1000Ω（带空格格式）
  cOPEN       - 设置电阻为开路状态
  s           - 切换电阻短路状态（短路/正常）
  z           - 暂停自动递增
  x           - 继续自动递增

{TermColors.BRIGHT_CYAN}注意事项：{TermColors.RESET}
  - 时间间隔最小为0.1秒
  - 行号范围：1-{len(self.resistance_values)}
  - 自动递增到达范围末尾或最后一个电阻值时自动停止

{TermColors.BRIGHT_CYAN}{TermColors.BOLD}=========================================={TermColors.RESET}
"""
        print(help_text)
        
    def run_interactive(self):
        """交互式运行测试"""
        if not self.load_resistance_values():
            return
            
        if not self.connect_serial():
            return
        
        print("\n===== 电阻测试程序 =====")
        if not self.test_started:
            print("命令: s-开始测试, q-退出")
        else:
            print("命令: n-下一个, p-上一个, j-跳转到行号, t-跳转到温度, a-自动递增(支持范围), r-重新设置当前值, o-切换电阻连接/断开, s-切换短路状态, f-重头开始, c-设置自定义电阻值, h-帮助, z-暂停自动递增, x-继续自动递增, q-退出")
        
        try:
            # 设置初始电阻值，但只有在测试开始后才设置
            if self.test_started:
                current, comment = self.get_current_resistance()
                if current:
                    current_value = self.get_current_resistance_value()
                    if ',' in current:
                        values = current.split(',')
                        comment_display = f"{TermColors.BRIGHT_BLACK}[{comment}]{TermColors.RESET}" if comment else ""
                        print(f"\n当前电阻值 ({self.current_index + 1}/{len(self.resistance_values)}) [{self.current_sub_index + 1}/{len(values)}]: {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} (组: {current}) {comment_display}")
                    else:
                        comment_display = f"{TermColors.BRIGHT_BLACK}[{comment}]{TermColors.RESET}" if comment else ""
                        print(f"\n当前电阻值 ({self.current_index + 1}/{len(self.resistance_values)}): {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} {comment_display}")
                    self.set_resistance(current)
            else:
                print("\n请输入's'开始测试序列")
            
            while True:
                if not self.test_started:
                    cmd = self.get_user_input("输入命令 (s/q): ")
                else:
                    cmd = self.get_user_input("输入命令 (n/p/j/t/a/r/o/s/f/c/q/z/x): ")
                
                # 检查暂停/继续命令
                if cmd == 'z' and self.auto_increment_active:
                    if not self.auto_increment_paused:
                        self.pause_auto_increment()
                    continue
                elif cmd == 'x' and self.auto_increment_active:
                    if self.auto_increment_paused:
                        self.resume_auto_increment()
                    continue
                
                if cmd == 'q':
                    print("\n退出前将电阻设置为开路状态...")
                    self.disconnect_resistance()
                    break
                elif cmd == 's' and not self.test_started:
                    self.test_started = True
                    print("\n测试已开始")
                    print("命令: n-下一个, p-上一个, r-重新设置当前值, o-切换电阻连接/断开, s-切换短路状态, f-重头开始, c-设置自定义电阻值, q-退出")
                    # 设置初始电阻值
                    current, comment = self.get_current_resistance()
                    if current:
                        current_value = self.get_current_resistance_value()
                        comment_display = f"{TermColors.BRIGHT_BLACK}[{comment}]{TermColors.RESET}" if comment else ""
                        if ',' in current:
                            values = current.split(',')
                            print(f"\n当前电阻值 ({self.current_index + 1}/{len(self.resistance_values)}) [{self.current_sub_index + 1}/{len(values)}]: {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} (组: {current}) {comment_display}")
                        else:
                            print(f"\n当前电阻值 ({self.current_index + 1}/{len(self.resistance_values)}): {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} {comment_display}")
                        self.set_resistance(current)
                elif cmd == 'n' and self.test_started:
                    if self.next_resistance():
                        current, comment = self.get_current_resistance()
                        current_value = self.get_current_resistance_value()
                        comment_display = f"{TermColors.BRIGHT_BLACK}[{comment}]{TermColors.RESET}" if comment else ""
                        if ',' in current:
                            values = current.split(',')
                            print(f"\n当前电阻值 ({self.current_index + 1}/{len(self.resistance_values)}) [{self.current_sub_index + 1}/{len(values)}]: {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} (组: {current}) {comment_display}")
                        else:
                            print(f"\n当前电阻值 ({self.current_index + 1}/{len(self.resistance_values)}): {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} {comment_display}")
                        self.set_resistance(current)
                elif cmd == 'p' and self.test_started:
                    if self.previous_resistance():
                        current, comment = self.get_current_resistance()
                        current_value = self.get_current_resistance_value()
                        comment_display = f"{TermColors.BRIGHT_BLACK}[{comment}]{TermColors.RESET}" if comment else ""
                        if ',' in current:
                            values = current.split(',')
                            print(f"\n当前电阻值 ({self.current_index + 1}/{len(self.resistance_values)}) [{self.current_sub_index + 1}/{len(values)}]: {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} (组: {current}) {comment_display}")
                        else:
                            print(f"\n当前电阻值 ({self.current_index + 1}/{len(self.resistance_values)}): {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} {comment_display}")
                        self.set_resistance(current)
                elif cmd.startswith('j') and self.test_started:
                      try:
                          line_number = int(cmd[1:])
                          if 1 <= line_number <= len(self.resistance_values):
                              self.current_index = line_number - 1
                              self.current_sub_index = 0
                              current, comment = self.get_current_resistance()
                              current_value = self.get_current_resistance_value()
                              comment_display = f"[{comment}]" if comment else ""
                              if ',' in current:
                                  values = current.split(',')
                                  print(f"\n跳转到第 {line_number} 行: {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} (组: {current}) {TermColors.BRIGHT_BLACK}{comment_display}{TermColors.RESET}")
                              else:
                                  print(f"\n跳转到第 {line_number} 行: {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} {TermColors.BRIGHT_BLACK}{comment_display}{TermColors.RESET}")
                              self.set_resistance(current)
                          else:
                              print("\n无效的行号。")
                      except (ValueError, IndexError):
                          print("\n无效的命令格式。请使用 'j<行号>'。")
                elif cmd.startswith('t') and self.test_started:
                      try:
                          temperature = cmd[1:].strip()
                          index, resistance, comment = self.find_resistance_by_temperature(temperature)
                          if index is not None:
                              self.current_index = index
                              self.current_sub_index = 0
                              current_value = self.get_current_resistance_value()
                              comment_display = f"[{comment}]" if comment else ""
                              if ',' in resistance:
                                  values = resistance.split(',')
                                  print(f"\n跳转到温度 {temperature}°C: {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} (组: {resistance}) {TermColors.BRIGHT_BLACK}{comment_display}{TermColors.RESET}")
                              else:
                                  print(f"\n跳转到温度 {temperature}°C: {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} {TermColors.BRIGHT_BLACK}{comment_display}{TermColors.RESET}")
                              self.set_resistance(resistance)
                          else:
                              print(f"\n未找到温度 {temperature}°C 对应的电阻值。")
                      except Exception:
                          print("\n无效的命令格式。请使用 't<温度>'，例如 't25' 或 't-10'。")
                elif cmd.startswith('a') and self.test_started:
                    # 自动递增功能
                    if self.auto_increment_active:
                        # 如果已在运行，则停止
                        self.stop_auto_increment()
                    else:
                        # 开始自动递增，支持范围参数
                        params = cmd[1:].strip()
                        if params:
                            # 解析参数，格式: a<时间间隔> 或 a<起始行>-<结束行> 或 a<时间间隔>:<起始行>-<结束行>
                            try:
                                if ':' in params:
                                    # 格式: 时间间隔:起始行-结束行
                                    interval_part, range_part = params.split(':', 1)
                                    interval = float(interval_part)
                                    if '-' in range_part:
                                        start_line, end_line = range_part.split('-', 1)
                                        start_line = int(start_line) if start_line.strip() else None
                                        end_line = int(end_line) if end_line.strip() else None
                                        self.start_auto_increment(interval, start_line, end_line)
                                    else:
                                        start_line = int(range_part.strip())
                                        self.start_auto_increment(interval, start_line)
                                elif '-' in params:
                                    # 格式: 起始行-结束行（使用时间间隔默认值）
                                    start_line, end_line = params.split('-', 1)
                                    start_line = int(start_line) if start_line.strip() else None
                                    end_line = int(end_line) if end_line.strip() else None
                                    self.start_auto_increment(None, start_line, end_line)
                                else:
                                    # 只有时间间隔
                                    interval = float(params)
                                    self.start_auto_increment(interval)
                            except (ValueError, IndexError):
                                print("\n无效的参数格式。使用 'a' 开始（默认设置），'a<时间间隔>'，'a<起始行>-<结束行>'，或 'a<时间间隔>:<起始行>-<结束行>'")
                        else:
                            # 没有参数，使用默认设置
                            self.start_auto_increment()
                elif cmd == 'r' and self.test_started:
                    current, comment = self.get_current_resistance()
                    current_value = self.get_current_resistance_value()
                    if ',' in current:
                        values = current.split(',')
                        print(f"\n重新设置电阻值 [{self.current_sub_index + 1}/{len(values)}]: {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} (组: {current}) {comment}")
                    else:
                        print(f"\n重新设置电阻值: {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} {comment}")
                    self.set_resistance(current)
                elif cmd == 'o' and self.test_started:
                    if self.toggle_resistance_connection():
                        status = "断开" if not self.is_connected else "连接"
                        print(f"\n电阻状态已切换为: {status}")
                elif cmd == 's' and self.test_started:
                    if self.toggle_resistance_short():
                        status = "短路" if self.is_short_circuited else "正常"
                        print(f"\n电阻短路状态已切换为: {status}")
                elif cmd == 'f' and self.test_started:
                    if self.reset_to_first_group():
                        print("\n已重置到第一组电阻值")
                        current, comment = self.get_current_resistance()
                        current_value = self.get_current_resistance_value()
                        comment_display = f"{TermColors.BRIGHT_BLACK}[{comment}]{TermColors.RESET}" if comment else ""
                        if ',' in current:
                            values = current.split(',')
                            print(f"\n当前电阻值 ({self.current_index + 1}/{len(self.resistance_values)}) [{self.current_sub_index + 1}/{len(values)}]: {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} (组: {current}) {comment_display}")
                        else:
                            print(f"\n当前电阻值 ({self.current_index + 1}/{len(self.resistance_values)}): {TermColors.BRIGHT_GREEN}{TermColors.BOLD}{current_value}{TermColors.RESET} {comment_display}")
                        self.set_resistance(current)
                elif cmd.startswith('c') and self.test_started:
                    # 设置自定义电阻值 - 支持 c1000 或 c 1000 格式
                    custom_value = cmd[1:].strip()
                    if custom_value:
                        # 格式: c1000 或 cOPEN
                        self.set_custom_resistance(custom_value)
                    else:
                        # 格式: c 1000 - 需要额外输入
                        custom_value = input("请输入自定义电阻值 (数字或 OPEN): ").strip()
                        if custom_value:
                            self.set_custom_resistance(custom_value)
                        else:
                            print("\n未输入电阻值")
                elif cmd == 'h':
                    # 显示帮助信息
                    self.show_help()
                else:
                    if not self.test_started:
                        print("无效命令，请输入's'开始测试或'q'退出")
                    else:
                        print("无效命令")
        
        finally:
            self.disconnect_serial()
            print("\n测试结束")

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
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='电阻测试程序')
    parser.add_argument('-f', '--file', type=str, help='电阻值文件路径')
    parser.add_argument('-p', '--port', type=str, help='串口号，例如COM1')
    parser.add_argument('-g', '--group', type=int, default=0, help='起始电阻组索引（从0开始）')
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    
    # 确定电阻值文件路径
    if args.file:
        resistance_file = Path(args.file)
        if not resistance_file.exists():
            print(f"错误: 指定的电阻值文件 '{args.file}' 不存在")
            return
    else:
        resistance_file = script_dir / "resistance_values.txt"
    
    # 列出所有可用的COM端口
    available_ports = list_available_com_ports()
    
    # 确定串口
    if args.port:
        port = args.port
    else:
        default_port = "COM1"
        if available_ports:
            default_port = available_ports[0]
        port = input(f"请输入串口号 (默认 {default_port}): ").strip() or default_port
    
    tester = ResistanceTester(resistance_file, port=port)
    
    # 加载电阻值文件
    tester.load_resistance_values()
    
    # 设置起始组索引
    if args.group > 0:
        tester.current_index = min(args.group, len(tester.resistance_values) - 1)
        print(f"从第 {tester.current_index + 1} 组电阻值开始测试")
    
    # 注册信号处理函数，处理Ctrl+C
    def signal_handler(sig, frame):
        print("\n检测到Ctrl+C，正在将电阻设置为开路并退出...")
        if tester.ser and tester.ser.is_open:
            tester.disconnect_resistance()
            tester.disconnect_serial()
        sys.exit(0)
    
    # 注册SIGINT信号处理器（Ctrl+C）
    signal.signal(signal.SIGINT, signal_handler)
    
    tester.run_interactive()

if __name__ == "__main__":
    main()