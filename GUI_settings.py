from tkinter import END, Text, Toplevel, messagebox, ttk


def build_settings_panel(app, parent):
    return app._build_settings_panel_legacy(parent)


# 视频页面“压缩设置”相关函数逐步集中到本模块。
# 当前阶段采用“转发到 legacy 实现 + 已迁出的真实实现”并存的方式，
# 后续继续把 gui.py 中对应方法体搬到这里。


def load_video_preset(app):
    window = Toplevel(app.root)
    app._set_window_icon(window)
    window.title("加载预设")
    app._set_window_geometry(window, "940x420")
    window.minsize(860, 340)
    box = ttk.Frame(window, padding=16)
    box.pack(fill="both", expand=True)
    box.columnconfigure(0, weight=3)
    box.columnconfigure(1, weight=2)
    box.columnconfigure(2, weight=3)
    box.rowconfigure(1, weight=1)

    ttk.Label(box, text="用户预设").grid(row=0, column=0, sticky="w")
    ttk.Label(box, text="主要参数预览").grid(row=0, column=1, sticky="w", padx=(8, 8))
    ttk.Label(box, text="内置预设").grid(row=0, column=2, sticky="w")

    user_box = ttk.Frame(box)
    user_box.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
    user_box.columnconfigure(0, weight=1)
    user_box.rowconfigure(0, weight=1)
    user_list = app._create_work_listbox(user_box, exportselection=False)
    user_list.grid(row=0, column=0, sticky="nsew")
    for item in app.user_video_presets:
        user_list.insert(END, item["name"])
    if app.user_video_presets:
        user_list.selection_set(0)

    preview_box = ttk.Frame(box)
    preview_box.grid(row=1, column=1, sticky="nsew", padx=8)
    preview_box.columnconfigure(0, weight=1)
    preview_box.rowconfigure(0, weight=1)
    preview_text = Text(
        preview_box,
        wrap="word",
        height=12,
        width=28,
        background=app.COLORS["entry_bg"],
        foreground=app.COLORS["text"],
        insertbackground=app.COLORS["text"],
        relief="solid",
        borderwidth=1,
        font=("Microsoft YaHei UI", app._ui_metrics()["font"]),
        padx=10,
        pady=8,
    )
    preview_text.grid(row=0, column=0, sticky="nsew")
    preview_scroll = ttk.Scrollbar(preview_box, orient="vertical", command=preview_text.yview)
    preview_scroll.grid(row=0, column=1, sticky="ns")
    preview_text.configure(yscrollcommand=preview_scroll.set, state="disabled")

    builtin_names = list(app._builtin_video_presets())
    builtin_box = ttk.Frame(box)
    builtin_box.grid(row=1, column=2, sticky="nsew", padx=(8, 0))
    builtin_box.columnconfigure(0, weight=1)
    builtin_box.rowconfigure(0, weight=1)
    builtin_list = app._create_work_listbox(builtin_box, exportselection=False)
    builtin_list.grid(row=0, column=0, sticky="nsew")
    for name in builtin_names:
        builtin_list.insert(END, name)
    if builtin_names:
        builtin_list.selection_set(0)

    actions = ttk.Frame(box)
    actions.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 0))
    actions.columnconfigure((0, 1), weight=1)

    def refresh_user_preview(_event=None):
        selection = user_list.curselection()
        if selection:
            preset = app.user_video_presets[selection[0]]
            text = format_preset_preview(app, preset["settings"])
        else:
            text = "暂无用户预设。"
        preview_text.configure(state="normal")
        preview_text.delete("1.0", END)
        preview_text.insert("1.0", text)
        preview_text.configure(state="disabled")

    user_list.bind("<<ListboxSelect>>", refresh_user_preview)
    refresh_user_preview()

    def apply_user_preset():
        selection = user_list.curselection()
        if not selection:
            messagebox.showwarning("没有选择", "请先选择一个用户预设。")
            return
        preset = app.user_video_presets[selection[0]]
        app._apply_video_settings_dict(preset["settings"])
        app._log(f"已加载用户预设：{preset['name']}")
        window.destroy()

    def apply_builtin_preset():
        selection = builtin_list.curselection()
        if not selection:
            messagebox.showwarning("没有选择", "请先选择一个内置预设。")
            return
        name = builtin_names[selection[0]]
        preset = app._builtin_video_presets()[name]
        app._apply_video_settings_dict(preset)
        app._log(f"已加载内置预设：{name}")
        window.destroy()

    ttk.Button(actions, text="加载用户预设", style="Accent.TButton", command=apply_user_preset).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ttk.Button(actions, text="加载内置预设", command=apply_builtin_preset).grid(row=0, column=1, sticky="ew", padx=(6, 0))


def format_preset_preview(app, settings):
    data = dict(settings or {})

    def value(key, default="未设置"):
        text = str(data.get(key, "")).strip()
        return text if text else default

    lines = [
        f"编码器：{value('encoder_name')}",
        f"预设速度：{value('preset_name', app.preset_name.get())}",
        f"质量模式：{value('quality_mode', 'CRF / 恒定质量')}",
        f"CRF/CQ：{value('cq_value', '23')}",
        f"目标码率：{value('bitrate')}",
        f"分辨率：{value('resolution_name')}",
        f"锐化：{value('sharpen_name', '关闭')}",
        f"音频：{value('audio_mode')}",
        f"音频码率：{value('audio_bitrate')}",
        f"容器：{value('muxer_name')}",
        f"输出倍速：{value('output_speed', '1.0')}x",
    ]
    effects = []
    if data.get("use_lut") and str(data.get("lut_path", "")).strip():
        effects.append(f"LUT：{data.get('lut_path')}")
    if value("sharpen_name", "关闭") != "关闭":
        effects.append(f"锐化：{value('sharpen_name')}")
    if str(data.get("hidden_watermark_enabled", "")).lower() in {"true", "1"} or data.get("hidden_watermark_enabled") is True:
        effects.append(f"隐藏水印：{value('hidden_watermark_mode', 'text')}")
    extra = str(data.get("extra_ffmpeg_args", "")).strip()
    if extra:
        effects.append(f"高级参数：{extra}")
    custom = str(data.get("custom_command", "")).strip()
    if value("quality_mode", "") == "自定义命令" and custom:
        effects.append(f"自定义命令：{custom}")
    lines.append("")
    lines.append("影响画面/声音的设置：")
    if effects:
        lines.extend(f"- {item}" for item in effects)
    else:
        lines.append("- 无额外效果设置")
    return "\n".join(lines)


def video_settings_dict(app):
    return app._video_settings_dict_legacy()


def apply_video_settings_dict(app, data):
    return app._apply_video_settings_dict_legacy(data)


def builtin_video_presets(app):
    return app._builtin_video_presets_legacy()


def sync_custom_size_state(app):
    return app._sync_custom_size_state_legacy()


def update_audio_bitrate_state(app):
    return app._update_audio_bitrate_state_legacy()


def toggle_advanced_encoders(app):
    return app._toggle_advanced_encoders_legacy()


def save_video_preset(app):
    return app.save_video_preset_legacy()
