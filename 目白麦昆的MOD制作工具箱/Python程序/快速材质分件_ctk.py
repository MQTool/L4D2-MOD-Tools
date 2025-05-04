'''
CustomTkinter version of the Material Splitter App.
'''
import tkinter as tk # Still needed for messagebox, filedialog
from tkinter import filedialog, messagebox
import customtkinter
from PIL import Image, ImageTk # Will be adapted for CTkImage
import os
import shutil
from collections import defaultdict, deque
from functools import partial
import json # <<< ADDED import

# --- Constants ---
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

# Cache for get_relative_original_path
_get_relative_path_cache = {}

# --- Core Logic Functions (Copied from original) ---

def get_relative_original_path(file_path, input_path):
    """
    Extracts the path relative to 'materials/' from the file path, up to the second-to-last folder.
    Uses a cache to avoid redundant calculations.
    """
    # Check cache first
    if file_path in _get_relative_path_cache:
        return _get_relative_path_cache[file_path]
        
    # Normalize paths
    file_path = os.path.abspath(file_path)
    input_path = os.path.abspath(input_path)

    # Find the position of 'materials' in the path
    materials_dir = "materials"
    split_path = file_path.split(os.sep)
    try:
        materials_index = split_path.index(materials_dir)
    except ValueError:
        # Use messagebox here as it's outside the main app class initially
        messagebox.showerror("错误", f"文件路径 '{file_path}' 不包含 'materials/' 文件夹。")
        # Don't cache errors, let them propagate
        raise ValueError("File path does not contain 'materials/'")

    # Extract path from 'materials/' up to the second-to-last folder
    relative_parts = split_path[materials_index:-1] # Include 'materials', exclude the last folder
    relative_path = os.path.join(*relative_parts) if relative_parts else ""
    
    # Store in cache before returning
    _get_relative_path_cache[file_path] = relative_path
    return relative_path

def modify_vmt_content(dest_file, component_material, emissive):
    """
    Modifies the content of a VMT file based on component and emissive flags.
    """
    if not dest_file.lower().endswith(".vmt"):
        return
    if emissive:
        # Emissive takes precedence
        if not os.path.exists(dest_file):
            return
        try:
            with open(dest_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            found_emissive_enabled = False
            modified = False
            for i, line in enumerate(lines):
                # Check and modify $EmissiveBlendEnabled
                if "$EmissiveBlendEnabled" in line and '"1"' in line:
                    lines[i] = line.replace('"1"', '"0"')
                    found_emissive_enabled = True
                    modified = True
                    # Don't break yet, check for $selfillum too
                
                # Check and modify $selfillum
                if "$selfillum" in line and '"1"' in line:
                     lines[i] = line.replace('"1"', '"0"') # Also turn off selfillum if emissive is checked
                     modified = True
            
            # If neither EmissiveBlendEnabled nor selfillum was found set to 1, 
            # but we need to disable emissive, add $selfillum 0 (common practice)
            if not found_emissive_enabled and not any('"$selfillum" "0"' in l for l in lines):
                 # Find the last closing brace '}'
                last_brace_index = -1
                # Find the second to last closing brace for potentially better insertion in patch files
                brace_indices = [i for i, line in enumerate(lines) if "}" in line.strip()] # Find all lines with '}'
                if len(brace_indices) >= 2:
                    # Use the index of the second to last brace
                    insert_brace_line_index = brace_indices[-2] 
                elif len(brace_indices) == 1:
                    # Fallback to the last brace if only one exists
                    insert_brace_line_index = brace_indices[-1]
                else:
                    insert_brace_line_index = -1 # No brace found

                if insert_brace_line_index != -1:
                    # Find the actual position of '}' in that line
                    brace_pos = lines[insert_brace_line_index].find("}")
                    if brace_pos != -1:
                         # Insert before the brace on that line, maintaining indent if possible
                         indent = lines[insert_brace_line_index][:brace_pos].split("\n")[-1] # Get indent of the brace line
                         # Add extra indent for the parameter, adjust spacing, remove quotes around 0
                         lines.insert(insert_brace_line_index, indent + '    $selfillum                  0\n') 
                         modified = True
                    else: # Fallback if somehow '}' isn't in the line
                         # Use consistent formatting
                         lines.insert(insert_brace_line_index, '    $selfillum                  0\n')
                         modified = True
                else: # Fallback if no closing brace found (unlikely for valid VMT)
                     # Use consistent formatting
                     lines.append('    $selfillum                  0\n')
                     modified = True

            if modified:
                with open(dest_file, "w", encoding="utf-8") as f:
                    f.writelines(lines)
        except Exception as e:
             messagebox.showerror("错误", f"修改夜光 VMT 文件时出错: {e}")

    elif component_material:
        # Component material: Overwrite with VMT_REPLACEMENT
        try:
            with open(dest_file, "w", encoding="utf-8") as vmt_file:
                vmt_file.write(VMT_REPLACEMENT)
        except Exception as e:
            messagebox.showerror("错误", f"写入组件 VMT 文件时出错: {e}")

def generate_addoninfo_content(fs_data, final_name, idx, graph, name_to_index, all_selectors_data, batch_prefix, addon_desc_name, author_name):
    """
    Generates the content for addoninfo.txt based on the file selector's data and hierarchy.
    fs_data: Dictionary containing data for the current file selector.
    all_selectors_data: List of dictionaries for all file selectors.
    """
    original_name = fs_data['name']
    
    # Construct addontitle without brackets and add a space before "关"
    addontitle = f'addontitle "{final_name}"\n'

    # Construct addonDescription
    if addon_desc_name:
        addon_description = f'addonDescription "此MOD为{addon_desc_name}人物的可选组件\n'
    else:
        # Fallback to using the final name if addon_desc_name is not provided
        base_desc_name = batch_prefix + " " + original_name if batch_prefix else original_name
        addon_description = f'addonDescription "此MOD为{base_desc_name}人物的可选组件\n'

    if fs_data['emissive']:
        addon_description += f'开启此MOD将会关闭人物的夜光效果\n'
    else:
        addon_description += f'开启此MOD后，人物的{original_name}模型将不会显示\n'

    # Get all descendants for the current node
    descendants_indices = get_all_descendants(idx, graph)
    
    # Separate descendants based on their own settings
    hide_descendants_names = []
    emissive_off_descendants_names = []
    if descendants_indices: # Only process if there are descendants
        for child_idx in descendants_indices:
            child_data = all_selectors_data[child_idx]
            child_name = child_data['name']
            if child_data['emissive']: # If the descendant itself is an emissive-off mod
                emissive_off_descendants_names.append(child_name)
            else: # If the descendant itself is a hide mod
                hide_descendants_names.append(child_name)

        # Add description for hidden descendants
        if hide_descendants_names:
            formatted_hide_descendants = '与'.join([f'{name}' for name in hide_descendants_names])
            conjunction_hide = f'同时{formatted_hide_descendants}模型强制不显示'
            addon_description += f'{conjunction_hide}\n'
            
        # Add description for emissive-off descendants
        if emissive_off_descendants_names:
            formatted_emissive_off_descendants = '与'.join([f'{name}' for name in emissive_off_descendants_names])
            conjunction_emissive = f'同时{formatted_emissive_off_descendants}夜光效果强制关闭'
            addon_description += f'{conjunction_emissive}\n'

    addon_description += '"\n'

    # Construct the full AddonInfo block
    addoninfo = '"AddonInfo"\n{\n'
    addoninfo += addontitle
    addoninfo += 'addonContent_Skin "1"\n'
    addoninfo += 'addonContent_Survivor "1"\n'
    addoninfo += 'addonversion "1.0"\n'
    addoninfo += f'addonauthor "{author_name if author_name else ""}"\n' # Use provided author name or empty string
    addoninfo += 'addonauthorSteamID ""\n'
    addoninfo += 'addonURL0 ""\n'
    addoninfo += addon_description
    addoninfo += '}\n'

    return addoninfo

def get_all_descendants(parent_idx, graph):
    """
    Gets all descendant indices for a given parent index (recursively).
    """
    descendants = []
    queue = deque(graph.get(parent_idx, [])) # Start with direct children
    visited = set(graph.get(parent_idx, []))
    
    while queue:
        current = queue.popleft()
        descendants.append(current)
        for child in graph.get(current, []):
            if child not in visited:
                visited.add(child)
                queue.append(child)
    return descendants


# --- Placeholder Classes ---

class CTkFileSelector:
    def __init__(self, master_scrollable_frame, index, app_instance):
        self.app = app_instance
        self.index = index
        self.selected_files = [] # Store full paths
        # Use CTk variables
        self.name_var = customtkinter.StringVar()
        self.component_material_var = customtkinter.BooleanVar()
        self.emissive_var = customtkinter.BooleanVar()
        self.parent_checkbox_var = customtkinter.BooleanVar()
        self.parent_menu_var = customtkinter.StringVar()
        self.use_level_var = customtkinter.BooleanVar()
        self.level_choice_var = customtkinter.StringVar()

        # --- Create UI Elements within the master scrollable frame ---
        self.frame = customtkinter.CTkFrame(master_scrollable_frame, width=400)
        self.frame.pack(side=tk.LEFT, padx=5, pady=5, fill="y", expand=True)
        # Configure row weights: Only row 4 (Textbox) should expand
        self.frame.grid_rowconfigure(0, weight=0)
        self.frame.grid_rowconfigure(1, weight=0)
        self.frame.grid_rowconfigure(2, weight=0)
        self.frame.grid_rowconfigure(3, weight=0) # Options Frame row
        self.frame.grid_rowconfigure(4, weight=1) # File Display Textbox row

        # File block name
        name_label = customtkinter.CTkLabel(self.frame, text="文件块名称：")
        name_label.grid(row=0, column=0, padx=5, pady=(5, 2), sticky="w")
        name_entry = customtkinter.CTkEntry(self.frame, textvariable=self.name_var, width=150)
        name_entry.grid(row=1, column=0, padx=5, pady=2, sticky="w")
        name_entry.bind("<KeyRelease>", lambda event: self.app.update_parent_menus())

        # Buttons
        button_frame = customtkinter.CTkFrame(self.frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, padx=0, pady=2, sticky="w")
        choose_button = customtkinter.CTkButton(button_frame, text="选择文件 (.vmt)", width=120, command=self.choose_files)
        choose_button.pack(side=tk.LEFT, padx=5)
        delete_button = customtkinter.CTkButton(button_frame, text="删除块", width=60, command=lambda: self.app.remove_file_selector(self))
        delete_button.pack(side=tk.LEFT, padx=5)

        # Options Frame (Moved to Row 3)
        options_frame = customtkinter.CTkFrame(self.frame)
        options_frame.grid(row=3, column=0, padx=5, pady=5, sticky="ew")
        # Configure columns for side-by-side options
        options_frame.grid_columnconfigure(0, weight=0) # Checkbox label
        options_frame.grid_columnconfigure(1, weight=1) # Combobox / Second Checkbox

        # Row 0: Component & Emissive Checks
        comp_check = customtkinter.CTkCheckBox(options_frame, text="组件材质", variable=self.component_material_var)
        comp_check.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        emissive_check = customtkinter.CTkCheckBox(options_frame, text="夜光组件", variable=self.emissive_var)
        emissive_check.grid(row=0, column=1, padx=(10, 5), pady=2, sticky="w") # Place next to comp_check

        # Row 1: Parent Check & Combo
        parent_check = customtkinter.CTkCheckBox(options_frame, text="设定父级", variable=self.parent_checkbox_var, command=self.toggle_parent_options)
        parent_check.grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.parent_menu = customtkinter.CTkComboBox(options_frame, variable=self.parent_menu_var, state="disabled", width=180, # Adjusted width
                                                 command=self._parent_selection_changed)
        self.parent_menu.grid(row=1, column=1, padx=(10, 5), pady=2, sticky="ew") # Place next to parent_check

        # Row 2: Level Check & Combo
        self.level_checkbox = customtkinter.CTkCheckBox(options_frame, text="使用指定层级", variable=self.use_level_var, command=self.toggle_level_options)
        self.level_checkbox.grid(row=2, column=0, padx=5, pady=(5, 5), sticky="w")
        # Store default text color
        self.default_level_checkbox_text_color = self.level_checkbox.cget("text_color") 
        self.default_level_checkbox_fg_color = self.level_checkbox.cget("fg_color")
        
        self.level_choice_menu = customtkinter.CTkComboBox(options_frame, variable=self.level_choice_var, state="disabled", width=180, # Adjusted width
                                                     command=lambda choice: self.app.update_menu_states_for_all())
        self.level_choice_menu.grid(row=2, column=1, padx=(10, 5), pady=(5, 5), sticky="ew") # Place next to level_check

        # File display area (using a CTkTextbox - Now in Row 4)
        self.file_display_widget = customtkinter.CTkTextbox(self.frame, wrap="word", state="disabled")
        self.file_display_widget.grid(row=4, column=0, padx=5, pady=5, sticky="nsew") # Row 4 is correct

    def choose_files(self):
        """Handles the file selection for this block."""
        initial_dir = None
        if self.app.use_default_path_var.get() and self.app.default_file_path:
            initial_dir = self.app.default_file_path
        elif self.app.input_path_var.get():
            initial_dir = self.app.input_path_var.get()

        if not initial_dir or not os.path.exists(initial_dir):
            messagebox.showerror("错误", "请先在顶部设置有效的输入路径")
            return

        file_paths = filedialog.askopenfilenames(initialdir=initial_dir, title="选择 VMT 文件", filetypes=[("VMT Files", "*.vmt")])
        if file_paths:
            self.selected_files = list(file_paths) # Store the full paths
            # Update default path if the option is enabled
            if self.app.use_default_path_var.get():
                self.app.default_file_path = os.path.dirname(file_paths[0])

            # Update the display Textbox (show all files)
            self.file_display_widget.configure(state="normal") # Enable editing
            self.file_display_widget.delete("1.0", "end") # Clear existing content
            display_text = "\n".join([os.path.basename(p) for p in self.selected_files])
            self.file_display_widget.insert("1.0", display_text) # Insert new content
            self.file_display_widget.configure(state="disabled") # Disable editing

            self.app.update_stats()
            self.app.update_menu_states_for_all()

    def toggle_parent_options(self):
        """Enables/disables the parent selection combobox and updates related states."""
        self._update_parent_menu_state()
        # Update potential conflicts and checkbox states based on parent change
        # self.app.update_selector_states(self.index) # Replaced by centralized call below
        self.app.update_selector_states() # <<< Centralized call
        # self.app.update_parent_menus() # Replaced by centralized call below
        # self.app.update_selector_states() # <<< Already called above

    def toggle_level_options(self):
        """Handles the 'Use Level' checkbox toggle, including validation and state updates."""
        # If currently checked, user wants to uncheck - always allowed
        if not self.use_level_var.get(): 
             self._update_level_choice_menu_state()
             # Notify app to potentially re-enable related checkboxes
             # self.app.update_selector_states(self.index) 
             self.app.update_selector_states() # <<< CORRECTED: No parameter
             return

        # If currently unchecked, user wants to check - need validation
        # Note: validate_level_specification_conflict does not exist anymore, logic is inside update_selector_states
        # The check happens implicitly now when update_selector_states runs
        # allow_check = self.app.validate_level_specification_conflict(self.index, check_only=True)
        # if not allow_check:
        #     # Prevent checking
        #     self.use_level_var.set(False) # Revert variable
        #     return 
            
        # If validation passes (or rather, if no conflict prevents checking after update)
        self._update_level_choice_menu_state()
        # Notify app to potentially disable related checkboxes
        # self.app.update_selector_states(self.index)
        self.app.update_selector_states() # <<< CORRECTED: No parameter

    def _parent_selection_changed(self, choice):
        """Called when parent selection changes via combobox."""
        # Update potential conflicts and checkbox states based on parent change
        self.app.update_selector_states()
        self.app.update_menu_states_for_all() # Keep this for now, might optimize later

    def _update_parent_menu_state(self):
        """Helper to update parent menu state based on checkbox."""
        if not hasattr(self, 'parent_menu'): return # UI not fully built
        if self.parent_checkbox_var.get():
            self.parent_menu.configure(state="readonly")
        else:
            self.parent_menu_var.set("")
            self.parent_menu.configure(state="disabled")

    def _update_level_choice_menu_state(self):
        """Helper to update level choice menu state based on checkbox."""
        if not hasattr(self, 'level_choice_menu'): return
        if self.use_level_var.get():
            choices = self.app.get_level_choices()
            self.level_choice_menu.configure(values=choices, state="readonly")
            if self.level_choice_var.get() not in choices:
                self.level_choice_var.set("")
        else:
            self.level_choice_var.set("")
            self.level_choice_menu.configure(values=[], state="disabled")

    def set_level_checkbox_state(self, enabled: bool):
        """Allows the app to enable/disable the 'Use Level' checkbox, its text color, and background."""
        if hasattr(self, 'level_checkbox'): # Ensure checkbox exists
            disabled_text_color = "gray60" # Define standard disabled text color
            disabled_fg_color = ("gray75", "gray25") # Define standard disabled background color
            
            if enabled:
                self.level_checkbox.configure(
                    state=tk.NORMAL, 
                    text_color=self.default_level_checkbox_text_color, # Restore default text color
                    fg_color=self.default_level_checkbox_fg_color # Restore original background
                )
            else:
                self.level_checkbox.configure(
                    state=tk.DISABLED, 
                    text_color=disabled_text_color, # Set disabled text color
                    fg_color=disabled_fg_color # Set disabled background color
                )

    def get_data(self):
        """Returns the configuration data of this file selector."""
        return {
            "name": self.name_var.get().strip(), # Use name_var
            "files": self.selected_files,
            "component": self.component_material_var.get(),
            "emissive": self.emissive_var.get(),
            "has_parent": self.parent_checkbox_var.get(),
            "parent_name": self.parent_menu_var.get().strip() if self.parent_checkbox_var.get() else None,
            "use_level": self.use_level_var.get(),
            "level_name": self.level_choice_var.get().strip() if self.use_level_var.get() else None,
            # "ui_frame": self.frame # <<< ENSURE THIS LINE IS REMOVED OR COMMENTED OUT
        }

    # --- Methods to update own dropdown options --- START <<< MOVED INSIDE CLASS
    def update_parent_options(self):
        """Updates the parent dropdown choices for this specific selector."""
        if not hasattr(self, 'parent_menu'): return # UI not fully built
        options = self.app.get_parent_choices(self.index)
        self.parent_menu.configure(values=options)
        # Clear selection if current parent is no longer valid (only if checkbox is checked)
        if self.parent_checkbox_var.get() and self.parent_menu_var.get() not in options:
            self.parent_menu_var.set("")
            
    def update_level_choices_for_self(self):
        """Updates the level choice dropdown for this specific selector."""
        if not hasattr(self, 'level_choice_menu'): return # UI not fully built
        choices = self.app.get_level_choices()
        self.level_choice_menu.configure(values=choices)
        # Clear selection if current choice is no longer valid (only if checkbox is checked)
        if self.use_level_var.get() and self.level_choice_var.get() not in choices:
             self.level_choice_var.set("")
    # --- Methods to update own dropdown options --- END <<< MOVED INSIDE CLASS

    def get_parent_choices(self, exclude_index=-1):
        """Returns a list of valid names that can be parents, excluding the name at exclude_index."""
        choices = []
        for i, fs in enumerate(self.file_selectors_data):
            if i == exclude_index:
                continue
            name = fs.name_var.get().strip()
            if name:
                choices.append(name)
        return choices

class MaterialSplitterApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("快速材质分件 (CustomTkinter) - 由B站メジロ_McQueen与AI共同开发")
        self.geometry("1200x800")
        self.minsize(900, 700)

        # --- Appearance Settings ---
        customtkinter.set_appearance_mode("System") # Default to system theme
        customtkinter.set_default_color_theme("blue") # Default theme

        # --- Configure grid layout (1x2) ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Top paths frame
        self.grid_rowconfigure(1, weight=1) # Middle frame (image & levels)
        self.grid_rowconfigure(2, weight=2) # Lower frame (controls & selectors) - Give more weight
        self.grid_rowconfigure(3, weight=0) # Status bar
        self.grid_rowconfigure(4, weight=0) # Action button

        # --- Data Structures ---
        self.file_selectors_data = [] # Will store CTkFileSelector instances
        self.folder_level_entries = [] # Will store CTkEntry widgets for levels
        self.selector_index_counter = 0
        self.input_path_var = customtkinter.StringVar()
        self.output_path_var = customtkinter.StringVar()
        self.image_path = ""
        self.ctk_image_preview = None # For CTkLabel image
        self.use_default_path_var = customtkinter.BooleanVar(value=True)
        self.default_file_path = None # Store the default directory for file choosing
        self.batch_prefix_var = customtkinter.BooleanVar()
        self.addon_desc_var = customtkinter.BooleanVar()
        self.author_name_var = customtkinter.BooleanVar()
        self.batch_prefix_entry_var = customtkinter.StringVar() # Added for CTkEntry
        self.addon_desc_entry_var = customtkinter.StringVar() # Added for CTkEntry
        self.author_name_entry_var = customtkinter.StringVar() # Added for CTkEntry

        # --- Build UI ---
        self._create_widgets()
        self.create_menu()
        self.update_stats()

    def _create_widgets(self):
        # --- Top Frame for Paths ---
        paths_frame = customtkinter.CTkFrame(self)
        paths_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        paths_frame.grid_columnconfigure((1, 4), weight=1)

        # Input Path
        input_path_label = customtkinter.CTkLabel(paths_frame, text="输入路径:")
        input_path_label.grid(row=0, column=0, padx=(10, 5), pady=5, sticky="w")

        input_path_entry = customtkinter.CTkEntry(paths_frame, textvariable=self.input_path_var, state="readonly")
        input_path_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        choose_input_button = customtkinter.CTkButton(paths_frame, text="选择", width=60, command=self.choose_input_directory)
        choose_input_button.grid(row=0, column=2, padx=(5, 10), pady=5, sticky="w")

        # Output Path
        output_path_label = customtkinter.CTkLabel(paths_frame, text="输出路径:")
        output_path_label.grid(row=0, column=3, padx=(10, 5), pady=5, sticky="w")

        output_path_entry = customtkinter.CTkEntry(paths_frame, textvariable=self.output_path_var, state="readonly")
        output_path_entry.grid(row=0, column=4, padx=5, pady=5, sticky="ew")

        choose_output_button = customtkinter.CTkButton(paths_frame, text="选择", width=60, command=self.choose_output_directory)
        choose_output_button.grid(row=0, column=5, padx=(5, 10), pady=5, sticky="w")

        # --- Middle Frame (Image & Levels) ---
        middle_frame = customtkinter.CTkFrame(self)
        middle_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        middle_frame.grid_columnconfigure((0, 1), weight=1) # Let both columns expand equally
        middle_frame.grid_rowconfigure(0, weight=1)

        # --- Middle Left: Image Selection & Preview ---
        image_frame = customtkinter.CTkFrame(middle_frame, width=420) # Added fixed width
        image_frame.grid(row=0, column=0, padx=(10, 5), pady=5, sticky="nsew")
        image_frame.grid_propagate(False) # Prevent it from shrinking
        image_frame.grid_rowconfigure(1, weight=1) # Allow image label to expand vertically
        image_frame.grid_columnconfigure(0, weight=1)

        image_buttons_frame = customtkinter.CTkFrame(image_frame, fg_color="transparent")
        image_buttons_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        choose_image_button = customtkinter.CTkButton(image_buttons_frame, text="选择图片 (.jpg)", command=self.choose_image)
        choose_image_button.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        # Image Preview Label
        self.image_preview_label = customtkinter.CTkLabel(image_frame,
                                                        text="未选择图片",
                                                        fg_color=("gray75", "gray25"), # Different colors for light/dark mode
                                                        corner_radius=6)
        self.image_preview_label.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # --- Middle Right: Folder Levels ---
        levels_frame = customtkinter.CTkFrame(middle_frame)
        levels_frame.grid(row=0, column=1, padx=(5, 10), pady=5, sticky="nsew")
        levels_frame.grid_columnconfigure(0, weight=1)
        levels_frame.grid_rowconfigure(1, weight=1) # Allow scrollable frame to expand

        folder_level_label = customtkinter.CTkLabel(levels_frame, text="文件夹层级:")
        folder_level_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.folder_levels_scrollable = customtkinter.CTkScrollableFrame(levels_frame)
        self.folder_levels_scrollable.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.folder_levels_scrollable.grid_columnconfigure(0, weight=1) # Make content inside expand horizontally

        add_folder_level_button = customtkinter.CTkButton(levels_frame, text="添加层级", command=self.add_folder_level)
        add_folder_level_button.grid(row=2, column=0, padx=10, pady=10)

        # --- Lower Frame (Controls & Selectors) ---
        lower_frame = customtkinter.CTkFrame(self)
        lower_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        lower_frame.grid_columnconfigure(0, weight=1)
        lower_frame.grid_rowconfigure(1, weight=1) # Allow selectors frame to expand

        # --- Lower Top: Controls ---
        controls_frame = customtkinter.CTkFrame(lower_frame)
        controls_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        # Configure columns for somewhat even distribution of controls
        controls_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=0) # Start with no weight

        # Add File Selector Button
        add_file_button = customtkinter.CTkButton(controls_frame, text="添加文件选择块", command=self.add_file_selector)
        add_file_button.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        # Default Path Option
        path_options_frame = customtkinter.CTkFrame(controls_frame, fg_color="transparent")
        path_options_frame.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        use_default_path_checkbox = customtkinter.CTkCheckBox(
            path_options_frame, text="新块使用默认路径", variable=self.use_default_path_var)
        use_default_path_checkbox.pack()

        # Batch Prefix Option
        batch_prefix_frame = customtkinter.CTkFrame(controls_frame, fg_color="transparent")
        batch_prefix_frame.grid(row=0, column=2, padx=10, pady=10, sticky="w")
        self.batch_prefix_checkbox = customtkinter.CTkCheckBox(
            batch_prefix_frame, text="MOD标题", variable=self.batch_prefix_var,
            command=self.toggle_batch_prefix)
        self.batch_prefix_checkbox.grid(row=0, column=0, sticky="w", padx=5)
        self.batch_prefix_entry = customtkinter.CTkEntry(
            batch_prefix_frame, width=180, state="disabled",
            textvariable=self.batch_prefix_entry_var)
        self.batch_prefix_entry.grid(row=0, column=1, sticky="w", padx=5)

        # Addon Description (Character Name) Option
        addon_desc_frame = customtkinter.CTkFrame(controls_frame, fg_color="transparent")
        addon_desc_frame.grid(row=0, column=3, padx=10, pady=10, sticky="w")
        self.addon_desc_checkbox = customtkinter.CTkCheckBox(
            addon_desc_frame, text="人物名称", variable=self.addon_desc_var,
            command=self.toggle_addon_desc)
        self.addon_desc_checkbox.grid(row=0, column=0, sticky="w", padx=5)
        self.addon_desc_entry = customtkinter.CTkEntry(
            addon_desc_frame, width=180, state="disabled",
            textvariable=self.addon_desc_entry_var)
        self.addon_desc_entry.grid(row=0, column=1, sticky="w", padx=5)

        # Author Name Option
        author_frame = customtkinter.CTkFrame(controls_frame, fg_color="transparent")
        author_frame.grid(row=0, column=4, padx=10, pady=10, sticky="w")
        self.author_name_checkbox = customtkinter.CTkCheckBox(
            author_frame, text="作者名称", variable=self.author_name_var,
            command=self.toggle_author_name_entry)
        self.author_name_checkbox.grid(row=0, column=0, sticky="w", padx=5)
        self.author_name_entry = customtkinter.CTkEntry(
            author_frame, width=180, state="disabled",
            textvariable=self.author_name_entry_var)
        self.author_name_entry.grid(row=0, column=1, sticky="w", padx=5)

        # Theme Switcher
        theme_frame = customtkinter.CTkFrame(controls_frame, fg_color="transparent")
        theme_frame.grid(row=0, column=5, padx=10, pady=10, sticky="e") # Align right
        controls_frame.grid_columnconfigure(5, weight=1) # Allow theme switcher to push right
        theme_label = customtkinter.CTkLabel(theme_frame, text="主题:")
        theme_label.pack(side=tk.LEFT, padx=5)
        theme_menu = customtkinter.CTkOptionMenu(theme_frame, values=["Light", "Dark", "System"],
                                               command=self.change_appearance_mode_event)
        theme_menu.pack(side=tk.LEFT, padx=5)
        theme_menu.set("System") # Default value


        # --- Lower Bottom: File Selectors Area ---
        self.file_selectors_scrollable = customtkinter.CTkScrollableFrame(lower_frame, orientation="horizontal")
        self.file_selectors_scrollable.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        # Make the inner frame resize (important for horizontal scrolling with pack)
        # No specific grid configuration needed here, pack inside CTkFileSelector handles it

        # --- Status Bar ---
        status_frame = customtkinter.CTkFrame(self)
        status_frame.grid(row=3, column=0, padx=10, pady=(5, 5), sticky="ew")
        status_frame.grid_columnconfigure((0, 1, 2), weight=1) # Distribute labels

        self.file_block_count_label = customtkinter.CTkLabel(status_frame, text="文件块总数：0")
        self.file_block_count_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.empty_file_block_count_label = customtkinter.CTkLabel(status_frame, text="空文件块数：0")
        self.empty_file_block_count_label.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        self.folder_level_count_label = customtkinter.CTkLabel(status_frame, text="文件夹层级数：0")
        self.folder_level_count_label.grid(row=0, column=2, padx=10, pady=5, sticky="w")
        self.update_stats() # Initial update

        # --- Action Button --- 
        action_frame = customtkinter.CTkFrame(self)
        action_frame.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        action_frame.grid_columnconfigure(0, weight=1) # Center the button

        split_button = customtkinter.CTkButton(action_frame, text="一键分件！", height=40,
                                             font=("Segoe UI", 16, "bold"), # Make button prominent
                                             command=self.one_click_split)
        split_button.grid(row=0, column=0, pady=10)

    def create_menu(self):
        """Creates the application menu bar."""
        self.menu_bar = tk.Menu(self)
        # --- File Menu --- 
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.file_menu.add_command(label="保存预设", command=self.save_preset) # <<< ADDED Save Preset
        self.file_menu.add_command(label="加载预设", command=self.load_preset) # <<< ADDED Load Preset (placeholder for now)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="退出", command=self.quit)
        self.menu_bar.add_cascade(label="文件", menu=self.file_menu)
        
        # --- Theme Menu --- 
        self.theme_menu = tk.Menu(self.menu_bar, tearoff=0)
        # (Theme options would be added here if needed, currently handled by OptionMenu)
        
        # --- Apply the menu bar to the window --- <<< ADDED THIS LINE
        self.configure(menu=self.menu_bar)

    def change_appearance_mode_event(self, new_mode):
        customtkinter.set_appearance_mode(new_mode)

    # --- Placeholder methods to be implemented/adapted ---
    def choose_input_directory(self):
        """Opens a dialog to choose the input directory."""
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.input_path_var.set(folder_path)
            # Reset default file choosing path when input changes
            self.default_file_path = None
            print(f"Input path set to: {folder_path}") # For debugging

    def choose_output_directory(self):
        """Opens a dialog to choose the output directory."""
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.output_path_var.set(folder_path)
            print(f"Output path set to: {folder_path}") # For debugging

    def choose_image(self):
        """Opens a dialog to choose a JPG image and displays a preview."""
        image_path = filedialog.askopenfilename(title="选择JPG图片", filetypes=[("JPG Files", "*.jpg"), ("JPEG Files", "*.jpeg")])
        if image_path:
            try:
                # Store path
                self.image_path = image_path

                # Open and create CTkImage
                pil_image = Image.open(image_path)
                # Calculate aspect ratio to fit within a larger preview size
                max_width = 400  # Increased from 250
                max_height = 400 # Increased from 250
                pil_image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

                self.ctk_image_preview = customtkinter.CTkImage(light_image=pil_image,
                                                              dark_image=pil_image,
                                                              size=pil_image.size)
                # Update label
                self.image_preview_label.configure(image=self.ctk_image_preview, text="") # Clear text
                print(f"Image selected: {image_path}")

            except Exception as e:
                self.image_path = ""
                self.ctk_image_preview = None
                self.image_preview_label.configure(image=None, text="图片加载失败")
                messagebox.showerror("错误", f"无法加载图片：{e}")

    def add_folder_level(self):
        """Adds a new folder level entry to the scrollable frame."""
        current_level_count = len(self.folder_level_entries)
        if current_level_count >= 10:
            messagebox.showwarning("警告", "最多只能添加10个文件夹层级！")
            return

        level_index = current_level_count # 0-based index
        level_num = level_index + 1 # 1-based number for label

        # Create a frame for the level entry within the scrollable frame
        level_frame = customtkinter.CTkFrame(self.folder_levels_scrollable)
        level_frame.grid(row=level_index, column=0, padx=5, pady=(0, 5), sticky="ew")
        level_frame.grid_columnconfigure(1, weight=1) # Make entry expand

        level_label = customtkinter.CTkLabel(level_frame, text=f"第{level_num}级：", width=50) # Fixed width for alignment
        level_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        level_entry = customtkinter.CTkEntry(level_frame)
        level_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        level_entry.bind("<KeyRelease>", lambda event: self.update_level_choices()) # Update choices on key release

        # Pass the frame and entry to the remove function
        remove_button = customtkinter.CTkButton(level_frame,
                                                text="删除",
                                                width=50,
                                                command=partial(self.remove_folder_level, level_frame, level_entry))
        remove_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")

        self.folder_level_entries.append(level_entry)
        self.update_stats() # Update counts
        self.update_level_choices() # Update dependent dropdowns

    def remove_folder_level(self, frame_to_remove, entry_to_remove):
        """Removes a folder level entry."""
        try:
            self.folder_level_entries.remove(entry_to_remove)
            frame_to_remove.destroy()
            # Re-grid remaining items to remove gaps (optional but good practice)
            for i, entry in enumerate(self.folder_level_entries):
                 # Assume the parent frame is the grid item we need to reposition
                 entry.master.grid(row=i) 
                 # Update label text if needed (e.g., "第N级")
                 label_widget = entry.master.grid_slaves(row=0, column=0)[0]
                 label_widget.configure(text=f"第{i+1}级：")
                 
            self.update_stats()
            self.update_level_choices()
        except ValueError:
            print("Error: Entry not found in list during removal.")
            pass # Should not happen if logic is correct

    def get_level_choices(self):
        """Gets the current valid folder level names."""
        return [entry.get().strip() for entry in self.folder_level_entries if entry.get().strip()]

    def add_file_selector(self, data=None):
        """Adds a new file selector frame to the scrollable frame."""
        # Pass the horizontal scrollable frame as the master
        selector = CTkFileSelector(self.file_selectors_scrollable, self.selector_index_counter, self)
        self.file_selectors_data.append(selector)
        self.selector_index_counter += 1

        # Set initial values if data is provided (from loading preset)
        if data:
            selector.name_var.set(data.get('name', '')) # <<< Use selector.
            selector.selected_files.clear() # <<< Use selector.
            selector.selected_files.extend(data.get('files', [])) # <<< Use selector. & key 'files'
            # Update display widget for the selector instance
            selector.file_display_widget.configure(state="normal") # <<< Use selector.
            selector.file_display_widget.delete("1.0", "end")
            display_text = "\n".join([os.path.basename(p) for p in selector.selected_files])
            selector.file_display_widget.insert("1.0", display_text) # <<< Use selector.
            selector.file_display_widget.configure(state="disabled") # <<< Use selector.
            
            # Set component/emissive state
            selector.component_material_var.set(data.get('component', False)) # <<< Use selector.
            selector.emissive_var.set(data.get('emissive', False)) # <<< Use selector.
            
            # Set parent state based on loaded data
            has_parent_loaded = bool(data.get('parent_name'))
            selector.parent_checkbox_var.set(has_parent_loaded) # <<< Use selector.
            selector.parent_menu_var.set(data.get('parent_name', '')) # <<< Use selector.
            
            # Set level state based on loaded data
            selector.use_level_var.set(data.get('use_level', False)) # <<< Use selector.
            selector.level_choice_var.set(data.get('level_name') or '') # Use 'or' for robust None handling <<< Use selector. & MODIFIED
            
            # Initial state update needed after setting values for THIS block
            # These will set the correct initial enable/disable state and options
            selector.update_parent_options() # Update options before toggling state
            selector.update_level_choices_for_self() # Update options before toggling state
            # Global state update happens once at the end of apply_preset_data
        else:
             # Default state update for new block
             selector.update_parent_options() # Ensure new block gets parent options
             selector.update_level_choices_for_self() # Ensure new block gets level options
             selector.toggle_parent_options() # Initialize state
             selector.toggle_level_options() # Initialize state
             # Don't call global update here for new blocks initially

        self.update_stats() # Update count after adding
        # Update parent menus for all blocks since a new name might be available
        self.update_parent_menus()
        # No need for full state update here unless absolutely necessary
        # self.update_selector_states() 
        print(f"Added file selector block '{selector.name_var.get()}'. Total: {len(self.file_selectors_data)}") # Simple debug print

    def remove_file_selector(self, selector_instance):
        """Removes a file selector block."""
        if selector_instance in self.file_selectors_data:
            selector_instance.frame.destroy() # Destroy the UI frame
            self.file_selectors_data.remove(selector_instance)
            # Update menus and stats
            self.update_stats()
            self.update_selector_states()

    def update_parent_menus(self):
        """Updates the parent dropdown choices in all file selectors."""
        current_names = [fs.name_var.get().strip() for fs in self.file_selectors_data if fs.name_var.get().strip()]
        # print(f"Updating parent menus. Current names: {current_names}") # Removed debug print
        for fs in self.file_selectors_data:
            current_name = fs.name_var.get().strip()
            # Filter out self
            options = [name for name in current_names if name != current_name]
            fs.parent_menu.configure(values=options)
            # If checkbox is checked, ensure state is readonly
            if fs.parent_checkbox_var.get():
                fs.parent_menu.configure(state="readonly")
                # Clear selection if current parent is no longer valid
                if fs.parent_menu_var.get() not in options:
                    fs.parent_menu_var.set("")
            else:
                # Ensure combobox is disabled if checkbox is off
                fs.parent_menu_var.set("")
                fs.parent_menu.configure(state="disabled")
        # Don't call update_menu_states_for_all here to avoid loops, rely on individual toggles
        # self.update_menu_states_for_all()

    def update_level_choices(self):
        """Updates the level choice dropdowns in all file selectors."""
        choices = self.get_level_choices()
        # print(f"Updating level choices to: {choices}") # Removed debug print
        for selector in self.file_selectors_data:
            if hasattr(selector, 'level_choice_menu'): # Check if the menu exists yet
                selector.level_choice_menu.configure(values=choices)
                if selector.use_level_var.get():
                    selector.level_choice_menu.configure(state="readonly")
                    # Keep selection if valid, otherwise clear
                    if selector.level_choice_var.get() not in choices:
                        selector.level_choice_var.set("")
                else:
                    selector.level_choice_menu.set("")
                    selector.level_choice_menu.configure(state="disabled")
        # We also need to update menu states if levels changed parents/hierarchy
        # Avoid calling this here if possible
        # self.update_menu_states_for_all() 

    def update_stats(self):
        """Updates the status labels with current counts."""
        total_blocks = len(self.file_selectors_data)
        # Calculate empty blocks based on name or selected files
        empty_blocks = sum(1 for fs in self.file_selectors_data if not fs.name_var.get().strip() or not fs.selected_files)
        total_levels = len(self.folder_level_entries)

        # Use the specific label attributes created in _create_widgets
        if hasattr(self, 'file_block_count_label'):
            self.file_block_count_label.configure(text=f"文件块总数：{total_blocks}")
        if hasattr(self, 'empty_file_block_count_label'):
            self.empty_file_block_count_label.configure(text=f"空文件块数：{empty_blocks}")
        if hasattr(self, 'folder_level_count_label'):
            self.folder_level_count_label.configure(text=f"文件夹层级数：{total_levels}")

    def update_selector_states(self):
        """Updates the enabled/disabled state of 'Use Level' checkboxes based on conflicts FOR ALL SELECTORS."""
        print(f"Updating ALL selector states...") # Changed print message
        selectors_data_list = [fs.get_data() for fs in self.file_selectors_data]
        name_to_index_map = {data['name']: i for i, data in enumerate(selectors_data_list) if data['name']}
        
        # Build parent map <<< ADDED
        parent_map = {i: name_to_index_map.get(data['parent_name']) 
                      for i, data in enumerate(selectors_data_list) if data.get('parent_name')}

        # Build graph
        graph = defaultdict(list)
        for i, data in enumerate(selectors_data_list):
            p_name = data.get('parent_name')
            if p_name and p_name in name_to_index_map:
                p_idx = name_to_index_map[p_name]
                graph[p_idx].append(i)
                
        # Get set of nodes currently specifying a level
        nodes_specifying_level = {i for i, data in enumerate(selectors_data_list) if data['use_level']}
        print(f"  Nodes specifying level: {nodes_specifying_level}") # <<< DEBUG PRINT

        # Update state for each selector
        for i, selector_instance in enumerate(self.file_selectors_data):
            can_enable_checkbox = True
            reason = ""
            is_self_specifying = i in nodes_specifying_level # Check if current node itself specifies
            print(f"    Checking node {i} ('{selector_instance.name_var.get()}'): Is self specifying? {is_self_specifying}") # <<< DEBUG PRINT
            
            # --- REVISED CONFLICT CHECK --- 
            # Conflict exists if self specifies level AND (ancestor OR descendant also specifies)
            # OR if self does NOT specify level BUT (ancestor OR descendant specifies)
            # Simplified: Conflict exists if (ancestor specifies) OR (descendant specifies)
            # The check should be: can_enable_checkbox = NOT (ancestor specifies OR descendant specifies)
            
            ancestor_conflict = self._check_ancestor_specifies_level(i, parent_map, nodes_specifying_level)
            print(f"      Ancestor conflict? {ancestor_conflict}") # <<< DEBUG PRINT
            descendant_conflict = False # Initialize
            if not ancestor_conflict: # Optimization: only check descendants if no ancestor conflict
                 descendant_conflict = self._check_descendant_specifies_level(i, graph, nodes_specifying_level)
                 print(f"      Descendant conflict? {descendant_conflict}") # <<< DEBUG PRINT
                 
            if ancestor_conflict:
                 can_enable_checkbox = False
                 reason = "祖先节点已指定层级"
            elif descendant_conflict:
                 can_enable_checkbox = False
                 reason = "后代节点已指定层级"
            # --- END REVISED CONFLICT CHECK --- 
                
            # --- REMOVED OLD CONFLICT CHECK --- 
            # Check parent conflict
            # parent_name = selectors_data_list[i]['parent_name']
            # if parent_name and parent_name in name_to_index_map:
            #     parent_idx = name_to_index_map[parent_name]
            #     if parent_idx in nodes_specifying_level: # If PARENT specifies level
            #         can_enable_checkbox = False
            #         reason = f"父级 '{parent_name}' 已指定层级"
            #
            # Check children conflict (only if parent didn't cause disable)
            # if can_enable_checkbox:
            #     children_indices = graph.get(i, [])
            #     for child_idx in children_indices:
            #         if child_idx in nodes_specifying_level: # If ANY CHILD specifies level
            #             can_enable_checkbox = False
            #             child_name = selectors_data_list[child_idx]['name']
            #             reason = f"子级 '{child_name}' 已指定层级"
            #             break
            # --- END REMOVED OLD CONFLICT CHECK --- 
                        
            # Apply the state based on the revised conflict status
            if reason:
                 print(f"    -> Node {i}: Disabling checkbox. Reason: {reason}") # <<< DEBUG PRINT
            else:
                 print(f"    -> Node {i}: Enabling checkbox.") # <<< DEBUG PRINT
            selector_instance.set_level_checkbox_state(can_enable_checkbox)
            
            # --- REMOVED OLD LOGIC --- 
            # is_currently_checked = selector_instance.use_level_var.get()
            # # print(f"  Node {i} ('{selector_instance.name_var.get()}'): Can enable: {can_enable_checkbox}, Currently checked: {is_currently_checked}, Reason: {reason}")
            # if not is_currently_checked:
            #      selector_instance.set_level_checkbox_state(can_enable_checkbox)
            # else:
            #      # Keep it enabled if it's already checked (user must uncheck it first)
            #      selector_instance.set_level_checkbox_state(True)
            # --- END REMOVED OLD LOGIC ---

    # --- Helper methods for hierarchy conflict checking --- START
    def _check_ancestor_specifies_level(self, node_idx, parent_map, nodes_specifying_level):
        """Checks if any ancestor of node_idx specifies a level."""
        current = node_idx
        visited = {node_idx} # Prevent infinite loop in case of cycles
        while True:
            parent_idx = parent_map.get(current)
            if parent_idx is None:
                return False # Reached root
            if parent_idx in visited:
                print(f"Warning: Cycle detected during ancestor check at {parent_idx}")
                return False # Cycle detected
            visited.add(parent_idx)
            if parent_idx in nodes_specifying_level:
                return True # Found ancestor specifying level
            current = parent_idx
            
    def _check_descendant_specifies_level(self, node_idx, graph, nodes_specifying_level):
        """Checks if any descendant of node_idx specifies a level using BFS."""
        queue = deque(graph.get(node_idx, []))
        visited = set(graph.get(node_idx, []))
        visited.add(node_idx) # Don't check self
        
        while queue:
            current = queue.popleft()
            if current in nodes_specifying_level:
                return True # Found descendant specifying level
            
            for child in graph.get(current, []):
                if child not in visited:
                    visited.add(child)
                    queue.append(child)
        return False # No descendant found
    # --- Helper methods for hierarchy conflict checking --- END

    def toggle_batch_prefix(self):
        """Enables/disables the batch prefix entry."""
        if self.batch_prefix_var.get():
            self.batch_prefix_entry.configure(state="normal")
        else:
            self.batch_prefix_entry_var.set("") # Clear content
            self.batch_prefix_entry.configure(state="disabled")

    def toggle_addon_desc(self):
        """Enables/disables the addon description entry."""
        if self.addon_desc_var.get():
            self.addon_desc_entry.configure(state="normal")
        else:
            self.addon_desc_entry_var.set("")
            self.addon_desc_entry.configure(state="disabled")

    def toggle_author_name_entry(self):
        """Enables/disables the author name entry."""
        if self.author_name_var.get():
            self.author_name_entry.configure(state="normal")
        else:
            self.author_name_entry_var.set("")
            self.author_name_entry.configure(state="disabled")

    def one_click_split(self):
        """Performs the core splitting logic using data from CTk widgets."""
        # Clear cache at the beginning of each run
        _get_relative_path_cache.clear()
        
        # 1. Gather Data from UI
        input_path = self.input_path_var.get().strip()
        output_path = self.output_path_var.get().strip()
        image_path = self.image_path # Already stored
        batch_prefix = self.batch_prefix_entry_var.get().strip() if self.batch_prefix_var.get() else ""
        addon_desc_name = self.addon_desc_entry_var.get().strip() if self.addon_desc_var.get() else ""
        author_name = self.author_name_entry_var.get().strip() if self.author_name_var.get() else ""

        # Folder levels
        additional_folders = self.get_level_choices()

        # File selector data (list of dictionaries)
        selectors_data = [fs.get_data() for fs in self.file_selectors_data]

        # 2. Perform Validations
        if not input_path or not output_path:
            messagebox.showerror("错误", "请输入有效的输入和输出路径")
            return
        if not os.path.exists(input_path):
            messagebox.showerror("错误", f"输入路径不存在: {input_path}")
            return
        if not os.path.exists(output_path):
             try:
                 os.makedirs(output_path)
                 print(f"Output path created: {output_path}")
             except Exception as e:
                 messagebox.showerror("错误", f"创建输出路径失败: {output_path}\n{e}")
                 return

        if not additional_folders:
            messagebox.showerror("错误", "请至少添加一个文件夹层级")
            return

        if not selectors_data:
            messagebox.showerror("错误", "请至少添加一个文件选择块")
            return

        # Check for empty name or files within selectors
        for idx, data in enumerate(selectors_data):
            if not data['name'] or not data['files']:
                messagebox.showerror("错误", f"文件块 {idx+1} 存在空名称或未选择文件，请修改后再分件")
                return
            # Check if selected files still exist (basic check)
            for f_path in data['files']:
                if not os.path.exists(f_path):
                     messagebox.showerror("错误", f"文件块 '{data['name']}' 中的文件 '{os.path.basename(f_path)}' 不存在或已移动，请重新选择。")
                     return
                 
            # Check if level name is valid if used
            if data['use_level'] and data['level_name'] not in additional_folders:
                 messagebox.showerror("错误", f"文件块 '{data['name']}' 使用的层级 '{data['level_name']}' 无效或未定义。")
                 return
                 
        # 3. Build Graph & Topological Sort
        graph = defaultdict(list)
        indegree = defaultdict(int)
        name_to_index = {data['name']: idx for idx, data in enumerate(selectors_data)}

        for idx, data in enumerate(selectors_data):
            parent_name = data['parent_name']
            if parent_name:
                if parent_name not in name_to_index:
                    messagebox.showerror("错误", f"文件块 '{data['name']}' 的父级 '{parent_name}' 未找到对应的文件块。")
                    return
                parent_idx = name_to_index[parent_name]
                graph[parent_idx].append(idx)
                indegree[idx] += 1

        queue = deque([idx for idx in range(len(selectors_data)) if indegree[idx] == 0])
        sorted_indices = []
        while queue:
            current = queue.popleft()
            sorted_indices.append(current)
            for neighbor in graph.get(current, []): # Use .get for safety
                indegree[neighbor] -= 1
                if indegree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_indices) != len(selectors_data):
            messagebox.showerror("错误", "检测到循环的父子级关系，请检查后重试。")
            return

        # --- Validate: Parent/Child Specify Level Conflict (Rule 0) ---
        for idx, data in enumerate(selectors_data):
            parent_name = data['parent_name']
            if parent_name:
                parent_idx = name_to_index.get(parent_name)
                if parent_idx is not None and data['use_level'] and selectors_data[parent_idx]['use_level']:
                    messagebox.showerror("配置错误", f"文件块 '{data['name']}' 和其父级 '{parent_name}' 不能同时指定层级。")
                    return

        # --- Early Check: Ensure enough levels for hierarchy ---
        if any(graph.values()) and len(additional_folders) < 2:
             messagebox.showerror("逻辑错误", "检测到父子级关系，但定义的文件夹层级少于2个。请至少定义两个层级以支持父子结构。")
             return

        # --- 5. Process Files (Using Anchor/Relative Logic for Placement) ---
        processed_addon_roots = set()
        fatal_error_occurred = False
        try:
            for idx in sorted_indices: # Process in topological order
                fs_data = selectors_data[idx]
                original_name = fs_data['name'] # Get name for messages
                selected_files = fs_data['files']
                component_material = fs_data['component']
                emissive = fs_data['emissive']
                # absolute_depth = depth_map.get(idx) # No longer use absolute depth directly here

                # --- Start: New Logic to Determine Target Level based on Anchor --- 
                print(f"\nDetermining target level for Node '{original_name}' (Index {idx})...")
                target_level_name = "" 
                target_level_index = -1
                error_occurred_placement = False
                
                # Need mapping from level name to its 1-based index
                level_name_to_num_map = {name: i + 1 for i, name in enumerate(additional_folders)}
                # Need parent map for distance calculation
                parent_map = {i: name_to_index.get(data['parent_name']) 
                              for i, data in enumerate(selectors_data) if data['parent_name']}

                anchor_idx, anchor_level_num = find_anchor_in_chain(idx, name_to_index, level_name_to_num_map, selectors_data, graph)

                if anchor_idx is not None:
                    # --- Case 1: Anchor Found --- 
                    if anchor_level_num is None: # Anchor found but level mapping failed
                         messagebox.showerror("错误", f"无法确定锚点节点 '{selectors_data[anchor_idx]['name']}' 的层级数值。")
                         error_occurred_placement = True
                         fatal_error_occurred = True
                         break
                    else:
                        distance = calculate_distance(anchor_idx, idx, graph, parent_map)
                        if distance is None:
                            messagebox.showerror("内部错误", f"无法计算节点 '{original_name}' 与其链中锚点 '{selectors_data[anchor_idx]['name']}' 的距离。")
                            error_occurred_placement = True
                            fatal_error_occurred = True
                            break
                        else:
                            target_level_num = anchor_level_num - distance
                            print(f"  Anchor is '{selectors_data[anchor_idx]['name']}' (L{anchor_level_num}), Distance={distance} -> Target Level Num={target_level_num}")
                            # Validate target level number
                            if target_level_num < 1 or target_level_num > len(additional_folders):
                                messagebox.showerror("层级错误", f"根据锚点计算出的节点 '{original_name}' 目标层级 ({target_level_num}) 超出有效范围 [1-{len(additional_folders)}].")
                                error_occurred_placement = True
                                fatal_error_occurred = True
                                break
                            else:
                                target_level_index = target_level_num - 1
                                target_level_name = additional_folders[target_level_index]
                else:
                    # --- Case 2: No Anchor Found --- 
                    print("  No anchor found, using relative height logic.")
                    relative_depths = calculate_relative_depths(idx, graph)
                    height = max(relative_depths.values()) if relative_depths else 1
                    target_level_num = height
                    print(f"  Subtree height={height} -> Target Level Num={target_level_num}")
                    # Validate target level number
                    if target_level_num < 1 or target_level_num > len(additional_folders):
                         messagebox.showerror("层级错误", f"根据相对高度计算出的节点 '{original_name}' 目标层级 ({target_level_num}) 超出定义的层级数 ({len(additional_folders)})。")
                         error_occurred_placement = True
                         fatal_error_occurred = True
                         break
                    else:
                         target_level_index = target_level_num - 1
                         target_level_name = additional_folders[target_level_index]
                
                if error_occurred_placement: 
                     print(f"Skipping node {original_name} due to placement error.")
                     continue # Skip to next node in sorted_indices if error occurred
                     
                # --- End: New Logic --- 
                                 
                print(f"Processing Node '{original_name}' (Idx {idx}) -> Target Level '{target_level_name}' (Index {target_level_index})")

                # Construct final addon name and root path
                if batch_prefix:
                    final_name = f"{batch_prefix} {original_name} 关"
                else:
                    final_name = f"{original_name} 关"
                addon_root_path = os.path.join(output_path, final_name)
                os.makedirs(addon_root_path, exist_ok=True) # Ensure root exists
                processed_addon_roots.add(addon_root_path)

                # Determine base path for copying
                if not selected_files:
                    print(f"Warning: Skipping block '{original_name}' - no files selected.")
                    continue
                representative_file = selected_files[0]
                # This call now uses cache
                relative_original_base = get_relative_original_path(representative_file, input_path)
                
                # Construct the final target path within the addon using determined level
                target_path = os.path.join(addon_root_path, relative_original_base, target_level_name)
                os.makedirs(target_path, exist_ok=True)
                
                # Determine which files to copy based on parent/leaf status
                is_parent = bool(graph.get(idx))
                if is_parent:
                    indices_to_copy_files_from = [idx] + get_all_descendants(idx, graph)
                    print(f"  Parent node '{original_name}': Copying files from self and descendants: {indices_to_copy_files_from}")
                else:
                    indices_to_copy_files_from = [idx]
                    print(f"  Leaf node '{original_name}': Copying files from self only: {indices_to_copy_files_from}")

                # Copy and modify selected files
                # print(f"  Copying files for '{original_name}' to '{target_level_name}' folder.") # Old print
                for source_idx in indices_to_copy_files_from:
                    source_fs_data = selectors_data[source_idx]
                    print(f"    Copying from source block: '{source_fs_data['name']}' (Idx {source_idx})")
                    for file_path in source_fs_data['files']: # Use files from the source block
                        if not os.path.exists(file_path):
                            print(f"Warning: File not found during copy: {file_path}")
                            continue
                        dest_file = os.path.join(target_path, os.path.basename(file_path))
                        shutil.copy(file_path, dest_file)
                        # Modify VMT based on THIS block's settings
                        modify_vmt_content(dest_file, component_material, emissive)
            
                # Generate addoninfo.txt in the addon root
                addoninfo_path = os.path.join(addon_root_path, "addoninfo.txt")
                # Use fs_data and idx of the current block
                addoninfo_content = generate_addoninfo_content(
                    fs_data, final_name, idx, graph, name_to_index, selectors_data, 
                    batch_prefix, addon_desc_name, author_name
                )
                with open(addoninfo_path, "w", encoding="utf-8") as addon_file:
                    addon_file.write(addoninfo_content)

                # --- ADDED: Image Copying Inside Loop (for each addon) ---
                if image_path:
                     current_image_target_dir = None
                     try:
                         # Determine target dir for THIS addon
                         parts = relative_original_base.split(os.sep)
                         if 'materials' in parts:
                             materials_index_in_rel = parts.index('materials')
                             image_base_parts = parts[:materials_index_in_rel]
                             current_image_target_dir = os.path.join(addon_root_path, *image_base_parts)
                         else:
                             current_image_target_dir = addon_root_path # Default to addon root
                             
                         if current_image_target_dir:
                             os.makedirs(current_image_target_dir, exist_ok=True) # Ensure it exists
                             dest_image_path = os.path.join(current_image_target_dir, os.path.basename(image_path))
                             if os.path.exists(image_path):
                                 print(f"  Copying image for addon '{final_name}' to: {dest_image_path}")
                                 shutil.copy(image_path, dest_image_path)
                             else:
                                 # Only show warning once maybe? Or per addon?
                                 # Let's keep it per addon for clarity if the source is missing mid-process.
                                  messagebox.showwarning("图片复制警告", f"源图片路径无效或文件不存在: {image_path} (Addon: {final_name})")
                         else:
                              messagebox.showwarning("图片复制警告", f"无法确定当前 Addon '{final_name}' 的图片目标目录。")
                     except Exception as e:
                         messagebox.showwarning("图片复制警告", f"无法将图片复制到 Addon '{final_name}' (目标: {current_image_target_dir}): {e}")
                # --- END: Added Image Copying --- 
            
            # --- Check for fatal errors BEFORE completion message --- 
            if fatal_error_occurred:
                 print("Fatal error occurred during processing, skipping completion message.")
                 return

            # --- 8. Completion Message --- (Now only runs if no fatal error)
            messagebox.showinfo("完成", "所有文件块已成功处理并输出！")

        except ValueError as ve: # Catch specific errors from get_relative_original_path
             messagebox.showerror("路径错误", str(ve))
        except Exception as e:
            messagebox.showerror("处理错误", f"在处理文件过程中发生意外错误：\n{type(e).__name__}: {e}")
            import traceback
            traceback.print_exc() # Print full traceback to console for debugging

    # --- Preset System Methods --- 
    def collect_preset_data(self):
        """Collects all relevant data for saving a preset."""
        preset_data = {
            'input_path': self.input_path_var.get(),
            'output_path': self.output_path_var.get(),
            'image_path': self.image_path, # <<< Correct: Use stored path
            'batch_prefix': self.batch_prefix_var.get(), # Checkbox state
            'batch_prefix_text': self.batch_prefix_entry_var.get(), # Text field content
            'addon_desc_enabled': self.addon_desc_var.get(), # Checkbox state
            'addon_desc_text': self.addon_desc_entry_var.get(), # Text field content
            'author_name_enabled': self.author_name_var.get(), # Checkbox state
            'author_name_text': self.author_name_entry_var.get(), # Text field content
            'theme': customtkinter.get_appearance_mode(), # Get current mode
            'additional_folders': self.get_level_choices(),
            'selectors': []
        }
        for selector in self.file_selectors_data:
            selector_data = selector.get_data()
            # Ensure selected_files is serializable (it should be list of strings)
            selector_data['selected_files'] = list(selector_data['files'])
            preset_data['selectors'].append(selector_data)
        return preset_data
        
    def save_preset(self):
        """Saves the current configuration to a preset file."""
        preset_file_path = filedialog.asksaveasfilename(
            title="保存预设",
            defaultextension=".json",
            filetypes=[("预设文件", "*.json"), ("所有文件", "*.*")]
        )
        if not preset_file_path:
            return # User cancelled
            
        try:
            preset_data = self.collect_preset_data()
            with open(preset_file_path, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, ensure_ascii=False, indent=4)
            messagebox.showinfo("成功", f"预设已成功保存到:\n{preset_file_path}")
        except Exception as e:
            messagebox.showerror("保存失败", f"保存预设时发生错误: {e}")
            
    def load_preset(self):
        """Loads configuration from a preset file."""
        preset_file_path = filedialog.askopenfilename(
            title="加载预设",
            filetypes=[("预设文件", "*.json"), ("所有文件", "*.*")]
        )
        if not preset_file_path:
            return # User cancelled
            
        try:
            with open(preset_file_path, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)
            
            # Basic validation (optional but good practice)
            required_keys = ['input_path', 'output_path', 'image_path', 'batch_prefix', 
                             'theme', 'additional_folders', 'selectors']
            if not all(key in preset_data for key in required_keys):
                 raise ValueError("预设文件缺少必要的键。")
                
            self.apply_preset_data(preset_data)
            messagebox.showinfo("成功", f"预设已成功加载自:\n{preset_file_path}")
            
        except FileNotFoundError:
             messagebox.showerror("加载失败", "选择的文件不存在。")
        except json.JSONDecodeError:
             messagebox.showerror("加载失败", "文件不是有效的 JSON 格式。")
        except ValueError as ve:
             messagebox.showerror("加载失败", f"预设文件内容无效: {ve}")
        except Exception as e:
            messagebox.showerror("加载失败", f"加载预设时发生未知错误: {e}")
            # Consider logging the full error here
            # traceback.print_exc()

    def apply_preset_data(self, preset_data):
        """Applies the loaded preset data to the application state."""
        # --- Clear existing state --- 
        self.clear_all_file_selectors() # Clear existing file blocks
        # self.additional_folders_list.clear() # <<< REMOVED: Attribute does not exist
        # Clear UI related to levels (important before adding new ones)
        for widget in self.folder_levels_scrollable.winfo_children(): # <<< CORRECTED: Target the scrollable frame
            widget.destroy()
        # Clear the list tracking entry widgets before rebuilding
        self.folder_level_entries.clear() 
        
        # --- Apply general settings --- 
        self.input_path_var.set(preset_data.get('input_path', ''))
        self.output_path_var.set(preset_data.get('output_path', ''))
        self.image_path = preset_data.get('image_path', '') # <<< Set self.image_path first
        self.batch_prefix_var.set(preset_data.get('batch_prefix', False)) # <<< Corrected: get boolean
        # Ensure entry state matches checkbox state after loading
        self.toggle_batch_prefix() 
        
        self.addon_desc_var.set(preset_data.get('addon_desc_enabled', False)) # Assuming preset saves checkbox state
        self.addon_desc_entry_var.set(preset_data.get('addon_desc_text', ''))
        self.toggle_addon_desc()
        
        self.author_name_var.set(preset_data.get('author_name_enabled', False))
        self.author_name_entry_var.set(preset_data.get('author_name_text', ''))
        self.toggle_author_name_entry()
        
        # --- Update image preview based on loaded path --- <<< REPLACED LOGIC
        # self.update_image_preview() # <<< REMOVED: Method does not exist
        if self.image_path and os.path.exists(self.image_path):
            try:
                pil_image = Image.open(self.image_path)
                max_width = 400
                max_height = 400
                pil_image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                self.ctk_image_preview = customtkinter.CTkImage(light_image=pil_image, dark_image=pil_image, size=pil_image.size)
                self.image_preview_label.configure(image=self.ctk_image_preview, text="")
                print(f"Preset loaded image: {self.image_path}")
            except Exception as e:
                self.image_path = "" # Clear invalid path
                self.ctk_image_preview = None
                self.image_preview_label.configure(image=None, text="预设图片加载失败")
                print(f"Error loading image from preset: {e}")
        else:
            self.image_path = "" # Clear path if file doesn't exist
            self.ctk_image_preview = None
            self.image_preview_label.configure(image=None, text="未选择图片")
        # --- End Update image preview --- 
        
        loaded_theme = preset_data.get('theme', 'System')
        # Assuming theme_var exists for the OptionMenu, if not, create it or adjust
        # self.theme_var.set(loaded_theme) # Need to check if theme_var exists
        self.change_appearance_mode_event(loaded_theme) # Apply theme directly
        
        # --- Apply level definitions --- 
        # self.additional_folders_list.extend(preset_data.get('additional_folders', [])) # <<< REMOVED
        # Rebuild the UI for level definitions based on the loaded list
        # self.update_additional_folders_ui() # <<< REMOVED: Method does not exist
        loaded_levels = preset_data.get('additional_folders', [])
        print(f"Loading levels from preset: {loaded_levels}") # Debug print
        for level_name in loaded_levels:
            self.add_folder_level() # Add UI row
            if self.folder_level_entries: # Check if added successfully
                try:
                    last_entry = self.folder_level_entries[-1]
                    last_entry.delete(0, tk.END) # Clear default value if any
                    last_entry.insert(0, level_name) # Set loaded name
                    print(f"  Added level UI for: {level_name}") # Debug print
                except IndexError:
                    print("Warning: Could not access last_entry after adding level.")
            else:
                print("Warning: folder_level_entries is empty after add_folder_level call.")
        # Update level choices in dropdowns after rebuilding UI
        self.update_level_choices() 

        # --- Apply file selectors --- 
        selectors_data = preset_data.get('selectors', [])
        for selector_config in selectors_data:
            # Ensure critical keys exist before trying to add
            if 'name' in selector_config and 'selected_files' in selector_config:
                 self.add_file_selector(data=selector_config)
            else:
                 print(f"Warning: Skipping invalid selector entry in preset: {selector_config}")
                 
        # --- Final UI Update --- 
        # After all blocks are added, update menus and states
        self.update_selector_states()
        self.update_stats() # Update counts
        self.update_idletasks() # <<< ADDED: Force UI update after loading

    def clear_all_file_selectors(self):
        """Removes all file selector frames."""
        for selector in self.file_selectors_data[:]: # Iterate over a copy
            self.remove_file_selector(selector)
        # Explicitly clear the list after destroying widgets
        self.file_selectors_data.clear()
        self.update_stats()
        # No need for extra call here, remove_file_selector handles the last update
        # self.update_menu_states_for_all() # Replaced by calls within remove_file_selector

    def get_parent_choices(self, exclude_index=-1):
        """Returns a list of valid names that can be parents, excluding the name at exclude_index."""
        choices = []
        for i, fs in enumerate(self.file_selectors_data):
            if i == exclude_index:
                continue
            name = fs.name_var.get().strip()
            if name:
                choices.append(name)
        return choices

# --- Helper Function for Relative Depths ---
def calculate_relative_depths(start_node_idx, graph):
    """Calculates relative depths within the subgraph starting from start_node_idx."""
    relative_depths = {}
    queue = deque([(start_node_idx, 1)]) # Store (node_index, relative_depth)
    visited = {start_node_idx}
    
    while queue:
        current_idx, depth = queue.popleft()
        relative_depths[current_idx] = depth
        
        for child_idx in graph.get(current_idx, []):
            if child_idx not in visited:
                visited.add(child_idx)
                queue.append((child_idx, depth + 1))
                
    return relative_depths

# --- Helper Functions for Anchor Logic ---
def find_anchor_in_chain(start_idx, name_to_index_map, index_to_name_map, selectors_data_list, graph):
    """Finds the anchor node (first specifying level) in the chain containing start_idx.
       Returns (anchor_idx, anchor_level_number) or (None, None).
    """
    # 1. Find the root of the chain
    current_idx = start_idx
    parent_map = {i: name_to_index_map.get(data['parent_name']) 
                  for i, data in enumerate(selectors_data_list) if data['parent_name']} 
    root_idx = start_idx
    visited_up = {start_idx}
    while True:
        parent_idx = parent_map.get(current_idx)
        if parent_idx is None or parent_idx in visited_up: # Reached root or cycle (should not happen)
             root_idx = current_idx
             break
        visited_up.add(parent_idx)
        current_idx = parent_idx
        
    # 2. Traverse down from root to find the first anchor
    queue = deque([root_idx])
    visited_down = {root_idx}
    while queue:
        current = queue.popleft()
        if selectors_data_list[current]['use_level']:
             level_name = selectors_data_list[current]['level_name']
             try:
                 # Find the 1-based level number
                 level_num = index_to_name_map.get(level_name) # Assuming index_to_name_map holds name -> level_num
                 if level_num is not None:
                      print(f"  Anchor found for chain of {start_idx}: Node {current} specifies level {level_name} ({level_num})")
                      return current, level_num 
                 else: # Fallback if level name mapping is wrong
                      print(f"Warning: Anchor level name '{level_name}' not found in mapping.")
                      # Try finding index directly in additional_folders? Less robust.
                      return current, None # Indicate anchor found but level unknown
             except Exception as e:
                 print(f"Error finding level number for anchor {level_name}: {e}")
                 return current, None # Indicate anchor found but level unknown
        
        for child in graph.get(current, []):
            if child not in visited_down:
                 visited_down.add(child)
                 queue.append(child)
                 
    # 3. No anchor found in the chain
    print(f"  No anchor found for chain containing {start_idx}")
    return None, None
    
def calculate_distance(start_idx, end_idx, graph, parent_map):
    """Calculates the directed distance between two nodes in the same chain.
       Positive: end is descendant of start. Negative: end is ancestor. 0: same node.
    """
    if start_idx == end_idx:
        return 0
        
    # Check downward (BFS)
    queue = deque([(start_idx, 0)])
    visited_down = {start_idx}
    while queue:
        current, dist = queue.popleft()
        if current == end_idx:
            print(f"  Distance from {start_idx} down to {end_idx}: {dist}")
            return dist
        for child in graph.get(current, []):
            if child not in visited_down:
                visited_down.add(child)
                queue.append((child, dist + 1))
                
    # Check upward
    current = start_idx
    dist = 0
    visited_up = {start_idx}
    while True:
         parent_idx = parent_map.get(current)
         if parent_idx is None: # Reached root without finding end
             break
         if parent_idx in visited_up: # Cycle detected
             break 
         visited_up.add(parent_idx)
         dist -= 1
         if parent_idx == end_idx:
             print(f"  Distance from {start_idx} up to {end_idx}: {dist}")
             return dist
         current = parent_idx
         
    print(f"Warning: Could not find path between {start_idx} and {end_idx}")
    return None # Should not happen if they are in the same chain

# --- Main Execution ---
if __name__ == "__main__":
    app = MaterialSplitterApp()
    app.mainloop() 