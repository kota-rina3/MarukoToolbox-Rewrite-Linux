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
import shutil
import webbrowser
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
    BUILD_VERSION,
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
    ENCODER_FILENAME_TAGS,
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
        self.app_version = f"v1.0.{BUILD_VERSION}"
        self.display_title = f"{APP_TITLE}    {self.app_version}"
        self.root.title(self.display_title)
        self.root.geometry(WINDOW_SIZE)
        self.root.minsize(*WINDOW_MIN_SIZE)
        self.icon_path = Path.cwd() / "gzya5-3b5gl-001.ico"
        self._set_window_icon(self.root)

        self.files = []
        self.common_trim_video = StringVar(value="")
        self.subtitle_source = StringVar(value="")
        self.subtitle_output_dir = StringVar(value=str(DEFAULT_OUTPUT_DIR / "subtitles"))
        self.subtitle_output_format = StringVar(value="MKV (.mkv)")
        self.subtitle_tracks = []
        self.subtitle_external_files = []
        self.audio_files = []
        self.retro_files = []
        self.anamorphic_files = []
        self.mux_merge_files = []
        self.mux_convert_files = []
        self.task_counter = 0
        self.active_workers = {}
        self.active_ffmpeg_jobs = {}
        self.cancelled_ffmpeg_jobs = set()
        self.job_windows = {}
        self.multi_job_mode = False
        self.multi_job_total = 0
        self.multi_job_finished = 0
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
        self.custom_height = IntVar(value=1080)
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
        self.audio_output_mode = StringVar(value="自定义")
        self.audio_overwrite_source = BooleanVar(value=False)
        self.audio_encoder_name = StringVar(value="AAC (.m4a)")
        self.audio_page_bitrate = StringVar(value="192k")
        self.audio_sample_rate = StringVar(value="48000")
        self.audio_channels = StringVar(value="2")
        self.audio_normalize = BooleanVar(value=False)
        self.common_output_dir = StringVar(value=str(DEFAULT_OUTPUT_DIR / "common"))
        self.common_trim_start = StringVar(value="00:00:00")
        self.common_trim_end = StringVar(value="00:00:10")
        self.common_trim_encoder = StringVar(value="CPU H.264 / AVC (libx264)")
        self.common_trim_muxer = StringVar(value="MP4 (.mp4)")
        self.anamorphic_output_dir = StringVar(value=str(DEFAULT_OUTPUT_DIR / "anamorphic"))
        self.anamorphic_factor = StringVar(value="1.33")
        self.anamorphic_mode = StringVar(value="保留反挤压宽画幅")
        self.anamorphic_target_aspect = StringVar(value="2.39:1")
        self.anamorphic_resolution = StringVar(value="保持反挤压尺寸")
        self.anamorphic_encoder_name = StringVar(value="CPU H.264 / AVC (libx264)")
        self.anamorphic_keep_audio = BooleanVar(value=True)
        self.anamorphic_auto_crop = BooleanVar(value=False)
        self.mux_output_dir = StringVar(value=str(DEFAULT_OUTPUT_DIR / "mux"))
        self.mux_merge_name = StringVar(value="merged")
        self.mux_merge_format = StringVar(value="MP4 (.mp4)")
        self.mux_convert_format = StringVar(value="MP4 (.mp4)")
        self.mux_audio_mode = StringVar(value="复制音频")
        self.mux_audio_bitrate = StringVar(value="192k")
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
        self.anamorphic_preview_image = None
        self.anamorphic_preview_window = None
        self.anamorphic_preview_label = None
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
        self.settings_path = self._app_settings_path()
        self.tab_order = ["视频", "字幕", "变形", "封装", "音频", "常用", "复古", "Lut调色", "批量压缩", "MediaInfo", "任务管理"]

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

    def _set_window_icon(self, window):
        if not self.icon_path.exists():
            return
        try:
            window.iconbitmap(str(self.icon_path))
        except Exception:
            pass

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
        ttk.Label(header, text=self.display_title, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="FFmpeg + NVIDIA NVENC / AMD AMF 批量压缩、CPU 对比和缩略图生成",
            style="HeaderHint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        header_actions = ttk.Frame(header, style="Header.TFrame")
        header_actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        for column in range(6):
            header_actions.columnconfigure(column, weight=1)
        header_buttons = [
            ("⚙ 设置", self.open_settings_window, ""),
            ("▶ 开始压缩", self.start_compression, "Accent.TButton"),
            ("＋ 视频任务入队", self.add_current_video_to_queue, ""),
            ("■ 停止", self.stop, ""),
            ("✓ 检测环境", self.check_environment, ""),
            ("GitHub 项目", self.open_github_project, ""),
        ]
        for column, (text, command, style) in enumerate(header_buttons):
            options = {"text": text, "command": command}
            if style:
                options["style"] = style
            ttk.Button(header_actions, **options).grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0))

        resource = ttk.Frame(header, style="Header.TFrame")
        resource.grid(row=0, column=1, rowspan=3, sticky="nse", padx=(18, 0))
        ttk.Label(resource, textvariable=self.resource_status, style="Status.TLabel").grid(row=0, column=0, sticky="e")
        self.resource_canvas = Canvas(resource, width=240, height=46, bg="#f7f9fc", highlightthickness=1, highlightbackground=self.COLORS["panel_border"])
        self.resource_canvas.grid(row=1, column=0, sticky="e", pady=(8, 0))
        ttk.Label(resource, text=f"版本 {self.app_version}", style="HeaderHint.TLabel").grid(row=2, column=0, sticky="e", pady=(6, 0))

    def _build_tabs(self, parent):
        self.notebook = ttk.Notebook(parent)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.common_tab = ttk.Frame(self.notebook, padding=0)
        self.video_tab = ttk.Frame(self.notebook, padding=0)
        self.subtitle_tab = ttk.Frame(self.notebook, padding=0)
        self.anamorphic_tab = ttk.Frame(self.notebook, padding=0)
        self.mux_tab = ttk.Frame(self.notebook, padding=0)
        self.audio_tab = ttk.Frame(self.notebook, padding=0)
        self.retro_tab = ttk.Frame(self.notebook, padding=0)
        self.lut_tab = ttk.Frame(self.notebook, padding=0)
        self.batch_tab = ttk.Frame(self.notebook, padding=0)
        self.mediainfo_tab = ttk.Frame(self.notebook, padding=0)
        self.tasks_tab = ttk.Frame(self.notebook, padding=0)
        self.tab_frames = {
            "视频": self.video_tab,
            "字幕": self.subtitle_tab,
            "变形": self.anamorphic_tab,
            "封装": self.mux_tab,
            "音频": self.audio_tab,
            "常用": self.common_tab,
            "复古": self.retro_tab,
            "Lut调色": self.lut_tab,
            "批量压缩": self.batch_tab,
            "MediaInfo": self.mediainfo_tab,
            "任务管理": self.tasks_tab,
        }
        self._apply_tab_order()
        self._build_common_tab(self.common_tab)
        self._build_video_tab(self.video_tab)
        self._build_subtitle_tab(self.subtitle_tab)
        self._build_anamorphic_tab(self.anamorphic_tab)
        self._build_mux_tab(self.mux_tab)
        self._build_audio_tab(self.audio_tab)
        self._build_retro_tab(self.retro_tab)
        self._build_lut_tab(self.lut_tab)
        self._build_batch_tab(self.batch_tab)
        self._build_mediainfo_tab(self.mediainfo_tab)
        self._build_tasks_tab(self.tasks_tab)

    def _apply_tab_order(self):
        if not hasattr(self, "notebook") or not hasattr(self, "tab_frames"):
            return
        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)
        for name in self.tab_order:
            frame = self.tab_frames.get(name)
            if frame is not None:
                self.notebook.add(frame, text=name)

    def _build_video_tab(self, parent):
        panel = self._scrollable_frame(parent)
        panel.columnconfigure(0, weight=3)
        panel.columnconfigure(1, weight=2)
        panel.rowconfigure(0, weight=1)
        self._build_video_file_panel(panel)
        self._build_settings_panel(panel)

    def _build_common_tab(self, parent):
        parent = self._scrollable_frame(parent)
        parent.columnconfigure(0, weight=1)
        trim = ttk.LabelFrame(parent, text="截取视频", padding=12)
        trim.grid(row=0, column=0, sticky="ew")
        trim.columnconfigure(1, weight=1)
        ttk.Label(trim, text="视频文件").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(trim, textvariable=self.common_trim_video).grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(trim, text="选择…", command=self.choose_common_trim_video).grid(row=0, column=2, pady=5)
        ttk.Button(trim, text="输出目录", command=lambda: self.open_output_dir(self.common_output_dir)).grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(trim, textvariable=self.common_output_dir).grid(row=1, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(trim, text="浏览…", command=self.choose_common_output_dir).grid(row=1, column=2, pady=5)
        time_row = ttk.Frame(trim)
        time_row.grid(row=2, column=1, sticky="ew", padx=8, pady=5)
        time_row.columnconfigure((0, 2), weight=1)
        ttk.Label(trim, text="截取时间").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(time_row, textvariable=self.common_trim_start).grid(row=0, column=0, sticky="ew")
        ttk.Label(time_row, text="到").grid(row=0, column=1, padx=8)
        ttk.Entry(time_row, textvariable=self.common_trim_end).grid(row=0, column=2, sticky="ew")
        ttk.Label(trim, text="编码器").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Combobox(trim, textvariable=self.common_trim_encoder, values=list(COMMON_ENCODERS), state="readonly").grid(row=3, column=1, columnspan=2, sticky="ew", padx=8, pady=5)
        ttk.Label(trim, text="输出容器").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Combobox(trim, textvariable=self.common_trim_muxer, values=[name for name in VIDEO_MUXERS if VIDEO_MUXERS[name] != "source"], state="readonly").grid(row=4, column=1, columnspan=2, sticky="ew", padx=8, pady=5)
        ttk.Button(trim, text="▶ 开始截取", style="Accent.TButton", command=self.start_common_trim).grid(row=5, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Label(trim, text="时间可输入 00:01:23、01:23 或秒数；会按选择的编码器和容器重新输出片段。", style="Hint.TLabel").grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))

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
        ttk.Button(output, text="输出目录", command=lambda: self.open_output_dir(self.output_dir)).grid(row=0, column=0, sticky="w")
        ttk.Entry(output, textvariable=self.output_dir).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(output, text="浏览…", command=self.choose_output_dir).grid(row=0, column=2)

    def _build_subtitle_tab(self, parent):
        parent = self._scrollable_frame(parent)
        parent.columnconfigure(0, weight=3)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        tracks_box = ttk.LabelFrame(parent, text="媒体轨道", padding=12)
        tracks_box.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tracks_box.rowconfigure(2, weight=1)
        tracks_box.columnconfigure(1, weight=1)
        ttk.Label(tracks_box, text="视频文件").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(tracks_box, textvariable=self.subtitle_source).grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(tracks_box, text="选择…", command=self.choose_subtitle_source).grid(row=0, column=2, pady=5)
        track_actions = ttk.Frame(tracks_box)
        track_actions.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 8))
        ttk.Button(track_actions, text="保留/取消选中轨道", command=self.toggle_selected_subtitle_track).pack(side="left")
        ttk.Button(track_actions, text="导出选中字幕", command=self.start_subtitle_export).pack(side="left", padx=8)
        columns = ("keep", "type", "index", "codec", "lang", "title")
        self.subtitle_track_tree = ttk.Treeview(tracks_box, columns=columns, show="headings", height=12)
        for key, text, width in [
            ("keep", "保留", 70),
            ("type", "类型", 70),
            ("index", "流", 60),
            ("codec", "编码", 110),
            ("lang", "语言", 80),
            ("title", "标题", 220),
        ]:
            self.subtitle_track_tree.heading(key, text=text)
            self.subtitle_track_tree.column(key, width=width, stretch=True)
        self.subtitle_track_tree.grid(row=2, column=0, columnspan=3, sticky="nsew")
        self.subtitle_track_tree.bind("<Double-1>", lambda event: self.toggle_selected_subtitle_track())
        track_scroll = ttk.Scrollbar(tracks_box, orient="vertical", command=self.subtitle_track_tree.yview)
        track_scroll.grid(row=2, column=3, sticky="ns")
        self.subtitle_track_tree.configure(yscrollcommand=track_scroll.set)

        ops = ttk.LabelFrame(parent, text="字幕操作", padding=12)
        ops.grid(row=0, column=1, sticky="nsew")
        ops.rowconfigure(4, weight=1)
        ops.columnconfigure(1, weight=1)
        ttk.Button(ops, text="输出目录", command=lambda: self.open_output_dir(self.subtitle_output_dir)).grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(ops, textvariable=self.subtitle_output_dir).grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(ops, text="浏览…", command=self.choose_subtitle_output_dir).grid(row=0, column=2, pady=5)
        ttk.Label(ops, text="输出格式").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(ops, textvariable=self.subtitle_output_format, values=[name for name in VIDEO_MUXERS if VIDEO_MUXERS[name] != "source"], state="readonly").grid(row=1, column=1, columnspan=2, sticky="ew", padx=8, pady=5)
        sub_actions = ttk.Frame(ops)
        sub_actions.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6, 8))
        ttk.Button(sub_actions, text="＋ 导入字幕", command=self.import_subtitle_files).pack(side="left")
        ttk.Button(sub_actions, text="− 移除导入", command=self.remove_selected_external_subtitle).pack(side="left", padx=8)
        self.external_subtitle_list = self._create_work_listbox(ops, selectmode="extended", height=7)
        self.external_subtitle_list.grid(row=3, column=0, columnspan=3, sticky="nsew")
        ttk.Button(ops, text="▶ 保存为新视频文件", style="Accent.TButton", command=self.start_subtitle_mux).grid(row=5, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Label(ops, text="双击轨道可决定是否保留；导入的字幕会放进新视频文件里。", style="Hint.TLabel").grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))

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
        ttk.Button(output, text="输出目录", command=lambda: self.open_output_dir(self.retro_output_dir)).grid(row=0, column=0, sticky="w")
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

    def _build_anamorphic_tab(self, parent):
        parent = self._scrollable_frame(parent)
        parent.columnconfigure(0, weight=3)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        files = ttk.LabelFrame(parent, text="变形镜头素材", padding=12)
        files.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        files.rowconfigure(1, weight=1)
        files.columnconfigure(0, weight=1)
        toolbar = ttk.Frame(files)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="＋ 添加视频", command=self.add_anamorphic_files).pack(side="left")
        ttk.Button(toolbar, text="▤ 添加文件夹", command=self.add_anamorphic_folder).pack(side="left", padx=6)
        ttk.Button(toolbar, text="− 移除", command=self.remove_selected_anamorphic).pack(side="left")
        ttk.Button(toolbar, text="清空", command=self.clear_anamorphic_files).pack(side="left", padx=6)
        list_frame = ttk.Frame(files)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.anamorphic_file_list = self._create_work_listbox(list_frame, selectmode="extended")
        self.anamorphic_file_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.anamorphic_file_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.anamorphic_file_list.configure(yscrollcommand=scrollbar.set)

        output = ttk.Frame(files)
        output.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        output.columnconfigure(1, weight=1)
        ttk.Button(output, text="输出目录", command=lambda: self.open_output_dir(self.anamorphic_output_dir)).grid(row=0, column=0, sticky="w")
        ttk.Entry(output, textvariable=self.anamorphic_output_dir).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(output, text="浏览…", command=self.choose_anamorphic_output_dir).grid(row=0, column=2)

        settings = ttk.LabelFrame(parent, text="反挤压与画幅", padding=12)
        settings.grid(row=0, column=1, sticky="nsew")
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="反挤压比例").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Combobox(settings, textvariable=self.anamorphic_factor, values=["1.25", "1.33", "1.50", "1.60", "1.80", "2.00"], state="readonly").grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Label(settings, text="画幅处理").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(
            settings,
            textvariable=self.anamorphic_mode,
            values=["保留反挤压宽画幅", "裁切到目标画幅", "加黑边适配目标画幅"],
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Label(settings, text="目标画幅").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Combobox(settings, textvariable=self.anamorphic_target_aspect, values=["16:9", "1.85:1", "2.00:1", "2.35:1", "2.39:1", "2.40:1"], state="readonly").grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Label(settings, text="输出分辨率").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Combobox(settings, textvariable=self.anamorphic_resolution, values=["保持反挤压尺寸", "4K 宽 3840", "2K 宽 2048", "1080p 宽 1920", "720p 宽 1280"], state="readonly").grid(row=3, column=1, sticky="ew", pady=5)
        ttk.Label(settings, text="编码器").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Combobox(settings, textvariable=self.anamorphic_encoder_name, values=list(COMMON_ENCODERS), state="readonly").grid(row=4, column=1, sticky="ew", pady=5)
        ttk.Checkbutton(settings, text="保留音频", variable=self.anamorphic_keep_audio).grid(row=5, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Checkbutton(settings, text="轻度锐化反挤压后的画面", variable=self.anamorphic_auto_crop).grid(row=6, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Button(settings, text="▶ 开始变形处理", style="Accent.TButton", command=self.start_anamorphic_processing).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ttk.Button(settings, text="▣ 生成预览帧", command=self.start_anamorphic_preview).grid(row=8, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Label(settings, text="适合手机外接变形镜头、微单变形镜头和素材反挤压归档。", style="Hint.TLabel").grid(row=9, column=0, columnspan=2, sticky="w", pady=(12, 0))

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
        ttk.Button(output, text="输出目录", command=lambda: self.open_output_dir(self.audio_output_dir)).grid(row=0, column=0, sticky="w")
        ttk.Entry(output, textvariable=self.audio_output_dir).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(output, text="浏览…", command=self.choose_audio_output_dir).grid(row=0, column=2)
        audio_output_modes = ttk.Frame(output)
        audio_output_modes.grid(row=1, column=1, columnspan=2, sticky="w", padx=8, pady=(8, 0))
        ttk.Radiobutton(audio_output_modes, text="自定义", value="自定义", variable=self.audio_output_mode).pack(side="left")
        ttk.Radiobutton(audio_output_modes, text="和源文件同一目录", value="和源文件同一目录", variable=self.audio_output_mode).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(output, text="覆盖源文件（警告）", variable=self.audio_overwrite_source).grid(row=2, column=1, columnspan=2, sticky="w", padx=8, pady=(8, 0))

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
        ttk.Button(settings, text="↩ 倒放保存", command=self.start_audio_reverse).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _build_mux_tab(self, parent):
        parent = self._scrollable_frame(parent)
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        merge = ttk.LabelFrame(parent, text="合并文件", padding=12)
        merge.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        merge.rowconfigure(1, weight=1)
        merge.columnconfigure(0, weight=1)
        merge_toolbar = ttk.Frame(merge)
        merge_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(merge_toolbar, text="＋ 添加文件", command=self.add_mux_merge_files).pack(side="left")
        ttk.Button(merge_toolbar, text="− 移除", command=self.remove_selected_mux_merge).pack(side="left", padx=6)
        ttk.Button(merge_toolbar, text="清空", command=self.clear_mux_merge_files).pack(side="left")
        self.mux_merge_list = self._create_work_listbox(merge, selectmode="extended")
        self.mux_merge_list.grid(row=1, column=0, sticky="nsew")
        merge_scroll = ttk.Scrollbar(merge, orient="vertical", command=self.mux_merge_list.yview)
        merge_scroll.grid(row=1, column=1, sticky="ns")
        self.mux_merge_list.configure(yscrollcommand=merge_scroll.set)
        merge_options = ttk.Frame(merge)
        merge_options.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        merge_options.columnconfigure(1, weight=1)
        ttk.Label(merge_options, text="输出名称").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(merge_options, textvariable=self.mux_merge_name).grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        ttk.Label(merge_options, text="输出格式").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(merge_options, textvariable=self.mux_merge_format, values=[name for name in VIDEO_MUXERS if VIDEO_MUXERS[name] != "source"], state="readonly").grid(row=1, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(merge_options, text="▶ 合并输出", style="Accent.TButton", command=self.start_mux_merge).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        convert = ttk.LabelFrame(parent, text="封装转换", padding=12)
        convert.grid(row=0, column=1, sticky="nsew")
        convert.rowconfigure(1, weight=1)
        convert.columnconfigure(0, weight=1)
        convert_toolbar = ttk.Frame(convert)
        convert_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(convert_toolbar, text="＋ 添加文件", command=self.add_mux_convert_files).pack(side="left")
        ttk.Button(convert_toolbar, text="▤ 添加文件夹", command=self.add_mux_convert_folder).pack(side="left", padx=6)
        ttk.Button(convert_toolbar, text="− 移除", command=self.remove_selected_mux_convert).pack(side="left")
        ttk.Button(convert_toolbar, text="清空", command=self.clear_mux_convert_files).pack(side="left", padx=6)
        self.mux_convert_list = self._create_work_listbox(convert, selectmode="extended")
        self.mux_convert_list.grid(row=1, column=0, sticky="nsew")
        convert_scroll = ttk.Scrollbar(convert, orient="vertical", command=self.mux_convert_list.yview)
        convert_scroll.grid(row=1, column=1, sticky="ns")
        self.mux_convert_list.configure(yscrollcommand=convert_scroll.set)
        convert_options = ttk.Frame(convert)
        convert_options.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        convert_options.columnconfigure(1, weight=1)
        ttk.Button(convert_options, text="输出目录", command=lambda: self.open_output_dir(self.mux_output_dir)).grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(convert_options, textvariable=self.mux_output_dir).grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(convert_options, text="浏览…", command=self.choose_mux_output_dir).grid(row=0, column=2, pady=5)
        ttk.Label(convert_options, text="输出格式").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(convert_options, textvariable=self.mux_convert_format, values=[name for name in VIDEO_MUXERS if VIDEO_MUXERS[name] != "source"], state="readonly").grid(row=1, column=1, columnspan=2, sticky="ew", padx=8, pady=5)
        ttk.Label(convert_options, text="音频处理").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Combobox(convert_options, textvariable=self.mux_audio_mode, values=["复制音频", "AAC 编码", "MP3 编码", "Opus 编码", "FLAC 无损", "WAV PCM", "移除音频"], state="readonly").grid(row=2, column=1, columnspan=2, sticky="ew", padx=8, pady=5)
        ttk.Label(convert_options, text="音频码率").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(convert_options, textvariable=self.mux_audio_bitrate).grid(row=3, column=1, columnspan=2, sticky="ew", padx=8, pady=5)
        ttk.Button(convert_options, text="▶ 开始封装转换", style="Accent.TButton", command=self.start_mux_convert).grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))

    def _build_batch_tab(self, parent):
        parent = self._scrollable_frame(parent)
        parent.columnconfigure(0, weight=1)
        box = ttk.LabelFrame(parent, text="批量压缩", padding=12)
        box.grid(row=0, column=0, sticky="nsew")
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text="输入文件夹").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(box, textvariable=self.batch_input_dir).grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(box, text="浏览…", command=self.choose_batch_input_dir).grid(row=0, column=2, pady=5)
        ttk.Button(box, text="输出文件夹", command=lambda: self.open_output_dir(self.batch_output_dir)).grid(row=1, column=0, sticky="w", pady=5)
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
        ttk.Button(setup, text="输出目录", command=lambda: self.open_output_dir(self.lut_page_output)).grid(row=2, column=0, sticky="w", pady=5)
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
        self.task_tree.column("status", width=82, anchor="center", stretch=False)
        self.task_tree.column("started", width=86, anchor="center", stretch=False)
        self.task_tree.column("finished", width=86, anchor="center", stretch=False)
        self.task_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=self.task_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.task_tree.configure(yscrollcommand=scrollbar.set)
        self.task_tree.bind("<ButtonPress-1>", self._task_drag_start)
        self.task_tree.bind("<B1-Motion>", self._task_drag_motion)
        self.task_tree.bind("<Double-1>", lambda event: self.start_selected_queued_tasks())
        self.task_tree.bind("<Delete>", lambda event: self.remove_selected_tasks())
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
            ttk.Label(panel, text="自定义宽高").grid(row=row, column=0, sticky="w", pady=5)
            size_row = ttk.Frame(panel)
            size_row.grid(row=row, column=1, sticky="ew", pady=5)
            size_row.columnconfigure((0, 2), weight=1)
            ttk.Spinbox(size_row, from_=320, to=7680, increment=2, textvariable=self.custom_width).grid(row=0, column=0, sticky="ew")
            ttk.Label(size_row, text="x", style="Hint.TLabel").grid(row=0, column=1, padx=8)
            ttk.Spinbox(size_row, from_=0, to=4320, increment=2, textvariable=self.custom_height).grid(row=0, column=2, sticky="ew")
            ttk.Label(size_row, text="宽 x 高；高度 0 表示自动保持比例", style="Hint.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

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
        self.root.bind("<Delete>", self._handle_delete_key)

    def open_github_project(self):
        webbrowser.open("https://github.com/arenascats/MarukoToolbox-Rewrite")

    def _app_settings_path(self):
        return Path.cwd() / "data" / "app_settings.json"

    def _handle_delete_key(self, event):
        if hasattr(self, "notebook") and self.notebook.select() == str(self.tasks_tab):
            self.remove_selected_tasks()

    def open_settings_window(self):
        window = Toplevel(self.root)
        self._set_window_icon(window)
        window.title("设置")
        window.geometry("620x760")
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

        order_box = ttk.LabelFrame(box, text="页面排序", padding=12)
        order_box.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        order_box.columnconfigure(0, weight=1)
        self.tab_order_list = self._create_work_listbox(order_box, height=6, exportselection=False)
        self.tab_order_list.grid(row=0, column=0, rowspan=3, sticky="ew")
        for name in self.tab_order:
            self.tab_order_list.insert(END, name)
        ttk.Button(order_box, text="上移", command=lambda: self._move_tab_order_item(-1)).grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=(0, 4))
        ttk.Button(order_box, text="下移", command=lambda: self._move_tab_order_item(1)).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=4)
        ttk.Button(order_box, text="默认顺序", command=self._reset_tab_order_list).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(4, 0))

        actions = ttk.Frame(box)
        actions.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        actions.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(actions, text="还原默认设置", command=self.restore_default_settings).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="查看日志", command=self.show_log_window).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(actions, text="删除日志", command=self.clear_log).grid(row=0, column=2, sticky="ew", padx=(6, 0))
        ttk.Button(box, text="应用并保存", style="Accent.TButton", command=lambda: [self._apply_app_settings(), window.destroy()]).grid(row=6, column=0, sticky="ew", pady=(14, 0))

    def _apply_preferred_encoder(self):
        if self.preferred_device.get() == "优先 CPU":
            self.encoder_name.set("CPU H.264 / AVC (libx264)")
        else:
            self.encoder_name.set("GPU H.265 / HEVC (hevc_nvenc)")
        self.refresh_encoder_choices()

    def _apply_app_settings(self):
        if hasattr(self, "tab_order_list"):
            self.tab_order = [self.tab_order_list.get(index) for index in range(self.tab_order_list.size())]
            self._apply_tab_order()
        self._apply_preferred_encoder()
        self._save_app_settings()
        self._log("设置已保存。")

    def _move_tab_order_item(self, direction):
        if not hasattr(self, "tab_order_list"):
            return
        selection = self.tab_order_list.curselection()
        if not selection:
            return
        index = selection[0]
        new_index = max(0, min(self.tab_order_list.size() - 1, index + direction))
        if index == new_index:
            return
        value = self.tab_order_list.get(index)
        self.tab_order_list.delete(index)
        self.tab_order_list.insert(new_index, value)
        self.tab_order_list.selection_set(new_index)

    def _reset_tab_order_list(self):
        if not hasattr(self, "tab_order_list"):
            return
        default_order = ["视频", "字幕", "变形", "封装", "音频", "常用", "复古", "Lut调色", "批量压缩", "MediaInfo", "任务管理"]
        self.tab_order_list.delete(0, END)
        for name in default_order:
            self.tab_order_list.insert(END, name)

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
        self._set_window_icon(window)
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
            "tab_order": self.tab_order,
            "audio_output_mode": self.audio_output_mode.get(),
            "audio_output_dir": self.audio_output_dir.get(),
            "audio_overwrite_source": self.audio_overwrite_source.get(),
            "video_settings": self._video_settings_dict(),
            "output_dir": self.output_dir.get(),
            "audio_encoder_name": self.audio_encoder_name.get(),
            "audio_page_bitrate": self.audio_page_bitrate.get(),
            "audio_sample_rate": self.audio_sample_rate.get(),
            "audio_channels": self.audio_channels.get(),
            "audio_normalize": self.audio_normalize.get(),
            "common_output_dir": self.common_output_dir.get(),
            "common_trim_start": self.common_trim_start.get(),
            "common_trim_end": self.common_trim_end.get(),
            "common_trim_encoder": self.common_trim_encoder.get(),
            "common_trim_muxer": self.common_trim_muxer.get(),
            "subtitle_output_dir": self.subtitle_output_dir.get(),
            "subtitle_output_format": self.subtitle_output_format.get(),
            "anamorphic_output_dir": self.anamorphic_output_dir.get(),
            "anamorphic_factor": self.anamorphic_factor.get(),
            "anamorphic_mode": self.anamorphic_mode.get(),
            "anamorphic_target_aspect": self.anamorphic_target_aspect.get(),
            "anamorphic_resolution": self.anamorphic_resolution.get(),
            "anamorphic_encoder_name": self.anamorphic_encoder_name.get(),
            "anamorphic_keep_audio": self.anamorphic_keep_audio.get(),
            "anamorphic_auto_crop": self.anamorphic_auto_crop.get(),
            "mux_output_dir": self.mux_output_dir.get(),
            "mux_merge_name": self.mux_merge_name.get(),
            "mux_merge_format": self.mux_merge_format.get(),
            "mux_convert_format": self.mux_convert_format.get(),
            "mux_audio_mode": self.mux_audio_mode.get(),
            "mux_audio_bitrate": self.mux_audio_bitrate.get(),
            "batch_input_dir": self.batch_input_dir.get(),
            "batch_output_dir": self.batch_output_dir.get(),
            "batch_preset_name": self.batch_preset_name.get(),
            "batch_keep_tree": self.batch_keep_tree.get(),
            "batch_include_audio": self.batch_include_audio.get(),
            "batch_vertical_mode": self.batch_vertical_mode.get(),
            "queue_parallel_jobs": self.queue_parallel_jobs.get(),
            "retro_output_dir": self.retro_output_dir.get(),
            "retro_format_name": self.retro_format_name.get(),
            "retro_resolution_name": self.retro_resolution_name.get(),
            "retro_bitrate": self.retro_bitrate.get(),
            "retro_audio_bitrate": self.retro_audio_bitrate.get(),
            "retro_deinterlace": self.retro_deinterlace.get(),
            "retro_denoise": self.retro_denoise.get(),
            "retro_remux_format": self.retro_remux_format.get(),
            "retro_remux_audio": self.retro_remux_audio.get(),
            "screenshot_dir": self.screenshot_dir.get(),
            "lut_page_video": self.lut_page_video.get(),
            "lut_page_folder": self.lut_page_folder.get(),
            "lut_page_output": self.lut_page_output.get(),
            "lut_page_time": self.lut_page_time.get(),
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
            "audio_output_mode": self.audio_output_mode,
            "audio_output_dir": self.audio_output_dir,
            "audio_overwrite_source": self.audio_overwrite_source,
            "output_dir": self.output_dir,
            "audio_encoder_name": self.audio_encoder_name,
            "audio_page_bitrate": self.audio_page_bitrate,
            "audio_sample_rate": self.audio_sample_rate,
            "audio_channels": self.audio_channels,
            "audio_normalize": self.audio_normalize,
            "common_output_dir": self.common_output_dir,
            "common_trim_start": self.common_trim_start,
            "common_trim_end": self.common_trim_end,
            "common_trim_encoder": self.common_trim_encoder,
            "common_trim_muxer": self.common_trim_muxer,
            "subtitle_output_dir": self.subtitle_output_dir,
            "subtitle_output_format": self.subtitle_output_format,
            "anamorphic_output_dir": self.anamorphic_output_dir,
            "anamorphic_factor": self.anamorphic_factor,
            "anamorphic_mode": self.anamorphic_mode,
            "anamorphic_target_aspect": self.anamorphic_target_aspect,
            "anamorphic_resolution": self.anamorphic_resolution,
            "anamorphic_encoder_name": self.anamorphic_encoder_name,
            "anamorphic_keep_audio": self.anamorphic_keep_audio,
            "anamorphic_auto_crop": self.anamorphic_auto_crop,
            "mux_output_dir": self.mux_output_dir,
            "mux_merge_name": self.mux_merge_name,
            "mux_merge_format": self.mux_merge_format,
            "mux_convert_format": self.mux_convert_format,
            "mux_audio_mode": self.mux_audio_mode,
            "mux_audio_bitrate": self.mux_audio_bitrate,
            "batch_input_dir": self.batch_input_dir,
            "batch_output_dir": self.batch_output_dir,
            "batch_preset_name": self.batch_preset_name,
            "batch_keep_tree": self.batch_keep_tree,
            "batch_include_audio": self.batch_include_audio,
            "batch_vertical_mode": self.batch_vertical_mode,
            "queue_parallel_jobs": self.queue_parallel_jobs,
            "retro_output_dir": self.retro_output_dir,
            "retro_format_name": self.retro_format_name,
            "retro_resolution_name": self.retro_resolution_name,
            "retro_bitrate": self.retro_bitrate,
            "retro_audio_bitrate": self.retro_audio_bitrate,
            "retro_deinterlace": self.retro_deinterlace,
            "retro_denoise": self.retro_denoise,
            "retro_remux_format": self.retro_remux_format,
            "retro_remux_audio": self.retro_remux_audio,
            "screenshot_dir": self.screenshot_dir,
            "lut_page_video": self.lut_page_video,
            "lut_page_folder": self.lut_page_folder,
            "lut_page_output": self.lut_page_output,
            "lut_page_time": self.lut_page_time,
        }
        for key, variable in mapping.items():
            if key in data:
                variable.set(data[key])
        if isinstance(data.get("video_settings"), dict):
            self._apply_video_settings_dict(data["video_settings"])
        if isinstance(data.get("tab_order"), list):
            valid = [name for name in data["tab_order"] if name in self.tab_frames]
            missing = [name for name in self.tab_order if name not in valid]
            self.tab_order = valid + missing
            self._apply_tab_order()
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
        self._set_window_icon(self.preview_window)
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

    def choose_common_trim_video(self):
        path = filedialog.askopenfilename(title="选择要截取的视频", filetypes=VIDEO_FILETYPES)
        if path:
            self.common_trim_video.set(path)

    def choose_common_output_dir(self):
        folder = filedialog.askdirectory(title="选择常用功能输出目录")
        if folder:
            self.common_output_dir.set(folder)

    def choose_subtitle_source(self):
        path = filedialog.askopenfilename(title="选择带字幕的视频文件", filetypes=VIDEO_FILETYPES)
        if path:
            self.subtitle_source.set(path)
            self.load_subtitle_tracks()

    def choose_subtitle_output_dir(self):
        folder = filedialog.askdirectory(title="选择字幕封装输出目录")
        if folder:
            self.subtitle_output_dir.set(folder)

    def open_output_dir(self, variable):
        folder = variable.get().strip()
        if not folder:
            messagebox.showwarning("无法打开目录", "请先设置输出目录。")
            return
        try:
            path = Path(folder).expanduser().resolve()
            path.mkdir(parents=True, exist_ok=True)
            self._open_folder(path)
        except Exception as exc:
            messagebox.showerror("打开目录失败", str(exc))

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
        self._set_window_icon(window)
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
            "custom_height": self.custom_height.get(),
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
            "custom_height": self.custom_height,
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

    def choose_anamorphic_output_dir(self):
        folder = filedialog.askdirectory(title="选择变形视频输出目录")
        if folder:
            self.anamorphic_output_dir.set(folder)

    def choose_mux_output_dir(self):
        folder = filedialog.askdirectory(title="选择封装输出目录")
        if folder:
            self.mux_output_dir.set(folder)

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

    def add_anamorphic_files(self):
        paths = filedialog.askopenfilenames(title="选择变形镜头视频", filetypes=VIDEO_FILETYPES)
        self._add_anamorphic_paths(paths)

    def add_anamorphic_folder(self):
        folder = filedialog.askdirectory(title="选择变形镜头视频文件夹")
        if folder:
            self._add_anamorphic_paths([folder])

    def _add_anamorphic_paths(self, paths):
        existing = set(self.anamorphic_files)
        for path in self._expand_paths(paths, VIDEO_EXTENSIONS):
            full = str(path.resolve())
            if full not in existing:
                self.anamorphic_files.append(full)
                self.anamorphic_file_list.insert(END, full)
                existing.add(full)
        self._log(f"已添加 {len(self.anamorphic_files)} 个变形镜头素材")

    def remove_selected_anamorphic(self):
        for index in reversed(self.anamorphic_file_list.curselection()):
            self.anamorphic_file_list.delete(index)
            del self.anamorphic_files[index]

    def clear_anamorphic_files(self):
        self.anamorphic_files.clear()
        self.anamorphic_file_list.delete(0, END)

    def add_mux_merge_files(self):
        paths = filedialog.askopenfilenames(title="选择要合并的文件", filetypes=VIDEO_FILETYPES + AUDIO_FILETYPES + [("所有文件", "*.*")])
        self._add_mux_paths(paths, self.mux_merge_files, self.mux_merge_list)

    def remove_selected_mux_merge(self):
        self._remove_selected_mux_paths(self.mux_merge_files, self.mux_merge_list)

    def clear_mux_merge_files(self):
        self.mux_merge_files.clear()
        self.mux_merge_list.delete(0, END)

    def add_mux_convert_files(self):
        paths = filedialog.askopenfilenames(title="选择要转换封装的文件", filetypes=VIDEO_FILETYPES + AUDIO_FILETYPES + [("所有文件", "*.*")])
        self._add_mux_paths(paths, self.mux_convert_files, self.mux_convert_list)

    def add_mux_convert_folder(self):
        folder = filedialog.askdirectory(title="选择封装转换文件夹")
        if folder:
            paths = [str(p) for p in Path(folder).rglob("*") if p.is_file() and (p.suffix.lower() in VIDEO_EXTENSIONS or p.suffix.lower() in AUDIO_EXTENSIONS)]
            self._add_mux_paths(paths, self.mux_convert_files, self.mux_convert_list)

    def remove_selected_mux_convert(self):
        self._remove_selected_mux_paths(self.mux_convert_files, self.mux_convert_list)

    def clear_mux_convert_files(self):
        self.mux_convert_files.clear()
        self.mux_convert_list.delete(0, END)

    def load_subtitle_tracks(self):
        source = Path(self.subtitle_source.get())
        if not source.exists():
            messagebox.showwarning("没有视频", "请先选择有效的视频文件。")
            return
        info = ffmpeg.probe_media_info(source)
        streams = info.get("streams", []) if info else []
        self.subtitle_tracks = []
        for item in self.subtitle_track_tree.get_children():
            self.subtitle_track_tree.delete(item)
        type_count = {"video": 0, "audio": 0, "subtitle": 0}
        for stream in streams:
            codec_type = stream.get("codec_type", "unknown")
            if codec_type not in type_count:
                continue
            type_count[codec_type] += 1
            tags = stream.get("tags", {}) or {}
            track = {
                "stream_index": stream.get("index"),
                "codec_type": codec_type,
                "codec": stream.get("codec_name") or "",
                "lang": tags.get("language") or "und",
                "title": tags.get("title") or f"{self._subtitle_type_label(codec_type)} {type_count[codec_type]}",
                "keep": True,
            }
            self.subtitle_tracks.append(track)
            self._insert_subtitle_track_row(len(self.subtitle_tracks) - 1, track)
        self._log(f"已读取轨道：视频 {type_count['video']}，音频 {type_count['audio']}，字幕 {type_count['subtitle']}")

    def _insert_subtitle_track_row(self, row_id, track):
        self.subtitle_track_tree.insert("", END, iid=str(row_id), values=(
            "是" if track["keep"] else "否",
            self._subtitle_type_label(track["codec_type"]),
            track["stream_index"],
            track["codec"],
            track["lang"],
            track["title"],
        ))

    def _subtitle_type_label(self, codec_type):
        return {"video": "视频", "audio": "音频", "subtitle": "字幕"}.get(codec_type, codec_type)

    def toggle_selected_subtitle_track(self):
        for item in self.subtitle_track_tree.selection():
            index = int(item)
            self.subtitle_tracks[index]["keep"] = not self.subtitle_tracks[index]["keep"]
            self.subtitle_track_tree.item(item, values=(
                "是" if self.subtitle_tracks[index]["keep"] else "否",
                self._subtitle_type_label(self.subtitle_tracks[index]["codec_type"]),
                self.subtitle_tracks[index]["stream_index"],
                self.subtitle_tracks[index]["codec"],
                self.subtitle_tracks[index]["lang"],
                self.subtitle_tracks[index]["title"],
            ))

    def import_subtitle_files(self):
        paths = filedialog.askopenfilenames(title="导入外部字幕", filetypes=[("字幕文件", "*.srt *.ass *.ssa *.vtt"), ("所有文件", "*.*")])
        existing = set(self.subtitle_external_files)
        for raw in paths:
            path = Path(raw)
            if path.is_file():
                full = str(path.resolve())
                if full not in existing:
                    self.subtitle_external_files.append(full)
                    self.external_subtitle_list.insert(END, full)
                    existing.add(full)

    def remove_selected_external_subtitle(self):
        for index in reversed(self.external_subtitle_list.curselection()):
            self.external_subtitle_list.delete(index)
            del self.subtitle_external_files[index]

    def _add_mux_paths(self, paths, target_list, listbox):
        existing = set(target_list)
        for raw in paths:
            path = Path(raw)
            if path.is_file():
                full = str(path.resolve())
                if full not in existing:
                    target_list.append(full)
                    listbox.insert(END, full)
                    existing.add(full)
        self._log(f"已添加 {len(target_list)} 个封装文件")

    def _remove_selected_mux_paths(self, target_list, listbox):
        for index in reversed(listbox.curselection()):
            listbox.delete(index)
            del target_list[index]

    def check_environment(self):
        info = ffmpeg.detect_environment()
        if not info.ffmpeg:
            messagebox.showerror("环境检测", "未找到 ffmpeg。请安装 FFmpeg 6.0+ 并加入 PATH。")
            return
        window = Toplevel(self.root)
        self._set_window_icon(window)
        window.title("环境检测与 Benchmark")
        window.geometry("1280x720")
        window.minsize(1120, 620)
        box = ttk.Frame(window, padding=14)
        box.pack(fill="both", expand=True)
        box.columnconfigure(0, weight=1)
        box.columnconfigure(1, weight=2)
        box.rowconfigure(0, weight=1)

        info_box = ttk.LabelFrame(box, text="现有环境信息", padding=12)
        info_box.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        info_box.columnconfigure(0, weight=1)
        env_text = Text(info_box, height=12, wrap="word", bg="#ffffff", fg=self.COLORS["text"], relief="solid", borderwidth=1)
        env_text.grid(row=0, column=0, sticky="nsew")
        info_box.rowconfigure(0, weight=1)
        text = "\n".join([
            f"ffmpeg: {info.ffmpeg}",
            f"ffprobe: {info.ffprobe or '未找到，仍可压缩但进度估算会变弱'}",
            f"NVENC 编码器: {'可用' if info.has_nvenc else '未检测到'}",
            f"AMF 编码器: {'可用' if info.has_amf else '未检测到'}",
        ])
        env_text.insert(END, text)
        env_text.configure(state="disabled")

        bench = ttk.LabelFrame(box, text="Benchmark", padding=12)
        bench.grid(row=0, column=1, sticky="nsew")
        bench.columnconfigure(1, weight=1)
        bench.columnconfigure(2, weight=0)
        bench.columnconfigure(3, weight=0)
        bench.rowconfigure(3, weight=1)

        video_path = StringVar(value="")
        ttk.Label(bench, text="测试视频").grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Entry(bench, textvariable=video_path).grid(row=0, column=1, sticky="ew", padx=8, pady=(0, 8))
        ttk.Button(bench, text="选择…", command=lambda: self._choose_benchmark_video(video_path)).grid(row=0, column=2, pady=(0, 8))

        encoder_box = ttk.Frame(bench)
        encoder_box.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        encoder_vars = {}
        default_encoders = [name for name in COMMON_ENCODERS if name in ENCODERS]
        for index, name in enumerate(ENCODERS):
            var = BooleanVar(value=name in default_encoders)
            encoder_vars[name] = var
            ttk.Checkbutton(encoder_box, text=name, variable=var).grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 12), pady=3)

        action_row = ttk.Frame(bench)
        action_row.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        action_row.columnconfigure(0, weight=1)
        status = StringVar(value="等待开始")
        ttk.Label(action_row, textvariable=status, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        stop_button = ttk.Button(action_row, text="停止 Benchmark", command=lambda: self._stop_environment_benchmark(status))
        stop_button.grid(row=0, column=1, sticky="e", padx=(0, 8))
        ttk.Button(
            action_row,
            text="开始 Benchmark",
            style="Accent.TButton",
            command=lambda: self._start_environment_benchmark(video_path, encoder_vars, result_tree, status),
        ).grid(row=0, column=2, sticky="e")

        columns = ("encoder", "status", "size", "ratio", "elapsed")
        result_tree = ttk.Treeview(bench, columns=columns, show="headings", height=10)
        result_tree.heading("encoder", text="编码器")
        result_tree.heading("status", text="状态")
        result_tree.heading("size", text="压缩后大小")
        result_tree.heading("ratio", text="压缩率")
        result_tree.heading("elapsed", text="耗时")
        result_tree.column("encoder", width=360, minwidth=260, stretch=True)
        result_tree.column("status", width=130, minwidth=110, anchor="center", stretch=True)
        result_tree.column("size", width=130, minwidth=110, anchor="e", stretch=True)
        result_tree.column("ratio", width=110, minwidth=90, anchor="e", stretch=True)
        result_tree.column("elapsed", width=110, minwidth=90, anchor="e", stretch=True)
        result_tree.grid(row=3, column=0, columnspan=3, sticky="nsew")
        scrollbar = ttk.Scrollbar(bench, orient="vertical", command=result_tree.yview)
        scrollbar.grid(row=3, column=3, sticky="ns")
        result_tree.configure(yscrollcommand=scrollbar.set)

    def _choose_benchmark_video(self, variable):
        path = filedialog.askopenfilename(title="选择 Benchmark 视频", filetypes=VIDEO_FILETYPES)
        if path:
            variable.set(path)

    def _start_environment_benchmark(self, video_path, encoder_vars, result_tree, status):
        source = Path(video_path.get())
        if not source.exists():
            messagebox.showwarning("没有视频", "请先选择一个用于 Benchmark 的视频文件。")
            return
        selected = [name for name, var in encoder_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("没有编码器", "请至少勾选一个编码器。")
            return
        for item in result_tree.get_children():
            result_tree.delete(item)
        for name in selected:
            result_tree.insert("", END, iid=name, values=(name, "等待中", "-", "-", "-"))
        status.set("Benchmark 运行中")
        self.benchmark_result_tree = result_tree
        self.benchmark_status = status
        self._start_worker("环境 Benchmark", self._environment_benchmark_worker, source, selected)

    def _stop_environment_benchmark(self, status):
        self.stop_requested = True
        status.set("正在停止 Benchmark")
        for job in self.active_ffmpeg_jobs.values():
            job["cancel"] = True
            process = job.get("process")
            if process and process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass

    def _environment_benchmark_worker(self, source, selected):
        settings = self._settings()
        bench_dir = Path(self.output_dir.get()).resolve() / "benchmark"
        bench_dir.mkdir(parents=True, exist_ok=True)
        source_size = source.stat().st_size if source.exists() else 0
        for index, name in enumerate(selected, start=1):
            if self.stop_requested:
                break
            encoder_key = ENCODERS[name]
            tag = ENCODER_FILENAME_TAGS.get(encoder_key, re.sub(r"[^A-Za-z0-9]+", "_", encoder_key).strip("_"))
            safe_name = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
            target = bench_dir / f"{source.stem}_benchmark_{index}_{tag}_{safe_name}.mkv"
            start = time.perf_counter()
            self.messages.put(("benchmark_update", (name, "运行中", "-", "-", "-")))
            cmd = ffmpeg.build_compress_command(source, target, settings, encoder_override=encoder_key, benchmark=True)
            ok = self._run_ffmpeg(cmd, source, show_job_window=False, benchmark_name=name)
            elapsed = time.perf_counter() - start
            if self.stop_requested:
                self.messages.put(("benchmark_update", (name, "已停止", "-", "-", self._format_seconds(elapsed))))
            elif ok and target.exists():
                target_size = target.stat().st_size
                saved_ratio = max(0, (1 - target_size / source_size) * 100) if source_size and target_size else 0
                self.messages.put(("benchmark_update", (
                    name,
                    "支持",
                    self._format_size(target_size),
                    f"{saved_ratio:.1f}%",
                    self._format_seconds(elapsed),
                )))
            else:
                self.messages.put(("benchmark_update", (name, "不支持", "-", "-", self._format_seconds(elapsed))))
            self.messages.put(("progress", index / len(selected) * 100))
        self.messages.put(("benchmark_done", "Benchmark 完成" if not self.stop_requested else "Benchmark 已停止"))

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
        files = self._selected_files() or list(self.files)
        settings = self._settings()
        output_dir = Path(self.output_dir.get()).resolve()
        task_id = self._create_task(self._describe_video_queue_task(files, output_dir))
        self.queued_tasks[task_id] = {
            "type": "video",
            "files": files,
            "settings": settings,
            "output_dir": output_dir,
            "conflict_action": self.file_conflict_action.get(),
        }
        self._update_task_status(task_id, "已加入队列")
        self.notebook.select(self.tasks_tab)

    def _describe_video_queue_task(self, files, output_dir):
        first = Path(files[0])
        if len(files) == 1:
            return f"压缩视频 {first} 到 {output_dir}"
        return f"压缩视频 {first} 等 {len(files)} 个文件到 {output_dir}"

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

    def start_audio_reverse(self):
        if not self._confirm_overwrite_if_needed():
            return
        if not self.audio_files:
            messagebox.showwarning("没有音频", "请先添加单个或批量音频文件。")
            return
        self._start_worker("音频倒放", self._audio_reverse_worker)

    def start_common_trim(self):
        source = Path(self.common_trim_video.get())
        if not source.exists():
            messagebox.showwarning("没有视频", "请先选择要截取的视频文件。")
            return
        if self._parse_time_seconds(self.common_trim_end.get()) <= self._parse_time_seconds(self.common_trim_start.get()):
            messagebox.showwarning("时间无效", "结束时间必须大于开始时间。")
            return
        self._start_worker("截取视频", self._common_trim_worker, source)

    def start_subtitle_mux(self):
        source = Path(self.subtitle_source.get())
        if not source.exists():
            messagebox.showwarning("没有视频", "请先选择视频文件。")
            return
        if not self.subtitle_tracks:
            self.load_subtitle_tracks()
        if not any(track["keep"] for track in self.subtitle_tracks) and not self.subtitle_external_files:
            messagebox.showwarning("没有轨道", "请至少保留一个原轨道或导入一个字幕文件。")
            return
        self._start_worker("字幕封装", self._subtitle_mux_worker, source)

    def start_subtitle_export(self):
        selected = self.subtitle_track_tree.selection()
        if not selected:
            messagebox.showwarning("没有字幕", "请先选中一个字幕轨道。")
            return
        track = self.subtitle_tracks[int(selected[0])]
        if track["codec_type"] != "subtitle":
            messagebox.showwarning("不是字幕轨道", "只能导出字幕轨道。")
            return
        self._start_worker("导出字幕", self._subtitle_export_worker, Path(self.subtitle_source.get()), track)

    def start_retro_processing(self):
        if not self._confirm_overwrite_if_needed():
            return
        if not self.retro_files:
            messagebox.showwarning("没有素材", "请先添加古老素材文件。")
            return
        self._start_worker("复古处理", self._retro_worker)

    def start_anamorphic_processing(self):
        if not self._confirm_overwrite_if_needed():
            return
        if not self.anamorphic_files:
            messagebox.showwarning("没有视频", "请先添加变形镜头拍摄的视频文件。")
            return
        self._start_worker("变形处理", self._anamorphic_worker)

    def start_anamorphic_preview(self):
        source = self.anamorphic_files[0] if self.anamorphic_files else ""
        if hasattr(self, "anamorphic_file_list") and self.anamorphic_file_list.curselection():
            source = self.anamorphic_files[self.anamorphic_file_list.curselection()[0]]
        if not source:
            messagebox.showwarning("没有视频", "请先添加或选中一个变形镜头视频。")
            return
        self._start_worker("变形预览帧", self._anamorphic_preview_worker, Path(source))

    def start_mux_merge(self):
        if len(self.mux_merge_files) < 2:
            messagebox.showwarning("文件不足", "请至少添加两个要合并的文件。")
            return
        self._start_worker("合并文件", self._mux_merge_worker)

    def start_mux_convert(self):
        if not self.mux_convert_files:
            messagebox.showwarning("没有文件", "请先添加要封装转换的文件。")
            return
        self._start_worker("封装转换", self._mux_convert_worker)

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
        for job in self.active_ffmpeg_jobs.values():
            job["cancel"] = True
            process = job.get("process")
            if process and process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass
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
        if hasattr(self, "task_tree"):
            self.task_tree.insert("", END, iid=task_id, values=(task_name, "等待中", "", ""))
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
            custom_height=self.custom_height.get(),
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
            overwrite=self.file_conflict_action.get() == "覆盖" or self.audio_overwrite_source.get(),
            normalize=self.audio_normalize.get(),
            output_mode=self.audio_output_mode.get(),
            overwrite_source=self.audio_overwrite_source.get(),
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
        self.messages.put(("multi_job_start", total if jobs > 1 else 0))
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
                job_id = f"video_{time.time_ns()}"
                futures.append(executor.submit(self._compress_one, source_path, target, settings, job_id))
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
        self.messages.put(("multi_job_end", not self.stop_requested))
        if self.auto_open_output.get() and not self.stop_requested:
            self._open_folder(output_dir)

    def _compress_one(self, source_path, target, settings, job_id=None):
        if self.stop_requested:
            return None
        start = time.perf_counter()
        source_size = source_path.stat().st_size if source_path.exists() else 0
        self.messages.put(("status", f"正在压缩：{source_path.name}"))
        ok = self._run_encode_job(source_path, target, settings, job_id=job_id)
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

    def _common_trim_worker(self, source_path):
        output_dir = Path(self.common_output_dir.get()).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = VIDEO_MUXERS[self.common_trim_muxer.get()]
        target = ffmpeg.unique_path(output_dir, source_path, suffix, self.file_conflict_action.get() == "覆盖", tag="trim")
        start_time = self.common_trim_start.get().strip()
        end_time = self.common_trim_end.get().strip()
        self.messages.put(("status", f"截取视频：{source_path.name}"))
        start = time.perf_counter()
        source_size = source_path.stat().st_size if source_path.exists() else 0
        ok = self._run_ffmpeg(self._build_common_trim_command(source_path, target, start_time, end_time), source_path)
        elapsed = time.perf_counter() - start
        target_size = target.stat().st_size if ok and target.exists() else 0
        result = CompressionResult(source_path, target, ok, elapsed, source_size, target_size)
        self._log_compression_result(result)
        self.messages.put(("status", "截取视频完成" if ok else "截取视频失败"))
        if ok and self.auto_open_output.get():
            self._open_folder(output_dir)

    def _build_common_trim_command(self, source_path, target, start_time, end_time):
        ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"
        encoder_key = ENCODERS.get(self.common_trim_encoder.get(), "libx264")
        encoder, pix_fmt = ffmpeg.resolve_encoder(encoder_key)
        cmd = [
            ffmpeg_path,
            "-hide_banner",
            "-y" if self.file_conflict_action.get() == "覆盖" else "-n",
            "-ss",
            start_time,
            "-to",
            end_time,
            "-i",
            str(source_path),
            "-map",
            "0",
            "-c:v",
            encoder,
        ]
        if "nvenc" in encoder:
            cmd += ["-preset", "p5", "-rc", "vbr", "-cq", "23", "-b:v", "0"]
        elif encoder.endswith("_amf"):
            cmd += ["-quality", "balanced", "-rc", "cqp", "-qp_i", "23", "-qp_p", "23", "-qp_b", "23"]
        elif encoder == "libsvtav1":
            cmd += ["-preset", "6", "-crf", "28"]
        elif encoder == "libvpx-vp9":
            cmd += ["-crf", "30", "-b:v", "0", "-row-mt", "1"]
        elif encoder == "prores_ks":
            cmd += ["-profile:v", "3"]
        else:
            cmd += ["-preset", "medium", "-crf", "23"]
        if pix_fmt:
            cmd += ["-pix_fmt", pix_fmt]
        cmd += ["-c:a", "copy", "-map_metadata", "0", str(target)]
        return cmd

    def _video_target_path(self, output_dir, source_path, settings, action=None):
        action = action or self.file_conflict_action.get()
        base_target = ffmpeg.unique_video_output_path(output_dir, source_path, settings, True)
        if action == "跳过" and base_target.exists():
            return None
        if action == "覆盖":
            return base_target
        return ffmpeg.unique_video_output_path(output_dir, source_path, settings, False)

    def _run_encode_job(self, source_path, target, settings, job_id=None):
        if settings.quality_mode == "2PASS / 两遍码率":
            return self._run_two_pass(source_path, target, settings, job_id=job_id)
        return self._run_ffmpeg(ffmpeg.build_compress_command(source_path, target, settings), source_path, job_id=job_id)

    def _run_two_pass(self, source_path, target, settings, job_id=None):
        temp = target.with_suffix(".passlog")
        base = ffmpeg.build_compress_command(source_path, target, settings)
        first = list(base[:-1]) + ["-pass", "1", "-an", "-f", "null", os.devnull]
        second = list(base[:-1]) + ["-pass", "2", str(target)]
        pass1_id = f"{job_id}_pass1" if job_id else None
        pass2_id = f"{job_id}_pass2" if job_id else None
        ok1 = self._run_ffmpeg(first, source_path, job_id=pass1_id, title_suffix="第 1 遍")
        ok2 = self._run_ffmpeg(second, source_path, job_id=pass2_id, title_suffix="第 2 遍") if ok1 else False
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
        settings = self._audio_settings()
        total = len(self.audio_files)
        results = []
        last_output_dir = Path(self.audio_output_dir.get()).resolve()
        for index, source in enumerate(self.audio_files, start=1):
            if self.stop_requested:
                break
            source_path = Path(source)
            output_dir = source_path.parent if settings.output_mode == "和源文件同一目录" else Path(self.audio_output_dir.get()).resolve()
            last_output_dir = output_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            target = ffmpeg.unique_audio_output_path(output_dir, source_path, settings)
            self.messages.put(("status", f"[{index}/{total}] 正在压缩音频：{source_path.name}"))
            results.append(self._convert_audio_one(source_path, target, settings))
            self.messages.put(("progress", index / total * 100))
        self._log_compression_summary(results)
        self.messages.put(("status", "音频任务完成" if not self.stop_requested else "音频任务已停止"))
        if self.auto_open_output.get() and not self.stop_requested:
            self._open_folder(last_output_dir)

    def _convert_audio_one(self, source_path, target, settings):
        start = time.perf_counter()
        source_size = source_path.stat().st_size if source_path.exists() else 0
        ok = self._run_ffmpeg(ffmpeg.build_audio_command(source_path, target, settings), source_path)
        elapsed = time.perf_counter() - start
        target_size = target.stat().st_size if ok and target.exists() else 0
        result = CompressionResult(source_path, target, ok, elapsed, source_size, target_size)
        self._log_compression_result(result)
        return result

    def _audio_reverse_worker(self):
        settings = self._audio_settings()
        total = len(self.audio_files)
        results = []
        last_output_dir = Path(self.audio_output_dir.get()).resolve()
        for index, source in enumerate(self.audio_files, start=1):
            if self.stop_requested:
                break
            source_path = Path(source)
            output_dir = source_path.parent if settings.output_mode == "和源文件同一目录" else Path(self.audio_output_dir.get()).resolve()
            last_output_dir = output_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            _, suffix = AUDIO_ENCODERS[settings.encoder_name]
            target = ffmpeg.unique_path(output_dir, source_path, suffix, settings.overwrite, tag="reverse")
            self.messages.put(("status", f"[{index}/{total}] 倒放音频：{source_path.name}"))
            results.append(self._reverse_audio_one(source_path, target, settings))
            self.messages.put(("progress", index / total * 100))
        self._log_compression_summary(results)
        self.messages.put(("status", "音频倒放完成" if not self.stop_requested else "音频倒放已停止"))
        if self.auto_open_output.get() and not self.stop_requested:
            self._open_folder(last_output_dir)

    def _reverse_audio_one(self, source_path, target, settings):
        start = time.perf_counter()
        source_size = source_path.stat().st_size if source_path.exists() else 0
        ok = self._run_ffmpeg(self._build_audio_reverse_command(source_path, target, settings), source_path)
        elapsed = time.perf_counter() - start
        target_size = target.stat().st_size if ok and target.exists() else 0
        result = CompressionResult(source_path, target, ok, elapsed, source_size, target_size)
        self._log_compression_result(result)
        return result

    def _build_audio_reverse_command(self, source_path, target, settings):
        ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"
        encoder, _ = AUDIO_ENCODERS[settings.encoder_name]
        filters = ["areverse"]
        if settings.normalize:
            filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
        cmd = [ffmpeg_path, "-hide_banner", "-y" if settings.overwrite else "-n", "-i", str(source_path), "-vn", "-af", ",".join(filters), "-c:a", encoder]
        if settings.bitrate.strip() and encoder not in {"flac", "pcm_s16le"}:
            cmd += ["-b:a", settings.bitrate.strip()]
        if settings.sample_rate.strip():
            cmd += ["-ar", settings.sample_rate.strip()]
        if settings.channels.strip():
            cmd += ["-ac", settings.channels.strip()]
        cmd += [str(target)]
        return cmd

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

    def _anamorphic_worker(self):
        output_dir = Path(self.anamorphic_output_dir.get()).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        total = len(self.anamorphic_files)
        results = []
        for index, source in enumerate(self.anamorphic_files, start=1):
            if self.stop_requested:
                break
            source_path = Path(source)
            target = self._anamorphic_target_path(output_dir, source_path)
            self.messages.put(("status", f"[{index}/{total}] 变形处理：{source_path.name}"))
            results.append(self._anamorphic_one(source_path, target))
            self.messages.put(("progress", index / total * 100))
        self._log_compression_summary(results)
        self.messages.put(("status", "变形处理完成" if not self.stop_requested else "变形处理已停止"))
        if self.auto_open_output.get() and not self.stop_requested:
            self._open_folder(output_dir)

    def _anamorphic_one(self, source_path, target):
        start = time.perf_counter()
        source_size = source_path.stat().st_size if source_path.exists() else 0
        ok = self._run_ffmpeg(self._build_anamorphic_command(source_path, target), source_path)
        elapsed = time.perf_counter() - start
        target_size = target.stat().st_size if ok and target.exists() else 0
        result = CompressionResult(source_path, target, ok, elapsed, source_size, target_size)
        self._log_compression_result(result)
        return result

    def _mux_merge_worker(self):
        output_dir = Path(self.mux_output_dir.get()).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = VIDEO_MUXERS[self.mux_merge_format.get()]
        target = self._mux_merge_target_path(output_dir, suffix)
        list_path = output_dir / "_mux_concat_list.txt"
        list_text = "\n".join(f"file '{self._escape_concat_path(path)}'" for path in self.mux_merge_files)
        list_path.write_text(list_text, encoding="utf-8")
        try:
            self.messages.put(("status", "正在合并文件"))
            ok = self._run_ffmpeg(self._build_mux_merge_command(list_path, target), Path(self.mux_merge_files[0]))
            self.messages.put(("log", f"合并完成：{target}" if ok and target.exists() else "合并失败：请确认文件编码、分辨率、帧率和流结构兼容。"))
        finally:
            try:
                list_path.unlink()
            except Exception:
                pass

    def _mux_convert_worker(self):
        output_dir = Path(self.mux_output_dir.get()).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = VIDEO_MUXERS[self.mux_convert_format.get()]
        total = len(self.mux_convert_files)
        for index, raw in enumerate(self.mux_convert_files, start=1):
            if self.stop_requested:
                break
            source = Path(raw)
            target = ffmpeg.unique_path(output_dir, source, suffix, self.file_conflict_action.get() == "覆盖", tag="mux")
            self.messages.put(("status", f"[{index}/{total}] 封装转换：{source.name}"))
            ok = self._run_ffmpeg(self._build_mux_convert_command(source, target), source)
            self.messages.put(("log", f"封装完成：{target.name}" if ok and target.exists() else f"封装失败：{source.name}"))
            self.messages.put(("progress", index / total * 100))
        self.messages.put(("status", "封装转换完成" if not self.stop_requested else "封装转换已停止"))
        if self.auto_open_output.get() and not self.stop_requested:
            self._open_folder(output_dir)

    def _build_mux_merge_command(self, list_path, target):
        ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"
        return [
            ffmpeg_path,
            "-hide_banner",
            "-y" if self.file_conflict_action.get() == "覆盖" else "-n",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            "-map_metadata",
            "0",
            str(target),
        ]

    def _build_mux_convert_command(self, source, target):
        ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"
        cmd = [ffmpeg_path, "-hide_banner", "-y" if self.file_conflict_action.get() == "覆盖" else "-n", "-i", str(source), "-map", "0", "-c:v", "copy"]
        mode = self.mux_audio_mode.get()
        if mode == "复制音频":
            cmd += ["-c:a", "copy"]
        elif mode == "移除音频":
            cmd += ["-an"]
        else:
            audio_encoder = {
                "AAC 编码": "aac",
                "MP3 编码": "libmp3lame",
                "Opus 编码": "libopus",
                "FLAC 无损": "flac",
                "WAV PCM": "pcm_s16le",
            }.get(mode, "aac")
            cmd += ["-c:a", audio_encoder]
            if mode not in {"FLAC 无损", "WAV PCM"} and self.mux_audio_bitrate.get().strip():
                cmd += ["-b:a", self.mux_audio_bitrate.get().strip()]
        cmd += ["-map_metadata", "0", str(target)]
        return cmd

    def _mux_merge_target_path(self, output_dir, suffix):
        name = self.mux_merge_name.get().strip() or "merged"
        target = output_dir / f"{name}{suffix}"
        if self.file_conflict_action.get() == "覆盖" or not target.exists():
            return target
        counter = 1
        while True:
            candidate = output_dir / f"{name}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def _escape_concat_path(self, path):
        return str(Path(path).resolve()).replace("\\", "/").replace("'", r"'\''")

    def _subtitle_mux_worker(self, source):
        output_dir = Path(self.subtitle_output_dir.get()).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = VIDEO_MUXERS[self.subtitle_output_format.get()]
        target = ffmpeg.unique_path(output_dir, source, suffix, self.file_conflict_action.get() == "覆盖", tag="subtitles")
        self.messages.put(("status", f"保存字幕封装：{source.name}"))
        ok = self._run_ffmpeg(self._build_subtitle_mux_command(source, target), source)
        self.messages.put(("log", f"字幕封装完成：{target}" if ok and target.exists() else "字幕封装失败"))
        if ok and self.auto_open_output.get():
            self._open_folder(output_dir)

    def _subtitle_export_worker(self, source, track):
        output_dir = Path(self.subtitle_output_dir.get()).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        lang = re.sub(r"[^A-Za-z0-9_-]+", "_", track.get("lang") or "und")
        target = output_dir / f"{source.stem}_subtitle_{track['stream_index']}_{lang}.srt"
        counter = 1
        while target.exists() and self.file_conflict_action.get() != "覆盖":
            target = output_dir / f"{source.stem}_subtitle_{track['stream_index']}_{lang}_{counter}.srt"
            counter += 1
        self.messages.put(("status", f"导出字幕：{source.name}"))
        ok = self._run_ffmpeg(self._build_subtitle_export_command(source, track["stream_index"], target), source)
        self.messages.put(("log", f"字幕已导出：{target}" if ok and target.exists() else "字幕导出失败：图形字幕可能无法直接导出为 SRT。"))

    def _build_subtitle_mux_command(self, source, target):
        ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"
        cmd = [ffmpeg_path, "-hide_banner", "-y" if self.file_conflict_action.get() == "覆盖" else "-n", "-i", str(source)]
        for subtitle in self.subtitle_external_files:
            cmd += ["-i", subtitle]
        for track in self.subtitle_tracks:
            if track["keep"]:
                cmd += ["-map", f"0:{track['stream_index']}"]
        for index, _ in enumerate(self.subtitle_external_files, start=1):
            cmd += ["-map", f"{index}:0"]
        cmd += ["-c", "copy"]
        suffix = target.suffix.lower()
        if suffix in {".mp4", ".mov", ".m4v"}:
            cmd += ["-c:s", "mov_text"]
        cmd += ["-map_metadata", "0", str(target)]
        return cmd

    def _build_subtitle_export_command(self, source, stream_index, target):
        ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"
        return [
            ffmpeg_path,
            "-hide_banner",
            "-y" if self.file_conflict_action.get() == "覆盖" else "-n",
            "-i",
            str(source),
            "-map",
            f"0:{stream_index}",
            str(target),
        ]

    def _anamorphic_preview_worker(self, source_path):
        output_dir = Path(self.anamorphic_output_dir.get()).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"{source_path.stem}_anamorphic_preview.jpg"
        cmd = self._build_anamorphic_command(source_path, target, preview=True)
        self.messages.put(("status", f"生成变形预览帧：{source_path.name}"))
        ok = self._run_ffmpeg(cmd, source_path)
        if ok and target.exists():
            self.messages.put(("log", f"变形预览帧已生成：{target}"))
            self.messages.put(("anamorphic_preview", str(target)))
        else:
            self.messages.put(("log", "变形预览帧生成失败"))

    def _anamorphic_target_path(self, output_dir, source_path):
        suffix = source_path.suffix if source_path.suffix.lower() in VIDEO_EXTENSIONS else ".mp4"
        return ffmpeg.unique_path(output_dir, source_path, suffix, self.file_conflict_action.get() == "覆盖", tag="anamorphic")

    def _build_anamorphic_command(self, source_path, target, preview=False):
        ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"
        factor = self._float_or_default(self.anamorphic_factor.get(), 1.33)
        filters = [f"scale=trunc(iw*{factor:.4f}/2)*2:trunc(ih/2)*2"]
        if self.anamorphic_auto_crop.get():
            filters.append("unsharp=5:5:0.6:3:3:0.0")
        mode = self.anamorphic_mode.get()
        aspect = self._aspect_value(self.anamorphic_target_aspect.get())
        if mode == "裁切到目标画幅":
            filters.append(f"crop='trunc(min(iw,ih*{aspect:.6f})/2)*2':'trunc(min(ih,iw/{aspect:.6f})/2)*2'")
        elif mode == "加黑边适配目标画幅":
            filters.append(f"pad='trunc(max(iw,ih*{aspect:.6f})/2)*2':'trunc(max(ih,iw/{aspect:.6f})/2)*2':(ow-iw)/2:(oh-ih)/2:black")
        width = self._anamorphic_output_width()
        if width:
            filters.append(f"scale={width}:trunc(ow/a/2)*2")
        else:
            filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
        cmd = [ffmpeg_path, "-hide_banner", "-y", "-i", str(source_path), "-vf", ",".join(filters)]
        if preview:
            cmd += ["-frames:v", "1", "-q:v", "2", str(target)]
            return cmd
        encoder = ENCODERS.get(self.anamorphic_encoder_name.get(), "libx264")
        resolved_encoder, pix_fmt = ffmpeg.resolve_encoder(encoder)
        cmd += ["-c:v", resolved_encoder]
        if "nvenc" in resolved_encoder:
            cmd += ["-preset", "p5", "-rc", "vbr", "-cq", "23", "-b:v", "0"]
        elif resolved_encoder.endswith("_amf"):
            cmd += ["-quality", "balanced", "-rc", "cqp", "-qp_i", "23", "-qp_p", "23", "-qp_b", "23"]
        elif resolved_encoder == "prores_ks":
            cmd += ["-profile:v", "3"]
        elif resolved_encoder == "libsvtav1":
            cmd += ["-preset", "6", "-crf", "28"]
        elif resolved_encoder == "libvpx-vp9":
            cmd += ["-crf", "30", "-b:v", "0", "-row-mt", "1"]
        else:
            cmd += ["-preset", "medium", "-crf", "23"]
        if pix_fmt:
            cmd += ["-pix_fmt", pix_fmt]
        cmd += ["-c:a", "copy"] if self.anamorphic_keep_audio.get() else ["-an"]
        cmd += ["-map_metadata", "0", str(target)]
        return cmd

    def _anamorphic_output_width(self):
        mapping = {
            "4K 宽 3840": 3840,
            "2K 宽 2048": 2048,
            "1080p 宽 1920": 1920,
            "720p 宽 1280": 1280,
        }
        return mapping.get(self.anamorphic_resolution.get())

    def _aspect_value(self, text):
        if ":" in text:
            left, right = text.split(":", 1)
            return self._float_or_default(left, 2.39) / max(self._float_or_default(right, 1), 0.01)
        return self._float_or_default(text.replace(":1", ""), 2.39)

    def _float_or_default(self, value, default):
        try:
            return float(str(value).strip())
        except Exception:
            return default

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
            output_mode="自定义",
            overwrite_source=False,
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
            custom_height=self.custom_height.get(),
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

    def _run_ffmpeg(self, cmd, source, job_id=None, title_suffix="", show_job_window=True, benchmark_name=None):
        job_id = job_id or f"ffmpeg_{time.time_ns()}"
        duration = ffmpeg.duration_seconds(source)
        if "-progress" not in cmd and len(cmd) > 2:
            cmd = list(cmd[:-1]) + ["-progress", "pipe:1", "-nostats", cmd[-1]]
        title = Path(source).name
        if title_suffix:
            title = f"{title} - {title_suffix}"
        command_text = " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd)
        if show_job_window:
            self.messages.put(("job_start", (job_id, title)))
        self.messages.put(("log", command_text))
        if show_job_window:
            self.messages.put(("job_log", (job_id, command_text)))
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
            self.active_ffmpeg_jobs[job_id] = {"process": process, "cancel": False}
            if job_id in self.cancelled_ffmpeg_jobs:
                self.active_ffmpeg_jobs[job_id]["cancel"] = True
            for line in process.stdout:
                job = self.active_ffmpeg_jobs.get(job_id, {})
                if self.stop_requested or job.get("cancel"):
                    process.terminate()
                    if show_job_window:
                        self.messages.put(("job_log", (job_id, "已请求停止此任务。")))
                        self.messages.put(("job_done", (job_id, False)))
                    return False
                line = line.strip()
                if line:
                    self.messages.put(("log", line))
                    if show_job_window:
                        self.messages.put(("job_log", (job_id, line)))
                    seconds = self._parse_ffmpeg_progress_seconds(line) or ffmpeg.parse_time(line)
                    if seconds and duration:
                        progress = min(seconds / duration * 100, 99)
                        self.messages.put(("subprogress", progress))
                        if show_job_window:
                            self.messages.put(("job_progress", (job_id, progress)))
                        if benchmark_name:
                            self.messages.put(("benchmark_update", (benchmark_name, f"运行中 {progress:.0f}%", "-", "-", "-")))
            code = process.wait()
            if code != 0:
                self.messages.put(("log", f"ffmpeg 退出码：{code}"))
                self.messages.put(("log", "编码失败提示：如果当前使用的是显卡硬件编码器，请换用 CPU H.264 / AVC (libx264) 后再次尝试。"))
                if show_job_window:
                    self.messages.put(("job_log", (job_id, f"ffmpeg 退出码：{code}")))
                    self.messages.put(("job_log", (job_id, "编码失败提示：如果当前使用的是显卡硬件编码器，请换用 CPU H.264 / AVC (libx264) 后再次尝试。")))
            if show_job_window:
                self.messages.put(("job_progress", (job_id, 100 if code == 0 else 0)))
                self.messages.put(("job_done", (job_id, code == 0)))
            return code == 0
        except FileNotFoundError:
            self.messages.put(("log", "未找到 ffmpeg，请安装并加入 PATH。"))
            if show_job_window:
                self.messages.put(("job_log", (job_id, "未找到 ffmpeg，请安装并加入 PATH。")))
                self.messages.put(("job_done", (job_id, False)))
            return False
        except Exception as exc:
            self.messages.put(("log", f"任务失败：{exc}"))
            self.messages.put(("log", "编码失败提示：如果当前使用的是显卡硬件编码器，请换用 CPU H.264 / AVC (libx264) 后再次尝试。"))
            if show_job_window:
                self.messages.put(("job_log", (job_id, f"任务失败：{exc}")))
                self.messages.put(("job_log", (job_id, "编码失败提示：如果当前使用的是显卡硬件编码器，请换用 CPU H.264 / AVC (libx264) 后再次尝试。")))
                self.messages.put(("job_done", (job_id, False)))
            return False
        finally:
            self.cancelled_ffmpeg_jobs.discard(job_id)
            self.active_ffmpeg_jobs.pop(job_id, None)

    def _parse_ffmpeg_progress_seconds(self, line):
        if line.startswith("out_time_ms="):
            try:
                return int(line.split("=", 1)[1]) / 1_000_000
            except Exception:
                return 0
        if line.startswith("out_time="):
            return ffmpeg.parse_time("time=" + line.split("=", 1)[1])
        return 0

    def _parse_time_seconds(self, value):
        text = str(value).strip()
        if not text:
            return 0
        if ":" not in text:
            try:
                return float(text)
            except Exception:
                return 0
        parts = text.split(":")
        try:
            numbers = [float(part) for part in parts]
        except Exception:
            return 0
        seconds = 0
        for number in numbers:
            seconds = seconds * 60 + number
        return seconds

    def _create_thumbnail(self, video_path, thumbnail_time, output_dir=None):
        thumb = (output_dir / f"{video_path.stem}.jpg") if output_dir else video_path.with_suffix(".jpg")
        self.messages.put(("status", f"生成缩略图：{thumb.name}"))
        ffmpeg.run_capture(ffmpeg.build_thumbnail_command(video_path, thumb, thumbnail_time))
        self.messages.put(("log", f"缩略图已生成：{thumb}"))

    def _log_compression_result(self, result: CompressionResult):
        if not result.ok:
            self.messages.put(("log", f"压缩失败：{result.source.name}，用时 {self._format_seconds(result.elapsed_seconds)}"))
            self.messages.put(("log", "建议换用 CPU H.264 / AVC (libx264) 编码器再次尝试。"))
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
                if not self.multi_job_mode:
                    self._log(payload)
            elif kind == "status":
                if not self.multi_job_mode:
                    self.current_task.set(payload)
                    self._log(payload)
            elif kind == "progress":
                self.progress.set(payload)
            elif kind == "subprogress":
                if not self.multi_job_mode:
                    self.progress.set(payload)
                    self.current_task.set(f"当前文件进度：{payload:.0f}%")
            elif kind == "multi_job_start":
                self._start_multi_job_mode(payload)
            elif kind == "multi_job_end":
                self._end_multi_job_mode(payload)
            elif kind == "job_start":
                job_id, title = payload
                self._create_job_window(job_id, title)
            elif kind == "job_log":
                job_id, text = payload
                self._append_job_log(job_id, text)
            elif kind == "job_progress":
                job_id, value = payload
                self._update_job_progress(job_id, value)
            elif kind == "job_done":
                job_id, ok = payload
                self._finish_job_window(job_id, ok)
            elif kind == "benchmark_update":
                self._update_benchmark_result(payload)
            elif kind == "benchmark_done":
                self._finish_benchmark(payload)
            elif kind == "preview":
                self._show_preview(payload)
            elif kind == "anamorphic_preview":
                self._show_anamorphic_preview(payload)
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

    def _start_multi_job_mode(self, total):
        self.multi_job_mode = total > 1
        self.multi_job_total = total
        self.multi_job_finished = 0
        if self.multi_job_mode:
            self.current_task.set(f"正在编码：0/{total}")
            self.progress.set(0)
            self._log(f"正在编码：共 {total} 个任务")

    def _end_multi_job_mode(self, completed):
        if self.multi_job_mode:
            text = "停止编码" if completed else "停止编码：任务已停止"
            self.current_task.set(text)
            self._log(text)
        self.multi_job_mode = False
        self.multi_job_total = 0
        self.multi_job_finished = 0

    def _update_benchmark_result(self, payload):
        name, status, size, ratio, elapsed = payload
        tree = getattr(self, "benchmark_result_tree", None)
        if not tree:
            return
        try:
            if tree.exists(name):
                tree.item(name, values=(name, status, size, ratio, elapsed))
        except Exception:
            pass

    def _finish_benchmark(self, text):
        status = getattr(self, "benchmark_status", None)
        if status:
            try:
                status.set(text)
            except Exception:
                pass
        self.current_task.set(text)
        self._log(text)

    def _create_job_window(self, job_id, title):
        if job_id in self.job_windows:
            return
        window = Toplevel(self.root)
        self._set_window_icon(window)
        window.title(f"任务进度 - {title}")
        window.geometry("760x360")
        window.minsize(520, 260)
        box = ttk.Frame(window, padding=12)
        box.pack(fill="both", expand=True)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(2, weight=1)
        status = StringVar(value=f"运行中：{title}")
        progress = DoubleVar(value=0)
        ttk.Label(box, textvariable=status, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Progressbar(box, variable=progress, maximum=100).grid(row=1, column=0, sticky="ew", pady=(8, 10))
        log = Text(box, height=10, wrap="word", bg="#ffffff", fg=self.COLORS["text"], relief="solid", borderwidth=1)
        log.grid(row=2, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(box, orient="vertical", command=log.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        log.configure(yscrollcommand=scrollbar.set, state="disabled")
        window.protocol("WM_DELETE_WINDOW", lambda: self._cancel_job_window(job_id))
        self.job_windows[job_id] = {
            "window": window,
            "status": status,
            "progress": progress,
            "log": log,
            "closed": False,
        }

    def _append_job_log(self, job_id, text):
        info = self.job_windows.get(job_id)
        if not info:
            return
        log = info["log"]
        log.configure(state="normal")
        log.insert(END, text + "\n")
        log.see(END)
        log.configure(state="disabled")

    def _update_job_progress(self, job_id, value):
        info = self.job_windows.get(job_id)
        if not info:
            return
        info["progress"].set(value)
        info["status"].set(f"当前文件进度：{value:.0f}%")

    def _finish_job_window(self, job_id, ok):
        info = self.job_windows.get(job_id)
        is_file_done = not job_id.endswith("_pass1")
        if self.multi_job_mode and is_file_done:
            self.multi_job_finished += 1
            total = max(1, self.multi_job_total)
            self.progress.set(min(self.multi_job_finished / total * 100, 100))
            self.current_task.set(f"正在编码：{self.multi_job_finished}/{total}")
        if not info or info.get("closed"):
            return
        info["progress"].set(100 if ok else info["progress"].get())
        info["done"] = True
        info["ok"] = ok
        self._append_job_log(job_id, "任务完成。" if ok else "任务已停止或失败。")
        if ok:
            self._countdown_close_job_window(job_id, 3)
        else:
            info["status"].set("已停止或失败")

    def _countdown_close_job_window(self, job_id, seconds):
        info = self.job_windows.get(job_id)
        if not info or info.get("closed"):
            return
        if seconds <= 0:
            try:
                info["window"].destroy()
            except Exception:
                pass
            self.job_windows.pop(job_id, None)
            return
        info["status"].set(f"已完成，{seconds} 秒后自动关闭")
        info["window"].after(1000, lambda: self._countdown_close_job_window(job_id, seconds - 1))

    def _cancel_job_window(self, job_id):
        info = self.job_windows.get(job_id)
        was_done = bool(info and info.get("done"))
        if info:
            info["closed"] = True
            try:
                info["window"].destroy()
            except Exception:
                pass
            self.job_windows.pop(job_id, None)
        job = self.active_ffmpeg_jobs.get(job_id)
        if job:
            job["cancel"] = True
            process = job.get("process")
            if process and process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass
        elif not was_done:
            self.cancelled_ffmpeg_jobs.add(job_id)

    def _show_preview(self, path):
        self.preview_image = PhotoImage(file=path)
        self.preview_label.configure(image=self.preview_image, text="")

    def _show_anamorphic_preview(self, path):
        if not self.anamorphic_preview_window or not self.anamorphic_preview_window.winfo_exists():
            self.anamorphic_preview_window = Toplevel(self.root)
            self._set_window_icon(self.anamorphic_preview_window)
            self.anamorphic_preview_window.title("变形预览帧")
            self.anamorphic_preview_window.geometry("960x540")
            self.anamorphic_preview_window.columnconfigure(0, weight=1)
            self.anamorphic_preview_window.rowconfigure(0, weight=1)
            self.anamorphic_preview_label = ttk.Label(self.anamorphic_preview_window, anchor="center")
            self.anamorphic_preview_label.grid(row=0, column=0, sticky="nsew")
        self.anamorphic_preview_image = PhotoImage(file=path)
        self.anamorphic_preview_label.configure(image=self.anamorphic_preview_image, text="")
        self.anamorphic_preview_window.lift()

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


