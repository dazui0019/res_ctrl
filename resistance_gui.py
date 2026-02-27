#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
电阻测试仪 UI 控制界面
基于 tkinter 封装 resistance_cli.py 的功能
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import time
import os
import json
from serial.tools import list_ports


class ResistanceTester:
    def __init__(self, port="COM1", baudrate=9600, verbose=False):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.is_connected = False
        self.verbose = verbose

    def log(self, message):
        if self.verbose:
            print(message)

    def connect_serial(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.log(f"成功连接到串口 {self.port}")
            return True
        except Exception as e:
            self.log(f"连接串口失败: {e}")
            return False

    def disconnect_serial(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.log("串口连接已关闭")

    def send_command(self, command):
        if not self.ser or not self.ser.is_open:
            self.log("串口未连接")
            return False

        try:
            self.ser.write(command.encode())
            time.sleep(0.5)
            response = self.ser.read_all().decode(errors='ignore')
            self.log(f"发送: {command.strip()}, 响应: {response.strip()}")
            return True
        except Exception as e:
            self.log(f"发送指令失败: {e}")
            return False

    def disconnect_resistance(self):
        self.log("正在将电阻设置为开路状态...")
        result = self.send_command("AT+RES.DISCONNECT\r\n")
        if result:
            self.log("电阻已成功设置为开路状态")
            self.is_connected = False
        return result

    def connect_resistance(self):
        self.log("正在将电阻设置为连接状态...")
        result = self.send_command("AT+RES.CONNECT\r\n")
        if result:
            self.log("电阻已成功设置为连接状态")
            self.is_connected = True
        return result

    def short_resistance(self):
        self.log("正在将电阻设置为短路状态...")
        result = self.send_command("AT+RES.SHORT\r\n")
        if result:
            self.log("电阻已成功设置为短路状态")
            self.is_connected = True
        return result

    def unshort_resistance(self):
        self.log("正在取消电阻短路状态...")
        result = self.send_command("AT+RES.UNSHORTEN\r\n")
        if result:
            self.log("电阻短路状态已取消")
            self.is_connected = True
        return result

    def set_custom_resistance(self, resistance_value):
        try:
            if resistance_value.upper() == "OPEN":
                return self.disconnect_resistance()

            value = float(resistance_value)

            if value < 0:
                self.log("电阻值不能为负数")
                return False

            if value > 7000000:
                self.log("电阻值过大（最大支持7MΩ）")
                return False

            if not self.connect_resistance():
                return False

            success = self.send_command(f"AT+RES.SP={value}\r\n")
            if success:
                self.log(f"已设置自定义电阻值: {value}Ω")
                return True
            else:
                self.log("设置电阻值失败")
                return False

        except ValueError:
            self.log("无效的电阻值，请输入数字或 OPEN")
            return False
        except Exception as e:
            self.log(f"设置电阻值时出错: {e}")
            return False


class NTCProfile:
    """NTC 阻值表"""
    def __init__(self, filepath):
        self.filepath = filepath
        self.profiles = []  # [(temp, resistance), ...]
        self.load()

    def load(self):
        """加载 NTC 阻值表"""
        if not os.path.exists(self.filepath):
            return

        with open(self.filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(';'):
                    continue
                parts = line.split(';')
                if len(parts) >= 2:
                    try:
                        res = int(parts[0].strip())
                        temp = parts[1].strip()
                        self.profiles.append((temp, res))
                    except ValueError:
                        continue

    def get_items(self):
        """获取用于下拉框的选项"""
        return [f"{temp} ({res}Ω)" for temp, res in self.profiles]

    def find_by_temp(self, temp_str):
        """
        根据温度字符串查找阻值
        支持格式: "25", "25C", "-20", "-20C", "100C" 等
        """
        temp_str = temp_str.strip().upper()

        # 去除C后缀
        if temp_str.endswith('C'):
            temp_str = temp_str[:-1]

        try:
            temp_val = int(temp_str)
        except ValueError:
            return None

        # 查找匹配的阻值
        for temp, res in self.profiles:
            # 提取数字部分比较
            temp_num = int(temp.replace('C', ''))
            if temp_num == temp_val:
                return res, temp

        return None

    def get_resistance(self, index):
        """根据索引获取阻值"""
        if 0 <= index < len(self.profiles):
            return str(self.profiles[index][1])
        return None


class ConfigManager:
    """配置文件管理"""
    def __init__(self, config_file):
        self.config_file = config_file
        self.config = self.load()

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass

        # 默认配置
        return {
            "common_temps": ["25C", "0C", "-20C", "-40C", "100C", "50C"]
        }

    def save(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def get_common_temps(self):
        return self.config.get("common_temps", [])

    def set_common_temps(self, temps):
        self.config["common_temps"] = temps
        self.save()


class ResistanceGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("电阻测试仪控制")
        self.root.geometry("520x680")

        self.tester = None
        self.is_connected = False

        # 路径
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ntc_file = os.path.join(base_dir, "ntc_res.txt")
        config_file = os.path.join(base_dir, "resistance_gui_config.json")

        # 加载NTC和配置
        self.ntc = NTCProfile(ntc_file)
        self.config = ConfigManager(config_file)

        self.setup_ui()

    def setup_ui(self):
        # ===== 串口设置 =====
        frame_port = ttk.LabelFrame(self.root, text="串口设置", padding=10)
        frame_port.pack(fill="x", padx=10, pady=5)

        ttk.Label(frame_port, text="串口:").grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(frame_port, width=20, state="readonly")
        self.port_combo.grid(row=0, column=1, padx=5, sticky="w")
        ttk.Button(frame_port, text="刷新", command=self.refresh_ports).grid(row=0, column=2, padx=5)

        ttk.Label(frame_port, text="波特率:").grid(row=1, column=0, sticky="w", pady=5)
        self.baudrate_var = tk.IntVar(value=9600)
        ttk.Entry(frame_port, textvariable=self.baudrate_var, width=22).grid(row=1, column=1, padx=5, sticky="w", pady=5)

        self.connect_btn = ttk.Button(frame_port, text="连接串口", command=self.toggle_connection, width=20)
        self.connect_btn.grid(row=2, column=0, columnspan=3, pady=10)

        # ===== NTC 档位选择 =====
        frame_ntc = ttk.LabelFrame(self.root, text="NTC 温度设置", padding=10)
        frame_ntc.pack(fill="x", padx=10, pady=5)

        # 温度输入
        temp_frame = ttk.Frame(frame_ntc)
        temp_frame.pack(fill="x")

        ttk.Label(temp_frame, text="输入温度(°C):").pack(side="left")
        self.temp_entry = ttk.Entry(temp_frame, width=15)
        self.temp_entry.pack(side="left", padx=5)
        self.temp_entry.bind("<Return>", self.on_temp_input)  # 回车确认

        ttk.Button(temp_frame, text="设置", command=self.on_temp_input).pack(side="left", padx=5)
        ttk.Label(temp_frame, text="(如: 25, -20, 100)", font=('', 8)).pack(side="left")

        # 常用温度按钮
        self.btn_frame = ttk.Frame(frame_ntc)
        self.btn_frame.pack(fill="x", pady=10)

        ttk.Label(self.btn_frame, text="常用温度:").pack(anchor="w", pady=(10, 5))
        self.update_common_temp_buttons()

        # 快捷设置按钮
        ttk.Button(self.btn_frame, text="⚙ 编辑常用温度", command=self.edit_common_temps).pack(anchor="w")

        # ===== 电阻控制 =====
        frame_res = ttk.LabelFrame(self.root, text="电阻控制", padding=10)
        frame_res.pack(fill="x", padx=10, pady=5)

        ttk.Label(frame_res, text="电阻值 (Ω):").grid(row=0, column=0, sticky="w")
        self.resistance_entry = ttk.Entry(frame_res, width=20)
        self.resistance_entry.grid(row=0, column=1, padx=5, sticky="w")
        ttk.Button(frame_res, text="设置", command=self.set_resistance).grid(row=0, column=2, padx=5)

        ttk.Label(frame_res, text="快速操作:").grid(row=1, column=0, sticky="w", pady=10)

        btn_frame2 = ttk.Frame(frame_res)
        btn_frame2.grid(row=2, column=0, columnspan=3)

        ttk.Button(btn_frame2, text="连接", command=self.connect_resistance, width=10).pack(side="left", padx=3)
        ttk.Button(btn_frame2, text="开路 (OPEN)", command=self.set_open, width=12).pack(side="left", padx=3)
        ttk.Button(btn_frame2, text="短路", command=self.short_resistance, width=10).pack(side="left", padx=3)
        ttk.Button(btn_frame2, text="取消短路", command=self.unshort_resistance, width=10).pack(side="left", padx=3)

        # ===== 日志 =====
        frame_log = ttk.LabelFrame(self.root, text="日志输出", padding=10)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(frame_log, height=8, state="disabled")
        self.log_text.pack(fill="both", expand=True)

        ttk.Button(frame_log, text="清空日志", command=self.clear_log).pack(anchor="e", pady=5)

        # 初始化
        self.refresh_ports()
        self.add_log("程序启动，请选择串口并连接")

    def update_common_temp_buttons(self):
        """更新常用温度按钮"""
        # 清除旧按钮
        for widget in self.btn_frame.winfo_children():
            if isinstance(widget, ttk.Button) and widget.cget("text") != "⚙ 编辑常用温度":
                widget.destroy()

        # 重新添加按钮（排除编辑按钮）
        temps = self.config.get_common_temps()
        for temp in temps:
            btn = ttk.Button(
                self.btn_frame,
                text=temp,
                command=lambda t=temp: self.quick_select_temp(t)
            )
            btn.pack(side="left", padx=3, pady=5)

    def edit_common_temps(self):
        """编辑常用温度"""
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑常用温度")
        dialog.geometry("350x200")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="输入常用温度(用逗号分隔):").pack(pady=10)
        ttk.Label(dialog, text="例如: 25C, 0C, -20C, 100C", font=('', 8)).pack()

        entry = ttk.Entry(dialog, width=40)
        entry.pack(pady=10)
        entry.insert(0, ", ".join(self.config.get_common_temps()))

        def save():
            temps_str = entry.get()
            temps = [t.strip() for t in temps_str.split(",") if t.strip()]
            # 规范化格式（统一加C后缀）
            normalized = []
            for t in temps:
                t = t.upper()
                if not t.endswith('C'):
                    t += 'C'
                normalized.append(t)

            if normalized:
                self.config.set_common_temps(normalized)
                self.update_common_temp_buttons()
                self.add_log(f"已更新常用温度: {', '.join(normalized)}")
            dialog.destroy()

        ttk.Button(dialog, text="保存", command=save).pack(pady=10)
        ttk.Button(dialog, text="取消", command=dialog.destroy).pack()

    def refresh_ports(self):
        ports = list_ports.comports()
        port_list = [p.device for p in ports]
        self.port_combo["values"] = port_list
        if port_list:
            self.port_combo.current(0)

    def on_temp_input(self, event=None):
        """温度输入处理 - 直接设置电阻"""
        temp_str = self.temp_entry.get().strip()
        if not temp_str:
            return

        result = self.ntc.find_by_temp(temp_str)
        if result:
            res, temp = result
            self.resistance_entry.delete(0, "end")
            self.resistance_entry.insert(0, str(res))
            self.add_log(f"温度 {temp} -> 阻值 {res}Ω")
            # 直接设置电阻
            self.set_resistance()
        else:
            messagebox.showwarning("警告", f"未找到温度 {temp_str} 对应的阻值")

    def quick_select_temp(self, temp):
        """快速选择温度 - 直接设置电阻"""
        result = self.ntc.find_by_temp(temp)
        if result:
            res, t = result
            self.resistance_entry.delete(0, "end")
            self.resistance_entry.insert(0, str(res))
            self.temp_entry.delete(0, "end")
            self.temp_entry.insert(0, temp.replace('C', ''))
            self.add_log(f"温度 {t} -> 阻值 {res}Ω")
            # 直接设置电阻
            self.set_resistance()
        else:
            messagebox.showwarning("警告", f"未找到温度 {temp}")

    def toggle_connection(self):
        if self.is_connected:
            if self.tester:
                self.tester.disconnect_serial()
            self.is_connected = False
            self.connect_btn.config(text="连接串口")
            self.port_combo.config(state="readonly")
            self.add_log("串口已断开")
        else:
            port = self.port_combo.get()
            if not port:
                messagebox.showwarning("警告", "请先选择串口")
                return

            baudrate = self.baudrate_var.get()
            self.tester = ResistanceTester(port=port, baudrate=baudrate, verbose=True)

            if self.tester.connect_serial():
                self.is_connected = True
                self.connect_btn.config(text="断开串口")
                self.port_combo.config(state="disabled")
                self.add_log(f"已连接到 {port}")

    def set_resistance(self):
        if not self.is_connected or not self.tester:
            messagebox.showwarning("警告", "请先连接串口")
            return

        value = self.resistance_entry.get()
        if not value:
            messagebox.showwarning("警告", "请输入电阻值")
            return

        if self.tester.set_custom_resistance(value):
            self.add_log(f"已设置电阻值: {value}Ω")

    def set_open(self):
        if not self.is_connected or not self.tester:
            messagebox.showwarning("警告", "请先连接串口")
            return

        if self.tester.disconnect_resistance():
            self.add_log("已设置为开路状态 (OPEN)")

    def connect_resistance(self):
        if not self.is_connected or not self.tester:
            messagebox.showwarning("警告", "请先连接串口")
            return

        if self.tester.connect_resistance():
            self.add_log("电阻已连接")

    def short_resistance(self):
        if not self.is_connected or not self.tester:
            messagebox.showwarning("警告", "请先连接串口")
            return

        if self.tester.short_resistance():
            self.add_log("电阻已设置为短路状态")

    def unshort_resistance(self):
        if not self.is_connected or not self.tester:
            messagebox.showwarning("警告", "请先连接串口")
            return

        if self.tester.unshort_resistance():
            self.add_log("电阻短路状态已取消")

    def add_log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        log_text = f"[{timestamp}] {message}\n"

        self.log_text.config(state="normal")
        self.log_text.insert("end", log_text)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")


def main():
    root = tk.Tk()
    app = ResistanceGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
