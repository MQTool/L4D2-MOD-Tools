import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import json
from pathlib import Path
import re
import threading

class AudioConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("音频转换工具")
        self.root.geometry("900x700")
        
        # 设置变量
        self.source_folder = tk.StringVar()
        self.target_folder = tk.StringVar()
        self.output_folder = tk.StringVar()
        
        self.source_files = []
        self.target_files = []
        self.mappings = []  # 存储映射关系
        
        # 当前选择的源和目标
        self.current_source = None  # 源只能单选
        self.current_targets = []  # 目标可以多选
        
        # 创建UI
        self.create_ui()
    
    def create_ui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 文件夹选择区域
        folder_frame = ttk.LabelFrame(main_frame, text="文件夹选择", padding="10")
        folder_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 源文件夹
        ttk.Label(folder_frame, text="源文件夹:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(folder_frame, textvariable=self.source_folder, width=50).grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        ttk.Button(folder_frame, text="浏览...", command=self.select_source_folder).grid(row=0, column=2, padx=5, pady=5)
        
        # 目标文件夹
        ttk.Label(folder_frame, text="目标文件夹:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(folder_frame, textvariable=self.target_folder, width=50).grid(row=1, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        ttk.Button(folder_frame, text="浏览...", command=self.select_target_folder).grid(row=1, column=2, padx=5, pady=5)
        
        # 输出文件夹
        ttk.Label(folder_frame, text="输出文件夹:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(folder_frame, textvariable=self.output_folder, width=50).grid(row=2, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        ttk.Button(folder_frame, text="浏览...", command=self.select_output_folder).grid(row=2, column=2, padx=5, pady=5)
        
        # 当前选择区域
        selection_frame = ttk.LabelFrame(main_frame, text="当前选择", padding="10")
        selection_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(selection_frame, text="当前源:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.current_source_label = ttk.Label(selection_frame, text="未选择")
        self.current_source_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(selection_frame, text="当前目标:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.current_target_label = ttk.Label(selection_frame, text="未选择")
        self.current_target_label.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
        # 映射操作按钮
        self.map_button = ttk.Button(selection_frame, text="建立映射", command=self.add_mapping, state="disabled")
        self.map_button.grid(row=0, column=4, padx=5, pady=5)
        
        self.clear_selection_button = ttk.Button(selection_frame, text="清除选择", command=self.clear_selection, state="disabled")
        self.clear_selection_button.grid(row=0, column=5, padx=5, pady=5)
        
        # 文件列表和映射区域
        lists_frame = ttk.Frame(main_frame)
        lists_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 源文件列表 - 单选模式
        source_frame = ttk.LabelFrame(lists_frame, text="源文件列表", padding="10")
        source_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.source_listbox = tk.Listbox(source_frame, selectmode=tk.SINGLE, height=15)
        self.source_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        source_scrollbar = ttk.Scrollbar(source_frame, orient=tk.VERTICAL, command=self.source_listbox.yview)
        source_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.source_listbox.config(yscrollcommand=source_scrollbar.set)
        
        # 源文件选择按钮
        source_button_frame = ttk.Frame(source_frame)
        source_button_frame.pack(fill=tk.X, pady=5)
        self.set_source_button = ttk.Button(source_button_frame, text="设定为源对象", command=self.set_as_source)
        self.set_source_button.pack(side=tk.LEFT, padx=5)
        
        # 目标文件列表 - 多选模式
        target_frame = ttk.LabelFrame(lists_frame, text="目标文件列表", padding="10")
        target_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        
        self.target_listbox = tk.Listbox(target_frame, selectmode=tk.EXTENDED, height=15)
        self.target_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        target_scrollbar = ttk.Scrollbar(target_frame, orient=tk.VERTICAL, command=self.target_listbox.yview)
        target_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.target_listbox.config(yscrollcommand=target_scrollbar.set)
        
        # 目标文件选择按钮
        target_button_frame = ttk.Frame(target_frame)
        target_button_frame.pack(fill=tk.X, pady=5)
        self.set_target_button = ttk.Button(target_button_frame, text="设定为目标对象", command=self.set_as_target)
        self.set_target_button.pack(side=tk.LEFT, padx=5)
        
        # 按钮区域
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(buttons_frame, text="删除映射", command=self.remove_mapping).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(buttons_frame, text="清除所有映射", command=self.clear_mappings).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(buttons_frame, text="开始转换", command=self.start_conversion).pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 映射列表区域
        mapping_frame = ttk.LabelFrame(main_frame, text="转换映射", padding="10")
        mapping_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建一个表格来显示映射关系
        columns = ("源文件", "目标文件")
        self.mapping_tree = ttk.Treeview(mapping_frame, columns=columns, show="headings", height=10)
        
        for col in columns:
            self.mapping_tree.heading(col, text=col)
            self.mapping_tree.column(col, width=400)
        
        self.mapping_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        mapping_scrollbar = ttk.Scrollbar(mapping_frame, orient=tk.VERTICAL, command=self.mapping_tree.yview)
        mapping_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.mapping_tree.config(yscrollcommand=mapping_scrollbar.set)
        
        # 进度区域
        progress_frame = ttk.LabelFrame(main_frame, text="转换进度", padding="10")
        progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        self.status_label = ttk.Label(progress_frame, text="就绪")
        self.status_label.pack(fill=tk.X, padx=5, pady=5)
    
    def select_source_folder(self):
        folder = filedialog.askdirectory(title="选择源文件夹")
        if folder:
            self.source_folder.set(folder)
            self.load_audio_files(folder, self.source_listbox, "source")
    
    def select_target_folder(self):
        folder = filedialog.askdirectory(title="选择目标文件夹")
        if folder:
            self.target_folder.set(folder)
            self.load_audio_files(folder, self.target_listbox, "target")
    
    def select_output_folder(self):
        folder = filedialog.askdirectory(title="选择输出文件夹")
        if folder:
            self.output_folder.set(folder)
    
    def load_audio_files(self, folder, listbox, list_type):
        listbox.delete(0, tk.END)
        
        # 支持的音频格式
        audio_extensions = (".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a")
        
        files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(audio_extensions)]
        
        for file in files:
            listbox.insert(tk.END, file)
        
        if list_type == "source":
            self.source_files = files
        else:
            self.target_files = files
    
    def set_as_source(self):
        """将当前选中的源列表项设为源对象"""
        selected = self.source_listbox.curselection()
        if not selected:
            messagebox.showwarning("警告", "请在源列表中选择一个文件")
            return
        
        # 获取选中的源文件
        self.current_source = self.source_listbox.get(selected[0])
        self.current_source_label.config(text=self.current_source)
        
        # 更新按钮状态
        self.update_button_states()
    
    def set_as_target(self):
        """将当前选中的目标列表项设为目标对象"""
        selected = self.target_listbox.curselection()
        if not selected:
            messagebox.showwarning("警告", "请在目标列表中选择至少一个文件")
            return
        
        # 获取所有选中的目标文件
        self.current_targets = [self.target_listbox.get(idx) for idx in selected]
        
        # 更新显示标签 - 显示选中的文件数量
        if len(self.current_targets) == 1:
            self.current_target_label.config(text=self.current_targets[0])
        else:
            self.current_target_label.config(text=f"已选择 {len(self.current_targets)} 个文件")
        
        # 更新按钮状态
        self.update_button_states()
    
    def update_button_states(self):
        """更新按钮状态"""
        if self.current_source is not None and self.current_targets:
            self.map_button.config(state="normal")
            self.clear_selection_button.config(state="normal")
        elif self.current_source is not None or self.current_targets:
            self.map_button.config(state="disabled")
            self.clear_selection_button.config(state="normal")
        else:
            self.map_button.config(state="disabled")
            self.clear_selection_button.config(state="disabled")
    
    def clear_selection(self):
        """清除当前选择"""
        self.current_source = None
        self.current_targets = []
        self.current_source_label.config(text="未选择")
        self.current_target_label.config(text="未选择")
        self.update_button_states()
    
    def add_mapping(self):
        """添加映射关系"""
        if not self.current_source or not self.current_targets:
            messagebox.showwarning("警告", "请先选择源和目标文件")
            return
        
        # 检查源文件是否已有映射
        existing_mappings = []
        for mapping in self.mappings:
            if mapping[0] == self.current_source:
                existing_mappings.append(mapping)
        
        if existing_mappings:
            if not messagebox.askyesno("确认", f"源文件 {self.current_source} 已有映射，是否覆盖？"):
                return
            
            # 移除旧映射
            for mapping in existing_mappings:
                self.mappings.remove(mapping)
            
            # 从树视图中删除已有的映射
            for item in self.mapping_tree.get_children():
                if self.mapping_tree.item(item, "values")[0] == self.current_source:
                    self.mapping_tree.delete(item)
        
        # 添加新映射 - 源文件对应多个目标文件
        for target in self.current_targets:
            # 检查这个特定的映射是否已存在
            if (self.current_source, target) in self.mappings:
                continue
                
            self.mappings.append((self.current_source, target))
            self.mapping_tree.insert("", tk.END, values=(self.current_source, target))
        
        # 重置当前选择
        self.clear_selection()
    
    def remove_mapping(self):
        selected_items = self.mapping_tree.selection()
        
        if not selected_items:
            messagebox.showwarning("警告", "请选择要删除的映射")
            return
        
        for item in selected_items:
            values = self.mapping_tree.item(item, "values")
            source_file = values[0]
            target_file = values[1]
            
            # 从映射列表中移除特定的映射
            if (source_file, target_file) in self.mappings:
                self.mappings.remove((source_file, target_file))
            
            # 从树状图中移除
            self.mapping_tree.delete(item)
    
    def clear_mappings(self):
        if not self.mappings:
            return
            
        if messagebox.askyesno("确认", "确定要清除所有映射吗？"):
            self.mappings = []
            for item in self.mapping_tree.get_children():
                self.mapping_tree.delete(item)
    
    def start_conversion(self):
        if not self.mappings:
            messagebox.showwarning("警告", "请添加至少一个映射")
            return
            
        if not self.output_folder.get():
            messagebox.showwarning("警告", "请选择输出文件夹")
            return
            
        # 创建输出文件夹（如果不存在）
        output_path = self.output_folder.get()
        os.makedirs(output_path, exist_ok=True)
        
        # 启动转换线程
        conversion_thread = threading.Thread(target=self.run_conversion)
        conversion_thread.daemon = True
        conversion_thread.start()
    
    def run_conversion(self):
        total_mappings = len(self.mappings)
        completed = 0
        
        self.status_label.config(text="开始转换...")
        self.progress_bar["maximum"] = total_mappings
        self.progress_bar["value"] = 0
        
        for source_file, target_file in self.mappings:
            self.status_label.config(text=f"正在处理: {source_file} 转换为 {target_file} 格式")
            
            source_path = os.path.join(self.source_folder.get(), source_file)
            target_path = os.path.join(self.target_folder.get(), target_file)
            
            # 直接使用目标文件名作为输出文件名
            output_path = os.path.join(self.output_folder.get(), target_file)
            
            # 创建临时文件路径
            temp_dir = os.path.join(self.output_folder.get(), "temp")
            os.makedirs(temp_dir, exist_ok=True)
            temp_file = os.path.join(temp_dir, f"temp_{source_file}")
            
            try:
                # 获取音频信息
                source_info = self.get_audio_info(source_path)
                target_info = self.get_audio_info(target_path)
                
                # 获取目标文件的精确时长
                target_duration = target_info["duration"]
                
                # 第一步：将源文件转换为目标文件的采样率和通道数
                convert_command = [
                    "ffmpeg", "-y",
                    "-i", source_path,
                    "-ac", str(target_info["channels"]),
                    "-ar", str(target_info["sample_rate"]),
                    temp_file
                ]
                
                process = subprocess.Popen(convert_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()
                
                if process.returncode != 0:
                    raise Exception(f"FFmpeg 错误 (转换): {stderr.decode('utf-8', errors='ignore')}")
                
                # 检查转换后文件的时长
                converted_info = self.get_audio_info(temp_file)
                source_duration = converted_info["duration"]
                
                # 第二步：无论如何都强制调整时长为目标时长
                if source_duration < target_duration:
                    # 源音频较短，添加静音
                    silence_command = [
                        "ffmpeg", "-y",
                        "-i", temp_file,
                        "-af", f"apad=pad_dur={target_duration - source_duration}",
                        "-t", str(target_duration),  # 强制设置输出文件时长
                        output_path
                    ]
                    
                    process = subprocess.Popen(silence_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = process.communicate()
                    
                    if process.returncode != 0:
                        raise Exception(f"FFmpeg 错误 (添加静音): {stderr.decode('utf-8', errors='ignore')}")
                else:
                    # 源音频较长或相等，直接设置精确时长
                    trim_command = [
                        "ffmpeg", "-y",
                        "-i", temp_file,
                        "-t", str(target_duration),  # 强制精确时长
                        "-af", "asetpts=PTS-STARTPTS",  # 确保时间戳从0开始
                        output_path
                    ]
                    
                    process = subprocess.Popen(trim_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = process.communicate()
                    
                    if process.returncode != 0:
                        raise Exception(f"FFmpeg 错误 (精确时长): {stderr.decode('utf-8', errors='ignore')}")
                
                # 验证输出文件时长
                output_info = self.get_audio_info(output_path)
                output_duration = output_info["duration"]
                
                # 如果时长仍然不匹配，进行最后的强制处理
                if abs(output_duration - target_duration) > 0.001:  # 允许1毫秒的误差
                    self.status_label.config(text=f"进行最终时长修正: {output_duration} -> {target_duration}")
                    
                    # 创建一个精确时长的静音文件
                    silence_path = os.path.join(temp_dir, "silence.wav")
                    silence_command = [
                        "ffmpeg", "-y",
                        "-f", "lavfi",
                        "-i", f"anullsrc=channel_layout=stereo:sample_rate={target_info['sample_rate']}",
                        "-t", str(target_duration),
                        silence_path
                    ]
                    
                    process = subprocess.Popen(silence_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = process.communicate()
                    
                    if process.returncode != 0:
                        raise Exception(f"FFmpeg 错误 (创建静音): {stderr.decode('utf-8', errors='ignore')}")
                    
                    # 混合当前输出和静音文件，采用最短文件的时长（即目标时长）
                    final_command = [
                        "ffmpeg", "-y",
                        "-i", output_path,
                        "-i", silence_path,
                        "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=shortest:dropout_transition=0,volume=2",
                        "-t", str(target_duration),  # 最后再次确保时长精确
                        os.path.join(temp_dir, "final_output.wav")
                    ]
                    
                    process = subprocess.Popen(final_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = process.communicate()
                    
                    if process.returncode != 0:
                        raise Exception(f"FFmpeg 错误 (最终混合): {stderr.decode('utf-8', errors='ignore')}")
                    
                    # 将最终输出移动到目标位置
                    os.replace(os.path.join(temp_dir, "final_output.wav"), output_path)
                    
                    # 删除临时静音文件
                    if os.path.exists(silence_path):
                        os.remove(silence_path)
                
                # 清理临时文件
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                
                completed += 1
                self.progress_bar["value"] = completed
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"处理 {source_file} 时出错: {str(e)}"))
                self.status_label.config(text=f"错误: {str(e)}")
                return
        
        # 清理临时目录
        try:
            os.rmdir(temp_dir)
        except:
            pass
        
        self.status_label.config(text=f"完成! 已转换 {completed} 个文件")
        self.root.after(0, lambda: messagebox.showinfo("完成", f"已成功转换 {completed} 个文件"))
    
    def get_audio_info(self, file_path):
        """获取音频文件的信息（频道数、采样率、采样大小和时长）"""
        command = ["ffprobe", "-v", "error", "-show_entries", 
                  "stream=channels,sample_rate:format=duration", 
                  "-of", "json", file_path]
        
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"FFprobe 错误: {stderr.decode('utf-8', errors='ignore')}")
        
        info = json.loads(stdout)
        
        # 获取音频属性
        audio_stream = info.get("streams", [{}])[0]
        format_info = info.get("format", {})
        
        return {
            "channels": int(audio_stream.get("channels", 2)),
            "sample_rate": int(audio_stream.get("sample_rate", 44100)),
            "duration": float(format_info.get("duration", 0))
        }

if __name__ == "__main__":
    root = tk.Tk()
    app = AudioConverter(root)
    root.mainloop() 