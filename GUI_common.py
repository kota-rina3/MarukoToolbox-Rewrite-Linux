import math
import tempfile
from pathlib import Path
from tkinter import END, ttk, filedialog, messagebox

import ffmpeg_utils as ffmpeg
from config import AUDIO_FILETYPES, COMMON_ENCODERS, VIDEO_FILETYPES, VIDEO_MUXERS


def build_common_tab(app, parent):
    parent = app._scrollable_frame(parent)
    parent.columnconfigure(0, weight=1)

    trim = ttk.LabelFrame(parent, text="截取视频", padding=12)
    trim.grid(row=0, column=0, sticky="ew")
    trim.columnconfigure(1, weight=1)
    ttk.Label(trim, text="视频文件").grid(row=0, column=0, sticky="w", pady=5)
    ttk.Entry(trim, textvariable=app.common_trim_video).grid(row=0, column=1, sticky="ew", padx=8, pady=5)
    ttk.Button(trim, text="选择…", command=app.choose_common_trim_video).grid(row=0, column=2, pady=5)
    ttk.Button(trim, text="输出目录", style="OutputDir.TButton", command=lambda: app.open_output_dir(app.common_output_dir)).grid(row=1, column=0, sticky="w", pady=5)
    ttk.Entry(trim, textvariable=app.common_output_dir).grid(row=1, column=1, sticky="ew", padx=8, pady=5)
    ttk.Button(trim, text="浏览…", command=app.choose_common_output_dir).grid(row=1, column=2, pady=5)
    time_row = ttk.Frame(trim)
    time_row.grid(row=2, column=1, sticky="ew", padx=8, pady=5)
    time_row.columnconfigure((0, 2), weight=1)
    ttk.Label(trim, text="截取时间").grid(row=2, column=0, sticky="w", pady=5)
    ttk.Entry(time_row, textvariable=app.common_trim_start).grid(row=0, column=0, sticky="ew")
    ttk.Label(time_row, text="到").grid(row=0, column=1, padx=8)
    ttk.Entry(time_row, textvariable=app.common_trim_end).grid(row=0, column=2, sticky="ew")
    ttk.Label(trim, text="编码器").grid(row=3, column=0, sticky="w", pady=5)
    app.common_trim_encoder_combo = ttk.Combobox(trim, textvariable=app.common_trim_encoder, values=app._filtered_encoder_list(list(COMMON_ENCODERS)), state="readonly")
    app.common_trim_encoder_combo.grid(row=3, column=1, columnspan=2, sticky="ew", padx=8, pady=5)
    ttk.Label(trim, text="输出容器").grid(row=4, column=0, sticky="w", pady=5)
    ttk.Combobox(trim, textvariable=app.common_trim_muxer, values=[name for name in VIDEO_MUXERS if VIDEO_MUXERS[name] != "source"], state="readonly").grid(row=4, column=1, columnspan=2, sticky="ew", padx=8, pady=5)
    ttk.Button(trim, text="▶ 开始截取", style="Accent.TButton", command=app.start_common_trim).grid(row=5, column=0, columnspan=3, sticky="ew", pady=(12, 0))
    ttk.Label(trim, text="时间可输入 00:01:23、01:23 或秒数；会按选择的编码器和容器重新输出片段。", style="Hint.TLabel").grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))

    tools = ttk.LabelFrame(parent, text="音视频工具", padding=12)
    tools.grid(row=1, column=0, sticky="ew", pady=(10, 0))
    tools.columnconfigure(1, weight=1)
    ttk.Label(tools, text="声道复制").grid(row=0, column=0, sticky="w", pady=5)
    ttk.Combobox(tools, textvariable=app.common_channel_copy_mode, values=["左复制到右", "右复制到左"], state="readonly").grid(row=0, column=1, sticky="ew", pady=5)
    action_row = ttk.Frame(tools)
    action_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    action_row.columnconfigure((0, 1), weight=1)
    ttk.Button(action_row, text="分离音视频", command=app.start_common_demux).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ttk.Button(action_row, text="复制左右声道", command=app.start_common_channel_copy).grid(row=0, column=1, sticky="ew", padx=(6, 0))
    ttk.Label(tools, text="使用上方“视频文件”和“输出目录”；支持从视频提取音频或复制单侧声道。", style="Hint.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

    slideshow = ttk.LabelFrame(parent, text="一图流", padding=12)
    slideshow.grid(row=2, column=0, sticky="ew", pady=(10, 0))
    slideshow.columnconfigure(1, weight=1)
    ttk.Label(
        slideshow,
        text="将一张或多张图片与一段音频合成为视频；图片会按顺序循环播放，每张图片的停留时间可单独统一设置。",
        style="Hint.TLabel",
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
    ttk.Label(slideshow, text="图片").grid(row=1, column=0, sticky="w", pady=5)
    ttk.Entry(slideshow, textvariable=app.common_slideshow_images_text).grid(row=1, column=1, sticky="ew", padx=8, pady=5)
    ttk.Button(slideshow, text="选择…", command=app.choose_common_slideshow_images).grid(row=1, column=2, pady=5)
    image_list_box = ttk.Frame(slideshow)
    image_list_box.grid(row=2, column=1, sticky="nsew", padx=8, pady=(0, 5))
    image_list_box.columnconfigure(0, weight=1)
    image_list_box.rowconfigure(0, weight=1)
    app.common_slideshow_image_list = app._create_work_listbox(image_list_box, exportselection=False, height=5)
    app.common_slideshow_image_list.grid(row=0, column=0, sticky="nsew")
    image_scroll = ttk.Scrollbar(image_list_box, orient="vertical", command=app.common_slideshow_image_list.yview)
    image_scroll.grid(row=0, column=1, sticky="ns")
    app.common_slideshow_image_list.configure(yscrollcommand=image_scroll.set)
    image_actions = ttk.Frame(slideshow)
    image_actions.grid(row=2, column=2, sticky="ns", pady=(0, 5))
    ttk.Button(image_actions, text="上移", command=app.move_common_slideshow_image_up).pack(fill="x")
    ttk.Button(image_actions, text="下移", command=app.move_common_slideshow_image_down).pack(fill="x", pady=4)
    ttk.Button(image_actions, text="删除", command=app.remove_common_slideshow_images).pack(fill="x")
    ttk.Label(slideshow, text="音频").grid(row=3, column=0, sticky="w", pady=5)
    ttk.Entry(slideshow, textvariable=app.common_slideshow_audio).grid(row=3, column=1, sticky="ew", padx=8, pady=5)
    ttk.Button(slideshow, text="选择…", command=app.choose_common_slideshow_audio).grid(row=3, column=2, pady=5)
    ttk.Label(slideshow, text="输出目录").grid(row=4, column=0, sticky="w", pady=5)
    ttk.Entry(slideshow, textvariable=app.common_output_dir).grid(row=4, column=1, sticky="ew", padx=8, pady=5)
    ttk.Button(slideshow, text="浏览…", command=app.choose_common_output_dir).grid(row=4, column=2, pady=5)
    ttk.Label(slideshow, text="单张停留").grid(row=5, column=0, sticky="w", pady=5)
    slideshow_time_row = ttk.Frame(slideshow)
    slideshow_time_row.grid(row=5, column=1, sticky="w", padx=8, pady=5)
    ttk.Spinbox(slideshow_time_row, from_=0.5, to=3600, increment=0.5, width=10, textvariable=app.common_slideshow_image_duration).pack(side="left")
    ttk.Label(slideshow_time_row, text="秒").pack(side="left", padx=(6, 0))
    ttk.Label(slideshow, text="输出分辨率").grid(row=6, column=0, sticky="w", pady=5)
    ttk.Combobox(slideshow, textvariable=app.common_slideshow_resolution, values=["保持首图尺寸", "720p", "1080p", "1440p", "2160p"], state="readonly").grid(row=6, column=1, columnspan=2, sticky="ew", padx=8, pady=5)
    ttk.Label(slideshow, text="画面模式").grid(row=7, column=0, sticky="w", pady=5)
    ttk.Combobox(slideshow, textvariable=app.common_slideshow_fill_mode, values=["完整显示留黑边", "铺满裁切", "直接拉伸"], state="readonly").grid(row=7, column=1, columnspan=2, sticky="ew", padx=8, pady=5)
    ttk.Label(slideshow, text="编码器").grid(row=8, column=0, sticky="w", pady=5)
    ttk.Combobox(slideshow, textvariable=app.common_slideshow_encoder, values=app._filtered_encoder_list(list(COMMON_ENCODERS)), state="readonly").grid(row=8, column=1, columnspan=2, sticky="ew", padx=8, pady=5)
    ttk.Label(slideshow, text="帧率").grid(row=9, column=0, sticky="w", pady=5)
    ttk.Spinbox(slideshow, from_=1, to=120, increment=1, width=10, textvariable=app.common_slideshow_fps).grid(row=9, column=1, sticky="w", padx=8, pady=5)
    ttk.Button(slideshow, text="▶ 生成一图流", style="Accent.TButton", command=app.start_common_slideshow).grid(row=10, column=0, columnspan=3, sticky="ew", pady=(12, 0))
    ttk.Label(slideshow, text="支持单图或多图循环，音频播完后自动结束；可调整图片顺序、分辨率和显示模式。", style="Hint.TLabel").grid(row=11, column=0, columnspan=3, sticky="w", pady=(10, 0))


def choose_common_slideshow_audio(app):
    path = filedialog.askopenfilename(title="选择一图流音频", filetypes=AUDIO_FILETYPES)
    if path:
        app.common_slideshow_audio.set(path)


def choose_common_trim_video(app):
    path = filedialog.askopenfilename(title="选择要截取的视频", filetypes=VIDEO_FILETYPES)
    if path:
        app.common_trim_video.set(path)


def start_common_trim(app):
    source = Path(app.common_trim_video.get())
    if not source.exists():
        messagebox.showwarning("没有视频", "请先选择要截取的视频文件。")
        return
    if app._parse_time_seconds(app.common_trim_end.get()) <= app._parse_time_seconds(app.common_trim_start.get()):
        messagebox.showwarning("时间无效", "结束时间必须大于开始时间。")
        return
    app._start_worker("截取视频", app._common_trim_worker, source)


def start_common_slideshow(app):
    if not app.common_slideshow_images:
        messagebox.showwarning("没有图片", "请先选择至少一张图片。")
        return
    audio_path = Path(app.common_slideshow_audio.get())
    if not audio_path.exists():
        messagebox.showwarning("没有音频", "请先选择有效的音频文件。")
        return
    try:
        if float(app.common_slideshow_image_duration.get()) <= 0:
            raise ValueError
    except Exception:
        messagebox.showwarning("停留时间无效", "单张图片停留时间必须大于 0 秒。")
        return
    try:
        if int(app.common_slideshow_fps.get()) <= 0:
            raise ValueError
    except Exception:
        messagebox.showwarning("帧率无效", "帧率必须大于 0。")
        return
    app._start_worker("生成一图流", app._common_slideshow_worker, audio_path)


def choose_common_slideshow_images(app):
    paths = filedialog.askopenfilenames(
        title="选择一图流图片",
        filetypes=[
            ("图片文件", "*.png;*.jpg;*.jpeg;*.bmp;*.webp"),
            ("PNG", "*.png"),
            ("JPEG", "*.jpg;*.jpeg"),
            ("BMP", "*.bmp"),
            ("WebP", "*.webp"),
        ],
    )
    if paths:
        app.common_slideshow_images = [str(path) for path in paths]
        refresh_common_slideshow_images(app)


def refresh_common_slideshow_images(app, selection_index=None):
    preview = ", ".join(Path(path).name for path in app.common_slideshow_images[:3])
    if len(app.common_slideshow_images) > 3:
        preview += f" ... 共 {len(app.common_slideshow_images)} 张"
    if not preview:
        preview = ""
    app.common_slideshow_images_text.set(preview)
    listbox = getattr(app, "common_slideshow_image_list", None)
    if not listbox:
        return
    listbox.delete(0, END)
    for index, path in enumerate(app.common_slideshow_images, start=1):
        listbox.insert(END, f"{index:02d}. {Path(path).name}")
    if selection_index is not None and app.common_slideshow_images:
        selection_index = max(0, min(selection_index, len(app.common_slideshow_images) - 1))
        listbox.selection_set(selection_index)
        listbox.activate(selection_index)


def remove_common_slideshow_images(app):
    listbox = getattr(app, "common_slideshow_image_list", None)
    if not listbox:
        return
    indexes = list(listbox.curselection())
    if not indexes:
        return
    for index in reversed(indexes):
        del app.common_slideshow_images[index]
    next_index = indexes[0] if app.common_slideshow_images else None
    refresh_common_slideshow_images(app, next_index)


def move_common_slideshow_image_up(app):
    move_common_slideshow_image(app, -1)


def move_common_slideshow_image_down(app):
    move_common_slideshow_image(app, 1)


def move_common_slideshow_image(app, direction):
    listbox = getattr(app, "common_slideshow_image_list", None)
    if not listbox:
        return
    selection = list(listbox.curselection())
    if len(selection) != 1:
        return
    index = selection[0]
    target = index + direction
    if target < 0 or target >= len(app.common_slideshow_images):
        return
    app.common_slideshow_images[index], app.common_slideshow_images[target] = app.common_slideshow_images[target], app.common_slideshow_images[index]
    refresh_common_slideshow_images(app, target)


def build_common_slideshow_concat_file(app, audio_duration, image_duration):
    images = [Path(path) for path in app.common_slideshow_images if Path(path).exists()]
    if not images:
        raise FileNotFoundError("未找到可用图片。")
    cycle_duration = max(len(images) * image_duration, 0.1)
    repeat_count = max(1, int(math.ceil(max(audio_duration, image_duration) / cycle_duration)))
    sequence = images * repeat_count
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as handle:
        for image in sequence:
            handle.write(f"file '{concat_escape_path(image)}'\n")
            handle.write(f"duration {image_duration:.3f}\n")
        handle.write(f"file '{concat_escape_path(sequence[-1])}'\n")
        return handle.name


def build_common_slideshow_command(app, concat_file, audio_path, target):
    ffmpeg_path = app.ffmpeg.find_tool("ffmpeg") if hasattr(app, "ffmpeg") else __import__("ffmpeg_utils").find_tool("ffmpeg")
    encoder_key = app.ENCODERS.get(app.common_slideshow_encoder.get(), "libx264") if hasattr(app, "ENCODERS") else None
    if encoder_key is None:
        from config import ENCODERS
        encoder_key = ENCODERS.get(app.common_slideshow_encoder.get(), "libx264")
    import ffmpeg_utils as ffmpeg
    encoder, pix_fmt = ffmpeg.resolve_encoder(encoder_key)
    fps = max(int(app.common_slideshow_fps.get()), 1)
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-y" if app.file_conflict_action.get() == "覆盖" else "-n",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-i",
        str(audio_path),
        "-vf",
        common_slideshow_video_filter(app),
        "-r",
        str(fps),
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
    else:
        cmd += ["-preset", "medium", "-crf", "23"]
    if pix_fmt:
        cmd += ["-pix_fmt", pix_fmt]
    elif target.suffix.lower() == ".mp4":
        cmd += ["-pix_fmt", "yuv420p"]
    cmd += [
        "-vsync",
        "cfr",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(target),
    ]
    return cmd


def concat_escape_path(path):
    return Path(path).as_posix().replace("'", r"'\''")


def common_slideshow_resolution_size(app):
    resolution = app.common_slideshow_resolution.get()
    mapping = {
        "720p": (1280, 720),
        "1080p": (1920, 1080),
        "1440p": (2560, 1440),
        "2160p": (3840, 2160),
    }
    if resolution in mapping:
        return mapping[resolution]
    try:
        import ffmpeg_utils as ffmpeg
        first = Path(app.common_slideshow_images[0])
        info = ffmpeg.probe_media_info(first)
        streams = info.get("streams", []) if isinstance(info, dict) else []
        first_stream = streams[0] if streams else {}
        width = max(int(first_stream.get("width", 1920)), 2)
        height = max(int(first_stream.get("height", 1080)), 2)
        return width, height
    except Exception:
        return 1920, 1080


def common_slideshow_video_filter(app):
    width, height = common_slideshow_resolution_size(app)
    mode = app.common_slideshow_fill_mode.get()
    if mode == "铺满裁切":
        return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    if mode == "直接拉伸":
        return f"scale={width}:{height}"
    return f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"


def common_trim_worker(app, source_path):
    output_dir = Path(app.common_output_dir.get()).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = VIDEO_MUXERS[app.common_trim_muxer.get()]
    target = ffmpeg.unique_path(output_dir, source_path, suffix, app.file_conflict_action.get() == "覆盖", tag="trim")
    start_time = app.common_trim_start.get().strip()
    end_time = app.common_trim_end.get().strip()
    app.messages.put(("status", f"截取视频：{source_path.name}"))
    start = __import__("time").perf_counter()
    source_size = source_path.stat().st_size if source_path.exists() else 0
    ok = app._run_ffmpeg(build_common_trim_command(app, source_path, target, start_time, end_time), source_path)
    elapsed = __import__("time").perf_counter() - start
    target_size = target.stat().st_size if ok and target.exists() else 0
    result = app.CompressionResult(source_path, target, ok, elapsed, source_size, target_size) if hasattr(app, "CompressionResult") else None
    if result is not None:
        app._log_compression_result(result)
    else:
        from data import CompressionResult
        app._log_compression_result(CompressionResult(source_path, target, ok, elapsed, source_size, target_size))
    app.messages.put(("status", "截取视频完成" if ok else "截取视频失败"))
    if ok and app.auto_open_output.get():
        app._open_folder(output_dir)


def common_slideshow_worker(app, audio_path):
    output_dir = Path(app.common_output_dir.get()).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    overwrite = app.file_conflict_action.get() == "覆盖"
    first_image = Path(app.common_slideshow_images[0])
    target = ffmpeg.unique_path(output_dir, first_image, ".mp4", overwrite, tag="slideshow")
    app.messages.put(("status", f"生成一图流：{audio_path.name}"))
    audio_duration = ffmpeg.duration_seconds(audio_path)
    image_duration = max(float(app.common_slideshow_image_duration.get()), 0.1)
    list_path = None
    ok = False
    try:
        list_path = build_common_slideshow_concat_file(app, audio_duration, image_duration)
        cmd = build_common_slideshow_command(app, list_path, audio_path, target)
        ok = app._run_ffmpeg(cmd, audio_path)
    finally:
        if list_path:
            try:
                Path(list_path).unlink(missing_ok=True)
            except Exception:
                pass
    if ok:
        app.messages.put(("log", f"一图流已导出：{target}"))
    app.messages.put(("status", "一图流生成完成" if ok else "一图流生成失败"))
    if ok and app.auto_open_output.get():
        app._open_folder(output_dir)


def build_common_trim_command(app, source_path, target, start_time, end_time):
    ffmpeg_path = ffmpeg.find_tool("ffmpeg")
    from config import ENCODERS
    encoder_key = ENCODERS.get(app.common_trim_encoder.get(), "libx264")
    encoder, pix_fmt = ffmpeg.resolve_encoder(encoder_key)
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-y" if app.file_conflict_action.get() == "覆盖" else "-n",
        "-ss",
        start_time,
        "-to",
        end_time,
        "-i",
        str(source_path),
        "-map",
        "0:v?",
        "-map",
        "0:a?",
        "-dn",
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
