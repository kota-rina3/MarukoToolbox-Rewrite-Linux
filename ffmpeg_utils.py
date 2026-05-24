import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from config import AUDIO_ENCODERS, AUDIO_MODES, ENCODER_FILENAME_TAGS, ENCODERS, PRESETS, RESOLUTIONS, RETRO_FORMATS, RETRO_RESOLUTIONS, SHARPEN_LEVELS, VIDEO_MUXERS
from data import AudioSettings, CompressionSettings, EnvironmentInfo, RetroSettings


def detect_environment() -> EnvironmentInfo:
    ffmpeg = shutil.which("ffmpeg") or ""
    ffprobe = shutil.which("ffprobe") or ""
    encoders = run_capture([ffmpeg, "-hide_banner", "-encoders"]) if ffmpeg else ""
    encoder_text = encoders.lower()
    return EnvironmentInfo(
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        has_nvenc="nvenc" in encoder_text,
        has_amf="_amf" in encoder_text,
    )


def build_compress_command(source: Path, target: Path, settings: CompressionSettings, encoder_override=None, benchmark=False):
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    if settings.quality_mode == "自定义命令" and settings.custom_command.strip():
        command = settings.custom_command.replace("{input}", str(source)).replace("{output}", str(target))
        return [ffmpeg] + shlex.split(command, posix=True)
    encoder_key = encoder_override or ENCODERS[settings.encoder_key]
    encoder, pix_fmt = resolve_encoder(encoder_key)
    is_nvenc = "nvenc" in encoder
    is_amf = encoder.endswith("_amf")
    preset_gpu, preset_cpu = PRESETS[settings.preset_name]
    cq = str(settings.cq_value)
    bitrate = settings.bitrate.strip()
    use_cpu_filters = has_lut(settings) or has_sharpen(settings)

    cmd = [ffmpeg, "-hide_banner", "-y" if settings.overwrite or benchmark else "-n"]
    if is_nvenc and not use_cpu_filters:
        cmd += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
    elif is_nvenc:
        cmd += ["-hwaccel", "cuda"]
    cmd += ["-i", str(source)]

    filters = video_filters(settings, is_nvenc and not use_cpu_filters)
    if filters:
        cmd += ["-vf", ",".join(filters)]

    cmd += ["-c:v", encoder]
    if is_nvenc:
        cmd += ["-preset", preset_gpu, "-rc", "vbr", "-cq", cq, "-b:v", bitrate or "0"]
        cmd += ["-spatial-aq", "1", "-temporal-aq", "1", "-rc-lookahead", "32", "-bf", "3", "-surfaces", "64"]
    elif is_amf:
        amf_quality = {"p1": "speed", "p3": "speed", "p5": "balanced", "p7": "quality"}.get(preset_gpu, "balanced")
        cmd += ["-quality", amf_quality]
        if bitrate:
            cmd += ["-rc", "vbr", "-b:v", bitrate]
        else:
            cmd += ["-rc", "cqp", "-qp_i", cq, "-qp_p", cq, "-qp_b", cq]
    else:
        if encoder == "libsvtav1":
            cmd += ["-preset", "6", "-crf", cq]
        elif encoder == "libvpx-vp9":
            cmd += ["-crf", cq, "-b:v", bitrate or "0", "-row-mt", "1"]
        elif encoder == "prores_ks":
            cmd += ["-profile:v", "3"]
        else:
            cmd += ["-preset", preset_cpu, "-crf", cq]
        if bitrate:
            cmd += ["-b:v", bitrate]

    if pix_fmt:
        cmd += ["-pix_fmt", pix_fmt]
    cmd += audio_args(settings)
    if settings.extra_ffmpeg_args.strip():
        cmd += settings.extra_ffmpeg_args.strip().split()
    cmd += ["-map_metadata", "0", str(target)]
    return cmd


def build_thumbnail_command(video_path: Path, thumb_path: Path, thumbnail_time: float):
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    return [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-ss",
        str(thumbnail_time),
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(thumb_path),
    ]


def build_proxy_command(source: Path, target: Path, width=1280, bitrate="1200k"):
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    return [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-i",
        str(source),
        "-vf",
        f"scale={width}:-2",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "28",
        "-b:v",
        bitrate,
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-movflags",
        "+faststart",
        str(target),
    ]


def build_audio_command(source: Path, target: Path, settings: AudioSettings):
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    encoder, _ = AUDIO_ENCODERS[settings.encoder_name]
    cmd = [ffmpeg, "-hide_banner", "-y" if settings.overwrite else "-n", "-i", str(source), "-vn"]
    filters = []
    if settings.normalize:
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    if filters:
        cmd += ["-af", ",".join(filters)]
    cmd += ["-c:a", encoder]
    if settings.bitrate.strip() and encoder not in {"flac", "pcm_s16le"}:
        cmd += ["-b:a", settings.bitrate.strip()]
    if settings.sample_rate.strip():
        cmd += ["-ar", settings.sample_rate.strip()]
    if settings.channels.strip():
        cmd += ["-ac", settings.channels.strip()]
    cmd += [str(target)]
    return cmd


def build_retro_command(source: Path, target: Path, settings: RetroSettings):
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    preset = RETRO_FORMATS[settings.format_name]
    cmd = [ffmpeg, "-hide_banner", "-y" if settings.overwrite else "-n", "-i", str(source)]
    filters = retro_filters(settings)
    if filters and "-vn" not in preset["video"]:
        cmd += ["-vf", ",".join(filters)]
    cmd += preset["video"] + preset["audio"]
    if settings.bitrate.strip() and "-b:v" not in preset["video"] and "-vn" not in preset["video"]:
        cmd += ["-b:v", settings.bitrate.strip()]
    if settings.audio_bitrate.strip() and "-b:a" not in preset["audio"]:
        cmd += ["-b:a", settings.audio_bitrate.strip()]
    cmd += [str(target)]
    return cmd


def build_remux_command(source: Path, target: Path, audio_mode="copy", overwrite=False):
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-y" if overwrite else "-n",
        "-i",
        str(source),
        "-map",
        "0",
        "-c:v",
        "copy",
    ]
    if audio_mode == "aac":
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-c:a", "copy"]
    cmd += ["-map_metadata", "0", str(target)]
    return cmd


def build_preview_command(source: Path, preview_path: Path, settings: CompressionSettings):
    return build_frame_command(source, preview_path, settings.thumbnail_time, settings, width=520)


def build_frame_command(source: Path, frame_path: Path, seconds: float, settings: CompressionSettings, width=960):
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    return [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-ss",
        str(max(0, seconds)),
        "-i",
        str(source),
        "-vf",
        ",".join(preview_filters(settings, width=width)),
        "-frames:v",
        "1",
        str(frame_path),
    ]


def build_screenshot_command(source: Path, target: Path, seconds: float, settings: CompressionSettings):
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    filters = video_filters(settings, use_gpu_filters=False)
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-ss",
        str(max(0, seconds)),
        "-i",
        str(source),
    ]
    if filters:
        cmd += ["-vf", ",".join(filters)]
    cmd += ["-frames:v", "1", "-q:v", "2", str(target)]
    return cmd


def build_lut_thumbnail_command(source: Path, target: Path, seconds: float, lut_path: Path, width=360):
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    escaped = filter_path(str(lut_path))
    return [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-ss",
        str(max(0, seconds)),
        "-i",
        str(source),
        "-vf",
        f"lut3d=file='{escaped}',scale={width}:-2",
        "-frames:v",
        "1",
        str(target),
    ]


def run_capture(cmd):
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return result.stdout or ""
    except Exception as exc:
        return str(exc)


def duration_seconds(source: Path):
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0
    output = run_capture([
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(source),
    ])
    try:
        return float(json.loads(output)["format"]["duration"])
    except Exception:
        return 0


def probe_media_info(source: Path):
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {}
    output = run_capture([
        ffprobe,
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(source),
    ])
    try:
        return json.loads(output)
    except Exception:
        return {}


def parse_time(line: str):
    marker = "time="
    if marker not in line:
        return 0
    value = line.split(marker, 1)[1].split(" ", 1)[0]
    try:
        hours, minutes, seconds = value.split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except Exception:
        return 0


def unique_output_path(output_dir: Path, source: Path, overwrite: bool):
    suffix = output_suffix(source, None)
    return unique_path(output_dir, source, suffix, overwrite)


def unique_video_output_path(output_dir: Path, source: Path, settings: CompressionSettings, overwrite: bool):
    suffix = output_suffix(source, settings.muxer_name)
    encoder_key = ENCODERS[settings.encoder_key]
    tag = ENCODER_FILENAME_TAGS.get(encoder_key, "compressed")
    return unique_path(output_dir, source, suffix, overwrite, tag=tag)


def unique_audio_output_path(output_dir: Path, source: Path, settings: AudioSettings):
    _, suffix = AUDIO_ENCODERS[settings.encoder_name]
    return unique_path(output_dir, source, suffix, settings.overwrite)


def unique_retro_output_path(output_dir: Path, source: Path, settings: RetroSettings):
    preset = RETRO_FORMATS[settings.format_name]
    return unique_path(output_dir, source, preset["suffix"], settings.overwrite, tag=preset["tag"])


def unique_proxy_output_path(output_dir: Path, source: Path):
    return unique_path(output_dir, source, ".mp4", False, tag="proxy")


def unique_path(output_dir: Path, source: Path, suffix: str, overwrite: bool, tag="compressed"):
    stem = f"{source.stem}_{tag}"
    target = output_dir / f"{stem}{suffix}"
    if overwrite or not target.exists():
        return target
    counter = 2
    while True:
        target = output_dir / f"{stem}_{counter}{suffix}"
        if not target.exists():
            return target
        counter += 1


def output_suffix(source: Path, muxer_name):
    if muxer_name and VIDEO_MUXERS[muxer_name] != "source":
        return VIDEO_MUXERS[muxer_name]
    return source.suffix or ".mp4"


def audio_args(settings: CompressionSettings):
    mode = AUDIO_MODES[settings.audio_mode]
    if mode == "copy":
        return ["-c:a", "copy"]
    if mode == "none":
        return ["-an"]
    args = ["-c:a", mode]
    if settings.audio_bitrate.strip() and mode != "flac":
        args += ["-b:a", settings.audio_bitrate.strip()]
    return args


def resolve_encoder(encoder_key: str):
    if encoder_key == "hevc_nvenc_10bit":
        return "hevc_nvenc", "p010le"
    if encoder_key == "av1_nvenc_10bit":
        return "av1_nvenc", "p010le"
    if encoder_key == "libx265_10bit":
        return "libx265", "yuv420p10le"
    return encoder_key, ""


def video_filters(settings: CompressionSettings, use_gpu_filters: bool):
    filters = []
    mode = RESOLUTIONS[settings.resolution_name]
    if mode:
        if mode == "custom":
            width = settings.custom_width if settings.custom_width > 0 else -2
            height = settings.custom_height if settings.custom_height > 0 else -2
            scale = f"{width}:{height}"
        else:
            scale = mode
        filters.append(f"scale_cuda={scale}" if use_gpu_filters else f"scale={scale}")
    if has_lut(settings):
        filters.append(f"lut3d=file='{filter_path(settings.lut_path)}'")
    if has_sharpen(settings):
        filters.append(SHARPEN_LEVELS[settings.sharpen_name])
    return filters


def retro_filters(settings: RetroSettings):
    filters = []
    if settings.deinterlace:
        filters.append("yadif")
    if settings.denoise:
        filters.append("hqdn3d=1.5:1.5:6:6")
    resolution = RETRO_RESOLUTIONS[settings.resolution_name]
    if resolution:
        filters.append(f"scale={resolution}:flags=lanczos")
    return filters


def preview_filters(settings: CompressionSettings, width=520):
    filters = []
    if has_lut(settings):
        filters.append(f"lut3d=file='{filter_path(settings.lut_path)}'")
    if has_sharpen(settings):
        filters.append(SHARPEN_LEVELS[settings.sharpen_name])
    filters.append(f"scale={width}:-2")
    return filters


def has_lut(settings: CompressionSettings):
    return settings.use_lut and bool(settings.lut_path.strip())


def has_sharpen(settings: CompressionSettings):
    return bool(SHARPEN_LEVELS.get(settings.sharpen_name))


def filter_path(path: str):
    return path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
