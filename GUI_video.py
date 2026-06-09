from tkinter import ttk


def build_video_tab(app, parent):
    panel = app._scrollable_frame(parent)
    panel.columnconfigure(0, weight=3)
    panel.columnconfigure(1, weight=2)
    panel.rowconfigure(0, weight=1)
    app._build_video_file_panel(panel)
    app._build_settings_panel(panel)


def build_video_file_panel(app, parent):
    panel = ttk.LabelFrame(parent, text="任务列表", padding=12)
    panel.grid(row=0, column=0, sticky="new", padx=(0, 10))
    panel.rowconfigure(2, weight=0)
    panel.columnconfigure(0, weight=1)

    toolbar = ttk.Frame(panel)
    toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    app.video_add_button = ttk.Button(toolbar, text="＋ 添加视频", command=app.add_files)
    app.video_add_button.pack(side="left")
    ttk.Button(toolbar, text="▤ 添加文件夹", command=app.add_folder).pack(side="left", padx=6)
    ttk.Button(toolbar, text="▶ 预览", command=app.open_player_preview).pack(side="left")
    ttk.Button(toolbar, text="− 移除", command=app.remove_selected).pack(side="left", padx=(6, 0))
    ttk.Button(toolbar, text="清空", command=app.clear_files).pack(side="left", padx=6)

    output = ttk.Frame(panel)
    output.grid(row=1, column=0, sticky="ew", pady=(0, 10))
    output.columnconfigure(1, weight=1)
    app.video_output_dir_button = ttk.Button(output, text="输出目录", style="OutputDir.TButton", command=lambda: app.open_output_dir(app.output_dir))
    app.video_output_dir_button.grid(row=0, column=0, sticky="w")
    ttk.Entry(output, textvariable=app.output_dir).grid(row=0, column=1, sticky="ew", padx=8)
    app.video_output_browse_button = ttk.Button(output, text="浏览…", command=app.choose_output_dir)
    app.video_output_browse_button.grid(row=0, column=2)

    list_frame = ttk.Frame(panel)
    list_frame.grid(row=2, column=0, sticky="ew")
    list_frame.rowconfigure(0, weight=0)
    list_frame.columnconfigure(0, weight=1)
    app.file_list = app._create_work_listbox(list_frame, selectmode="extended", height=video_task_list_height(app))
    app.file_list.grid(row=0, column=0, sticky="ew")
    scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=app.file_list.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    app.file_list.configure(yscrollcommand=scrollbar.set)


def video_task_list_height(app):
    try:
        screen_height = app.root.winfo_screenheight()
    except Exception:
        screen_height = 1080
    if screen_height <= 1200:
        return 7
    if screen_height <= 1800:
        return 9
    return 11
