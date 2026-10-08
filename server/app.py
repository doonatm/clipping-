import os
import re
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db
from . import media
from . import ai_services

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
PROJECTS_DIR = DATA_DIR / "projects"
STATIC_DIR = Path(__file__).resolve().parent / "static"

for d in [DATA_DIR, UPLOADS_DIR, PROJECTS_DIR, STATIC_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Initialize database
db.init_db()

app = FastAPI(title="AutoShorts Web Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SettingsPayload(BaseModel):
    deepgramApiKey: Optional[str] = None
    deepseekApiKey: Optional[str] = None
    anthropicApiKey: Optional[str] = None
    geminiApiKey: Optional[str] = None
    openaiApiKey: Optional[str] = None
    groqApiKey: Optional[str] = None
    openrouterApiKey: Optional[str] = None
    llmProvider: Optional[str] = "deepseek"

class TranscribePayload(BaseModel):
    provider: Optional[str] = "deepgram"
    apiKey: Optional[str] = None

class GenerateCandidatesPayload(BaseModel):
    provider: Optional[str] = None
    apiKey: Optional[str] = None
    modelName: Optional[str] = None
    clipCount: Optional[int] = 3
    minDuration: Optional[float] = 20.0
    maxDuration: Optional[float] = 60.0

class YouTubePayload(BaseModel):
    url: str
    captionStyle: Optional[str] = "modern-box"
    transcriptionMode: Optional[str] = "cloud"

class RenamePayload(BaseModel):
    name: str

class SelectCountPayload(BaseModel):
    count: int

def stream_file_range(file_path: Path, range_header: Optional[str]):
    file_size = file_path.stat().st_size
    content_type = "video/mp4"
    if file_path.suffix.lower() in [".wav", ".mp3", ".m4a"]:
        content_type = f"audio/{file_path.suffix.lower().strip('.')}"

    if not range_header:
        def full_iter():
            with open(file_path, "rb") as f:
                while chunk := f.read(64 * 1024):
                    yield chunk
        return StreamingResponse(
            full_iter(),
            media_type=content_type,
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes"
            }
        )

    # Range: bytes=start-end
    match = re.search(r"bytes=(\d+)-(\d*)", range_header)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid Range header")

    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else file_size - 1
    end = min(end, file_size - 1)
    chunk_size = (end - start) + 1

    def range_iter():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = chunk_size
            while remaining > 0:
                read_len = min(remaining, 64 * 1024)
                data = f.read(read_len)
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        range_iter(),
        status_code=206,
        media_type=content_type,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
        }
    )

@app.get("/api/environment")
def get_environment():
    settings = db.get_all_settings()
    ffmpeg_exe = media.get_ffmpeg_path()
    has_ffmpeg = bool(ffmpeg_exe and os.path.exists(ffmpeg_exe))
    has_ytdlp = False
    try:
        import yt_dlp
        has_ytdlp = True
    except ImportError:
        has_ytdlp = bool(shutil.which("yt-dlp"))

    return {
        "hasFfmpeg": has_ffmpeg,
        "ffmpegPath": ffmpeg_exe,
        "hasYtdlp": has_ytdlp,
        "hasDeepgramKey": bool(settings.get("DEEPGRAM_API_KEY")),
        "hasDeepseekKey": bool(settings.get("DEEPSEEK_API_KEY")),
        "hasAnthropicKey": bool(settings.get("ANTHROPIC_API_KEY")),
        "hasGeminiKey": bool(settings.get("GEMINI_API_KEY")),
        "hasOpenaiKey": bool(settings.get("OPENAI_API_KEY")),
        "hasGroqKey": bool(settings.get("GROQ_API_KEY")),
        "hasOpenrouterKey": bool(settings.get("OPENROUTER_API_KEY")),
        "llmProvider": settings.get("LLM_PROVIDER", "deepseek"),
    }

@app.get("/api/settings")
def get_settings():
    settings = db.get_all_settings()
    # Mask keys for security
    def mask(val):
        if not val:
            return ""
        if len(val) <= 8:
            return "••••••••"
        return val[:3] + "••••••••" + val[-4:]

    return {
        "deepgramApiKey": mask(settings.get("DEEPGRAM_API_KEY")),
        "deepseekApiKey": mask(settings.get("DEEPSEEK_API_KEY")),
        "anthropicApiKey": mask(settings.get("ANTHROPIC_API_KEY")),
        "geminiApiKey": mask(settings.get("GEMINI_API_KEY")),
        "openaiApiKey": mask(settings.get("OPENAI_API_KEY")),
        "groqApiKey": mask(settings.get("GROQ_API_KEY")),
        "openrouterApiKey": mask(settings.get("OPENROUTER_API_KEY")),
        "llmProvider": settings.get("LLM_PROVIDER", "deepseek"),
    }

@app.post("/api/settings")
def save_settings(payload: SettingsPayload):
    mapping = {
        "DEEPGRAM_API_KEY": payload.deepgramApiKey,
        "DEEPSEEK_API_KEY": payload.deepseekApiKey,
        "ANTHROPIC_API_KEY": payload.anthropicApiKey,
        "GEMINI_API_KEY": payload.geminiApiKey,
        "OPENAI_API_KEY": payload.openaiApiKey,
        "GROQ_API_KEY": payload.groqApiKey,
        "OPENROUTER_API_KEY": payload.openrouterApiKey,
        "LLM_PROVIDER": payload.llmProvider,
    }
    for k, v in mapping.items():
        if v and not v.startswith("•••"):
            db.set_setting(k, v)
            os.environ[k] = v
        elif k == "LLM_PROVIDER" and v:
            db.set_setting(k, v)
            os.environ[k] = v
    return {"status": "ok", "message": "Settings saved successfully"}

@app.get("/api/projects")
def list_projects():
    return db.list_projects()

@app.post("/api/projects/upload")
async def upload_project(
    file: UploadFile = File(...),
    captionStyle: str = Form("modern-box"),
    transcriptionMode: str = Form("cloud")
):
    clean_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", file.filename)
    dest_path = UPLOADS_DIR / clean_filename
    base = dest_path.stem
    ext = dest_path.suffix
    idx = 1
    while dest_path.exists():
        dest_path = UPLOADS_DIR / f"{base}_{idx}{ext}"
        idx += 1

    with open(dest_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)

    # Probe media
    duration = None
    try:
        probe = media.probe_media(str(dest_path))
        duration = probe.get("durationSec")
    except Exception as e:
        print("Probe warning:", e)

    project = db.create_project(
        source_path=str(dest_path),
        transcription_mode=transcriptionMode,
        caption_style=captionStyle,
        name=Path(clean_filename).stem,
        source_duration=duration
    )
    return project

@app.post("/api/projects/youtube")
def youtube_project(payload: YouTubePayload):
    try:
        import yt_dlp
    except ImportError:
        raise HTTPException(status_code=400, detail="yt-dlp Python package is not installed.")

    ffmpeg_exe = media.get_ffmpeg_path()
    out_template = str(UPLOADS_DIR / "%(title).50s-%(id)s.%(ext)s")

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
    }
    if ffmpeg_exe and os.path.exists(ffmpeg_exe):
        ydl_opts["ffmpeg_location"] = ffmpeg_exe

    node_path = shutil.which("node") or ("C:\\node.exe" if os.path.exists("C:\\node.exe") else None)
    if node_path:
        ydl_opts["js_runtimes"] = {"node": {"path": node_path}}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(payload.url, download=True)
            filepath = ydl.prepare_filename(info)

            # Check if file exists or if it was merged to .mp4
            if not os.path.exists(filepath):
                mp4_path = str(Path(filepath).with_suffix(".mp4"))
                if os.path.exists(mp4_path):
                    filepath = mp4_path
                else:
                    video_id = info.get("id", "")
                    matching = list(UPLOADS_DIR.glob(f"*{video_id}*"))
                    if matching:
                        filepath = str(matching[0])
                    else:
                        raise HTTPException(status_code=500, detail="Downloaded YouTube file could not be located.")

            duration = info.get("duration")
            title = info.get("title") or Path(filepath).stem

    except yt_dlp.utils.DownloadError as e:
        err_msg = str(e)
        if "This video is unavailable" in err_msg:
            raise HTTPException(
                status_code=400,
                detail="This YouTube video is unavailable or private. Please verify the URL and ensure the video is publicly accessible."
            )
        elif "Sign in to confirm" in err_msg or "bot" in err_msg.lower():
            raise HTTPException(
                status_code=400,
                detail="YouTube requested a bot/sign-in verification for this link. Please try another video or upload the file directly."
            )
        else:
            clean_msg = err_msg.replace("ERROR: ", "").split(";")[0].strip()
            raise HTTPException(status_code=400, detail=f"YouTube download failed: {clean_msg}")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"YouTube import error: {str(e)}")

    # Probe duration if missing
    if not duration:
        try:
            probe = media.probe_media(filepath)
            duration = probe.get("durationSec")
        except Exception:
            pass

    project = db.create_project(
        source_path=filepath,
        transcription_mode=payload.transcriptionMode or "cloud",
        caption_style=payload.captionStyle or "modern-box",
        name=title,
        source_duration=duration
    )
    return project

@app.post("/api/projects/demo")
def create_demo_project():
    # 1. Generate or locate a demo video file
    demo_video_path = UPLOADS_DIR / "autoshorts_sample.mp4"
    if not demo_video_path.exists() or demo_video_path.stat().st_size == 0:
        ffmpeg = media.get_ffmpeg_path()
        # Generate a high quality 60s sample 1080p landscape video with audio tone
        cmd = [
            ffmpeg,
            "-y",
            "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
            "-t", "45",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            str(demo_video_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not demo_video_path.exists():
            raise HTTPException(status_code=500, detail="Failed to synthesize sample video")

    # 2. Create project
    project = db.create_project(
        source_path=str(demo_video_path),
        transcription_mode="demo",
        caption_style="modern-box",
        name="AutoShorts Viral Masterclass (Sample)",
        source_duration=45.0
    )

    # 3. Create demo transcript
    transcript_data = ai_services.get_demo_transcript(duration=45.0)
    db.save_transcript(
        project_id=project["id"],
        engine="demo",
        raw_json=json.dumps(transcript_data, indent=2),
        language="en"
    )

    # 4. Generate candidates via heuristic
    candidates = ai_services.detect_candidates_heuristic(transcript_data)
    db.replace_candidates(project["id"], candidates)
    db.update_project_status(project["id"], "ready", duration=45.0)

    return db.get_project_detail(project["id"])

@app.get("/api/projects/{project_id}")
def get_project_detail(project_id: str):
    detail = db.get_project_detail(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Project not found")
    return detail

@app.patch("/api/projects/{project_id}")
def rename_project(project_id: str, payload: RenamePayload):
    db.rename_project(project_id, payload.name.strip())
    return {"status": "ok"}

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    p = db.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    # Remove project directory if exists
    p_dir = PROJECTS_DIR / project_id
    if p_dir.exists():
        shutil.rmtree(p_dir, ignore_errors=True)

    db.delete_project(project_id)
    return {"status": "ok"}

@app.post("/api/projects/{project_id}/transcribe")
def transcribe_project(project_id: str, payload: TranscribePayload):
    p = db.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    db.update_project_status(project_id, "transcribing")

    provider = (payload.provider or "local").lower()
    settings = db.get_all_settings()

    p_dir = PROJECTS_DIR / project_id
    p_dir.mkdir(parents=True, exist_ok=True)
    audio_path = str(p_dir / "audio.wav")

    try:
        # Extract 16kHz audio
        media.extract_audio(p["source_path"], audio_path)

        if provider in ["local", "offline", "whisper-local"]:
            transcript = ai_services.transcribe_local_whisper(audio_path)
        elif provider == "demo":
            # If user uploaded or imported a real video, transcribe with real local Whisper!
            if p.get("source_path") and os.path.exists(p["source_path"]):
                transcript = ai_services.transcribe_local_whisper(audio_path)
            else:
                transcript = ai_services.get_demo_transcript(p.get("source_duration") or 60.0)
        elif provider == "deepgram":
            key = payload.apiKey or settings.get("DEEPGRAM_API_KEY")
            if not key:
                transcript = ai_services.transcribe_local_whisper(audio_path)
            else:
                transcript = ai_services.transcribe_deepgram(audio_path, key)
        elif provider in ["openai", "whisper"]:
            key = payload.apiKey or settings.get("OPENAI_API_KEY")
            if not key:
                transcript = ai_services.transcribe_local_whisper(audio_path)
            else:
                transcript = ai_services.transcribe_openai_whisper(audio_path, key)
        elif provider == "groq":
            key = payload.apiKey or settings.get("GROQ_API_KEY")
            if not key:
                transcript = ai_services.transcribe_local_whisper(audio_path)
            else:
                transcript = ai_services.transcribe_openai_whisper(audio_path, key, base_url="https://api.groq.com/openai/v1")
        else:
            transcript = ai_services.transcribe_local_whisper(audio_path)

        raw_json = json.dumps(transcript, indent=2)
        saved = db.save_transcript(project_id, provider, raw_json, transcript.get("language", "en"))
        # Preserve real source_duration from video probe
        effective_duration = p.get("source_duration") or transcript.get("duration")
        db.update_project_status(project_id, "analyzing", duration=effective_duration)
        return saved
    except Exception as e:
        db.update_project_status(project_id, "error")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/{project_id}/generate-candidates")
def generate_candidates(project_id: str, payload: GenerateCandidatesPayload):
    p = db.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    transcript_row = db.get_latest_transcript(project_id)
    if not transcript_row:
        raise HTTPException(status_code=400, detail="Please transcribe the video before detecting viral moments.")

    transcript_data = json.loads(transcript_row["rawJson"])
    settings = db.get_all_settings()

    provider = (payload.provider or settings.get("LLM_PROVIDER") or "deepseek").lower()
    api_key = payload.apiKey

    clip_cnt = payload.clipCount or 3
    min_dur = payload.minDuration or 20.0
    max_dur = payload.maxDuration or 60.0
    source_dur = p.get("source_duration")
    source_path = p.get("source_path")

    try:
        if provider == "deepseek":
            key = api_key or settings.get("DEEPSEEK_API_KEY")
            if not key:
                candidates = ai_services.detect_candidates_heuristic(transcript_data, clip_count=clip_cnt, min_duration=min_dur, max_duration=max_dur, source_duration=source_dur, source_path=source_path)
            else:
                candidates = ai_services.detect_candidates_with_deepseek(transcript_data, key, payload.modelName)
        elif provider == "gemini":
            key = api_key or settings.get("GEMINI_API_KEY")
            if not key:
                candidates = ai_services.detect_candidates_heuristic(transcript_data, clip_count=clip_cnt, min_duration=min_dur, max_duration=max_dur, source_duration=source_dur, source_path=source_path)
            else:
                candidates = ai_services.detect_candidates_with_gemini(transcript_data, key, payload.modelName)
        elif provider == "openai":
            key = api_key or settings.get("OPENAI_API_KEY")
            if not key:
                candidates = ai_services.detect_candidates_heuristic(transcript_data, clip_count=clip_cnt, min_duration=min_dur, max_duration=max_dur, source_duration=source_dur, source_path=source_path)
            else:
                candidates = ai_services.detect_candidates_with_openai(transcript_data, key, payload.modelName)
        elif provider == "claude":
            key = api_key or settings.get("ANTHROPIC_API_KEY")
            if not key:
                candidates = ai_services.detect_candidates_heuristic(transcript_data, clip_count=clip_cnt, min_duration=min_dur, max_duration=max_dur, source_duration=source_dur, source_path=source_path)
            else:
                candidates = ai_services.detect_candidates_with_claude(transcript_data, key, payload.modelName)
        elif provider == "groq":
            key = api_key or settings.get("GROQ_API_KEY")
            if not key:
                candidates = ai_services.detect_candidates_heuristic(transcript_data, clip_count=clip_cnt, min_duration=min_dur, max_duration=max_dur, source_duration=source_dur, source_path=source_path)
            else:
                candidates = ai_services.detect_candidates_with_groq(transcript_data, key, payload.modelName)
        else:
            candidates = ai_services.detect_candidates_heuristic(transcript_data, clip_count=clip_cnt, min_duration=min_dur, max_duration=max_dur, source_duration=source_dur, source_path=source_path)

        if not candidates:
            candidates = ai_services.detect_candidates_heuristic(transcript_data, clip_count=clip_cnt, min_duration=min_dur, max_duration=max_dur, source_duration=source_dur, source_path=source_path)

        saved_candidates = db.replace_candidates(project_id, candidates)
        db.update_project_status(project_id, "ready")
        return saved_candidates
    except Exception as e:
        print("Candidate detection fallback triggered due to error:", e)
        candidates = ai_services.detect_candidates_heuristic(transcript_data, clip_count=clip_cnt, min_duration=min_dur, max_duration=max_dur, source_duration=source_dur, source_path=source_path)
        saved = db.replace_candidates(project_id, candidates)
        db.update_project_status(project_id, "ready")
        return saved

@app.post("/api/projects/{project_id}/select-count")
def set_selected_count(project_id: str, payload: SelectCountPayload):
    db.set_selected_clip_count(project_id, payload.count)
    return db.get_candidates(project_id)

@app.post("/api/candidates/{candidate_id}/render")
def render_candidate_clip(candidate_id: str, caption_style: Optional[str] = Query(None)):
    candidate = db.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    project = db.get_project(candidate["projectId"])
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.update_clip_for_candidate(candidate_id, "rendering")

    p_dir = PROJECTS_DIR / project["id"] / "clips"
    p_dir.mkdir(parents=True, exist_ok=True)
    out_file = str(p_dir / f"clip_{candidate['rank']:02d}_vertical.mp4")

    start_sec = candidate["startSec"]
    end_sec = candidate["endSec"]

    words = []
    transcript_row = db.get_latest_transcript(project["id"])
    if transcript_row:
        t_data = json.loads(transcript_row["rawJson"])
        words = t_data.get("words", [])

    # Check if candidate time range has accurate word timestamps
    range_words = [
        w for w in words
        if w.get("end", 0) > start_sec and w.get("start", 0) < end_sec
    ]

    # If missing or incomplete words, transcribe this exact slice on demand with local Whisper (~3-5s)
    if not range_words and project.get("source_path") and os.path.exists(project["source_path"]):
        slice_words = ai_services.transcribe_local_whisper_slice(project["source_path"], start_sec, end_sec)
        if slice_words:
            words.extend(slice_words)
            if transcript_row:
                t_data["words"] = words
                db.save_transcript(project["id"], transcript_row.get("engine", "local"), json.dumps(t_data), transcript_row.get("language", "en"))

    final_caption_style = caption_style or project.get("caption_style") or "tiktok-viral"

    try:
        res = media.render_vertical_clip(
            source_path=project["source_path"],
            start_sec=start_sec,
            end_sec=end_sec,
            output_path=out_file,
            caption_style=final_caption_style,
            words=words
        )
        db.update_clip_for_candidate(
            candidate_id=candidate_id,
            status="done",
            output_path=res["outputPath"],
            srt_path=res.get("srtPath")
        )
        return {
            "status": "done",
            "candidateId": candidate_id,
            "outputPath": res["outputPath"],
            "srtPath": res.get("srtPath"),
            "assPath": res.get("assPath")
        }
    except Exception as e:
        db.update_clip_for_candidate(
            candidate_id=candidate_id,
            status="error",
            render_log=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Rendering clip failed: {e}")

# Media Streaming & Downloads
@app.get("/api/media/stream/{project_id}")
def stream_source_media(project_id: str, request: Request):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    path = Path(project["source_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Source media file missing")

    range_header = request.headers.get("range")
    return stream_file_range(path, range_header)

@app.get("/api/media/clips/{candidate_id}/stream")
def stream_clip_media(candidate_id: str, request: Request):
    clip = db.get_clip_for_candidate(candidate_id)
    if not clip or not clip.get("outputPath") or not Path(clip["outputPath"]).exists():
        raise HTTPException(status_code=404, detail="Rendered clip not found")

    path = Path(clip["outputPath"])
    range_header = request.headers.get("range")
    return stream_file_range(path, range_header)

@app.get("/api/media/clips/{candidate_id}/download")
def download_clip(candidate_id: str):
    candidate = db.get_candidate(candidate_id)
    clip = db.get_clip_for_candidate(candidate_id)
    if not clip or not clip.get("outputPath") or not Path(clip["outputPath"]).exists():
        raise HTTPException(status_code=404, detail="Clip not available for download")

    rank = candidate.get("rank", 1) if candidate else 1
    return FileResponse(
        path=clip["outputPath"],
        filename=f"autoshorts_clip_{rank:02d}.mp4",
        media_type="video/mp4"
    )

@app.get("/api/media/clips/{candidate_id}/subtitles")
def download_subtitles(candidate_id: str):
    candidate = db.get_candidate(candidate_id)
    clip = db.get_clip_for_candidate(candidate_id)
    if not clip or not clip.get("captionAssPath") or not Path(clip["captionAssPath"]).exists():
        raise HTTPException(status_code=404, detail="Subtitles not available")

    rank = candidate.get("rank", 1) if candidate else 1
    return FileResponse(
        path=clip["captionAssPath"],
        filename=f"autoshorts_clip_{rank:02d}.srt",
        media_type="text/plain"
    )

# Mount Static UI
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
