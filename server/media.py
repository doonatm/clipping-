import os
import re
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

def get_ffmpeg_path() -> str:
    # 1. Check imageio_ffmpeg
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass

    # 2. Check system PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    # 3. Default fallback
    return "ffmpeg"

def get_ffprobe_path() -> Optional[str]:
    system_ffprobe = shutil.which("ffprobe")
    if system_ffprobe:
        return system_ffprobe
    return None

def probe_media(path: str) -> Dict[str, Any]:
    """
    Probes video/audio metadata using ffprobe if present,
    or directly via ffmpeg -i inspection so it works everywhere.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Media file not found: {path}")

    ffprobe = get_ffprobe_path()
    if ffprobe:
        try:
            cmd = [
                ffprobe,
                "-v", "error",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                path
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            video = next((s for s in streams if s.get("codec_type") == "video"), None)
            audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
            duration_str = data.get("format", {}).get("duration")
            duration = float(duration_str) if duration_str else None
            width = int(video.get("width")) if video and video.get("width") else None
            height = int(video.get("height")) if video and video.get("height") else None

            return {
                "durationSec": duration,
                "hasVideo": video is not None,
                "width": width,
                "height": height,
                "videoCodec": video.get("codec_name") if video else None,
                "audioCodec": audio.get("codec_name") if audio else None,
            }
        except Exception:
            pass

    # Fallback to ffmpeg -i parsing
    ffmpeg = get_ffmpeg_path()
    cmd = [ffmpeg, "-i", path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stderr = proc.stderr

    # Parse Duration: 00:01:23.45
    duration = None
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", stderr)
    if dur_match:
        hours, mins, secs = dur_match.groups()
        duration = int(hours) * 3600 + int(mins) * 60 + float(secs)

    # Parse Video Stream: Video: h264 (...), 1920x1080
    has_video = "Video:" in stderr
    width, height = None, None
    video_codec = None
    if has_video:
        v_match = re.search(r"Video:\s*([a-zA-Z0-9_-]+).*?(\d{2,5})x(\d{2,5})", stderr)
        if v_match:
            video_codec = v_match.group(1)
            width = int(v_match.group(2))
            height = int(v_match.group(3))

    has_audio = "Audio:" in stderr
    audio_codec = None
    if has_audio:
        a_match = re.search(r"Audio:\s*([a-zA-Z0-9_-]+)", stderr)
        if a_match:
            audio_codec = a_match.group(1)

    return {
        "durationSec": duration,
        "hasVideo": has_video,
        "width": width,
        "height": height,
        "videoCodec": video_codec,
        "audioCodec": audio_codec,
    }

def extract_audio(source_path: str, output_wav: str) -> str:
    ffmpeg = get_ffmpeg_path()
    os.makedirs(os.path.dirname(os.path.abspath(output_wav)), exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i", source_path,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        output_wav
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {res.stderr}")
    return output_wav

def format_srt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def format_ass_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int((seconds - int(seconds)) * 100)
    return f"{hours}:{mins:02d}:{secs:02d}.{centis:02d}"

def generate_srt(words: List[Dict[str, Any]], start_sec: float, end_sec: float) -> str:
    candidate_words = [
        w for w in words
        if w.get("end", 0) > start_sec and w.get("start", 0) < end_sec
    ]
    if not candidate_words:
        return ""

    lines = []
    index = 1
    chunk_size = 3
    for i in range(0, len(candidate_words), chunk_size):
        chunk = candidate_words[i:i + chunk_size]
        first = chunk[0]
        last = chunk[-1]
        start_rel = max(0.0, first.get("start", start_sec) - start_sec)
        end_rel = max(start_rel + 0.2, min(end_sec - start_sec, last.get("end", end_sec) - start_sec))

        text = " ".join(w.get("text", "") for w in chunk).strip()
        if not text:
            continue

        lines.append(f"{index}")
        lines.append(f"{format_srt_time(start_rel)} --> {format_srt_time(end_rel)}")
        lines.append(f"{text}\n")
        index += 1

    return "\n".join(lines)

def generate_ass(words: List[Dict[str, Any]], start_sec: float, end_sec: float, caption_style: str = "tiktok-viral") -> str:
    candidate_words = [
        w for w in words
        if w.get("end", 0) > start_sec and w.get("start", 0) < end_sec
    ]
    if not candidate_words:
        return ""

    style_key = (caption_style or "tiktok-viral").lower()

    # 1080x1920 resolution canvas. Alignment=2 (bottom center).
    # MarginV=320 places text at ~16.7% from bottom (Y ~ 1560-1600), leaving top 80% clear
    # for the speaker's face and upper body!
    if any(k in style_key for k in ["tiktok", "viral", "yellow"]):
        # Bold vibrant yellow with sharp black outline
        style_def = "Style: SubStyle,Arial,58,&H0000FFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3.2,0,2,40,40,320,1"
    elif any(k in style_key for k in ["neon", "cyan"]):
        # Electric cyan punch
        style_def = "Style: SubStyle,Arial,56,&H00FFFF00,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3.0,0,2,40,40,320,1"
    elif any(k in style_key for k in ["hormozi", "impact", "white"]):
        # Crisp pure white with bold black outline
        style_def = "Style: SubStyle,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3.5,0,2,40,40,320,1"
    elif any(k in style_key for k in ["minimal", "cinema"]):
        # Minimal clean subtitles
        style_def = "Style: SubStyle,Segoe UI,48,&H00E0E0E0,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1.8,0,2,40,40,300,1"
    else:
        # Modern Box: White text with translucent dark backing pill (BorderStyle=4)
        style_def = "Style: SubStyle,Segoe UI,54,&H00FFFFFF,&H000000FF,&H00000000,&H85000000,1,0,0,0,100,100,0,0,4,1.5,0,2,40,40,320,1"

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_def}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    chunk_size = 3
    for i in range(0, len(candidate_words), chunk_size):
        chunk = candidate_words[i:i + chunk_size]
        first = chunk[0]
        last = chunk[-1]
        start_rel = max(0.0, first.get("start", start_sec) - start_sec)
        end_rel = max(start_rel + 0.25, min(end_sec - start_sec, last.get("end", end_sec) - start_sec))

        text = " ".join(w.get("text", "") for w in chunk).strip()
        if not text:
            continue
        text = text.replace("\\", "")

        events.append(f"Dialogue: 0,{format_ass_time(start_rel)},{format_ass_time(end_rel)},SubStyle,,0,0,0,,{text}")

    return header + "\n".join(events) + "\n"

_CACHED_ENCODER_CONFIG = None

def get_optimized_encoder_config() -> Dict[str, Any]:
    global _CACHED_ENCODER_CONFIG
    if _CACHED_ENCODER_CONFIG is not None:
        return _CACHED_ENCODER_CONFIG

    ffmpeg = get_ffmpeg_path()
    # Test Intel QSV hardware acceleration
    try:
        test_cmd = [
            ffmpeg, "-y", "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.1",
            "-c:v", "h264_qsv", "-f", "null", "-"
        ]
        res = subprocess.run(test_cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            _CACHED_ENCODER_CONFIG = {
                "name": "Intel Iris Xe Hardware Acceleration (QSV)",
                "codec": "h264_qsv",
                "args": ["-c:v", "h264_qsv", "-global_quality", "22", "-preset", "faster"]
            }
            return _CACHED_ENCODER_CONFIG
    except Exception:
        pass

    # High-performance multi-threaded CPU fallback
    _CACHED_ENCODER_CONFIG = {
        "name": "Multi-threaded CPU (libx264)",
        "codec": "libx264",
        "args": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-threads", "0", "-pix_fmt", "yuv420p"]
    }
    return _CACHED_ENCODER_CONFIG

def render_vertical_clip(
    source_path: str,
    start_sec: float,
    end_sec: float,
    output_path: str,
    caption_style: str = "tiktok-viral",
    words: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    ffmpeg = get_ffmpeg_path()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    duration = max(0.5, end_sec - start_sec)
    probe = probe_media(source_path)
    has_video = probe.get("hasVideo", False)
    encoder_cfg = get_optimized_encoder_config()

    srt_path = None
    ass_path = None
    if words:
        ass_content = generate_ass(words, start_sec, end_sec, caption_style)
        if ass_content:
            ass_path = str(Path(output_path).with_suffix(".ass"))
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_content)

        srt_content = generate_srt(words, start_sec, end_sec)
        if srt_content:
            srt_path = str(Path(output_path).with_suffix(".srt"))
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)

    # Base crop filter for 9:16 vertical orientation
    crop_filter = "crop=w='2*trunc(min(iw,ih*9/16)/2)':h='2*trunc(min(ih,iw*16/9)/2)',scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"

    cmd = [
        ffmpeg,
        "-y",
        "-ss", f"{start_sec:.3f}",
        "-i", source_path,
        "-t", f"{duration:.3f}",
        "-threads", "0"
    ]

    if has_video:
        burned_successfully = False
        if ass_path and caption_style != "clean":
            escaped_ass = ass_path.replace("\\", "/").replace(":", "\\:")
            sub_filter = f"{crop_filter},ass='{escaped_ass}'"
            sub_cmd = cmd + ["-vf", sub_filter] + encoder_cfg["args"] + ["-c:a", "aac", "-b:a", "192k", output_path]
            res = subprocess.run(sub_cmd, capture_output=True, text=True)
            if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                burned_successfully = True

        if not burned_successfully:
            clean_cmd = cmd + ["-vf", crop_filter] + encoder_cfg["args"] + ["-c:a", "aac", "-b:a", "192k", output_path]
            res = subprocess.run(clean_cmd, capture_output=True, text=True)
            if res.returncode != 0:
                # Fallback to software libx264 if hardware encoder hit format issue
                cpu_cmd = cmd + [
                    "-vf", crop_filter,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-threads", "0", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", output_path
                ]
                res_cpu = subprocess.run(cpu_cmd, capture_output=True, text=True)
                if res_cpu.returncode != 0:
                    raise RuntimeError(f"FFmpeg render failed: {res_cpu.stderr}")
    else:
        cmd.extend(["-vn", "-c:a", "aac", "-b:a", "192k", output_path])
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg render failed: {res.stderr}")

    return {
        "outputPath": output_path,
        "srtPath": srt_path,
        "assPath": ass_path
    }
