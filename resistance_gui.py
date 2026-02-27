#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
电阻测试仪 UI 控制界面
支持多设备RS485控制
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import time
import os
import json
from serial.tools import list_ports


class ResistanceTester:
    """电阻测试器类 - 每个实例对应一个SN设备"""
    def __init__(self, port, baudrate, sn, serial_obj=None):
        self.port = port
        self.baudrate = baudrate
        self.sn = sn
        self.ser = serial_obj  # 共享串口对象
        self.is_connected = False
        self.verbose = True
        self.current_resistance = None  # 当前电阻值
        self.resistance_label = None  # 显示标签
        self.name = "未命名"  # 设备名称

    def _format_command(self, cmd):
        """格式化指令，支持RS485 SN码"""
        if self.sn:
            if cmd.startswith("AT+"):
                base = cmd.replace("\r\n", "")
                return f"AT+{base[3:]}@{self.sn}\r\n"
        return cmd

    def send_command(self, command):
        """发送指令"""
        if not self.ser or not self.ser.is_open:
            return False

        command = self._format_command(command)

        try:
            self.ser.write(command.encode())
            time.sleep(0.3)
            response = self.ser.read_all().decode(errors='ignore')
            return response
        except Exception as e:
            return None

    def set_resistance(self, value):
        """设置电阻值"""
        try:
            if str(value).upper() == "OPEN":
                self.send_command("AT+RES.DISCONNECT\r\n")
                self.current_resistance = "OPEN"
                self.update_label()
                return True

            val = float(value)
            if val < 0 or val > 7000000:
                return False

            self.send_command("AT+RES.CONNECT\r\n")
            time.sleep(0.1)
            self.send_command(f"AT+RES.SP={val}\r\n")
            self.current_resistance = f"{int(val)}Ω"
            self.update_label()
            return True
        except:
            return False

    def update_label(self):
        """更新显示标签"""
        if self.resistance_label:
            self.resistance_label.config(text=f"当前: {self.current_resistance}")

    def disconnect_resistance(self):
        """开路"""
        return self.send_command("AT+RES.DISCONNECT\r\n")

    def connect_resistance(self):
        """连接"""
        return self.send_command("AT+RES.CONNECT\r\n")

    def short_resistance(self):
        """短路"""
        return self.send_command("AT+RES.SHORT\r\n")

    def unshort_resistance(self):
        """取消短路"""
        return self.send_command("AT+RES.UNSHORTEN\r\n")


class NTCProfile:
    """NTC 阻值表"""
    def __init__(self, filepath):
        self.filepath = filepath
        self.profiles = []
        self.load()

    def load(self):
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

    def find_by_temp(self, temp_str):
        temp_str = temp_str.strip().upper()
        if temp_str.endswith('C'):
            temp_str = temp_str[:-1]
        try:
            temp_val = int(temp_str)
        except ValueError:
            return None
        for temp, res in self.profiles:
            temp_num = int(temp.replace('C', ''))
            if temp_num == temp_val:
                return res, temp
        return None


class ResistanceGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("电阻测试仪控制 (多设备RS485)")
        self.root.geometry("800x600")

        # 串口和设备管理
        self.ser = None
        self.is_serial_connected = False
        self.devices = {}  # {sn: ResistanceTester}

        # 路径
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ntc_file = os.path.join(base_dir, "ntc_res.txt")
        self.config_file = os.path.join(base_dir, "devices_config.json")

        self.ntc = NTCProfile(ntc_file)

        # 加载保存的设备
        self.load_devices()

        self.setup_ui()
        self.refresh_ports()

        # 显示已加载的设备
        if self.devices:
            self.rebuild_device_grid()

        self.add_log("程序启动，请先连接串口")

    def setup_ui(self):
        # ===== 串口设置 =====
        frame_port = ttk.LabelFrame(self.root, text="串口连接", padding=10)
        frame_port.pack(fill="x", padx=10, pady=5)

        ttk.Label(frame_port, text="串口:").grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(frame_port, width=15, state="readonly")
        self.port_combo.grid(row=0, column=1, padx=5, sticky="w")
        ttk.Button(frame_port, text="刷新", command=self.refresh_ports).grid(row=0, column=2, padx=5)

        ttk.Label(frame_port, text="波特率:").grid(row=0, column=3, sticky="w", padx=(20,0))
        self.baudrate_var = tk.IntVar(value=9600)
        ttk.Entry(frame_port, textvariable=self.baudrate_var, width=10).grid(row=0, column=4, padx=5)

        self.connect_btn = ttk.Button(frame_port, text="连接串口", command=self.toggle_serial_connection, width=15)
        self.connect_btn.grid(row=0, column=5, padx=20)

        # ===== 设备管理 =====
        frame_device = ttk.LabelFrame(self.root, text="设备管理", padding=10)
        frame_device.pack(fill="x", padx=10, pady=5)

        # 添加设备
        add_frame = ttk.Frame(frame_device)
        add_frame.pack(fill="x")

        ttk.Label(add_frame, text="名称:").pack(side="left")
        self.name_entry = ttk.Entry(add_frame, width=10)
        self.name_entry.pack(side="left", padx=5)

        ttk.Label(add_frame, text="SN码:").pack(side="left")
        self.sn_entry = ttk.Entry(add_frame, width=10)
        self.sn_entry.pack(side="left", padx=5)
        ttk.Button(add_frame, text="添加设备", command=self.add_device).pack(side="left", padx=5)
        ttk.Label(add_frame, text="(如: 设备1, 001)", font=('', 8)).pack(side="left")

        # 统一控制按钮
        control_frame = ttk.Frame(frame_device)
        control_frame.pack(fill="x", pady=5)
        ttk.Label(control_frame, text="选中设备控制:").pack(side="left", padx=5)
        ttk.Button(control_frame, text="连接", command=self.selected_connect).pack(side="left", padx=3)
        ttk.Button(control_frame, text="开路", command=self.selected_open).pack(side="left", padx=3)
        ttk.Button(control_frame, text="短路", command=self.selected_short).pack(side="left", padx=3)
        ttk.Button(control_frame, text="取消短路", command=self.selected_unshort).pack(side="left", padx=3)
        ttk.Button(control_frame, text="全选", command=self.select_all).pack(side="left", padx=10)
        ttk.Button(control_frame, text="取消全选", command=self.deselect_all).pack(side="left", padx=3)
        ttk.Button(control_frame, text="删除选中", command=self.delete_selected).pack(side="left", padx=10)

        # 设备列表区域 - 使用Grid平铺
        list_frame = ttk.Frame(frame_device)
        list_frame.pack(fill="both", expand=True, pady=10)

        # 画布和滚动条
        self.canvas = tk.Canvas(list_frame, bg="white")
        self.scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.device_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.device_frame, anchor="nw")

        self.device_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # 设备网格布局参数
        self.device_cols = 3  # 每行显示3个设备
        self.device_count = 0


        # ===== 日志 =====
        frame_log = ttk.LabelFrame(self.root, text="日志", padding=10)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(frame_log, height=8, state="disabled")
        self.log_text.pack(fill="both", expand=True)

        ttk.Button(frame_log, text="清空日志", command=self.clear_log).pack(anchor="e", pady=5)

    def load_devices(self):
        """加载保存的设备配置"""
        if not os.path.exists(self.config_file):
            return

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                saved_devices = json.load(f)
            for sn, info in saved_devices.items():
                # 先创建设备实例（串口为None，稍后设置）
                device = ResistanceTester(None, None, sn, None)
                device.name = info.get('name', '未命名')
                self.devices[sn] = device
        except Exception as e:
            print(f"加载设备配置失败: {e}")

    def save_devices(self):
        """保存设备配置到JSON文件"""
        try:
            devices_data = {}
            for sn, device in self.devices.items():
                devices_data[sn] = {'name': getattr(device, 'name', '未命名')}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(devices_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存设备配置失败: {e}")

    def refresh_ports(self):
        ports = list_ports.comports()
        port_list = [p.device for p in ports]
        self.port_combo["values"] = port_list
        if port_list:
            self.port_combo.current(0)

    def toggle_serial_connection(self):
        if self.is_serial_connected:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.is_serial_connected = False
            self.connect_btn.config(text="连接串口")
            self.port_combo.config(state="readonly")
            self.add_log("串口已断开")
        else:
            port = self.port_combo.get()
            if not port:
                messagebox.showwarning("警告", "请先选择串口")
                return

            try:
                self.ser = serial.Serial(port, self.baudrate_var.get(), timeout=1)
                self.is_serial_connected = True
                self.connect_btn.config(text="断开串口")
                self.port_combo.config(state="disabled")

                # 更新所有设备的串口对象
                for device in self.devices.values():
                    device.ser = self.ser
                    device.port = port
                    device.baudrate = self.baudrate_var.get()

                self.add_log(f"已连接到 {port}")
            except Exception as e:
                messagebox.showerror("错误", f"连接失败: {e}")

    def add_device(self):
        if not self.is_serial_connected:
            messagebox.showwarning("警告", "请先连接串口")
            return

        name = self.name_entry.get().strip() or "未命名"
        sn = self.sn_entry.get().strip()
        if not sn:
            messagebox.showwarning("警告", "请输入SN码")
            return

        if sn in self.devices:
            messagebox.showwarning("警告", f"设备 {sn} 已存在")
            return

        # 创建设备实例
        device = ResistanceTester(
            port=self.ser.port,
            baudrate=self.ser.baudrate,
            sn=sn,
            serial_obj=self.ser
        )
        device.name = name  # 保存设备名称
        self.devices[sn] = device

        # 创建设备UI
        self.create_device_ui(sn, device)
        self.name_entry.delete(0, "end")
        self.sn_entry.delete(0, "end")
        self.add_log(f"已添加设备 {name} (SN:{sn})")
        self.save_devices()  # 保存配置

    def create_device_ui(self, sn, device):
        """创建设备控制UI"""
        name = getattr(device, 'name', '未命名')
        frame = ttk.LabelFrame(self.device_frame, text=f"{name} (SN:{sn})", padding=5)
        row = self.device_count // self.device_cols
        col = self.device_count % self.device_cols
        frame.grid(row=row, column=col, padx=3, pady=3, sticky="n")
        self.device_count += 1

        # 选择复选框
        var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, variable=var).pack(anchor="w")

        # 电阻值设置 (第一行)
        res_frame = ttk.Frame(frame)
        res_frame.pack(fill="x", pady=2)
        ttk.Label(res_frame, text="阻值:").pack(side="left", padx=2)
        entry = ttk.Entry(res_frame, width=8)
        entry.pack(side="left", padx=2)
        ttk.Button(res_frame, text="设置", command=lambda: self.set_device_resistance(sn, entry), width=4).pack(side="left", padx=2)

        # 温度设置 (第二行)
        temp_frame = ttk.Frame(frame)
        temp_frame.pack(fill="x", pady=2)
        ttk.Label(temp_frame, text="温度:").pack(side="left", padx=2)
        temp_entry = ttk.Entry(temp_frame, width=8)
        temp_entry.pack(side="left", padx=2)
        ttk.Button(temp_frame, text="设置", command=lambda: self.set_device_temp(sn, temp_entry), width=4).pack(side="left", padx=2)

        # 保存UI引用
        device.ui_entry = entry
        device.ui_var = var  # 保存复选框变量

        # 当前电阻值显示
        label = ttk.Label(frame, text="当前: --", foreground="blue")
        label.pack(pady=2)
        device.resistance_label = label
        device.ui_frame = frame  # 保存frame引用

        # 创建右键菜单
        menu = tk.Menu(frame, tearoff=0)
        menu.add_command(label="重命名", command=lambda: self.rename_device(sn, device, frame))
        menu.add_command(label="删除", command=lambda: self.delete_single_device(sn))
        frame.bind("<Button-3>", lambda e: menu.post(e.x_root, e.y_root))

    def delete_single_device(self, sn):
        """删除单个设备"""
        device = self.devices.get(sn)
        if not device:
            return
        name = getattr(device, 'name', '未命名')
        # 通过frame引用删除
        if hasattr(device, 'ui_frame'):
            device.ui_frame.destroy()
        del self.devices[sn]
        self.add_log(f"已删除设备 {name} (SN:{sn})")
        self.rebuild_device_grid()
        self.save_devices()

    def rename_device(self, sn, device, frame):
        """重命名设备"""
        dialog = tk.Toplevel(self.root)
        dialog.title("重命名设备")
        dialog.geometry("300x120")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="输入新名称:").pack(pady=10)
        entry = ttk.Entry(dialog, width=25)
        entry.pack(pady=5)
        entry.insert(0, device.name)

        def save_rename():
            new_name = entry.get().strip()
            if new_name:
                device.name = new_name
                # 更新标题
                frame.config(text=f"{new_name} (SN:{sn})")
                self.save_devices()  # 保存配置
                self.add_log(f"已将设备重命名为: {new_name} (SN:{sn})")
            dialog.destroy()

        ttk.Button(dialog, text="确定", command=save_rename).pack(pady=5)
        ttk.Button(dialog, text="取消", command=dialog.destroy).pack()

    def set_device_resistance(self, sn, entry):
        """设置设备电阻值"""
        device = self.devices.get(sn)
        if not device:
            return

        value = entry.get().strip()
        if not value:
            messagebox.showwarning("警告", "请输入电阻值")
            return

        if device.set_resistance(value):
            name = getattr(device, 'name', '未命名')
            self.add_log(f"[{name}({sn})] 已设置电阻值: {value}Ω")
        else:
            messagebox.showerror("错误", f"[{sn}] 设置失败")

    def set_device_temp(self, sn, temp_entry):
        """通过温度设置设备电阻"""
        device = self.devices.get(sn)
        if not device:
            return

        temp_str = temp_entry.get().strip()
        result = self.ntc.find_by_temp(temp_str)

        if result:
            res, temp = result
            if device.set_resistance(str(res)):
                name = getattr(device, 'name', '未命名')
                self.add_log(f"[{name}({sn})] 温度 {temp} -> 阻值 {res}Ω")
        else:
            messagebox.showwarning("警告", f"未找到温度 {temp_str} 对应的阻值")

    def selected_connect(self):
        """选中设备连接"""
        for sn, device in self.devices.items():
            if device.ui_var.get():
                device.connect_resistance()
                device.current_resistance = "已连接"
                device.update_label()
                name = getattr(device, 'name', '未命名')
                self.add_log(f"[{name}({sn})] 电阻已连接")

    def selected_open(self):
        """选中设备开路"""
        for sn, device in self.devices.items():
            if device.ui_var.get():
                device.disconnect_resistance()
                device.current_resistance = "OPEN"
                device.update_label()
                name = getattr(device, 'name', '未命名')
                self.add_log(f"[{name}({sn})] 已设置为开路")

    def selected_short(self):
        """选中设备短路"""
        for sn, device in self.devices.items():
            if device.ui_var.get():
                device.short_resistance()
                device.current_resistance = "短路"
                device.update_label()
                name = getattr(device, 'name', '未命名')
                self.add_log(f"[{name}({sn})] 已设置为短路")

    def selected_unshort(self):
        """取消选中设备短路"""
        for sn, device in self.devices.items():
            if device.ui_var.get():
                device.unshort_resistance()
                name = getattr(device, 'name', '未命名')
                self.add_log(f"[{name}({sn})] 取消短路")

    def select_all(self):
        """全选"""
        for device in self.devices.values():
            device.ui_var.set(True)

    def deselect_all(self):
        """取消全选"""
        for device in self.devices.values():
            device.ui_var.set(False)

    def delete_selected(self):
        """删除选中的设备"""
        # 收集要删除的SN
        to_delete = []
        for sn, device in self.devices.items():
            if device.ui_var.get():
                to_delete.append(sn)

        if not to_delete:
            return

        # 删除设备
        for sn in to_delete:
            device = self.devices.get(sn)
            name = getattr(device, 'name', '未命名')
            if device and hasattr(device, 'ui_entry'):
                # 通过frame引用删除
                device.ui_entry.master.master.destroy()
            del self.devices[sn]
            self.add_log(f"已删除设备 {name} (SN:{sn})")

        self.rebuild_device_grid()
        self.save_devices()  # 保存配置

    def rebuild_device_grid(self):
        """重新布局设备网格"""
        # 清除所有设备
        for widget in self.device_frame.winfo_children():
            widget.destroy()

        # 重新添加所有设备
        self.device_count = 0
        for sn, device in self.devices.items():
            self.create_device_ui(sn, device)

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
