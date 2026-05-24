import os
import queue
import traceback
import subprocess
import threading
import time
import ctypes
import re
import json
import shlex
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkinter import (
    BooleanVar,
    Canvas,
    DoubleVar,
    END,
    HORIZONTAL,
    IntVar,
    Listbox,
    PhotoImage,
    StringVar,
    Text,
    Tk,
    Toplevel,
    filedialog,
    messagebox,
    ttk,
)

import ffmpeg_utils as ffmpeg
from config import (
    APP_TITLE,
    AUDIO_ENCODERS,
    AUDIO_BITRATE_PRESETS,
    AUDIO_EXTENSIONS,
    AUDIO_FILETYPES,
    AUDIO_MODES,
    BATCH_PRESETS,
    COMMON_ENCODERS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PREVIEW_PATH,
    ENCODERS,
    LUT_FILETYPES,
    PRESETS,
    QUALITY_MODES,
    RETRO_FORMATS,
    RETRO_RESOLUTIONS,
    RESOLUTIONS,
    SHARPEN_LEVELS,
    VIDEO_MUXERS,
    VIDEO_EXTENSIONS,
    VIDEO_FILETYPES,
    WINDOW_MIN_SIZE,
    WINDOW_SIZE,
)
from data import AudioSettings, CompressionResult, CompressionSettings, RetroSettings


class VideoCompressorApp:
    COLORS = {
        "bg": "#eef1f5",
        "surface": "#ffffff",
        "surface_alt": "#f7f9fc",
        "panel": "#ffffff",
        "panel_border": "#cfd6df",
        "text": "#1f2937",
        "muted": "#657283",
        "accent": "#2563eb",
        "accent_hover": "#1d4ed8",
        "accent_pressed": "#1e40af",
        "button": "#f8fafc",
        "button_hover": "#e8eef7",
        "button_pressed": "#dbe4f0",
        "list_bg": "#ffffff",
        "list_fg": "#1f2937",
        "list_select": "#2f6fed",
    }

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.root.minsize(*WINDOW_MIN_SIZE)

        self.files = []
        self.audio_files = []
        self.retro_files = []
        self.task_counter = 0
        self.active_workers = {}
        self.queued_tasks = {}
        self.worker = None
        self.stop_requested = False
        self.messages = queue.Queue()

        self.encoder_name = StringVar(value="GPU H.265 / HEVC (hevc_nvenc)")
        self.advanced_encoders = BooleanVar(value=False)
        self.preferred_device = StringVar(value="优先 GPU")
        self.auto_open_output = BooleanVar(value=False)
        self.enable_drag_drop = BooleanVar(value=True)
        self.confirm_overwrite = BooleanVar(value=True)
        self.preset_name = StringVar(value="高速")
        self.resolution_name = StringVar(value="保持原分辨率")
        self.sharpen_name = StringVar(value="关闭")
        self.custom_width = IntVar(value=1920)
        self.quality_mode = StringVar(value="CRF / 恒定质量")
        self.cq_value = IntVar(value=23)
        self.bitrate = StringVar(value="")
        self.custom_command = StringVar(value='-y -i "{input}" -c:v libx264 -crf 23 -c:a copy "{output}"')
        self.audio_mode = StringVar(value="复制音频流")
        self.audio_bitrate = StringVar(value="160k")
        self.muxer_name = StringVar(value="MP4 (.mp4)")
        self.create_thumbnail = BooleanVar(value=True)
        self.thumbnail_only_selected = BooleanVar(value=False)
        self.thumbnail_time = DoubleVar(value=1.0)
        self.parallel_jobs = IntVar(value=2)
        self.extra_ffmpeg_args = StringVar(value="")
        self.use_lut = BooleanVar(value=False)
        self.lut_path = StringVar(value="")
        self.output_dir = StringVar(value=str(DEFAULT_OUTPUT_DIR))
        self.audio_output_dir = StringVar(value=str(DEFAULT_OUTPUT_DIR / "audio"))
        self.audio_encoder_name = StringVar(value="AAC (.m4a)")
        self.audio_page_bitrate = StringVar(value="192k")
        self.audio_sample_rate = StringVar(value="48000")
        self.audio_channels = StringVar(value="2")
        self.audio_normalize = BooleanVar(value=False)
        self.batch_input_dir = StringVar(value="")
        self.batch_output_dir = StringVar(value=str(DEFAULT_OUTPUT_DIR / "batch"))
        self.batch_preset_name = StringVar(value="网盘归档 H.265 1080p")
        self.batch_keep_tree = BooleanVar(value=True)
        self.batch_include_audio = BooleanVar(value=True)
        self.batch_vertical_mode = BooleanVar(value=False)
        self.queue_parallel_jobs = IntVar(value=1)
        self.retro_output_dir = StringVar(value=str(DEFAULT_OUTPUT_DIR / "retro"))
        self.retro_format_name = StringVar(value="AVI - MPEG4 + MP3 (.avi)")
        self.retro_resolution_name = StringVar(value="VCD 352x288")
        self.retro_bitrate = StringVar(value="900k")
        self.retro_audio_bitrate = StringVar(value="128k")
        self.retro_deinterlace = BooleanVar(value=True)
        self.retro_denoise = BooleanVar(value=True)
        self.retro_remux_format = StringVar(value="MP4 (.mp4)")
        self.retro_remux_audio = StringVar(value="复制音频")
        self.overwrite = BooleanVar(value=False)
        self.file_conflict_action = StringVar(value="重命名")
        self.progress = DoubleVar(value=0)
        self.current_task = StringVar(value="等待任务")
        self.resource_status = StringVar(value="CPU --%  |  GPU --%")
        self._last_cpu_times = None
        self.cpu_history = []
        self.gpu_history = []
        self.preview_image = None
        self.preview_path = DEFAULT_PREVIEW_PATH
        self.preview_window = None
        self.preview_source_path = None
        self.preview_seconds = DoubleVar(value=0.0)
        self.preview_duration = 0.0
        self.preview_playing = False
        self.preview_after_id = None
        self.screenshot_dir = StringVar(value=str(DEFAULT_OUTPUT_DIR / "screenshots"))
        self.preview_frame_path = DEFAULT_OUTPUT_DIR / "_player_preview.png"
        self.lut_page_video = StringVar(value="")
        self.lut_page_folder = StringVar(value="")
        self.lut_page_output = StringVar(value=str(DEFAULT_OUTPUT_DIR / "lut_previews"))
        self.lut_page_time = DoubleVar(value=1.0)
        self.lut_preview_images = {}
        self.lut_thumb_images = {}
        self.lut_tooltip_after = None
        self.lut_tooltip = None
        self.media_info_path = StringVar(value="")
        self.interface_language = StringVar(value="中文")
        self.tray_mode = BooleanVar(value=True)
        self.x264_priority = StringVar(value="正常")
        self.x264_threads = IntVar(value=0)
        self.x264_command = StringVar(value="")
        self.default_player = StringVar(value="")
        self.settings_path = DEFAULT_OUTPUT_DIR / "app_settings.json"

        self._configure_style()
        self._build_ui()
        self._bind_keys()
        self._setup_drag_drop()
        self._load_app_settings()
        self.root.protocol("WM_DELETE_WINDOW", self._on_main_close)
        self._poll_messages()
        self._poll_resources()

    def _configure_style(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        colors = self.COLORS
        self.root.configure(bg=colors["bg"])
        self.root.option_add("*Font", ("Microsoft YaHei UI", 10))
        self.root.option_add("*Listbox.Font", ("Microsoft YaHei UI", 10))
        self.root.option_add("*TCombobox*Listbox.Font", ("Microsoft YaHei UI", 10))

        style.configure(".", font=("Microsoft YaHei UI", 10), background=colors["bg"], foreground=colors["text"])
        style.configure("TFrame", background=colors["bg"])
        style.configure("Surface.TFrame", background=colors["surface"])
        style.configure("Header.TFrame", background=colors["surface"])
        style.configure("TLabel", background=colors["panel"], foreground=colors["text"])
        style.configure("Surface.TLabel", background=colors["surface"], foreground=colors["text"])
        style.configure("Title.TLabel", background=colors["surface"], foreground="#111827", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("Hint.TLabel", background=colors["bg"], foreground=colors["muted"], font=("Microsoft YaHei UI", 9))
        style.configure("HeaderHint.TLabel", background=colors["surface"], foreground=colors["muted"], font=("Microsoft YaHei UI", 9))
        style.configure("Status.TLabel", background=colors["surface"], foreground=colors["accent"], font=("Microsoft YaHei UI", 10, "bold"))

        style.configure(
            "TLabelframe",
            background=colors["panel"],
            bordercolor=colors["panel_border"],
            lightcolor=colors["panel_border"],
            darkcolor=colors["panel_border"],
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "TLabelframe.Label",
            background=colors["panel"],
            foreground="#111827",
            font=("Microsoft YaHei UI", 10, "bold"),
        )

        style.configure(
            "TButton",
            background=colors["button"],
            foreground=colors["text"],
            bordercolor=colors["panel_border"],
            lightcolor=colors["button"],
            darkcolor=colors["panel_border"],
            borderwidth=1,
            focusthickness=0,
            focuscolor=colors["button"],
            padding=(12, 7),
            relief="solid",
        )
        style.map(
            "TButton",
            background=[("active", colors["button_hover"]), ("pressed", colors["button_pressed"])],
            bordercolor=[("active", "#aeb9c8"), ("pressed", "#93a4b8")],
        )
        style.configure(
            "Accent.TButton",
            background=colors["accent"],
            foreground="#ffffff",
            bordercolor=colors["accent"],
            borderwidth=1,
            focuscolor=colors["accent"],
            font=("Microsoft YaHei UI", 10, "bold"),
            padding=(14, 8),
        )
        style.map(
            "Accent.TButton",
            background=[("active", colors["accent_hover"]), ("pressed", colors["accent_pressed"])],
            foreground=[("active", "#ffffff"), ("pressed", "#ffffff")],
        )

        style.configure("TEntry", fieldbackground="#ffffff", bordercolor=colors["panel_border"], padding=(8, 5), relief="flat")
        style.map("TEntry", bordercolor=[("focus", colors["accent"])])
        style.configure("TCombobox", fieldbackground="#ffffff", bordercolor=colors["panel_border"], arrowcolor=colors["muted"], padding=(8, 5))
        style.map("TCombobox", bordercolor=[("focus", colors["accent"])], fieldbackground=[("readonly", "#ffffff")])
        style.configure("TSpinbox", fieldbackground="#ffffff", bordercolor=colors["panel_border"], padding=(8, 5))
        style.configure("Horizontal.TScale", background=colors["panel"], troughcolor="#dbe3ee", sliderthickness=16)
        style.configure("Horizontal.TProgressbar", troughcolor="#dbe3ee", background=colors["accent"], bordercolor=colors["bg"], lightcolor=colors["accent"], darkcolor=colors["accent"])

        style.configure("TNotebook", background=colors["bg"], borderwidth=0, tabmargins=(0, 6, 0, 0))
        style.configure("TNotebook.Tab", background="#e2e8f0", foreground=colors["muted"], padding=(18, 9), font=("Microsoft YaHei UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", colors["surface"]), ("active", "#f1f5f9")], foreground=[("selected", colors["text"]), ("active", colors["text"])])

        style.configure("Treeview", background="#ffffff", fieldbackground="#ffffff", foreground=colors["text"], rowheight=30, bordercolor=colors["panel_border"])
        style.configure("Treeview.Heading", background="#e9eef5", foreground=colors["text"], font=("Microsoft YaHei UI", 10, "bold"), padding=(8, 7))
        style.map("Treeview", background=[("selected", colors["list_select"])], foreground=[("selected", "#ffffff")])
        style.configure("Vertical.TScrollbar", background="#d8e0eb", troughcolor=colors["bg"], arrowcolor=colors["muted"], bordercolor=colors["panel_border"])

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=18)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)
        main.rowconfigure(2, weight=0)

        self._build_header(main)
        self._build_tabs(main)
        self._build_bottom_panel(main)

    def _build_header(self, parent):
        header = ttk.Frame(parent, style="Header.TFrame", padding=(16, 12))
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, minsize=260)
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="FFmpeg + NVIDIA NVENC / AMD AMF 批量压缩、CPU 对比和缩略图生成",
            style="HeaderHint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        header_actions = ttk.Frame(header, style="Header.TFrame")
        header_actions.grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Button(header_actions, text="⚙ 设置", command=self.open_settings_window).pack(side="left")
        ttk.Button(header_actions, text="▶ 开始压缩", style="Accent.TButton", command=self.start_compression).pack(side="left", padx=(8, 0))
        ttk.Button(header_actions, text="＋ 视频任务入队", command=self.add_current_video_to_queue).pack(side="left", padx=(8, 0))
        ttk.Button(header_actions, text="■ 停止", command=self.stop).pack(side="left", padx=(8, 0))
        ttk.Button(header_actions, text="✓ 检测环境", command=self.check_environment).pack(side="left", padx=(8, 0))

        resource = ttk.Frame(header, style="Header.TFrame")
        resource.grid(row=0, column=1, rowspan=3, sticky="nse", padx=(18, 0))
        ttk.Label(resource, textvariable=self.resource_status, style="Status.TLabel").grid(row=0, column=0, sticky="e")
        self.resource_canvas = Canvas(resource, width=240, height=46, bg="#f7f9fc", highlightthickness=1, highlightbackground=self.COLORS["panel_border"])
        self.resource_canvas.grid(row=1, column=0, sticky="e", pady=(8, 0))

    def _build_tabs(self, parent):
        self.notebook = ttk.Notebook(parent)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.video_tab = ttk.Frame(self.notebook, padding=0)
        self.audio_tab = ttk.Frame(self.notebook, padding=0)
        self.retro_tab = ttk.Frame(self.notebook, padding=0)
        self.lut_tab = ttk.Frame(self.notebook, padding=0)
        self.batch_tab = ttk.Frame(self.notebook, padding=0)
        self.mediainfo_tab = ttk.Frame(self.notebook, padding=0)
        self.tasks_tab = ttk.Frame(self.notebook, padding=0)
        self.notebook.add(self.video_tab, text="视频")
        self.notebook.add(self.audio_tab, text="音频")
        self.notebook.add(self.retro_tab, text="复古")
        self.notebook.add(self.lut_tab, text="Lut调色")
        self.notebook.add(self.batch_tab, text="批量压缩")
        self.notebook.add(self.mediainfo_tab, text="MediaInfo")
        self.notebook.add(self.tasks_tab, text="任务管理")
        self._build_video_tab(self.video_tab)
        self._build_audio_tab(self.audio_tab)
        self._build_retro_tab(self.retro_tab)
        self._build_lut_tab(self.lut_tab)
        self._build_batch_tab(self.batch_tab)
        self._build_mediainfo_tab(self.mediainfo_tab)
        self._build_tasks_tab(self.tasks_tab)

    def _build_video_tab(self, parent):
        panel = self._scrollable_frame(parent)
        panel.columnconfigure(0, weight=3)
        panel.columnconfigure(1, weight=2)
        panel.rowconfigure(0, weight=1)
        self._build_video_file_panel(panel)
        self._build_settings_panel(panel)

    def _build_video_file_panel(self, parent):
        panel = ttk.LabelFrame(parent, text="任务列表", padding=12)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        panel.rowconfigure(1, weight=1)
        panel.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(panel)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="＋ 添加视频", command=self.add_files).pack(side="left")
        ttk.Button(toolbar, text="▤ 添加文件夹", command=self.add_folder).pack(side="left", padx=6)
        ttk.Button(toolbar, text="▶ 预览", command=self.open_player_preview).pack(side="left")
        ttk.Button(toolbar, text="− 移除", command=self.remove_selected).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="清空", command=self.clear_files).pack(side="left", padx=6)

        list_frame = ttk.Frame(panel)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.file_list = self._create_work_listbox(list_frame, selectmode="extended")
        self.file_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=scrollbar.set)

        output = ttk.Frame(panel)
        output.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        output.columnconfigure(1, weight=1)
        ttk.Label(output, text="输出目录").grid(row=0, column=0, sticky="w")
        ttk.Entry(output, textvariable=self.output_dir).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(output, text="浏览…", command=self.choose_output_dir).grid(row=0, column=2)

    def _build_settings_panel(self, parent):
        panel = ttk.LabelFrame(parent, text="压缩设置", padding=12)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.columnconfigure(1, weight=1)
        self.settings_panel = panel

        row = self._add_preset_controls(panel, 0)
        row = self._add_encoder_controls(panel, row)
        row = self._add_lut_controls(panel, row)
        row = self._add_thumbnail_controls(panel, row)

    def _rebuild_settings_panel(self):
        if not hasattr(self, "settings_panel"):
            return
        for child in self.settings_panel.winfo_children():
            child.destroy()
        row = self._add_preset_controls(self.settings_panel, 0)
        row = self._add_encoder_controls(self.settings_panel, row)
        row = self._add_lut_controls(self.settings_panel, row)
        self._add_thumbnail_controls(self.settings_panel, row)

    def _add_preset_controls(self, panel, row):
        preset_box = ttk.LabelFrame(panel, text="预设管理", padding=(10, 8))
        preset_box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        preset_box.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(preset_box, text="保存设置", command=self.save_video_settings).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(preset_box, text="加载预设", command=self.load_video_preset).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(preset_box, text="导入设置", command=self.import_video_settings).grid(row=0, column=2, sticky="ew", padx=(6, 0))
        return row + 1

    def _build_retro_tab(self, parent):
        parent = self._scrollable_frame(parent)
        parent.columnconfigure(0, weight=3)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        files = ttk.LabelFrame(parent, text="古老素材任务", padding=12)
        files.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        files.rowconfigure(1, weight=1)
        files.columnconfigure(0, weight=1)
        toolbar = ttk.Frame(files)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="＋ 添加素材", command=self.add_retro_files).pack(side="left")
        ttk.Button(toolbar, text="▤ 添加文件夹", command=self.add_retro_folder).pack(side="left", padx=6)
        ttk.Button(toolbar, text="− 移除", command=self.remove_selected_retro).pack(side="left")
        ttk.Button(toolbar, text="清空", command=self.clear_retro_files).pack(side="left", padx=6)
        list_frame = ttk.Frame(files)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.retro_file_list = self._create_work_listbox(list_frame, selectmode="extended")
        self.retro_file_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.retro_file_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.retro_file_list.configure(yscrollcommand=scrollbar.set)
        output = ttk.Frame(files)
        output.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        output.columnconfigure(1, weight=1)
        ttk.Label(output, text="输出目录").grid(row=0, column=0, sticky="w")
        ttk.Entry(output, textvariable=self.retro_output_dir).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(output, text="浏览…", command=self.choose_retro_output_dir).grid(row=0, column=2)

        settings = ttk.LabelFrame(parent, text="复古输出设置", padding=12)
        settings.grid(row=0, column=1, sticky="nsew")
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="输出格式").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Combobox(settings, textvariable=self.retro_format_name, values=list(RETRO_FORMATS), state="readonly").grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Label(settings, text="分辨率").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(settings, textvariable=self.retro_resolution_name, values=list(RETRO_RESOLUTIONS), state="readonly").grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Label(settings, text="视频码率").grid(row=2, column=0, sticky="w", pady=5)
        retro_rate = ttk.Frame(settings)
        retro_rate.grid(row=2, column=1, sticky="ew", pady=5)
        self._build_bitrate_buttons(retro_rate, self.retro_bitrate, ["500k", "700k", "900k", "1200k", "2000k"])
        ttk.Label(settings, text="音频码率").grid(row=3, column=0, sticky="w", pady=5)
        retro_audio_rate = ttk.Frame(settings)
        retro_audio_rate.grid(row=3, column=1, sticky="ew", pady=5)
        self._build_bitrate_buttons(retro_audio_rate, self.retro_audio_bitrate, ["64k", "96k", "128k", "192k"])
        ttk.Checkbutton(settings, text="反交错 yadif", variable=self.retro_deinterlace).grid(row=4, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Checkbutton(settings, text="轻度降噪 hqdn3d", variable=self.retro_denoise).grid(row=5, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Button(settings, text="▶ 开始复古处理", style="Accent.TButton", command=self.start_retro_processing).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ttk.Label(settings, text="RM/WMA 等老格式是否可写入，取决于本机 FFmpeg 编译支持。", style="Hint.TLabel").grid(row=7, column=0, columnspan=2, sticky="w", pady=(12, 0))

        remux = ttk.LabelFrame(parent, text="封装转换", padding=12)
        remux.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        remux.columnconfigure(1, weight=1)
        ttk.Label(remux, text="输出格式").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Combobox(remux, textvariable=self.retro_remux_format, values=[name for name in VIDEO_MUXERS if VIDEO_MUXERS[name] != "source"], state="readonly").grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Label(remux, text="音频编码").grid(row=1, column=0, sticky="w", pady=5)
        audio_row = ttk.Frame(remux)
        audio_row.grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Radiobutton(audio_row, text="复制音频", value="复制音频", variable=self.retro_remux_audio).pack(side="left")
        ttk.Radiobutton(audio_row, text="AAC 重新编码", value="AAC 重新编码", variable=self.retro_remux_audio).pack(side="left", padx=(14, 0))
        ttk.Button(remux, text="▶ 开始封装转换", style="Accent.TButton", command=self.start_retro_remux).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(remux, text="默认输出到源文件所在目录；视频流直接复制，只更换容器或音频编码。", style="Hint.TLabel").grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _build_audio_tab(self, parent):
        parent = self._scrollable_frame(parent)
        parent.columnconfigure(0, weight=3)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        files = ttk.LabelFrame(parent, text="音频任务", padding=12)
        files.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        files.rowconfigure(1, weight=1)
        files.columnconfigure(0, weight=1)
        toolbar = ttk.Frame(files)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="＋ 添加音频", command=self.add_audio_files).pack(side="left")
        ttk.Button(toolbar, text="▤ 添加文件夹", command=self.add_audio_folder).pack(side="left", padx=6)
        ttk.Button(toolbar, text="− 移除", command=self.remove_selected_audio).pack(side="left")
        ttk.Button(toolbar, text="清空", command=self.clear_audio_files).pack(side="left", padx=6)
        list_frame = ttk.Frame(files)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.audio_file_list = self._create_work_listbox(list_frame, selectmode="extended")
        self.audio_file_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.audio_file_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.audio_file_list.configure(yscrollcommand=scrollbar.set)
        output = ttk.Frame(files)
        output.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        output.columnconfigure(1, weight=1)
        ttk.Label(output, text="输出目录").grid(row=0, column=0, sticky="w")
        ttk.Entry(output, textvariable=self.audio_output_dir).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(output, text="浏览…", command=self.choose_audio_output_dir).grid(row=0, column=2)

        settings = ttk.LabelFrame(parent, text="音频压缩设置", padding=12)
        settings.grid(row=0, column=1, sticky="nsew")
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="编码器").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Combobox(settings, textvariable=self.audio_encoder_name, values=list(AUDIO_ENCODERS), state="readonly").grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Label(settings, text="码率").grid(row=1, column=0, sticky="w", pady=5)
        self.audio_bitrate_buttons_frame = ttk.Frame(settings)
        self.audio_bitrate_buttons_frame.grid(row=1, column=1, sticky="ew", pady=5)
        self._refresh_audio_bitrate_buttons()
        self.audio_encoder_name.trace_add("write", lambda *_: self._refresh_audio_bitrate_buttons())
        ttk.Label(settings, text="采样率").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Combobox(settings, textvariable=self.audio_sample_rate, values=["44100", "48000", "96000", ""], state="readonly").grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Label(settings, text="声道").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Combobox(settings, textvariable=self.audio_channels, values=["1", "2", "6", ""], state="readonly").grid(row=3, column=1, sticky="ew", pady=5)
        ttk.Checkbutton(settings, text="响度标准化", variable=self.audio_normalize).grid(row=4, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Button(settings, text="▶ 开始音频压缩", style="Accent.TButton", command=self.start_audio_compression).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def _build_batch_tab(self, parent):
        parent = self._scrollable_frame(parent)
        parent.columnconfigure(0, weight=1)
        box = ttk.LabelFrame(parent, text="批量压缩", padding=12)
        box.grid(row=0, column=0, sticky="nsew")
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text="输入文件夹").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(box, textvariable=self.batch_input_dir).grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(box, text="浏览…", command=self.choose_batch_input_dir).grid(row=0, column=2, pady=5)
        ttk.Label(box, text="输出文件夹").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(box, textvariable=self.batch_output_dir).grid(row=1, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(box, text="浏览…", command=self.choose_batch_output_dir).grid(row=1, column=2, pady=5)
        ttk.Label(box, text="批量预设").grid(row=2, column=0, sticky="w", pady=5)
        preset_row = ttk.Frame(box)
        preset_row.grid(row=2, column=1, columnspan=2, sticky="ew", pady=5)
        preset_row.columnconfigure(0, weight=1)
        ttk.Combobox(preset_row, textvariable=self.batch_preset_name, values=list(BATCH_PRESETS), state="readonly").grid(row=0, column=0, sticky="ew")
        ttk.Checkbutton(preset_row, text="竖屏模式", variable=self.batch_vertical_mode).grid(row=0, column=1, padx=(10, 0))
        ttk.Checkbutton(box, text="保留原目录结构", variable=self.batch_keep_tree).grid(row=3, column=0, columnspan=3, sticky="w", pady=5)
        ttk.Checkbutton(box, text="同时处理音频文件", variable=self.batch_include_audio).grid(row=4, column=0, columnspan=3, sticky="w", pady=5)
        ttk.Button(box, text="▶ 扫描并开始批量压缩", style="Accent.TButton", command=self.start_batch_compression).grid(row=5, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Label(
            box,
            text="批量页适合整盘素材归档：自动扫描输入文件夹，视频按预设压缩，音频可同步转 AAC。",
            style="Hint.TLabel",
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(12, 0))

    def _build_lut_tab(self, parent):
        parent = self._scrollable_frame(parent)
        parent.columnconfigure(0, weight=1)
        setup = ttk.LabelFrame(parent, text="LUT 批量缩略图对比", padding=12)
        setup.grid(row=0, column=0, sticky="ew")
        setup.columnconfigure(1, weight=1)
        ttk.Label(setup, text="视频文件").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(setup, textvariable=self.lut_page_video).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(setup, text="选择…", command=self.choose_lut_page_video).grid(row=0, column=2)
        ttk.Label(setup, text="LUT 文件夹").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(setup, textvariable=self.lut_page_folder).grid(row=1, column=1, sticky="ew", padx=8)
        ttk.Button(setup, text="选择…", command=self.choose_lut_page_folder).grid(row=1, column=2)
        ttk.Label(setup, text="输出目录").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(setup, textvariable=self.lut_page_output).grid(row=2, column=1, sticky="ew", padx=8)
        ttk.Button(setup, text="选择…", command=self.choose_lut_page_output).grid(row=2, column=2)
        ttk.Label(setup, text="取帧时间").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Spinbox(setup, from_=0, to=3600, increment=0.5, textvariable=self.lut_page_time).grid(row=3, column=1, sticky="ew", padx=8)
        ttk.Button(setup, text="▶ 生成所有 LUT 缩略图", style="Accent.TButton", command=self.start_lut_folder_preview).grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 0))

        result = ttk.LabelFrame(parent, text="缩略图结果", padding=12)
        result.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        result.columnconfigure(0, weight=1)
        result.rowconfigure(0, weight=1)
        self.lut_result_canvas = Canvas(result, height=170, bg=self.COLORS["surface_alt"], highlightthickness=1, highlightbackground=self.COLORS["panel_border"])
        self.lut_result_canvas.grid(row=0, column=0, sticky="ew")
        lut_scroll = ttk.Scrollbar(result, orient="horizontal", command=self.lut_result_canvas.xview)
        lut_scroll.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.lut_result_canvas.configure(xscrollcommand=lut_scroll.set)
        self.lut_result_strip = ttk.Frame(self.lut_result_canvas)
        self.lut_result_window = self.lut_result_canvas.create_window((0, 0), window=self.lut_result_strip, anchor="nw")
        self.lut_result_strip.bind("<Configure>", lambda event: self.lut_result_canvas.configure(scrollregion=self.lut_result_canvas.bbox("all")))

    def _build_mediainfo_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        toolbar = ttk.LabelFrame(parent, text="媒体信息", padding=12)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(1, weight=1)
        ttk.Button(toolbar, text="打开文件…", command=self.choose_mediainfo_file).grid(row=0, column=0, sticky="w")
        ttk.Entry(toolbar, textvariable=self.media_info_path).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(toolbar, text="读取信息", style="Accent.TButton", command=self.load_mediainfo).grid(row=0, column=2)
        ttk.Label(toolbar, text="支持拖入媒体文件；信息由本机 ffprobe 读取。", style="Hint.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        panel = ttk.Frame(parent)
        panel.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=1)
        self.media_info_text = Text(
            panel,
            wrap="word",
            borderwidth=1,
            relief="solid",
            background="#ffffff",
            foreground=self.COLORS["text"],
            insertbackground=self.COLORS["text"],
            font=("Microsoft YaHei UI", 10),
            padx=12,
            pady=10,
        )
        self.media_info_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=self.media_info_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.media_info_text.configure(yscrollcommand=scrollbar.set)

    def _build_tasks_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        panel = ttk.LabelFrame(parent, text="任务队列", padding=12)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=1)
        self.task_tree = ttk.Treeview(panel, columns=("name", "status", "started", "finished"), show="headings", height=14)
        self.task_tree.heading("name", text="任务")
        self.task_tree.heading("status", text="状态")
        self.task_tree.heading("started", text="开始时间")
        self.task_tree.heading("finished", text="结束时间")
        self.task_tree.column("name", width=360)
        self.task_tree.column("status", width=120)
        self.task_tree.column("started", width=150)
        self.task_tree.column("finished", width=150)
        self.task_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=self.task_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.task_tree.configure(yscrollcommand=scrollbar.set)
        self.task_tree.bind("<ButtonPress-1>", self._task_drag_start)
        self.task_tree.bind("<B1-Motion>", self._task_drag_motion)
        self.task_tree.bind("<Double-1>", lambda event: self.start_selected_queued_tasks())
        actions = ttk.Frame(panel)
        actions.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="▶ 开始选中", style="Accent.TButton", command=self.start_selected_queued_tasks).pack(side="left")
        ttk.Button(actions, text="▶ 开始全部", command=self.start_all_queued_tasks).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="移除选中", command=self.remove_selected_tasks).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="■ 停止全部", command=self.stop).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="清除已完成", command=self.clear_finished_tasks).pack(side="left", padx=8)

        options = ttk.Frame(panel)
        options.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Label(options, text="同时进行任务数").pack(side="left")
        ttk.Spinbox(options, from_=1, to=4, increment=1, width=6, textvariable=self.queue_parallel_jobs).pack(side="left", padx=(8, 16))
        ttk.Label(options, text="队列任务使用入队时的视频列表与压缩参数；拖动任务行可调整执行顺序，双击可启动选中任务。", style="Hint.TLabel").pack(side="left")

    def _scrollable_frame(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        canvas = Canvas(parent, highlightthickness=0, bg=self.COLORS["bg"], bd=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        inner.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))
        return inner

    def _create_work_listbox(self, parent, **kwargs):
        options = {
            "activestyle": "none",
            "borderwidth": 0,
            "highlightthickness": 1,
            "highlightbackground": self.COLORS["panel_border"],
            "highlightcolor": self.COLORS["accent"],
            "background": self.COLORS["list_bg"],
            "foreground": self.COLORS["list_fg"],
            "selectbackground": self.COLORS["list_select"],
            "selectforeground": "#ffffff",
            "relief": "flat",
            "font": ("Microsoft YaHei UI", 10),
        }
        options.update(kwargs)
        return Listbox(parent, **options)

    def _build_bitrate_buttons(self, parent, variable, values):
        for child in parent.winfo_children():
            child.destroy()
        parent.columnconfigure(len(values), weight=1)
        for index, value in enumerate(values):
            ttk.Radiobutton(parent, text=value, value="" if value in {"无损", "无需设置"} else value, variable=variable).grid(row=0, column=index, padx=(0, 6), sticky="w")

    def _refresh_audio_bitrate_buttons(self):
        if not hasattr(self, "audio_bitrate_buttons_frame"):
            return
        values = AUDIO_BITRATE_PRESETS.get(self.audio_encoder_name.get(), ["128k", "192k", "320k"])
        current = self.audio_page_bitrate.get()
        normalized_values = ["" if value == "无损" else value for value in values]
        if current not in normalized_values:
            self.audio_page_bitrate.set(normalized_values[0])
        self._build_bitrate_buttons(self.audio_bitrate_buttons_frame, self.audio_page_bitrate, values)

    def _refresh_video_audio_bitrate_buttons(self):
        if not hasattr(self, "video_audio_bitrate_buttons_frame"):
            return
        mode = self.audio_mode.get()
        if "Opus" in mode:
            values = ["96k", "128k", "160k", "192k"]
        elif "MP3" in mode:
            values = ["128k", "192k", "256k", "320k"]
        elif "FLAC" in mode or "复制" in mode or "移除" in mode:
            values = ["无损"] if "FLAC" in mode else ["无需设置"]
        else:
            values = ["128k", "160k", "192k", "256k", "320k"]
        normalized_values = ["" if value in {"无损", "无需设置"} else value for value in values]
        if self.audio_bitrate.get() not in normalized_values:
            self.audio_bitrate.set(normalized_values[0])
        self._build_bitrate_buttons(self.video_audio_bitrate_buttons_frame, self.audio_bitrate, values)

    def _encoder_choices(self):
        return list(ENCODERS) if self.advanced_encoders.get() else list(COMMON_ENCODERS)

    def refresh_encoder_choices(self):
        choices = self._encoder_choices()
        if hasattr(self, "encoder_combo"):
            self.encoder_combo.configure(values=choices)
        if self.encoder_name.get() not in choices:
            self.encoder_name.set(choices[0])
        self._rebuild_settings_panel()

    def _add_encoder_controls(self, panel, row):
        ttk.Label(panel, text="编码器").grid(row=row, column=0, sticky="w", pady=5)
        encoder_row = ttk.Frame(panel)
        encoder_row.grid(row=row, column=1, sticky="ew", pady=5)
        encoder_row.columnconfigure(0, weight=1)
        self.encoder_combo = ttk.Combobox(encoder_row, textvariable=self.encoder_name, values=self._encoder_choices(), state="readonly")
        self.encoder_combo.grid(row=0, column=0, sticky="ew")
        ttk.Checkbutton(encoder_row, text="高级模式", variable=self.advanced_encoders, command=self.refresh_encoder_choices).grid(row=0, column=1, padx=(8, 0))

        row += 1
        ttk.Label(panel, text="速度/质量").grid(row=row, column=0, sticky="w", pady=5)
        ttk.Combobox(panel, textvariable=self.preset_name, values=list(PRESETS), state="readonly").grid(row=row, column=1, sticky="ew", pady=5)

        if self.advanced_encoders.get():
            row += 1
            ttk.Label(panel, text="质量模式").grid(row=row, column=0, sticky="w", pady=5)
            ttk.Combobox(panel, textvariable=self.quality_mode, values=list(QUALITY_MODES), state="readonly").grid(row=row, column=1, sticky="ew", pady=5)

        row += 1
        ttk.Label(panel, text="CRF").grid(row=row, column=0, sticky="w", pady=5)
        quality = ttk.Frame(panel)
        quality.grid(row=row, column=1, sticky="ew", pady=5)
        quality.columnconfigure(0, weight=1)
        ttk.Scale(quality, from_=16, to=32, orient=HORIZONTAL, variable=self.cq_value).grid(row=0, column=0, sticky="ew")
        ttk.Label(quality, textvariable=self.cq_value, width=4).grid(row=0, column=1, padx=(8, 0))

        if self.advanced_encoders.get():
            row += 1
            ttk.Label(panel, text="目标码率").grid(row=row, column=0, sticky="w", pady=5)
            bitrate_row = ttk.Frame(panel)
            bitrate_row.grid(row=row, column=1, sticky="ew", pady=5)
            bitrate_row.columnconfigure(0, weight=1)
            ttk.Entry(bitrate_row, textvariable=self.bitrate).grid(row=0, column=0, sticky="ew")
            ttk.Label(bitrate_row, text="2PASS 使用，如 4000k", style="Hint.TLabel").grid(row=0, column=1, padx=(8, 0))

            row += 1
            ttk.Label(panel, text="自定义命令").grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(panel, textvariable=self.custom_command).grid(row=row, column=1, sticky="ew", pady=5)

        row += 1
        ttk.Label(panel, text="音频").grid(row=row, column=0, sticky="w", pady=5)
        ttk.Combobox(panel, textvariable=self.audio_mode, values=list(AUDIO_MODES), state="readonly").grid(row=row, column=1, sticky="ew", pady=5)

        row += 1
        ttk.Label(panel, text="音频码率").grid(row=row, column=0, sticky="w", pady=5)
        video_audio_rate_row = ttk.Frame(panel)
        video_audio_rate_row.grid(row=row, column=1, sticky="ew", pady=5)
        self.video_audio_bitrate_buttons_frame = video_audio_rate_row
        self._refresh_video_audio_bitrate_buttons()
        self.audio_mode.trace_add("write", lambda *_: self._refresh_video_audio_bitrate_buttons())

        row += 1
        ttk.Label(panel, text="分离器/容器").grid(row=row, column=0, sticky="w", pady=5)
        ttk.Combobox(panel, textvariable=self.muxer_name, values=list(VIDEO_MUXERS), state="readonly").grid(row=row, column=1, sticky="ew", pady=5)

        row += 1
        ttk.Label(panel, text="分辨率").grid(row=row, column=0, sticky="w", pady=5)
        ttk.Combobox(panel, textvariable=self.resolution_name, values=list(RESOLUTIONS), state="readonly").grid(row=row, column=1, sticky="ew", pady=5)

        row += 1
        ttk.Label(panel, text="锐化").grid(row=row, column=0, sticky="w", pady=5)
        ttk.Combobox(panel, textvariable=self.sharpen_name, values=list(SHARPEN_LEVELS), state="readonly").grid(row=row, column=1, sticky="ew", pady=5)

        if self.advanced_encoders.get():
            row += 1
            ttk.Label(panel, text="自定义宽度").grid(row=row, column=0, sticky="w", pady=5)
            ttk.Spinbox(panel, from_=320, to=7680, increment=2, textvariable=self.custom_width).grid(row=row, column=1, sticky="ew", pady=5)

        row += 1
        ttk.Label(panel, text="并发任务").grid(row=row, column=0, sticky="w", pady=5)
        parallel_row = ttk.Frame(panel)
        parallel_row.grid(row=row, column=1, sticky="ew", pady=5)
        parallel_row.columnconfigure(0, weight=1)
        ttk.Spinbox(parallel_row, from_=1, to=8, increment=1, textvariable=self.parallel_jobs).grid(row=0, column=0, sticky="ew")
        ttk.Label(parallel_row, text="批量时提高 GPU 占用", style="Hint.TLabel").grid(row=0, column=1, padx=(8, 0))

        return row + 1

    def _add_lut_controls(self, panel, row):
        if not self.advanced_encoders.get():
            return row
        ttk.Label(panel, text="LUT 调色").grid(row=row, column=0, sticky="w", pady=5)
        lut_row = ttk.Frame(panel)
        lut_row.grid(row=row, column=1, sticky="ew", pady=5)
        lut_row.columnconfigure(1, weight=1)
        ttk.Checkbutton(lut_row, text="启用", variable=self.use_lut).grid(row=0, column=0, sticky="w")
        ttk.Entry(lut_row, textvariable=self.lut_path).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(lut_row, text="选择…", command=self.choose_lut).grid(row=0, column=2)
        ttk.Button(lut_row, text="▶ 预览", command=self.start_lut_preview).grid(row=0, column=3, padx=(6, 0))

        row += 1
        preview_frame = ttk.Frame(panel)
        preview_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 8))
        preview_frame.columnconfigure(0, weight=1)
        self.preview_label = ttk.Label(preview_frame, text="选择视频和 LUT 后可预览当前缩略图时间点", anchor="center")
        self.preview_label.grid(row=0, column=0, sticky="ew")

        row += 1
        ttk.Label(panel, text="高级参数").grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(panel, textvariable=self.extra_ffmpeg_args).grid(row=row, column=1, sticky="ew", pady=5)
        return row + 1

    def _add_thumbnail_controls(self, panel, row):
        ttk.Checkbutton(panel, text="压缩后生成 JPG 缩略图", variable=self.create_thumbnail).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        if not self.advanced_encoders.get():
            return row + 1
        row += 1
        ttk.Checkbutton(panel, text="只给选中视频批量生成缩略图", variable=self.thumbnail_only_selected).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)

        row += 1
        ttk.Label(panel, text="缩略图时间").grid(row=row, column=0, sticky="w", pady=5)
        thumb_row = ttk.Frame(panel)
        thumb_row.grid(row=row, column=1, sticky="ew", pady=5)
        thumb_row.columnconfigure(0, weight=1)
        ttk.Spinbox(thumb_row, from_=0, to=3600, increment=0.5, textvariable=self.thumbnail_time).grid(row=0, column=0, sticky="ew")
        ttk.Label(thumb_row, text="秒", style="Hint.TLabel").grid(row=0, column=1, padx=(8, 0))

        return row + 1

    def _add_action_buttons(self, panel, row):
        actions = ttk.Frame(panel)
        actions.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        actions.columnconfigure((0, 1), weight=1)
        conflict = ttk.LabelFrame(actions, text="如果文件已存在", padding=(10, 8))
        conflict.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        for index, value in enumerate(("跳过", "覆盖", "重命名")):
            ttk.Radiobutton(conflict, text=value, value=value, variable=self.file_conflict_action).grid(row=0, column=index, sticky="w", padx=(0, 14))

        ttk.Button(actions, text="▶ 开始压缩", style="Accent.TButton", command=self.start_compression).grid(row=1, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="■ 停止", command=self.stop).grid(row=1, column=1, sticky="ew", padx=(6, 0))
        ttk.Button(actions, text="▣ 批量生成缩略图", command=self.start_thumbnail_batch).grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=(8, 0))
        ttk.Button(actions, text="◷ CPU/GPU Benchmark", command=self.start_benchmark).grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=(8, 0))
        ttk.Button(actions, text="⬇ 生成代理文件", command=self.start_proxy_files).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        return row + 1

    def _build_bottom_panel(self, parent):
        panel = ttk.Frame(parent)
        panel.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        panel.columnconfigure(0, weight=1)
        ttk.Label(panel, textvariable=self.current_task, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Progressbar(panel, variable=self.progress, maximum=100).grid(row=1, column=0, sticky="ew", pady=6)
        self.log = self._create_work_listbox(panel, height=7)
        self.log.grid(row=2, column=0, sticky="nsew")

    def _bind_keys(self):
        self.root.bind("<space>", lambda event: self.toggle_preview_playback())
        self.root.bind("<Left>", lambda event: self.seek_preview(-5))
        self.root.bind("<Right>", lambda event: self.seek_preview(5))
        self.root.bind("<Control-Left>", lambda event: self.seek_preview(-30))
        self.root.bind("<Control-Right>", lambda event: self.seek_preview(30))
        self.root.bind("<Home>", lambda event: self.seek_preview_to(0))
        self.root.bind("<End>", lambda event: self.seek_preview_to(self.preview_duration))
        self.root.bind("<Key-s>", lambda event: self.save_current_screenshot())
        self.root.bind("<Key-o>", lambda event: self.choose_screenshot_dir())

    def open_settings_window(self):
        window = Toplevel(self.root)
        window.title("设置")
        window.geometry("620x620")
        window.resizable(False, False)
        box = ttk.Frame(window, padding=16)
        box.pack(fill="both", expand=True)
        box.columnconfigure(0, weight=1)

        ui = ttk.LabelFrame(box, text="界面设置", padding=12)
        ui.grid(row=0, column=0, sticky="ew")
        ui.columnconfigure(1, weight=1)
        ttk.Label(ui, text="界面语言").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Combobox(ui, textvariable=self.interface_language, values=["中文", "English"], state="readonly").grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Checkbutton(ui, text="托盘模式：点击 X 后后台继续运行", variable=self.tray_mode).grid(row=1, column=0, columnspan=2, sticky="w", pady=5)

        codec = ttk.LabelFrame(box, text="x264 设置", padding=12)
        codec.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        codec.columnconfigure(1, weight=1)
        ttk.Label(codec, text="优先级").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Combobox(codec, textvariable=self.x264_priority, values=["低", "正常", "高"], state="readonly").grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Label(codec, text="线程数量").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Spinbox(codec, from_=0, to=64, increment=1, textvariable=self.x264_threads).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Label(codec, text="自定义命令行").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(codec, textvariable=self.x264_command).grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Label(codec, text="线程 0 表示由 x264 自动决定；自定义命令可用于覆盖当前视频页命令。", style="Hint.TLabel").grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        features = ttk.LabelFrame(box, text="功能设置", padding=12)
        features.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        features.columnconfigure(1, weight=1)
        ttk.Label(features, text="预览播放器").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(features, textvariable=self.default_player).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=5)
        ttk.Button(features, text="选择…", command=self.choose_default_player).grid(row=0, column=2, pady=5)
        ttk.Label(features, text="为空时调用 Windows 默认播放器。", style="Hint.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 0))
        ttk.Checkbutton(features, text="高级模式显示所有编码器和进阶参数", variable=self.advanced_encoders, command=self.refresh_encoder_choices).grid(row=2, column=0, columnspan=3, sticky="w", pady=5)
        ttk.Checkbutton(features, text="启用文件拖入（需要 tkinterdnd2 支持）", variable=self.enable_drag_drop, command=self._setup_drag_drop).grid(row=3, column=0, columnspan=3, sticky="w", pady=5)
        ttk.Checkbutton(features, text="覆盖前提醒", variable=self.confirm_overwrite).grid(row=4, column=0, columnspan=3, sticky="w", pady=5)
        ttk.Checkbutton(features, text="任务完成后打开输出目录", variable=self.auto_open_output).grid(row=5, column=0, columnspan=3, sticky="w", pady=5)

        device = ttk.LabelFrame(box, text="编码器偏好", padding=12)
        device.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        device.columnconfigure(1, weight=1)
        ttk.Label(device, text="编码器优先级").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Combobox(device, textvariable=self.preferred_device, values=["优先 GPU", "优先 CPU"], state="readonly").grid(row=0, column=1, sticky="ew", pady=5)

        actions = ttk.Frame(box)
        actions.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        actions.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(actions, text="还原默认设置", command=self.restore_default_settings).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="查看日志", command=self.show_log_window).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(actions, text="删除日志", command=self.clear_log).grid(row=0, column=2, sticky="ew", padx=(6, 0))
        ttk.Button(box, text="应用并保存", style="Accent.TButton", command=lambda: [self._apply_app_settings(), window.destroy()]).grid(row=5, column=0, sticky="ew", pady=(14, 0))

    def _apply_preferred_encoder(self):
        if self.preferred_device.get() == "优先 CPU":
            self.encoder_name.set("CPU H.264 / AVC (libx264)")
        else:
            self.encoder_name.set("GPU H.265 / HEVC (hevc_nvenc)")
        self.refresh_encoder_choices()

    def _apply_app_settings(self):
        self._apply_preferred_encoder()
        self._save_app_settings()
        self._log("设置已保存。")

    def choose_default_player(self):
        path = filedialog.askopenfilename(title="选择预览播放器", filetypes=[("程序", "*.exe"), ("所有文件", "*.*")])
        if path:
            self.default_player.set(path)

    def restore_default_settings(self):
        if not messagebox.askyesno("还原默认设置", "确认还原界面、功能和 x264 设置为默认值？"):
            return
        self.interface_language.set("中文")
        self.tray_mode.set(True)
        self.x264_priority.set("正常")
        self.x264_threads.set(0)
        self.x264_command.set("")
        self.default_player.set("")
        self.preferred_device.set("优先 GPU")
        self.enable_drag_drop.set(True)
        self.confirm_overwrite.set(True)
        self.auto_open_output.set(False)
        self.advanced_encoders.set(False)
        self.refresh_encoder_choices()
        self._save_app_settings()
        self._log("已还原默认设置。")

    def show_log_window(self):
        window = Toplevel(self.root)
        window.title("运行日志")
        window.geometry("760x460")
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        text = Text(frame, wrap="word", background="#ffffff", foreground=self.COLORS["text"], font=("Microsoft YaHei UI", 10))
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scrollbar.set)
        lines = [self.log.get(index) for index in range(self.log.size())] if hasattr(self, "log") else []
        text.insert("1.0", "\n".join(lines) if lines else "暂无日志。")
        text.configure(state="disabled")

    def clear_log(self):
        if messagebox.askyesno("删除日志", "确认清空当前运行日志？"):
            if hasattr(self, "log"):
                self.log.delete(0, END)
            self._log("日志已清空。")

    def _save_app_settings(self):
        data = {
            "interface_language": self.interface_language.get(),
            "tray_mode": self.tray_mode.get(),
            "x264_priority": self.x264_priority.get(),
            "x264_threads": self.x264_threads.get(),
            "x264_command": self.x264_command.get(),
            "default_player": self.default_player.get(),
            "preferred_device": self.preferred_device.get(),
            "enable_drag_drop": self.enable_drag_drop.get(),
            "confirm_overwrite": self.confirm_overwrite.get(),
            "auto_open_output": self.auto_open_output.get(),
            "advanced_encoders": self.advanced_encoders.get(),
        }
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            self._log(f"保存应用设置失败：{exc}")

    def _load_app_settings(self):
        if not self.settings_path.exists():
            return
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._log(f"读取应用设置失败：{exc}")
            return
        mapping = {
            "interface_language": self.interface_language,
            "tray_mode": self.tray_mode,
            "x264_priority": self.x264_priority,
            "x264_threads": self.x264_threads,
            "x264_command": self.x264_command,
            "default_player": self.default_player,
            "preferred_device": self.preferred_device,
            "enable_drag_drop": self.enable_drag_drop,
            "confirm_overwrite": self.confirm_overwrite,
            "auto_open_output": self.auto_open_output,
            "advanced_encoders": self.advanced_encoders,
        }
        for key, variable in mapping.items():
            if key in data:
                variable.set(data[key])
        self.refresh_encoder_choices()

    def _on_main_close(self):
        self._save_app_settings()
        if self.tray_mode.get():
            self.root.withdraw()
            self._log("托盘模式已启用：窗口已隐藏，任务会继续在后台运行。")
            return
        self.root.destroy()

    def _setup_drag_drop(self):
        if not self.enable_drag_drop.get():
            return
        try:
            from tkinterdnd2 import DND_FILES
        except Exception:
            self.messages.put(("log", "拖入增强未启用：如需文件拖拽，请安装 tkinterdnd2。"))
            return
        for widget, target in (
            (self.file_list, "video"),
            (getattr(self, "audio_file_list", None), "audio"),
            (getattr(self, "retro_file_list", None), "retro"),
            (getattr(self, "media_info_text", None), "mediainfo"),
        ):
            if not widget:
                continue
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", lambda event, kind=target: self._handle_drop(event.data, kind))
            except Exception as exc:
                self.messages.put(("log", f"拖入绑定失败：{exc}"))

    def _handle_drop(self, data, kind):
        paths = self.root.tk.splitlist(data)
        if kind == "audio":
            self._add_audio_paths(paths)
        elif kind == "retro":
            self._add_retro_paths(paths)
        elif kind == "mediainfo":
            self._set_mediainfo_path(paths)
        else:
            self._add_paths(paths)

    def open_player_preview(self):
        source = self._preview_source()
        if not source:
            messagebox.showwarning("没有视频", "请先添加视频，最好在列表中选中一个要预览的视频。")
            return
        try:
            if os.name == "nt":
                player = self.default_player.get().strip()
                if player:
                    subprocess.Popen([player, str(Path(source))], creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    os.startfile(str(Path(source)))
            else:
                messagebox.showinfo("播放预览", "当前仅实现 Windows 默认播放器调用。")
        except Exception as exc:
            messagebox.showerror("播放失败", f"无法调用系统播放器：{exc}")
        return
        self.preview_source_path = Path(source)
        self.preview_duration = ffmpeg.duration_seconds(self.preview_source_path)
        self.preview_seconds.set(0.0)
        if self.preview_window and self.preview_window.winfo_exists():
            self.preview_window.lift()
            self.render_preview_frame()
            return
        self.preview_window = Toplevel(self.root)
        self.preview_window.title(f"播放预览 - {self.preview_source_path.name}")
        self.preview_window.geometry("1040x720")
        self.preview_window.columnconfigure(0, weight=1)
        self.preview_window.rowconfigure(0, weight=1)
        self.preview_window.protocol("WM_DELETE_WINDOW", self.close_player_preview)
        self.preview_window.bind("<space>", lambda event: self.toggle_preview_playback())
        self.preview_window.bind("<Left>", lambda event: self.seek_preview(-5))
        self.preview_window.bind("<Right>", lambda event: self.seek_preview(5))
        self.preview_window.bind("<Control-Left>", lambda event: self.seek_preview(-30))
        self.preview_window.bind("<Control-Right>", lambda event: self.seek_preview(30))
        self.preview_window.bind("<Home>", lambda event: self.seek_preview_to(0))
        self.preview_window.bind("<End>", lambda event: self.seek_preview_to(self.preview_duration))
        self.preview_window.bind("<Key-s>", lambda event: self.save_current_screenshot())
        self.preview_window.bind("<Key-o>", lambda event: self.choose_screenshot_dir())

        body = ttk.Frame(self.preview_window, padding=12)
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        self.player_image_label = ttk.Label(body, text="正在生成预览帧...", anchor="center")
        self.player_image_label.grid(row=0, column=0, sticky="nsew")

        controls = ttk.Frame(body)
        controls.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        controls.columnconfigure(4, weight=1)
        ttk.Button(controls, text="后退 5s", command=lambda: self.seek_preview(-5)).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(controls, text="播放/暂停", command=self.toggle_preview_playback).grid(row=0, column=1, padx=6)
        ttk.Button(controls, text="前进 5s", command=lambda: self.seek_preview(5)).grid(row=0, column=2, padx=6)
        ttk.Button(controls, text="截图", command=self.save_current_screenshot).grid(row=0, column=3, padx=6)
        self.preview_time_label = ttk.Label(controls, text="00:00 / 00:00")
        self.preview_time_label.grid(row=0, column=4, sticky="e")

        slider = ttk.Scale(
            body,
            from_=0,
            to=max(self.preview_duration, 1),
            orient=HORIZONTAL,
            variable=self.preview_seconds,
            command=self._on_preview_slider,
        )
        slider.grid(row=2, column=0, sticky="ew", pady=8)

        save_row = ttk.Frame(body)
        save_row.grid(row=3, column=0, sticky="ew")
        save_row.columnconfigure(1, weight=1)
        ttk.Label(save_row, text="截图目录").grid(row=0, column=0, sticky="w")
        ttk.Entry(save_row, textvariable=self.screenshot_dir).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(save_row, text="选择", command=self.choose_screenshot_dir).grid(row=0, column=2)
        ttk.Label(
            body,
            text="快捷键：空格播放/暂停，←/→ 跳 5 秒，Ctrl+←/→ 跳 30 秒，Home/End 到首尾，S 截图，O 选择截图目录。",
            style="Hint.TLabel",
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))
        self.render_preview_frame()

    def close_player_preview(self):
        self.preview_playing = False
        if self.preview_after_id:
            self.root.after_cancel(self.preview_after_id)
            self.preview_after_id = None
        if self.preview_window and self.preview_window.winfo_exists():
            self.preview_window.destroy()
        self.preview_window = None

    def render_preview_frame(self):
        if not self.preview_source_path:
            return
        self.preview_frame_path.parent.mkdir(parents=True, exist_ok=True)
        if self.preview_frame_path.exists():
            try:
                self.preview_frame_path.unlink()
            except OSError:
                pass
        seconds = self._clamp_preview_time(self.preview_seconds.get())
        self.preview_seconds.set(seconds)
        output = ffmpeg.run_capture(ffmpeg.build_frame_command(self.preview_source_path, self.preview_frame_path, seconds, self._settings()))
        if self.preview_frame_path.exists() and self.preview_window and self.preview_window.winfo_exists():
            self.player_preview_image = PhotoImage(file=str(self.preview_frame_path))
            self.player_image_label.configure(image=self.player_preview_image, text="")
            self._update_preview_time_label()
        elif output:
            self._log("预览帧生成失败：" + output)

    def toggle_preview_playback(self):
        if not (self.preview_window and self.preview_window.winfo_exists()):
            return
        self.preview_playing = not self.preview_playing
        if self.preview_playing:
            self._tick_preview_playback()

    def _tick_preview_playback(self):
        if not self.preview_playing:
            return
        next_time = self.preview_seconds.get() + 1
        if self.preview_duration and next_time >= self.preview_duration:
            next_time = self.preview_duration
            self.preview_playing = False
        self.preview_seconds.set(self._clamp_preview_time(next_time))
        self.render_preview_frame()
        if self.preview_playing:
            self.preview_after_id = self.root.after(1000, self._tick_preview_playback)

    def seek_preview(self, delta):
        if not (self.preview_window and self.preview_window.winfo_exists()):
            return
        self.seek_preview_to(self.preview_seconds.get() + delta)

    def seek_preview_to(self, seconds):
        if not (self.preview_window and self.preview_window.winfo_exists()):
            return
        self.preview_seconds.set(self._clamp_preview_time(seconds))
        self.render_preview_frame()

    def _on_preview_slider(self, value):
        if not (self.preview_window and self.preview_window.winfo_exists()):
            return
        try:
            self.preview_seconds.set(self._clamp_preview_time(float(value)))
        except ValueError:
            return
        if not self.preview_playing:
            self.render_preview_frame()

    def choose_screenshot_dir(self):
        folder = filedialog.askdirectory(title="选择截图保存目录")
        if folder:
            self.screenshot_dir.set(folder)

    def save_current_screenshot(self):
        if not self.preview_source_path:
            messagebox.showwarning("没有预览视频", "请先打开播放预览窗口。")
            return
        screenshot_dir = Path(self.screenshot_dir.get()).resolve()
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        seconds = self._clamp_preview_time(self.preview_seconds.get())
        target = screenshot_dir / f"{self.preview_source_path.stem}_{int(seconds):06d}s_{timestamp}.jpg"
        output = ffmpeg.run_capture(ffmpeg.build_screenshot_command(self.preview_source_path, target, seconds, self._settings()))
        if target.exists():
            self._log(f"截图已保存：{target}")
        else:
            self._log("截图失败：" + output)

    def _clamp_preview_time(self, seconds):
        seconds = max(0.0, float(seconds))
        if self.preview_duration:
            return min(seconds, self.preview_duration)
        return seconds

    def _update_preview_time_label(self):
        if hasattr(self, "preview_time_label"):
            current = self._format_clock(self.preview_seconds.get())
            total = self._format_clock(self.preview_duration)
            self.preview_time_label.configure(text=f"{current} / {total}")

    def add_files(self):
        paths = filedialog.askopenfilenames(title="选择视频文件", filetypes=VIDEO_FILETYPES)
        self._add_paths(paths)

    def add_folder(self):
        folder = filedialog.askdirectory(title="选择视频文件夹")
        if not folder:
            return
        paths = [str(p) for p in Path(folder).rglob("*") if p.suffix.lower() in VIDEO_EXTENSIONS]
        self._add_paths(paths)

    def _add_paths(self, paths):
        existing = set(self.files)
        for path in self._expand_paths(paths, VIDEO_EXTENSIONS):
            full = str(path.resolve())
            if full not in existing:
                self.files.append(full)
                self.file_list.insert(END, full)
                existing.add(full)
        self._log(f"已添加 {len(self.files)} 个视频")

    def remove_selected(self):
        for index in reversed(self.file_list.curselection()):
            self.file_list.delete(index)
            del self.files[index]

    def clear_files(self):
        self.files.clear()
        self.file_list.delete(0, END)

    def choose_output_dir(self):
        folder = filedialog.askdirectory(title="选择输出目录")
        if folder:
            self.output_dir.set(folder)

    def save_video_settings(self):
        path = filedialog.asksaveasfilename(
            title="保存压缩设置",
            defaultextension=".json",
            filetypes=[("JSON 设置", "*.json"), ("所有文件", "*.*")],
        )
        if not path:
            return
        data = self._video_settings_dict()
        try:
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self._log(f"设置已保存：{path}")
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))

    def import_video_settings(self):
        path = filedialog.askopenfilename(title="导入压缩设置", filetypes=[("JSON 设置", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self._apply_video_settings_dict(data)
            self._log(f"设置已导入：{path}")
        except Exception as exc:
            messagebox.showerror("导入失败", str(exc))

    def load_video_preset(self):
        window = Toplevel(self.root)
        window.title("加载预设")
        window.geometry("420x150")
        window.resizable(False, False)
        box = ttk.Frame(window, padding=16)
        box.pack(fill="both", expand=True)
        preset_name = StringVar(value=self.batch_preset_name.get())
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text="预设").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Combobox(box, textvariable=preset_name, values=list(BATCH_PRESETS), state="readonly").grid(row=0, column=1, sticky="ew", pady=6)
        def apply_preset():
            preset = BATCH_PRESETS[preset_name.get()]
            self.encoder_name.set(preset["encoder"])
            self.resolution_name.set(preset["resolution"])
            self.cq_value.set(preset["cq"])
            self.audio_mode.set(preset["audio"])
            self.audio_bitrate.set(preset["audio_bitrate"])
            self.muxer_name.set(preset["muxer"])
            self.refresh_encoder_choices()
            window.destroy()
        ttk.Button(box, text="加载到当前设置", style="Accent.TButton", command=apply_preset).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(14, 0))

    def _video_settings_dict(self):
        return {
            "encoder_name": self.encoder_name.get(),
            "advanced_encoders": self.advanced_encoders.get(),
            "preset_name": self.preset_name.get(),
            "resolution_name": self.resolution_name.get(),
            "sharpen_name": self.sharpen_name.get(),
            "custom_width": self.custom_width.get(),
            "quality_mode": self.quality_mode.get(),
            "cq_value": self.cq_value.get(),
            "bitrate": self.bitrate.get(),
            "custom_command": self.custom_command.get(),
            "audio_mode": self.audio_mode.get(),
            "audio_bitrate": self.audio_bitrate.get(),
            "muxer_name": self.muxer_name.get(),
            "create_thumbnail": self.create_thumbnail.get(),
            "thumbnail_only_selected": self.thumbnail_only_selected.get(),
            "thumbnail_time": self.thumbnail_time.get(),
            "parallel_jobs": self.parallel_jobs.get(),
            "extra_ffmpeg_args": self.extra_ffmpeg_args.get(),
            "use_lut": self.use_lut.get(),
            "lut_path": self.lut_path.get(),
            "file_conflict_action": self.file_conflict_action.get(),
        }

    def _apply_video_settings_dict(self, data):
        setters = {
            "encoder_name": self.encoder_name,
            "advanced_encoders": self.advanced_encoders,
            "preset_name": self.preset_name,
            "resolution_name": self.resolution_name,
            "sharpen_name": self.sharpen_name,
            "custom_width": self.custom_width,
            "quality_mode": self.quality_mode,
            "cq_value": self.cq_value,
            "bitrate": self.bitrate,
            "custom_command": self.custom_command,
            "audio_mode": self.audio_mode,
            "audio_bitrate": self.audio_bitrate,
            "muxer_name": self.muxer_name,
            "create_thumbnail": self.create_thumbnail,
            "thumbnail_only_selected": self.thumbnail_only_selected,
            "thumbnail_time": self.thumbnail_time,
            "parallel_jobs": self.parallel_jobs,
            "extra_ffmpeg_args": self.extra_ffmpeg_args,
            "use_lut": self.use_lut,
            "lut_path": self.lut_path,
            "file_conflict_action": self.file_conflict_action,
        }
        for key, variable in setters.items():
            if key in data:
                variable.set(data[key])
        self.refresh_encoder_choices()

    def choose_audio_output_dir(self):
        folder = filedialog.askdirectory(title="选择音频输出目录")
        if folder:
            self.audio_output_dir.set(folder)

    def choose_retro_output_dir(self):
        folder = filedialog.askdirectory(title="选择复古输出目录")
        if folder:
            self.retro_output_dir.set(folder)

    def choose_batch_input_dir(self):
        folder = filedialog.askdirectory(title="选择批量输入文件夹")
        if folder:
            self.batch_input_dir.set(folder)

    def choose_batch_output_dir(self):
        folder = filedialog.askdirectory(title="选择批量输出文件夹")
        if folder:
            self.batch_output_dir.set(folder)

    def choose_lut(self):
        path = filedialog.askopenfilename(title="选择 LUT 文件", filetypes=LUT_FILETYPES)
        if path:
            self.lut_path.set(path)
            self.use_lut.set(True)

    def choose_lut_page_video(self):
        path = filedialog.askopenfilename(title="选择用于 LUT 对比的视频", filetypes=VIDEO_FILETYPES)
        if path:
            self.lut_page_video.set(path)

    def choose_lut_page_folder(self):
        folder = filedialog.askdirectory(title="选择 LUT 文件夹")
        if folder:
            self.lut_page_folder.set(folder)

    def choose_lut_page_output(self):
        folder = filedialog.askdirectory(title="选择 LUT 缩略图输出目录")
        if folder:
            self.lut_page_output.set(folder)

    def choose_mediainfo_file(self):
        path = filedialog.askopenfilename(title="选择媒体文件", filetypes=VIDEO_FILETYPES + AUDIO_FILETYPES + [("所有文件", "*.*")])
        if path:
            self.media_info_path.set(path)
            self.load_mediainfo()

    def _set_mediainfo_path(self, paths):
        for raw in paths:
            path = Path(raw)
            if path.is_file():
                self.media_info_path.set(str(path.resolve()))
                self.load_mediainfo()
                return

    def add_audio_files(self):
        paths = filedialog.askopenfilenames(title="选择音频文件", filetypes=AUDIO_FILETYPES)
        self._add_audio_paths(paths)

    def add_audio_folder(self):
        folder = filedialog.askdirectory(title="选择音频文件夹")
        if not folder:
            return
        paths = [str(p) for p in Path(folder).rglob("*") if p.suffix.lower() in AUDIO_EXTENSIONS]
        self._add_audio_paths(paths)

    def _add_audio_paths(self, paths):
        existing = set(self.audio_files)
        for path in self._expand_paths(paths, AUDIO_EXTENSIONS):
            full = str(path.resolve())
            if full not in existing:
                self.audio_files.append(full)
                self.audio_file_list.insert(END, full)
                existing.add(full)
        self._log(f"已添加 {len(self.audio_files)} 个音频")

    def _expand_paths(self, paths, extensions):
        expanded = []
        for raw in paths:
            path = Path(raw)
            if path.is_dir():
                expanded.extend(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in extensions)
            elif path.is_file() and path.suffix.lower() in extensions:
                expanded.append(path)
        return expanded

    def remove_selected_audio(self):
        for index in reversed(self.audio_file_list.curselection()):
            self.audio_file_list.delete(index)
            del self.audio_files[index]

    def clear_audio_files(self):
        self.audio_files.clear()
        self.audio_file_list.delete(0, END)

    def add_retro_files(self):
        paths = filedialog.askopenfilenames(title="选择古老素材文件", filetypes=VIDEO_FILETYPES)
        self._add_retro_paths(paths)

    def add_retro_folder(self):
        folder = filedialog.askdirectory(title="选择古老素材文件夹")
        if not folder:
            return
        self._add_retro_paths([folder])

    def _add_retro_paths(self, paths):
        existing = set(self.retro_files)
        for path in self._expand_paths(paths, VIDEO_EXTENSIONS):
            full = str(path.resolve())
            if full not in existing:
                self.retro_files.append(full)
                self.retro_file_list.insert(END, full)
                existing.add(full)
        self._log(f"已添加 {len(self.retro_files)} 个复古素材")

    def remove_selected_retro(self):
        for index in reversed(self.retro_file_list.curselection()):
            self.retro_file_list.delete(index)
            del self.retro_files[index]

    def clear_retro_files(self):
        self.retro_files.clear()
        self.retro_file_list.delete(0, END)

    def check_environment(self):
        info = ffmpeg.detect_environment()
        if not info.ffmpeg:
            messagebox.showerror("环境检测", "未找到 ffmpeg。请安装 FFmpeg 6.0+ 并加入 PATH。")
            return
        text = [
            f"ffmpeg: {info.ffmpeg}",
            f"ffprobe: {info.ffprobe or '未找到，仍可压缩但进度估算会变弱'}",
            f"NVENC 编码器: {'可用' if info.has_nvenc else '未检测到'}",
            f"AMF 编码器: {'可用' if info.has_amf else '未检测到'}",
        ]
        messagebox.showinfo("环境检测", "\n".join(text))

    def start_proxy_files(self):
        if not self._confirm_overwrite_if_needed():
            return
        if not self.files:
            messagebox.showwarning("没有视频", "请先添加视频文件。")
            return
        self._start_worker("生成代理文件", self._proxy_worker)

    def start_compression(self):
        if not self._confirm_overwrite_if_needed():
            return
        if not self.files:
            messagebox.showwarning("没有视频", "请先添加单个或批量视频。")
            return
        self._start_worker("视频压缩", self._compress_worker)

    def add_current_video_to_queue(self):
        if not self.files:
            messagebox.showwarning("没有视频", "请先添加视频文件。")
            return
        files = list(self.files)
        settings = self._settings()
        output_dir = Path(self.output_dir.get()).resolve()
        task_id = self._create_task(f"视频压缩（{len(files)} 个文件）")
        self.queued_tasks[task_id] = {
            "type": "video",
            "files": files,
            "settings": settings,
            "output_dir": output_dir,
            "conflict_action": self.file_conflict_action.get(),
        }
        self._update_task_status(task_id, "已加入队列")
        self.notebook.select(self.tasks_tab)

    def start_selected_queued_tasks(self):
        selected = [item for item in self.task_tree.selection() if item in self.queued_tasks and self._task_status(item) != "运行中"]
        if not selected:
            messagebox.showwarning("没有待启动任务", "请先选择已加入队列的任务。")
            return
        self._start_worker("启动选中队列任务", self._queued_tasks_worker, selected)

    def start_all_queued_tasks(self):
        task_ids = [item for item in self.task_tree.get_children() if item in self.queued_tasks and self._task_status(item) != "运行中"]
        if not task_ids:
            messagebox.showwarning("没有待启动任务", "请先通过顶部“加入队列”添加任务。")
            return
        self._start_worker("启动全部队列任务", self._queued_tasks_worker, task_ids)

    def move_selected_task(self, direction):
        if not hasattr(self, "task_tree"):
            return
        selected = self.task_tree.selection()
        if not selected:
            return
        item = selected[0]
        siblings = list(self.task_tree.get_children())
        index = siblings.index(item)
        new_index = max(0, min(len(siblings) - 1, index + direction))
        if new_index == index:
            return
        self.task_tree.move(item, "", new_index)
        self.task_tree.selection_set(item)

    def _task_drag_start(self, event):
        if not hasattr(self, "task_tree"):
            return
        item = self.task_tree.identify_row(event.y)
        self.dragged_task = item if item in self.queued_tasks else None
        if self.dragged_task:
            self.task_tree.selection_set(self.dragged_task)

    def _task_drag_motion(self, event):
        item = getattr(self, "dragged_task", None)
        if not item or not self.task_tree.exists(item):
            return
        target = self.task_tree.identify_row(event.y)
        if not target or target == item:
            return
        values = self.task_tree.item(item, "values")
        target_values = self.task_tree.item(target, "values")
        if (values and values[1] == "运行中") or (target_values and target_values[1] == "运行中"):
            return
        siblings = list(self.task_tree.get_children())
        self.task_tree.move(item, "", siblings.index(target))
        self.task_tree.selection_set(item)

    def remove_selected_tasks(self):
        if not hasattr(self, "task_tree"):
            return
        for item in self.task_tree.selection():
            values = self.task_tree.item(item, "values")
            if values and values[1] == "运行中":
                continue
            self.queued_tasks.pop(item, None)
            self.task_tree.delete(item)

    def _task_status(self, item):
        if not hasattr(self, "task_tree") or not self.task_tree.exists(item):
            return ""
        values = self.task_tree.item(item, "values")
        return values[1] if len(values) > 1 else ""

    def start_thumbnail_batch(self):
        files = self._selected_files() if self.thumbnail_only_selected.get() else list(self.files)
        if not files:
            messagebox.showwarning("没有视频", "请先添加视频，或在列表中选中要生成缩略图的视频。")
            return
        self._start_worker("批量缩略图", self._thumbnail_worker, files)

    def start_lut_preview(self):
        source = self._preview_source()
        if not source:
            messagebox.showwarning("没有视频", "请先添加视频，最好在列表中选中一个要预览的视频。")
            return
        if self.use_lut.get() and not self.lut_path.get().strip():
            messagebox.showwarning("没有 LUT", "请先选择 LUT 文件。")
            return
        if self.use_lut.get() and not Path(self.lut_path.get()).exists():
            messagebox.showwarning("LUT 不存在", "当前 LUT 文件路径不存在，请重新选择。")
            return
        self._start_worker("LUT 预览", self._lut_preview_worker, Path(source))

    def start_benchmark(self):
        sample = Path.cwd() / "test.mp4"
        if not sample.exists():
            messagebox.showwarning("缺少样本", f"未找到内置样本：{sample}")
            return
        self._start_worker("CPU/GPU Benchmark", self._benchmark_worker, sample)

    def start_audio_compression(self):
        if not self._confirm_overwrite_if_needed():
            return
        if not self.audio_files:
            messagebox.showwarning("没有音频", "请先添加单个或批量音频文件。")
            return
        self._start_worker("音频压缩", self._audio_worker)

    def start_retro_processing(self):
        if not self._confirm_overwrite_if_needed():
            return
        if not self.retro_files:
            messagebox.showwarning("没有素材", "请先添加古老素材文件。")
            return
        self._start_worker("复古处理", self._retro_worker)

    def start_retro_remux(self):
        if not self._confirm_overwrite_if_needed():
            return
        if not self.retro_files:
            messagebox.showwarning("没有素材", "请先添加要封装转换的素材文件。")
            return
        self._start_worker("封装转换", self._retro_remux_worker)

    def start_batch_compression(self):
        if not self._confirm_overwrite_if_needed():
            return
        input_dir = Path(self.batch_input_dir.get())
        if not input_dir.exists():
            messagebox.showwarning("输入文件夹不存在", "请先选择有效的批量输入文件夹。")
            return
        self._start_worker("批量压缩", self._batch_worker)

    def start_lut_folder_preview(self):
        video = Path(self.lut_page_video.get())
        folder = Path(self.lut_page_folder.get())
        if not video.exists():
            messagebox.showwarning("没有视频", "请先选择用于预览的视频。")
            return
        if not folder.exists():
            messagebox.showwarning("没有 LUT 文件夹", "请先选择有效的 LUT 文件夹。")
            return
        self._start_worker("LUT 批量预览", self._lut_folder_preview_worker)

    def stop(self):
        self.stop_requested = True
        self._log("正在请求停止，所有正在运行的 ffmpeg 任务会尽快停止。")

    def _confirm_overwrite_if_needed(self):
        if not (self.file_conflict_action.get() == "覆盖" and self.confirm_overwrite.get()):
            return True
        return messagebox.askyesno("确认覆盖", "当前文件冲突策略为覆盖，已存在文件会被替换。是否继续？")

    def _start_worker(self, task_name, target, *args):
        self.stop_requested = False
        self.progress.set(0)
        worker_id = f"worker_{time.time_ns()}"
        worker = threading.Thread(target=self._worker_wrapper, args=(None, target, args), daemon=True)
        self.active_workers[worker_id] = worker
        self.worker = worker
        worker.start()

    def _worker_wrapper(self, task_id, target, args):
        try:
            target(*args)
        except Exception as exc:
            self.messages.put(("log", f"任务异常：{exc}"))
        finally:
            for worker_id, worker in list(self.active_workers.items()):
                if worker is threading.current_thread():
                    self.active_workers.pop(worker_id, None)
                    break

    def _create_task(self, task_name):
        self.task_counter += 1
        task_id = f"task_{self.task_counter}"
        started = time.strftime("%H:%M:%S")
        if hasattr(self, "task_tree"):
            self.task_tree.insert("", END, iid=task_id, values=(task_name, "等待中", started, ""))
        return task_id

    def _update_task_status(self, task_id, status):
        if not hasattr(self, "task_tree") or not self.task_tree.exists(task_id):
            return
        values = list(self.task_tree.item(task_id, "values"))
        if len(values) < 4:
            return
        values[1] = status
        if status == "运行中":
            values[2] = time.strftime("%H:%M:%S")
        if status in {"已完成", "已停止", "失败"}:
            values[3] = time.strftime("%H:%M:%S")
        self.task_tree.item(task_id, values=values)

    def clear_finished_tasks(self):
        if not hasattr(self, "task_tree"):
            return
        for item in self.task_tree.get_children():
            values = self.task_tree.item(item, "values")
            if values and values[1] in {"已完成", "已停止", "失败"}:
                self.queued_tasks.pop(item, None)
                self.task_tree.delete(item)

    def _queued_tasks_worker(self, task_ids):
        pending = [task_id for task_id in task_ids if task_id in self.queued_tasks and self._task_status(task_id) != "运行中"]
        total = len(pending)
        if not total:
            return
        max_workers = max(1, min(self.queue_parallel_jobs.get(), 4, total))
        self.messages.put(("log", f"队列启动：{total} 个任务，同时进行 {max_workers} 个"))
        done = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._run_queued_task, task_id, self.queued_tasks[task_id]): task_id
                for task_id in pending
            }
            for future in as_completed(futures):
                task_id = futures[future]
                done += 1
                try:
                    ok = future.result()
                    self.messages.put(("task", (task_id, "已完成" if ok else "失败")))
                    if ok:
                        self.queued_tasks.pop(task_id, None)
                except Exception as exc:
                    self.messages.put(("log", f"队列任务异常：{exc}"))
                    self.messages.put(("task", (task_id, "失败")))
                self.messages.put(("progress", done / total * 100))
                if self.stop_requested:
                    break
        self.messages.put(("status", "队列任务完成" if not self.stop_requested else "队列任务已停止"))

    def _run_queued_task(self, task_id, task):
        self.messages.put(("task", (task_id, "运行中")))
        if task["type"] != "video":
            return False
        output_dir = task["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        results = []
        skipped = 0
        for source in task["files"]:
            if self.stop_requested:
                self.messages.put(("task", (task_id, "已停止")))
                return False
            source_path = Path(source)
            target = self._video_target_path(output_dir, source_path, task["settings"], task.get("conflict_action", "重命名"))
            if target is None:
                self.messages.put(("log", f"文件已存在，已跳过：{source_path.name}"))
                skipped += 1
                continue
            result = self._compress_one(source_path, target, task["settings"])
            if result:
                results.append(result)
        self._log_compression_summary(results)
        return (bool(results) or skipped > 0) and all(result.ok for result in results)

    def _settings(self):
        extra_args = self.extra_ffmpeg_args.get()
        if self.encoder_name.get() == "CPU H.264 / AVC (libx264)":
            x264_args = []
            if self.x264_threads.get() > 0:
                x264_args += ["-threads", str(self.x264_threads.get())]
            if self.x264_command.get().strip():
                x264_args += shlex.split(self.x264_command.get().strip(), posix=False)
            if x264_args:
                extra_args = " ".join([extra_args.strip(), *x264_args]).strip()
        return CompressionSettings(
            encoder_key=self.encoder_name.get(),
            preset_name=self.preset_name.get(),
            resolution_name=self.resolution_name.get(),
            sharpen_name=self.sharpen_name.get(),
            custom_width=self.custom_width.get(),
            cq_value=self.cq_value.get(),
            bitrate=self.bitrate.get(),
            audio_mode=self.audio_mode.get(),
            audio_bitrate=self.audio_bitrate.get(),
            muxer_name=self.muxer_name.get(),
            thumbnail_time=self.thumbnail_time.get(),
            overwrite=self.file_conflict_action.get() == "覆盖",
            use_lut=self.use_lut.get(),
            lut_path=self.lut_path.get(),
            extra_ffmpeg_args=extra_args,
            quality_mode=self.quality_mode.get(),
            custom_command=self.custom_command.get(),
        )

    def _audio_settings(self):
        return AudioSettings(
            encoder_name=self.audio_encoder_name.get(),
            bitrate=self.audio_page_bitrate.get(),
            sample_rate=self.audio_sample_rate.get(),
            channels=self.audio_channels.get(),
            overwrite=self.file_conflict_action.get() == "覆盖",
            normalize=self.audio_normalize.get(),
        )

    def _retro_settings(self):
        return RetroSettings(
            format_name=self.retro_format_name.get(),
            resolution_name=self.retro_resolution_name.get(),
            cq_value=self.cq_value.get(),
            bitrate=self.retro_bitrate.get(),
            audio_bitrate=self.retro_audio_bitrate.get(),
            deinterlace=self.retro_deinterlace.get(),
            denoise=self.retro_denoise.get(),
            overwrite=self.file_conflict_action.get() == "覆盖",
        )

    def _compress_worker(self):
        output_dir = Path(self.output_dir.get()).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        total = len(self.files)
        done = 0
        jobs = max(1, min(self.parallel_jobs.get(), 8, total))
        settings = self._settings()
        self.messages.put(("log", f"并发任务数：{jobs}"))
        with ThreadPoolExecutor(max_workers=jobs) as executor:
            futures = []
            for source in self.files:
                source_path = Path(source)
                target = self._video_target_path(output_dir, source_path, settings)
                if target is None:
                    done += 1
                    self.messages.put(("log", f"文件已存在，已跳过：{source_path.name}"))
                    self.messages.put(("progress", done / total * 100))
                    continue
                futures.append(executor.submit(self._compress_one, source_path, target, settings))
            results = []
            for future in as_completed(futures):
                done += 1
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        self._log_compression_result(result)
                except Exception as exc:
                    self.messages.put(("log", f"任务异常：{exc}"))
                self.messages.put(("progress", done / total * 100))
                if self.stop_requested:
                    break
        self._log_compression_summary(results)
        self.messages.put(("status", "任务完成" if not self.stop_requested else "任务已停止"))
        if self.auto_open_output.get() and not self.stop_requested:
            self._open_folder(output_dir)

    def _compress_one(self, source_path, target, settings):
        if self.stop_requested:
            return None
        start = time.perf_counter()
        source_size = source_path.stat().st_size if source_path.exists() else 0
        self.messages.put(("status", f"正在压缩：{source_path.name}"))
        ok = self._run_encode_job(source_path, target, settings)
        elapsed = time.perf_counter() - start
        target_size = target.stat().st_size if ok and target.exists() else 0
        if ok and self.create_thumbnail.get():
            self._create_thumbnail(target, settings.thumbnail_time)
        return CompressionResult(
            source=source_path,
            target=target,
            ok=ok,
            elapsed_seconds=elapsed,
            source_size=source_size,
            target_size=target_size,
        )

    def _video_target_path(self, output_dir, source_path, settings, action=None):
        action = action or self.file_conflict_action.get()
        base_target = ffmpeg.unique_video_output_path(output_dir, source_path, settings, True)
        if action == "跳过" and base_target.exists():
            return None
        if action == "覆盖":
            return base_target
        return ffmpeg.unique_video_output_path(output_dir, source_path, settings, False)

    def _run_encode_job(self, source_path, target, settings):
        if settings.quality_mode == "2PASS / 两遍码率":
            return self._run_two_pass(source_path, target, settings)
        return self._run_ffmpeg(ffmpeg.build_compress_command(source_path, target, settings), source_path)

    def _run_two_pass(self, source_path, target, settings):
        temp = target.with_suffix(".passlog")
        base = ffmpeg.build_compress_command(source_path, target, settings)
        first = list(base[:-1]) + ["-pass", "1", "-an", "-f", "null", os.devnull]
        second = list(base[:-1]) + ["-pass", "2", str(target)]
        ok1 = self._run_ffmpeg(first, source_path)
        ok2 = self._run_ffmpeg(second, source_path) if ok1 else False
        try:
            if temp.exists():
                temp.unlink()
        except Exception:
            pass
        return ok1 and ok2

    def _thumbnail_worker(self, files):
        output_dir = Path(self.output_dir.get()).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        total = len(files)
        thumbnail_time = self.thumbnail_time.get()
        for index, source in enumerate(files, start=1):
            if self.stop_requested:
                break
            source_path = Path(source)
            self.messages.put(("status", f"[{index}/{total}] 生成缩略图：{source_path.name}"))
            self._create_thumbnail(source_path, thumbnail_time, output_dir=output_dir)
            self.messages.put(("progress", index / total * 100))
        self.messages.put(("status", "缩略图任务完成" if not self.stop_requested else "缩略图任务已停止"))

    def _proxy_worker(self):
        output_dir = Path(self.output_dir.get()).resolve() / "proxy"
        output_dir.mkdir(parents=True, exist_ok=True)
        total = len(self.files)
        results = []
        for index, source in enumerate(self.files, start=1):
            if self.stop_requested:
                break
            source_path = Path(source)
            target = ffmpeg.unique_proxy_output_path(output_dir, source_path)
            start = time.perf_counter()
            self.messages.put(("status", f"[{index}/{total}] 生成代理文件：{source_path.name}"))
            ok = self._run_ffmpeg(ffmpeg.build_proxy_command(source_path, target), source_path)
            elapsed = time.perf_counter() - start
            results.append(CompressionResult(
                source=source_path,
                target=target,
                ok=ok,
                elapsed_seconds=elapsed,
                source_size=source_path.stat().st_size if source_path.exists() else 0,
                target_size=target.stat().st_size if ok and target.exists() else 0,
            ))
            self.messages.put(("progress", index / total * 100))
        self._log_compression_summary(results)
        self.messages.put(("status", "代理文件完成" if not self.stop_requested else "代理文件已停止"))
        if self.auto_open_output.get() and not self.stop_requested:
            self._open_folder(output_dir)

    def _audio_worker(self):
        output_dir = Path(self.audio_output_dir.get()).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        settings = self._audio_settings()
        total = len(self.audio_files)
        results = []
        for index, source in enumerate(self.audio_files, start=1):
            if self.stop_requested:
                break
            source_path = Path(source)
            target = ffmpeg.unique_audio_output_path(output_dir, source_path, settings)
            self.messages.put(("status", f"[{index}/{total}] 正在压缩音频：{source_path.name}"))
            results.append(self._convert_audio_one(source_path, target, settings))
            self.messages.put(("progress", index / total * 100))
        self._log_compression_summary(results)
        self.messages.put(("status", "音频任务完成" if not self.stop_requested else "音频任务已停止"))
        if self.auto_open_output.get() and not self.stop_requested:
            self._open_folder(output_dir)

    def _convert_audio_one(self, source_path, target, settings):
        start = time.perf_counter()
        source_size = source_path.stat().st_size if source_path.exists() else 0
        ok = self._run_ffmpeg(ffmpeg.build_audio_command(source_path, target, settings), source_path)
        elapsed = time.perf_counter() - start
        target_size = target.stat().st_size if ok and target.exists() else 0
        result = CompressionResult(source_path, target, ok, elapsed, source_size, target_size)
        self._log_compression_result(result)
        return result

    def _retro_worker(self):
        output_dir = Path(self.retro_output_dir.get()).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        settings = self._retro_settings()
        total = len(self.retro_files)
        results = []
        for index, source in enumerate(self.retro_files, start=1):
            if self.stop_requested:
                break
            source_path = Path(source)
            target = ffmpeg.unique_retro_output_path(output_dir, source_path, settings)
            self.messages.put(("status", f"[{index}/{total}] 复古处理：{source_path.name}"))
            results.append(self._retro_one(source_path, target, settings))
            self.messages.put(("progress", index / total * 100))
        self._log_compression_summary(results)
        self.messages.put(("status", "复古处理完成" if not self.stop_requested else "复古处理已停止"))
        if self.auto_open_output.get() and not self.stop_requested:
            self._open_folder(output_dir)

    def _retro_one(self, source_path, target, settings):
        start = time.perf_counter()
        source_size = source_path.stat().st_size if source_path.exists() else 0
        ok = self._run_ffmpeg(ffmpeg.build_retro_command(source_path, target, settings), source_path)
        elapsed = time.perf_counter() - start
        target_size = target.stat().st_size if ok and target.exists() else 0
        result = CompressionResult(source_path, target, ok, elapsed, source_size, target_size)
        self._log_compression_result(result)
        return result

    def _retro_remux_worker(self):
        total = len(self.retro_files)
        suffix = VIDEO_MUXERS[self.retro_remux_format.get()]
        audio_mode = "aac" if self.retro_remux_audio.get() == "AAC 重新编码" else "copy"
        results = []
        for index, source in enumerate(self.retro_files, start=1):
            if self.stop_requested:
                break
            source_path = Path(source)
            target = self._remux_target_path(source_path.parent, source_path, suffix)
            if target is None:
                self.messages.put(("log", f"文件已存在，已跳过：{source_path.name}"))
                continue
            self.messages.put(("status", f"[{index}/{total}] 封装转换：{source_path.name}"))
            start = time.perf_counter()
            ok = self._run_ffmpeg(ffmpeg.build_remux_command(source_path, target, audio_mode=audio_mode, overwrite=self.file_conflict_action.get() == "覆盖"), source_path)
            elapsed = time.perf_counter() - start
            results.append(CompressionResult(
                source=source_path,
                target=target,
                ok=ok,
                elapsed_seconds=elapsed,
                source_size=source_path.stat().st_size if source_path.exists() else 0,
                target_size=target.stat().st_size if ok and target.exists() else 0,
            ))
            self.messages.put(("progress", index / total * 100))
        self._log_compression_summary(results)
        self.messages.put(("status", "封装转换完成" if not self.stop_requested else "封装转换已停止"))

    def _remux_target_path(self, output_dir, source_path, suffix):
        target = output_dir / f"{source_path.stem}_remux{suffix}"
        action = self.file_conflict_action.get()
        if action == "跳过" and target.exists():
            return None
        if action == "覆盖" or not target.exists():
            return target
        counter = 2
        while True:
            candidate = output_dir / f"{source_path.stem}_remux_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def _lut_folder_preview_worker(self):
        video = Path(self.lut_page_video.get()).resolve()
        folder = Path(self.lut_page_folder.get()).resolve()
        output_dir = Path(self.lut_page_output.get()).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        lut_files = [
            p for p in folder.rglob("*")
            if p.suffix.lower() in {".cube", ".3dl", ".dat", ".m3d"}
        ]
        self.messages.put(("lut_clear", ""))
        total = len(lut_files)
        if not total:
            self.messages.put(("log", "LUT 文件夹中没有找到可用 LUT 文件。"))
            return
        for index, lut in enumerate(lut_files, start=1):
            if self.stop_requested:
                break
            target = output_dir / f"{video.stem}_{lut.stem}.png"
            self.messages.put(("status", f"[{index}/{total}] 生成 LUT 缩略图：{lut.name}"))
            output = ffmpeg.run_capture(ffmpeg.build_lut_thumbnail_command(video, target, self.lut_page_time.get(), lut))
            if target.exists():
                self.messages.put(("lut_item", (lut.name, str(target))))
            else:
                self.messages.put(("log", f"LUT 缩略图失败：{lut.name} {output}"))
            self.messages.put(("progress", index / total * 100))
        self.messages.put(("status", "LUT 批量缩略图完成"))

    def _batch_worker(self):
        input_dir = Path(self.batch_input_dir.get()).resolve()
        output_dir = Path(self.batch_output_dir.get()).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        preset = BATCH_PRESETS[self.batch_preset_name.get()]
        settings = self._batch_video_settings(preset)
        audio_settings = AudioSettings(
            encoder_name="AAC (.m4a)",
            bitrate=preset["audio_bitrate"],
            sample_rate="48000",
            channels="2",
            overwrite=self.file_conflict_action.get() == "覆盖",
            normalize=False,
        )
        candidates = [
            p for p in input_dir.rglob("*")
            if p.is_file() and (p.suffix.lower() in VIDEO_EXTENSIONS or (self.batch_include_audio.get() and p.suffix.lower() in AUDIO_EXTENSIONS))
        ]
        total = len(candidates)
        if not total:
            self.messages.put(("log", "批量扫描没有找到可处理的媒体文件。"))
            return
        results = []
        for index, source_path in enumerate(candidates, start=1):
            if self.stop_requested:
                break
            target_dir = self._batch_target_dir(input_dir, output_dir, source_path)
            target_dir.mkdir(parents=True, exist_ok=True)
            self.messages.put(("status", f"[{index}/{total}] 批量处理：{source_path.name}"))
            if source_path.suffix.lower() in VIDEO_EXTENSIONS:
                target = self._video_target_path(target_dir, source_path, settings)
                if target is None:
                    self.messages.put(("log", f"文件已存在，已跳过：{source_path.name}"))
                    self.messages.put(("progress", index / total * 100))
                    continue
                results.append(self._compress_one(source_path, target, settings))
            else:
                target = ffmpeg.unique_audio_output_path(target_dir, source_path, audio_settings)
                results.append(self._convert_audio_one(source_path, target, audio_settings))
            self.messages.put(("progress", index / total * 100))
        self._log_compression_summary([r for r in results if r])
        self.messages.put(("status", "批量压缩完成" if not self.stop_requested else "批量压缩已停止"))
        if self.auto_open_output.get() and not self.stop_requested:
            self._open_folder(output_dir)

    def _batch_video_settings(self, preset):
        resolution_name = preset["resolution"]
        if self.batch_vertical_mode.get():
            vertical_map = {
                "2160p / 4K": "竖屏 4K 2160x3840",
                "1440p / 2K": "竖屏 1440x2560",
                "1080p": "竖屏 1080x1920",
                "720p": "竖屏 720x1280",
            }
            resolution_name = vertical_map.get(resolution_name, resolution_name)
        return CompressionSettings(
            encoder_key=preset["encoder"],
            preset_name=self.preset_name.get(),
            resolution_name=resolution_name,
            sharpen_name=self.sharpen_name.get(),
            custom_width=self.custom_width.get(),
            quality_mode="CRF / 恒定质量",
            cq_value=preset["cq"],
            bitrate="",
            custom_command="",
            audio_mode=preset["audio"],
            audio_bitrate=preset["audio_bitrate"],
            muxer_name=preset["muxer"],
            thumbnail_time=self.thumbnail_time.get(),
            overwrite=self.file_conflict_action.get() == "覆盖",
            use_lut=self.use_lut.get(),
            lut_path=self.lut_path.get(),
            extra_ffmpeg_args=self.extra_ffmpeg_args.get(),
        )

    def _batch_target_dir(self, input_dir, output_dir, source_path):
        if not self.batch_keep_tree.get():
            return output_dir
        return output_dir / source_path.parent.relative_to(input_dir)

    def _lut_preview_worker(self, source_path):
        settings = self._settings()
        self.preview_path.parent.mkdir(parents=True, exist_ok=True)
        if self.preview_path.exists():
            self.preview_path.unlink()
        cmd = ffmpeg.build_preview_command(source_path, self.preview_path, settings)
        self.messages.put(("status", f"生成 LUT 预览：{source_path.name}"))
        output = ffmpeg.run_capture(cmd)
        if self.preview_path.exists():
            self.messages.put(("preview", str(self.preview_path)))
            self.messages.put(("log", f"LUT 预览已生成：{self.preview_path}"))
        else:
            self.messages.put(("log", "LUT 预览生成失败：" + output))
        self.messages.put(("status", "LUT 预览完成"))

    def _benchmark_worker(self, sample):
        settings = self._settings()
        bench_dir = Path(self.output_dir.get()).resolve() / "benchmark"
        bench_dir.mkdir(parents=True, exist_ok=True)
        jobs = [
            ("GPU H.265", "hevc_nvenc", bench_dir / "benchmark_gpu_h265.mp4"),
            ("AMD H.265", "hevc_amf", bench_dir / "benchmark_amd_h265.mp4"),
            ("CPU H.265", "libx265", bench_dir / "benchmark_cpu_h265.mp4"),
        ]
        results = []
        for i, (name, encoder, target) in enumerate(jobs, start=1):
            if self.stop_requested:
                break
            start = time.perf_counter()
            cmd = ffmpeg.build_compress_command(sample, target, settings, encoder_override=encoder, benchmark=True)
            self.messages.put(("status", f"Benchmark {name} 运行中"))
            ok = self._run_ffmpeg(cmd, sample)
            elapsed = time.perf_counter() - start
            size = target.stat().st_size / 1024 / 1024 if target.exists() else 0
            results.append(f"{name}: {'成功' if ok else '失败'}，{elapsed:.1f}s，{size:.1f} MB")
            self.messages.put(("progress", i / len(jobs) * 100))
        self.messages.put(("log", "Benchmark 结果：" + " | ".join(results)))
        self.messages.put(("status", "Benchmark 完成"))

    def _run_ffmpeg(self, cmd, source):
        duration = ffmpeg.duration_seconds(source)
        if "-progress" not in cmd and len(cmd) > 2:
            cmd = list(cmd[:-1]) + ["-progress", "pipe:1", "-nostats", cmd[-1]]
        self.messages.put(("log", " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd)))
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            if os.name == "nt" and "libx264" in [str(part) for part in cmd]:
                priority_flags = {"低": 0x00004000, "高": 0x00000080}
                creationflags |= priority_flags.get(self.x264_priority.get(), 0)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
            for line in process.stdout:
                if self.stop_requested:
                    process.terminate()
                    return False
                line = line.strip()
                if line:
                    self.messages.put(("log", line))
                    seconds = self._parse_ffmpeg_progress_seconds(line) or ffmpeg.parse_time(line)
                    if seconds and duration:
                        self.messages.put(("subprogress", min(seconds / duration * 100, 99)))
            code = process.wait()
            if code != 0:
                self.messages.put(("log", f"ffmpeg 退出码：{code}"))
            return code == 0
        except FileNotFoundError:
            self.messages.put(("log", "未找到 ffmpeg，请安装并加入 PATH。"))
            return False
        except Exception as exc:
            self.messages.put(("log", f"任务失败：{exc}"))
            return False

    def _parse_ffmpeg_progress_seconds(self, line):
        if line.startswith("out_time_ms="):
            try:
                return int(line.split("=", 1)[1]) / 1_000_000
            except Exception:
                return 0
        if line.startswith("out_time="):
            return ffmpeg.parse_time("time=" + line.split("=", 1)[1])
        return 0

    def _create_thumbnail(self, video_path, thumbnail_time, output_dir=None):
        thumb = (output_dir / f"{video_path.stem}.jpg") if output_dir else video_path.with_suffix(".jpg")
        self.messages.put(("status", f"生成缩略图：{thumb.name}"))
        ffmpeg.run_capture(ffmpeg.build_thumbnail_command(video_path, thumb, thumbnail_time))
        self.messages.put(("log", f"缩略图已生成：{thumb}"))

    def _log_compression_result(self, result: CompressionResult):
        if not result.ok:
            self.messages.put(("log", f"压缩失败：{result.source.name}，用时 {self._format_seconds(result.elapsed_seconds)}"))
            return
        self.messages.put((
            "log",
            (
                f"压缩完成：{result.source.name} -> {result.target.name} | "
                f"用时 {self._format_seconds(result.elapsed_seconds)} | "
                f"原大小 {self._format_size(result.source_size)} | "
                f"压后 {self._format_size(result.target_size)} | "
                f"压缩率 {result.saved_ratio:.1f}%"
            ),
        ))

    def _log_compression_summary(self, results):
        if len(results) <= 1:
            return
        finished = [result for result in results if result.ok]
        if not finished:
            self.messages.put(("log", "本次没有成功完成的压缩任务。"))
            return
        elapsed = sum(result.elapsed_seconds for result in finished)
        source_size = sum(result.source_size for result in finished)
        target_size = sum(result.target_size for result in finished)
        saved_ratio = max(0, (1 - target_size / source_size) * 100) if source_size and target_size else 0
        self.messages.put((
            "log",
            (
                f"批量汇总：成功 {len(finished)}/{len(results)} 个 | "
                f"总用时 {self._format_seconds(elapsed)} | "
                f"原大小 {self._format_size(source_size)} | "
                f"压后 {self._format_size(target_size)} | "
                f"总体压缩率 {saved_ratio:.1f}%"
            ),
        ))

    def _selected_files(self):
        return [self.files[index] for index in self.file_list.curselection()]

    def _open_folder(self, folder):
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", str(folder)], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as exc:
            self.messages.put(("log", f"打开输出目录失败：{exc}"))

    def _poll_resources(self):
        cpu = self._cpu_usage_percent()
        gpu = self._gpu_usage_percent()
        cpu_text = "--" if cpu is None else f"{cpu:.0f}"
        gpu_text = "--" if gpu is None else f"{gpu:.0f}"
        self.resource_status.set(f"CPU {cpu_text}%  |  GPU {gpu_text}%")
        self._append_resource_history(cpu, gpu)
        self._draw_resource_chart()
        self.root.after(1000, self._poll_resources)

    def _append_resource_history(self, cpu, gpu):
        self.cpu_history.append(0 if cpu is None else max(0, min(100, cpu)))
        self.gpu_history.append(0 if gpu is None else max(0, min(100, gpu)))
        self.cpu_history = self.cpu_history[-40:]
        self.gpu_history = self.gpu_history[-40:]

    def _draw_resource_chart(self):
        if not hasattr(self, "resource_canvas"):
            return
        canvas = self.resource_canvas
        canvas.delete("all")
        width = int(canvas["width"])
        height = int(canvas["height"])
        canvas.create_text(8, 10, text="CPU", anchor="w", fill="#166534", font=("Microsoft YaHei UI", 8, "bold"))
        canvas.create_text(8, 30, text="GPU", anchor="w", fill="#15803d", font=("Microsoft YaHei UI", 8, "bold"))
        self._draw_sparkline(canvas, self.cpu_history, 42, 6, width - 8, 20, "#16a34a")
        self._draw_sparkline(canvas, self.gpu_history, 42, 26, width - 8, 40, "#22c55e")

    def _draw_sparkline(self, canvas, values, x1, y1, x2, y2, color):
        canvas.create_rectangle(x1, y1, x2, y2, outline="#d1d5db", fill="#f8fafc")
        if len(values) < 2:
            return
        step = (x2 - x1) / max(1, len(values) - 1)
        points = []
        for index, value in enumerate(values):
            x = x1 + index * step
            y = y2 - (value / 100) * (y2 - y1)
            points.extend((x, y))
        canvas.create_line(*points, fill=color, width=2, smooth=True)

    def _cpu_usage_percent(self):
        if os.name != "nt":
            return None

        class FileTime(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]

        idle = FileTime()
        kernel = FileTime()
        user = FileTime()
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        idle_value = (idle.dwHighDateTime << 32) | idle.dwLowDateTime
        kernel_value = (kernel.dwHighDateTime << 32) | kernel.dwLowDateTime
        user_value = (user.dwHighDateTime << 32) | user.dwLowDateTime
        current = (idle_value, kernel_value + user_value)
        previous = self._last_cpu_times
        self._last_cpu_times = current
        if not previous:
            return None
        idle_delta = current[0] - previous[0]
        total_delta = current[1] - previous[1]
        if total_delta <= 0:
            return None
        return max(0, min(100, (1 - idle_delta / total_delta) * 100))

    def _gpu_usage_percent(self):
        if os.name != "nt":
            return None
        commands = [
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "$samples = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine -ErrorAction SilentlyContinue; "
                "$sum = ($samples | Where-Object {$_.Name -match 'engtype_(3D|Compute|VideoEncode|VideoDecode|Copy)'} | Measure-Object UtilizationPercentage -Sum).Sum; "
                "if ($null -eq $sum) {''} else {$sum}",
            ],
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "$samples = (Get-Counter '\\GPU Engine(*)\\Utilization Percentage' -ErrorAction SilentlyContinue).CounterSamples; "
                "$sum = ($samples | Where-Object {$_.InstanceName -match 'engtype_(3d|compute|videoencode|videodecode|copy)'} | Measure-Object CookedValue -Sum).Sum; "
                "if ($null -eq $sum) {''} else {$sum}",
            ],
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
        ]
        for command in commands:
            try:
                output = subprocess.check_output(
                    command,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=3,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                values = [float(value) for value in re.findall(r"[-+]?\d+(?:\.\d+)?", output)]
                if values:
                    return max(0, min(100, sum(values)))
            except Exception:
                continue
        return None

    def _poll_messages(self):
        while True:
            try:
                kind, payload = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._log(payload)
            elif kind == "status":
                self.current_task.set(payload)
                self._log(payload)
            elif kind == "progress":
                self.progress.set(payload)
            elif kind == "subprogress":
                self.progress.set(payload)
                self.current_task.set(f"当前文件进度：{payload:.0f}%")
            elif kind == "preview":
                self._show_preview(payload)
            elif kind == "task":
                task_id, status = payload
                self._update_task_status(task_id, status)
            elif kind == "lut_clear":
                self._clear_lut_thumbnails()
            elif kind == "lut_item":
                name, path = payload
                self._add_lut_thumbnail(name, path)
        self.root.after(120, self._poll_messages)

    def _log(self, text):
        self.log.insert(END, text)
        self.log.yview_moveto(1)

    def _show_preview(self, path):
        self.preview_image = PhotoImage(file=path)
        self.preview_label.configure(image=self.preview_image, text="")

    def _preview_source(self):
        selected = self._selected_files()
        if selected:
            return selected[0]
        if self.files:
            return self.files[0]
        return ""

    def _clear_lut_thumbnails(self):
        self.lut_preview_images.clear()
        self.lut_thumb_images.clear()
        if hasattr(self, "lut_result_strip"):
            for child in self.lut_result_strip.winfo_children():
                child.destroy()
        self._hide_lut_tooltip()

    def _add_lut_thumbnail(self, name, path):
        if not hasattr(self, "lut_result_strip"):
            return
        self.lut_preview_images[name] = path
        try:
            image = PhotoImage(file=path)
        except Exception:
            return
        self.lut_thumb_images[name] = image
        item = ttk.Frame(self.lut_result_strip, padding=(8, 8))
        item.pack(side="left", padx=(0, 8), pady=6)
        label = ttk.Label(item, image=image)
        label.pack()
        short_name = Path(name).stem
        ttk.Label(item, text=short_name[:16], style="Hint.TLabel").pack(pady=(5, 0))
        for widget in (item, label):
            widget.bind("<Enter>", lambda event, text=name: self._schedule_lut_tooltip(event, text))
            widget.bind("<Leave>", lambda event: self._hide_lut_tooltip())

    def _schedule_lut_tooltip(self, event, text):
        self._hide_lut_tooltip()
        x = event.x_root + 12
        y = event.y_root + 12
        self.lut_tooltip_after = self.root.after(1000, lambda: self._show_lut_tooltip(text, x, y))

    def _show_lut_tooltip(self, text, x, y):
        self._hide_lut_tooltip(cancel_after=False)
        tip = Toplevel(self.root)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        ttk.Label(tip, text=text, padding=(8, 5), relief="solid").pack()
        self.lut_tooltip = tip

    def _hide_lut_tooltip(self, cancel_after=True):
        if cancel_after and self.lut_tooltip_after:
            self.root.after_cancel(self.lut_tooltip_after)
            self.lut_tooltip_after = None
        if self.lut_tooltip:
            self.lut_tooltip.destroy()
            self.lut_tooltip = None

    def load_mediainfo(self):
        path = Path(self.media_info_path.get())
        if not path.exists():
            messagebox.showwarning("文件不存在", "请先选择有效的媒体文件。")
            return
        info = ffmpeg.probe_media_info(path)
        text = self._format_mediainfo(path, info) if info else "未能读取媒体信息。请确认 ffprobe 可用。"
        self.media_info_text.configure(state="normal")
        self.media_info_text.delete("1.0", END)
        self.media_info_text.insert("1.0", text)
        self.media_info_text.configure(state="disabled")

    def _format_mediainfo(self, path, info):
        fmt = info.get("format", {})
        streams = info.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), {})
        audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
        duration = self._safe_float(fmt.get("duration"))
        bitrate = self._safe_int(fmt.get("bit_rate"))
        size = self._safe_int(fmt.get("size"))
        lines = [
            f"文件名：{path.name}",
            f"封装格式：{fmt.get('format_long_name') or fmt.get('format_name') or '未知'}",
            "",
            "整体参数",
            "",
            f"    文件体积：{self._format_size(size)}",
            f"    视频时长：{duration:.3f} 秒" if duration else "    视频时长：未知",
            f"    整体码率：{self._format_bitrate(bitrate)}",
        ]
        created = fmt.get("tags", {}).get("creation_time") or video.get("tags", {}).get("creation_time")
        if created:
            lines.append(f"    录制编码时间：{created}")
        if video:
            width = video.get("width")
            height = video.get("height")
            fps = self._fps_text(video.get("avg_frame_rate") or video.get("r_frame_rate"))
            frames = video.get("nb_frames")
            v_bitrate = self._safe_int(video.get("bit_rate"))
            profile = video.get("profile")
            level = video.get("level")
            level_text = f"@L{level / 30:.1f}" if isinstance(level, int) and level else ""
            lines += [
                "",
                "视频流",
                "",
                f"    编码格式：{self._codec_name(video)}{f'，{profile}{level_text} 规格' if profile else ''}",
                f"    分辨率：{self._resolution_label(width, height)}",
                f"    帧率：{fps}，{video.get('field_order') or '逐行扫描'}",
                f"    色彩规格：{self._color_text(video)}",
                f"    视频码率：{self._format_bitrate(v_bitrate)}",
                f"    总帧数：{frames or '未知'} 帧",
            ]
        if audio:
            a_bitrate = self._safe_int(audio.get("bit_rate"))
            lines += [
                "",
                "音频流",
                "",
                f"    编码格式：{self._codec_name(audio)}",
                f"    码率：{self._format_bitrate(a_bitrate)}",
                f"    采样率：{self._sample_rate_text(audio)}，{self._channels_text(audio)}",
            ]
        return "\n".join(lines)

    def _codec_name(self, stream):
        name = stream.get("codec_long_name") or stream.get("codec_name") or "未知"
        codec = stream.get("codec_name", "")
        if codec == "hevc":
            return "HEVC (H.265)"
        if codec == "h264":
            return "AVC (H.264)"
        if codec == "aac":
            return "AAC-LC 有损压缩"
        return name

    def _resolution_label(self, width, height):
        if not width or not height:
            return "未知"
        ratio = "16:9" if round(width / height, 2) == 1.78 else f"{width}:{height}"
        prefix = "4K " if width >= 3840 or height >= 2160 else ""
        return f"{prefix}{width}×{height}，画幅 {ratio}"

    def _color_text(self, stream):
        bits = stream.get("bits_per_raw_sample") or stream.get("bits_per_sample")
        pix_fmt = stream.get("pix_fmt") or "未知采样"
        space = stream.get("color_space") or "未知矩阵"
        range_text = "全色域" if stream.get("color_range") == "pc" else "有限色域"
        return f"{bits or '未知'}bit 位深、{pix_fmt}、{range_text}、{space} 矩阵"

    def _sample_rate_text(self, stream):
        sample_rate = self._safe_int(stream.get("sample_rate"))
        return f"{sample_rate / 1000:.0f}kHz" if sample_rate else "未知采样率"

    def _channels_text(self, stream):
        channels = stream.get("channels")
        layout = stream.get("channel_layout")
        if channels == 2:
            return "双声道立体声"
        return layout or (f"{channels} 声道" if channels else "未知声道")

    def _fps_text(self, value):
        try:
            num, den = value.split("/")
            fps = float(num) / float(den)
            return f"恒定 {fps:.2f}fps"
        except Exception:
            return "帧率未知"

    def _format_bitrate(self, value):
        if not value:
            return "未知"
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}Mbps"
        return f"{value / 1000:.0f}Kbps"

    @staticmethod
    def _safe_int(value):
        try:
            return int(value)
        except Exception:
            return 0

    @staticmethod
    def _safe_float(value):
        try:
            return float(value)
        except Exception:
            return 0.0

    @staticmethod
    def _format_size(size):
        value = float(size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024 or unit == "TB":
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
            value /= 1024
        return f"{value:.1f} TB"

    @staticmethod
    def _format_seconds(seconds):
        seconds = int(round(seconds))
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}小时{minutes}分{sec}秒"
        if minutes:
            return f"{minutes}分{sec}秒"
        return f"{sec}秒"

    @staticmethod
    def _format_clock(seconds):
        seconds = int(max(0, round(seconds)))
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{sec:02d}"
        return f"{minutes:02d}:{sec:02d}"


def run_app():
    try:
        try:
            from tkinterdnd2 import TkinterDnD
            root = TkinterDnD.Tk()
        except Exception:
            root = Tk()
        VideoCompressorApp(root)
        root.mainloop()
    except Exception:
        crash_log = Path.cwd() / "crash.log"
        crash_log.write_text(traceback.format_exc(), encoding="utf-8")
        raise


