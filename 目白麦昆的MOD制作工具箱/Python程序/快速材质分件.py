import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk  # 需要安装 Pillow 库
import os
import shutil
from collections import defaultdict, deque
from functools import partial

# VMT文件替换内容（组件材质）
VMT_REPLACEMENT = """VertexlitGeneric
{
    $no_draw "1"
    $nodecal "1"
    $zero "0"
    "Proxies"
    {
        Equals
        {
            srcVar1     "$zero"
            resultVar   "$alpha"
        }
    }
}
"""

class ScrollableFrame(ttk.Frame):
    """
    A scrollable frame that can scroll both vertically and horizontally.
    """
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        # 创建 Canvas
        self.canvas = tk.Canvas(self, borderwidth=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        # 创建纵向和横向滚动条
        self.scrollbar_v = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollbar_v.grid(row=0, column=1, sticky="ns")
        
        self.scrollbar_h = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.scrollbar_h.grid(row=1, column=0, sticky="ew")
        
        # 配置 Canvas 的滚动命令
        self.canvas.configure(yscrollcommand=self.scrollbar_v.set, xscrollcommand=self.scrollbar_h.set)
        
        # 创建内部 Frame
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # 将内部 Frame 添加到 Canvas
        self.window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        # 绑定配置事件，确保滚动区域正确更新
        self.scrollable_frame.bind("<Configure>", self.on_frame_configure)
        
        # 使 ScrollableFrame 可扩展
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def on_frame_configure(self, event):
        # 更新滚动区域
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

class FileSelector:
    def __init__(self, master, index, app):
        self.app = app
        self.index = index
        self.selected_files = []

        # 创建文件选择块的框架
        self.frame = ttk.Frame(master.scrollable_frame, relief="groove", padding=5, width=450, height=500)
        self.frame.grid_propagate(False)  # 禁用自动调整大小
        self.frame.grid(row=0, column=index, padx=5, pady=5)

        # 文件块名称
        ttk.Label(self.frame, text="文件块名称：").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.name_entry = ttk.Entry(self.frame, width=20)
        self.name_entry.grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.name_entry.bind("<KeyRelease>", lambda event: self.app.update_parent_menus())

        # 选择文件按钮
        ttk.Button(self.frame, text="选择文件", command=self.choose_files).grid(row=2, column=0, padx=5, pady=2, sticky="w")

        # 删除按钮
        ttk.Button(self.frame, text="删除", command=partial(self.app.remove_file_selector, self)).grid(row=3, column=0, padx=5, pady=2, sticky="w")

        # 文件显示区域（添加独立垂直滚动条）
        self.file_display_container = ttk.Frame(self.frame)
        self.file_display_container.grid(row=4, column=0, padx=5, pady=2, sticky="nsew")
        self.frame.grid_rowconfigure(4, weight=1)

        self.file_display_scrollable = ScrollableFrame(self.file_display_container)
        self.file_display_scrollable.pack(fill=tk.BOTH, expand=True)

        self.file_display_frame = self.file_display_scrollable.scrollable_frame

        # 选项框
        options_frame = ttk.Frame(self.frame)
        options_frame.grid(row=5, column=0, padx=5, pady=2, sticky="w")

        self.component_material_var = tk.BooleanVar()
        self.emissive_var = tk.BooleanVar()
        self.parent_checkbox_var = tk.BooleanVar()

        ttk.Checkbutton(options_frame, text="组件材质", variable=self.component_material_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(options_frame, text="夜光组件", variable=self.emissive_var).grid(row=1, column=0, sticky="w")

        self.parent_checkbox = ttk.Checkbutton(options_frame, text="设定父级", variable=self.parent_checkbox_var, command=self.toggle_parent_options)
        self.parent_checkbox.grid(row=2, column=0, sticky="w")

        self.parent_menu_var = tk.StringVar()
        self.parent_menu = ttk.Combobox(options_frame, textvariable=self.parent_menu_var, state="disabled", width=18)
        self.parent_menu.grid(row=3, column=0, pady=2, sticky="w")
        self.parent_menu.bind("<<ComboboxSelected>>", lambda event: self.app.update_menu_states_for_all())

        # Add hierarchy selection
        # Use Level
        self.use_level_var = tk.BooleanVar()
        self.use_level_checkbox = ttk.Checkbutton(options_frame, text="使用指定层级", variable=self.use_level_var, command=self.toggle_level_options)
        self.use_level_checkbox.grid(row=4, column=0, sticky="w", pady=(10, 0))

        self.level_choice_var = tk.StringVar()
        self.level_choice_menu = ttk.Combobox(options_frame, textvariable=self.level_choice_var, state="disabled", width=18)
        self.level_choice_menu.grid(row=5, column=0, pady=2, sticky="w")
        self.level_choice_menu.bind("<<ComboboxSelected>>", lambda event: self.app.update_menu_states_for_all())

    def toggle_parent_options(self):
        if self.parent_checkbox_var.get():
            self.parent_menu.config(state="readonly")
        else:
            self.parent_menu.set("")
            self.parent_menu.config(state="disabled")
        self.app.update_parent_menus()  # 立即更新父级菜单

    def toggle_level_options(self):
        """
        启用或禁用层级选择菜单。
        """
        if self.use_level_var.get():
            # 启用层级选择时，刷新菜单
            choices = self.app.get_level_choices()
            self.level_choice_menu['values'] = choices
            self.level_choice_menu.config(state="readonly")
            if self.level_choice_var.get() not in choices:
                self.level_choice_var.set("")  # 如果当前值无效，清空选择
        else:
            # 禁用层级选择时，清空选择
            self.level_choice_menu.set("")
            self.level_choice_menu['values'] = []
            self.level_choice_menu.config(state="disabled")
        self.app.update_parent_menus()  # 更新父级菜单


    def choose_files(self):
    # 如果全局开关开启，并且有默认路径，则使用默认路径
        if self.app.use_default_path_var.get() and self.app.default_file_path:
            initial_path = self.app.default_file_path
        else:
            # 默认路径为空或未开启时，从输入框路径获取
            initial_path = self.app.input_path_display.get().strip()

        if not initial_path or not os.path.exists(initial_path):
            messagebox.showerror("错误", "请输入有效的输入路径")
            return

        file_paths = filedialog.askopenfilenames(initialdir=initial_path, title="选择 VMT 文件", filetypes=[("VMT Files", "*.vmt")])
        if file_paths:
            self.selected_files = file_paths
            # 更新默认路径为当前选择的文件的目录
            if self.app.use_default_path_var.get():
                self.app.default_file_path = os.path.dirname(file_paths[0])

            # 清空之前的显示
            for widget in self.file_display_frame.winfo_children():
                widget.destroy()
            for path in self.selected_files:
                ttk.Label(self.file_display_frame, text=os.path.basename(path), anchor="w").pack(fill="x", padx=5, pady=2)
            self.file_display_scrollable.canvas.configure(scrollregion=self.file_display_scrollable.canvas.bbox("all"))
        self.app.update_stats()
        self.app.update_menu_states_for_all()


class MaterialSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("快速材质分件  此MOD由B站メジロ_McQueen与GPT共同开发，禁止一切形式的再分发与修改行为")
        self.root.geometry("1200x800")  # 调整窗口大小以适应布局
        self.root.minsize(800, 600)

        # 创建主滚动框架（全局垂直和水平滚动条）
        self.main_scrollable = ScrollableFrame(root)
        self.main_scrollable.pack(fill=tk.BOTH, expand=True)

        # 创建主内容框架
        main_content = self.main_scrollable.scrollable_frame
        main_content.columnconfigure(0, weight=1)
        main_content.rowconfigure(1, weight=1)
        main_content.rowconfigure(2, weight=1)
        main_content.rowconfigure(3, weight=0)
        main_content.rowconfigure(4, weight=0)

        # 顶部路径选择框
        top_frame = ttk.Frame(main_content, padding=10)
        top_frame.grid(row=0, column=0, sticky="ew", pady=10)

        # 修改列权重，确保布局对称
        top_frame.columnconfigure(0, weight=0)  # 输入标签列
        top_frame.columnconfigure(1, weight=1)  # 输入路径输入框列（可拉伸）
        top_frame.columnconfigure(2, weight=0)  # 按钮列
        top_frame.columnconfigure(3, weight=0)  # 输出标签列
        top_frame.columnconfigure(4, weight=1)  # 输出路径输入框列（可拉伸）
        top_frame.columnconfigure(5, weight=0)  # 按钮列

        # 输入路径
        input_path_label = ttk.Label(top_frame, text="请选择输入路径：")
        input_path_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.input_path_display = ttk.Entry(top_frame)
        self.input_path_display.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.input_path_display.config(state="readonly")

        choose_input_button = ttk.Button(top_frame, text="选择路径", command=self.choose_input_directory)
        choose_input_button.grid(row=0, column=2, padx=5, pady=5, sticky="w")

        # 输出路径
        output_path_label = ttk.Label(top_frame, text="请选择输出路径：")
        output_path_label.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        self.output_path_display = ttk.Entry(top_frame)
        self.output_path_display.grid(row=0, column=4, padx=5, pady=5, sticky="ew")
        self.output_path_display.config(state="readonly")

        choose_output_button = ttk.Button(top_frame, text="选择路径", command=self.choose_output_directory)
        choose_output_button.grid(row=0, column=5, padx=5, pady=5, sticky="w")

        # 中部框架（左侧：图片，右侧：文件夹层级）
        middle_frame = ttk.Frame(main_content, padding=10)
        middle_frame.grid(row=1, column=0, sticky="nsew")
        middle_frame.columnconfigure(0, weight=1)
        middle_frame.columnconfigure(1, weight=1)
        middle_frame.rowconfigure(0, weight=1)

        # 中部左侧：图片选择与预览
        left_middle_frame = ttk.Frame(middle_frame)
        left_middle_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        left_middle_frame.columnconfigure(0, weight=1)
        left_middle_frame.rowconfigure(1, weight=1)

        # 图片选择与预览
        image_frame = ttk.LabelFrame(left_middle_frame, text="图片选择")
        image_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        image_frame.columnconfigure(0, weight=1)
        image_frame.rowconfigure(1, weight=1)

        image_buttons_frame = ttk.Frame(image_frame)
        image_buttons_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        image_buttons_frame.columnconfigure(1, weight=1)

        choose_image_button = ttk.Button(image_buttons_frame, text="选择图片", command=self.choose_image)
        choose_image_button.grid(row=0, column=0, padx=5, pady=5)

        # 固定图片预览区域大小
        self.image_preview = tk.Label(image_frame, background="#f0f0f0", width=200, height=200, anchor="center")
        self.image_preview.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

        self.selected_image = None  # 用于存储加载的图片路径
        self.image_path = ""  # Initialize image_path

        # 中部右侧：文件夹层级选择
        right_middle_frame = ttk.Frame(middle_frame)
        right_middle_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_middle_frame.columnconfigure(0, weight=1)
        right_middle_frame.rowconfigure(1, weight=1)

        folder_level_label = ttk.Label(right_middle_frame, text="文件夹层级：")
        folder_level_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        # 文件夹层级选择区域（固定大小）
        self.folder_levels_scrollable = ScrollableFrame(right_middle_frame)
        self.folder_levels_scrollable.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.folder_levels_scrollable.canvas.config(width=540, height=960)
        self.folder_levels_scrollable.grid_propagate(False)  # 禁用自动调整大小

        add_folder_level_button = ttk.Button(right_middle_frame, text="添加层级", command=self.add_folder_level)
        add_folder_level_button.grid(row=2, column=0, pady=5)

        # 下部框架：文件块选择区域
        lower_frame = ttk.Frame(main_content, padding=10)
        lower_frame.grid(row=2, column=0, sticky="nsew")
        lower_frame.columnconfigure(0, weight=1)
        lower_frame.rowconfigure(1, weight=1)

        # 添加文件块按钮和全局配置
        controls_frame = ttk.Frame(lower_frame)
        controls_frame.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        # 全局变量存储默认路径
        self.default_file_path = None  # 默认文件路径，初始化为空
        self.use_default_path_var = tk.BooleanVar(value=True)  # 开关状态，默认开启

        # 开关选项添加到界面
        path_options_frame = ttk.Frame(controls_frame)
        path_options_frame.grid(row=0, column=4, padx=20, pady=5, sticky="w")

        use_default_path_checkbox = ttk.Checkbutton(
            path_options_frame,
            text="新文件块使用默认路径",
            variable=self.use_default_path_var
        )
        use_default_path_checkbox.grid(row=0, column=0, sticky="w")

        # 添加文件选择块按钮
        add_file_button = ttk.Button(controls_frame, text="添加文件选择块", command=self.add_file_selector)
        add_file_button.grid(row=0, column=0, padx=5, pady=5)

        # 批量添加固定名称选项
        batch_prefix_frame = ttk.Frame(controls_frame)
        batch_prefix_frame.grid(row=0, column=1, padx=20, pady=5, sticky="w")

        self.batch_prefix_var = tk.BooleanVar()
        self.batch_prefix_checkbox = ttk.Checkbutton(
            batch_prefix_frame,
            text="MOD标题",
            variable=self.batch_prefix_var,
            command=self.toggle_batch_prefix
        )
        self.batch_prefix_checkbox.grid(row=0, column=0, sticky="w")
        self.batch_prefix_entry = ttk.Entry(batch_prefix_frame, width=25, state="disabled")
        self.batch_prefix_entry.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        # 作者名称选项
        author_frame = ttk.Frame(controls_frame)
        author_frame.grid(row=0, column=3, padx=20, pady=5, sticky="w")

        self.author_name_var = tk.BooleanVar()
        self.author_name_checkbox = ttk.Checkbutton(
            author_frame,
            text="作者名称",
            variable=self.author_name_var,
            command=self.toggle_author_name_entry
        )
        self.author_name_checkbox.grid(row=0, column=0, sticky="w")

        self.author_name_entry = ttk.Entry(author_frame, width=25, state="disabled")
        self.author_name_entry.grid(row=0, column=1, padx=5, pady=2, sticky="w")


        # AddonDescription 名称输入选项
        addon_desc_frame = ttk.Frame(controls_frame)
        addon_desc_frame.grid(row=0, column=2, padx=20, pady=5, sticky="w")

        self.addon_desc_var = tk.BooleanVar()
        self.addon_desc_checkbox = ttk.Checkbutton(
            addon_desc_frame,
            text="人物名称",
            variable=self.addon_desc_var,
            command=self.toggle_addon_desc
        )
        self.addon_desc_checkbox.grid(row=0, column=0, sticky="w")
        self.addon_desc_entry = ttk.Entry(addon_desc_frame, width=25, state="disabled")
        self.addon_desc_entry.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        # 文件块选择区域（固定高度和宽度）
        self.file_selectors_scrollable = ScrollableFrame(lower_frame, width=1920, height=540)
        self.file_selectors_scrollable.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.file_selectors_scrollable.canvas.config(width=1920, height=540)
        self.file_selectors_scrollable.grid_propagate(False)  # 禁止自动调整大小

        # 状态显示
        stats_frame = ttk.Frame(main_content, padding=10)
        stats_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        stats_frame.columnconfigure(0, weight=1)

        self.file_block_count_label = ttk.Label(stats_frame, text="文件块总数：0")
        self.file_block_count_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.empty_file_block_count_label = ttk.Label(stats_frame, text="空文件块数：0")
        self.empty_file_block_count_label.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        self.folder_level_count_label = ttk.Label(stats_frame, text="文件夹层级数：0")
        self.folder_level_count_label.grid(row=0, column=2, padx=10, pady=5, sticky="w")

        # 底部按钮
        button_frame = ttk.Frame(main_content, padding=10)
        button_frame.grid(row=4, column=0, pady=10)
        button_frame.columnconfigure(0, weight=1)

        split_button = ttk.Button(button_frame, text="一键分件！", command=self.one_click_split, width=20)
        split_button.grid(row=0, column=0, padx=5, pady=5)

        # 数据结构
        self.file_selectors = []
        self.folder_levels = []
        self.selector_index = 0

        # 初始化界面
        self.update_stats()
        self.update_menu_states_for_all()


    def toggle_author_name_entry(self):
        """
        启用或禁用作者名称输入框。
        """
        if self.author_name_var.get():
            self.author_name_entry.config(state="normal")  # 启用输入框
        else:
            self.author_name_entry.delete(0, tk.END)  # 清空输入框
            self.author_name_entry.config(state="disabled")  # 禁用输入框

    def toggle_batch_prefix(self):
        if self.batch_prefix_var.get():
            self.batch_prefix_entry.config(state="normal")
        else:
            self.batch_prefix_entry.delete(0, tk.END)
            self.batch_prefix_entry.config(state="disabled")

    def toggle_addon_desc(self):
        if self.addon_desc_var.get():
            self.addon_desc_entry.config(state="normal")
        else:
            self.addon_desc_entry.delete(0, tk.END)
            self.addon_desc_entry.config(state="disabled")

    def choose_input_directory(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.input_path_display.config(state="normal")
            self.input_path_display.delete(0, tk.END)
            self.input_path_display.insert(0, folder_path)
            self.input_path_display.config(state="readonly")

            # 重置默认文件选择路径
            self.default_file_path = None
            self.update_parent_menus()

    def choose_output_directory(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.output_path_display.config(state="normal")
            self.output_path_display.delete(0, tk.END)
            self.output_path_display.insert(0, folder_path)
            self.output_path_display.config(state="readonly")

    def choose_image(self):
        image_path = filedialog.askopenfilename(title="选择JPG图片", filetypes=[("JPG Files", "*.jpg"), ("JPEG Files", "*.jpeg")])
        if image_path:
            try:
                image = Image.open(image_path)
                image.thumbnail((200, 200))  # 调整大小以适应预览区域
                self.selected_image = ImageTk.PhotoImage(image)
                self.image_preview.config(image=self.selected_image, width=200, height=200)
                self.image_path = image_path  # 存储选择的图片路径
            except Exception as e:
                messagebox.showerror("错误", f"无法加载图片：{e}")

    def add_folder_level(self):
        # 计算当前层级数
        current_level_num = len(self.folder_levels) + 1
        if current_level_num > 10:
            messagebox.showwarning("警告", "最多只能添加10个文件夹层级！")
            return

        # 创建层级输入框
        level_frame = ttk.Frame(self.folder_levels_scrollable.scrollable_frame, padding=2)
        level_frame.grid(row=current_level_num-1, column=0, sticky="ew", padx=5, pady=2)
        level_frame.columnconfigure(1, weight=1)

        ttk.Label(level_frame, text=f"第{current_level_num}级：").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        level_entry = ttk.Entry(level_frame, width=15)
        level_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        # 删除按钮
        delete_button = ttk.Button(level_frame, text="删除", width=5, command=lambda: self.remove_folder_level(level_frame, level_entry))
        delete_button.grid(row=0, column=2, padx=5, pady=2, sticky="w")

        self.folder_levels.append(level_entry)
        self.update_level_choices()
        self.update_stats()
        self.update_menu_states_for_all()

    def remove_folder_level(self, frame, entry):
        frame.destroy()
        self.folder_levels.remove(entry)
        self.update_level_choices()
        self.update_stats()
        self.update_menu_states_for_all()

    def get_level_choices(self):
        # 从最高层级到最低层级排序，确保层级文件夹顺序正确
        return [entry.get().strip() for entry in self.folder_levels if entry.get().strip()]

    def add_file_selector(self):
        file_selector = FileSelector(self.file_selectors_scrollable, self.selector_index, self)
        self.file_selectors.append(file_selector)
        self.selector_index += 1
        self.update_level_choices()
        self.update_stats()
        self.update_menu_states_for_all()

    def remove_file_selector(self, file_selector):
        if file_selector in self.file_selectors:
            self.file_selectors.remove(file_selector)  # 从列表中移除
            file_selector.frame.destroy()  # 销毁对应的界面组件
            self.update_level_choices()  # 更新层级选择菜单
            self.update_stats()  # 更新状态统计信息
            self.update_menu_states_for_all()  # 更新菜单状态


    def update_parent_menus(self):
        # 更新所有父级下拉菜单的选项，避免循环引用
        current_names = [fs.name_entry.get().strip() for fs in self.file_selectors if fs.name_entry.get().strip()]
        for fs in self.file_selectors:
            if fs.parent_checkbox_var.get():
                current_name = fs.name_entry.get().strip()
                options = [name for name in current_names if name != current_name]
                fs.parent_menu['values'] = options
                # 自动刷新显示
                if fs.parent_menu_var.get() not in options:
                    fs.parent_menu_var.set("")
            else:
                fs.parent_menu['values'] = []
                fs.parent_menu.set("")
        self.update_menu_states_for_all()

    def update_level_choices(self):
        # 更新所有文件选择块的层级选择菜单
        choices = self.get_level_choices()
        for fs in self.file_selectors:
            if fs.use_level_var.get():
                fs.level_choice_menu['values'] = choices
                if fs.level_choice_var.get() not in choices:
                    fs.level_choice_var.set("")
                fs.level_choice_menu.config(state="readonly")
            else:
                fs.level_choice_menu.set("")
                fs.level_choice_menu['values'] = []
                fs.level_choice_menu.config(state="disabled")
        self.update_menu_states_for_all()

    def update_stats(self):
        total_blocks = len(self.file_selectors)
        empty_blocks = sum(1 for fs in self.file_selectors if not fs.name_entry.get().strip() or not fs.selected_files)
        total_levels = len(self.folder_levels)
        self.file_block_count_label.config(text=f"文件块总数：{total_blocks}")
        self.empty_file_block_count_label.config(text=f"空文件块数：{empty_blocks}")
        self.folder_level_count_label.config(text=f"文件夹层级数：{total_levels}")

    def update_menu_states_for_all(self):
        # 根据父子关系和层级选择更新层级和父级菜单的可用性
        current_names = [fs.name_entry.get().strip() for fs in self.file_selectors if fs.name_entry.get().strip()]
        for fs in self.file_selectors:
            # Update parent_menu state
            if fs.parent_checkbox_var.get():
                fs.parent_menu.config(state="readonly")
            else:
                fs.parent_menu.set("")
                fs.parent_menu.config(state="disabled")
            
            # Update level_choice_menu state
            if fs.use_level_var.get():
                fs.level_choice_menu.config(state="readonly")
            else:
                fs.level_choice_menu.set("")
                fs.level_choice_menu.config(state="disabled")
        self.update_stats()

    def one_click_split(self):
        input_path = self.input_path_display.get().strip()
        output_path = self.output_path_display.get().strip()
        image_path = getattr(self, 'image_path', '').strip()
        batch_prefix = self.batch_prefix_entry.get().strip() if self.batch_prefix_var.get() else ""
        addon_desc_name = self.addon_desc_entry.get().strip() if self.addon_desc_var.get() else ""

        if not input_path or not output_path:
            messagebox.showerror("错误", "请输入输入和输出路径")
            return

        if not os.path.exists(input_path):
            messagebox.showerror("错误", "输入路径不存在")
            return

        if not os.path.exists(output_path):
            messagebox.showerror("错误", "输出路径不存在")
            return

        # 获取文件夹层级
        additional_folders = self.get_level_choices()
        if not additional_folders:
            messagebox.showerror("错误", "请至少添加一个文件夹层级")
            return

        # 检查至少设置了必要的层级（根据需求调整，假设至少1层）
        if len(additional_folders) < 1:
            messagebox.showerror("错误", "请至少设置一个文件夹层级")
            return

        # 检查空文件块或空名称块
        for fs in self.file_selectors:
            name = fs.name_entry.get().strip()
            files = fs.selected_files
            if not name or not files:
                messagebox.showerror("错误", "存在空名称或无文件的文件块，请修改后再分件")
                return

        # 构建父子级关系图，确保子级先于父级
        graph = defaultdict(list)  # key: parent index, value: list of child indices
        indegree = defaultdict(int)  # key: index, value: number of parents

        name_to_index = {fs.name_entry.get().strip(): idx for idx, fs in enumerate(self.file_selectors)}
        for idx, fs in enumerate(self.file_selectors):
            parent_name = fs.parent_menu_var.get().strip()
            if parent_name:
                parent_idx = name_to_index.get(parent_name)
                if parent_idx is None:
                    messagebox.showerror("错误", f"父级名称 '{parent_name}' 未找到对应的文件块。")
                    return
                graph[parent_idx].append(idx)
                indegree[idx] += 1

        # 拓扑排序（确保子级先于父级）
        queue = deque([idx for idx in range(len(self.file_selectors)) if indegree[idx] == 0])
        sorted_indices = []

        while queue:
            current = queue.popleft()
            sorted_indices.append(current)
            for neighbor in graph[current]:
                indegree[neighbor] -= 1
                if indegree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_indices) != len(self.file_selectors):
            messagebox.showerror("错误", "检测到循环的父子级关系，请检查后重试。")
            return

        # 分配层级（从子级到父级）
        # depth_map: key: index, value: depth (1: 第一级, 2: 第二级, ...)
        depth_map = {}
        children_map = defaultdict(list)  # key: parent index, value: list of child indices

        for parent, children in graph.items():
            for child in children:
                children_map[parent].append(child)

        # 逆拓扑排序，从叶子节点开始
        reversed_sorted = sorted_indices[::-1]
        for idx in reversed_sorted:
            fs = self.file_selectors[idx]
            # 如果文件块没有子级，则为第一级
            if not children_map[idx]:
                if fs.use_level_var.get():
                    chosen_level = fs.level_choice_var.get()
                    if chosen_level not in additional_folders:
                        messagebox.showerror("错误", f"文件块 '{fs.name_entry.get().strip()}' 选择的层级 '{chosen_level}' 无效。")
                        return
                    chosen_level_idx = additional_folders.index(chosen_level) + 1  # 深度从1开始
                    depth_map[idx] = chosen_level_idx
                else:
                    depth_map[idx] = 1
            else:
                # 有子级，层级为子级最大深度 +1
                child_depths = [depth_map[child] for child in children_map[idx]]
                max_child_depth = max(child_depths) if child_depths else 0
                depth_map[idx] = max_child_depth + 1

        # 验证层级深度不超过定义的层级数
        max_depth = max(depth_map.values()) if depth_map else 0
        if max_depth > len(additional_folders):
            messagebox.showerror("错误", f"层级深度 {max_depth} 超过了设置的文件夹层级数 {len(additional_folders)}。请调整父子级关系或增加文件夹层级。")
            return

        # 复制文件并生成 addoninfo.txt
        for idx in sorted_indices:
            fs = self.file_selectors[idx]
            original_name = fs.name_entry.get().strip()
            selected_files = fs.selected_files
            component_material = fs.component_material_var.get()
            emissive = fs.emissive_var.get()
            depth = depth_map.get(idx, 1)
            folder_level_name = additional_folders[depth - 1]  # list index从0开始

            # 构建最终的文件块名称，关前面加一个空格
            if self.batch_prefix_var.get() and self.batch_prefix_entry.get().strip():
                final_name = f"{self.batch_prefix_entry.get().strip()} {original_name} 关"
            else:
                final_name = f"{original_name} 关"

            # 构建完整路径
            relative_original_path = self.get_relative_original_path(selected_files[0], input_path=input_path)
            final_path = os.path.join(output_path, final_name, relative_original_path, folder_level_name)

            os.makedirs(final_path, exist_ok=True)

            # 定义 addoninfo.txt 的路径，放在 final_name 目录下
            addoninfo_path = os.path.join(output_path, final_name, "addoninfo.txt")

            for file_path in selected_files:
                if not os.path.exists(file_path):
                    continue
                dest_file = os.path.join(final_path, os.path.basename(file_path))
                shutil.copy(file_path, dest_file)
                if dest_file.lower().endswith(".vmt"):
                    self.modify_vmt_content(dest_file, component_material, emissive)

            # 生成 addoninfo.txt
            try:
                addoninfo_content = self.generate_addoninfo_content(
                    fs, final_name, idx, graph, name_to_index, batch_prefix, addon_desc_name
                )
                with open(addoninfo_path, "w", encoding="utf-8") as addon_file:
                    addon_file.write(addoninfo_content)
            except Exception as e:
                messagebox.showerror("错误", f"生成 addoninfo.txt 时出错：{e}")
                return

            # 复制图片到与 materials 同级的目录
            if image_path:
                try:
                    # 查找是否有包含 "materials" 的文件路径
                    for file_selector_inner in self.file_selectors:
                        for file_path_inner in file_selector_inner.selected_files:
                            if "materials" in file_path_inner:
                                # 计算 materials 同级的父级目录路径
                                relative_original_path_inner = self.get_relative_original_path(file_path_inner, input_path=input_path)
                                split_path_inner = relative_original_path_inner.split(os.sep)
                                try:
                                    materials_index_inner = split_path_inner.index("materials")  # 定位 materials
                                except ValueError:
                                    continue  # 如果没有找到 'materials'，跳过
                                parent_path_parts_inner = split_path_inner[:materials_index_inner]  # 提取 materials 上级路径
                                parent_folder_path_inner = os.path.join(output_path, final_name, *parent_path_parts_inner)

                                # 确保目标文件夹存在
                                os.makedirs(parent_folder_path_inner, exist_ok=True)

                                # 复制图片到目标路径（与 materials 同级）
                                shutil.copy(image_path, parent_folder_path_inner)
                                break  # 每个文件块只需要复制一次图片
                except Exception as e:
                    messagebox.showerror("错误", f"复制图片时出错：{e}")
                    return
                
        # 额外步骤：将所有子级文件复制到父级对应的层级文件夹
        for parent_idx, children in graph.items():
            parent_fs = self.file_selectors[parent_idx]
            parent_name = parent_fs.name_entry.get().strip()
            parent_depth = depth_map.get(parent_idx, 1)
            parent_folder_level_name = additional_folders[parent_depth - 1]
            relative_original_path = self.get_relative_original_path(parent_fs.selected_files[0], input_path=input_path)

            # 构建父级文件夹名称，考虑 batch_prefix_entry
            if self.batch_prefix_var.get() and self.batch_prefix_entry.get().strip():
                parent_final_name = f"{self.batch_prefix_entry.get().strip()} {parent_name} 关"
            else:
                parent_final_name = f"{parent_name} 关"

            # 拼接父级的最终路径
            parent_final_path = os.path.join(output_path, parent_final_name, relative_original_path, parent_folder_level_name)
            os.makedirs(parent_final_path, exist_ok=True)  # 确保路径存在

            # 获取所有子级（包括嵌套子级）的索引
            all_descendants = self.get_all_descendants(parent_idx, graph)

            for child_idx in all_descendants:
                child_fs = self.file_selectors[child_idx]
                for file_path in child_fs.selected_files:
                    if not os.path.exists(file_path):
                        continue

                    # 生成目标文件路径
                    dest_file = os.path.join(parent_final_path, os.path.basename(file_path))

                    # 确保目标文件夹存在
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)

                    # 复制文件
                    shutil.copy(file_path, dest_file)

                    # 修改 .vmt 文件内容
                    if dest_file.lower().endswith(".vmt"):
                        self.modify_vmt_content(dest_file, child_fs.component_material_var.get(), child_fs.emissive_var.get())



        messagebox.showinfo("完成", "所有文件块已成功输出")

    def get_all_descendants(self, parent_idx, graph):
        """
        获取指定父级的所有子级（递归）
        """
        descendants = []
        queue = deque([parent_idx])
        while queue:
            current = queue.popleft()
            for child in graph[current]:
                if child not in descendants:
                    descendants.append(child)
                    queue.append(child)
        return descendants

    def get_hierarchy_names(self, idx, name_to_index, depth_map):
        """
        根据文件块的索引，返回其在输出路径中的层级名称列表。
        例如，文件块2的父级是文件块1，文件块1的父级是文件块3，则返回 ['第三', '第一', '第二']
        """
        hierarchy = []
        current_idx = idx
        while True:
            fs = self.file_selectors[current_idx]
            hierarchy.insert(0, fs.name_entry.get().strip())
            parent_name = fs.parent_menu_var.get().strip()
            if parent_name:
                parent_idx = name_to_index.get(parent_name)
                if parent_idx is None:
                    break
                current_idx = parent_idx
            else:
                break
        return hierarchy

    def get_relative_original_path(self, file_path, input_path):
        """
        从文件路径中提取相对于'materials/'的路径，直到倒数第二个文件夹。
        例如：
            file_path: /path/to/materials/1/2/3/file.vmt
            input_path: /path/to/materials/1/2/3/
            返回: materials/1/2
        """
        # 规范路径
        file_path = os.path.abspath(file_path)
        input_path = os.path.abspath(input_path)

        # 查找'materials'在路径中的位置
        materials_dir = "materials"
        split_path = file_path.split(os.sep)
        try:
            materials_index = split_path.index(materials_dir)
        except ValueError:
            messagebox.showerror("错误", f"文件路径 '{file_path}' 不包含 'materials/' 文件夹。")
            raise ValueError("文件路径不包含 'materials/'")

        # 提取从'materials/'开始的路径，直到倒数第二个文件夹
        relative_parts = split_path[materials_index:-1]  # 包括'materials'，不包括最后一个文件夹
        relative_path = os.path.join(*relative_parts) if relative_parts else ""
        return relative_path

    def modify_vmt_content(self, dest_file, component_material, emissive):
        if not dest_file.lower().endswith(".vmt"):
            return
        if emissive:
            # Emissive优先
            if not os.path.exists(dest_file):
                return
            with open(dest_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            found_emissive_enabled = False
            for i, line in enumerate(lines):
                if "$EmissiveBlendEnabled" in line and '"1"' in line:
                    lines[i] = line.replace('"1"', '"0"')
                    found_emissive_enabled = True
                    break
            if not found_emissive_enabled:
                # 在倒数第三行插入$selfillum "0"
                insert_line_index = len(lines) - 2  # 倒数第三行的索引
                if insert_line_index < 0:
                    insert_line_index = 0
                lines.insert(insert_line_index, '    "$selfillum" "0"\n')  # 添加四个空格，缩进
            with open(dest_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
        else:
            # 非Emissive模式
            if component_material:
                # 全覆盖
                try:
                    with open(dest_file, "w", encoding="utf-8") as vmt_file:
                        vmt_file.write(VMT_REPLACEMENT)
                except Exception as e:
                    messagebox.showerror("错误", f"修改 VMT 文件时出错：{e}")

    def generate_addoninfo_content(self, fs, final_name, idx, graph, name_to_index, batch_prefix, addon_desc_name):
        """
        根据文件块的配置生成 addoninfo.txt 的内容。
        """
        # Construct addontitle without brackets and add a space before "关"
        addontitle = f'addontitle "{final_name}"\n'
        original_name = fs.name_entry.get().strip()

        # Construct addonDescription
        if addon_desc_name:
            addon_description = f'addonDescription "此MOD为{addon_desc_name}人物的可选组件\n'
        else:
            addon_description = f'addonDescription "此MOD为{final_name}人物的可选组件\n'

        if fs.emissive_var.get():
            addon_description += f'开启此MOD将会关闭人物的夜光效果\n'
        else:
            addon_description += f'开启此MOD后，人物的{original_name}模型将不会显示\n'

        # 如果有子级，添加不显示子级模型的描述
        descendants = self.get_all_descendants(idx, graph)
        descendant_names = [self.file_selectors[child].name_entry.get().strip() for child in descendants]
        if descendant_names:
            # 格式化子级名称，带括号，并用“与”连接
            formatted_descendants = '与'.join([f'{name}' for name in descendant_names])
            conjunction = f'同时{formatted_descendants}模型强制不显示'
            addon_description += f'{conjunction}\n'

        addon_description += '"\n'

         # 获取作者名称（如果启用作者输入框）
        if self.author_name_var.get() and self.author_name_entry.get().strip():
            author_name = self.author_name_entry.get().strip()
        else:
            author_name = ""

        # Construct the full AddonInfo block
        addoninfo = '"AddonInfo"\n{\n'
        addoninfo += addontitle
        addoninfo += 'addonContent_Skin "1"\n'
        addoninfo += 'addonContent_Survivor "1"\n'
        addoninfo += 'addonversion "1.0"\n'
        addoninfo += f'addonauthor "{author_name}"\n'
        addoninfo += 'addonauthorSteamID ""\n'
        addoninfo += 'addonURL0 ""\n'
        addoninfo += addon_description
        addoninfo += '}\n'

        return addoninfo

def main():
    try:
        root = tk.Tk()
        app = MaterialSplitterApp(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("程序已被用户中断。")


if __name__ == "__main__":
    main()
