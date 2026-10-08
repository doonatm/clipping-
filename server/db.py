import os
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "autoshorts.db"

def get_connection() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT,
            source_path TEXT NOT NULL,
            source_duration REAL,
            status TEXT NOT NULL,
            transcription_mode TEXT NOT NULL,
            caption_style TEXT DEFAULT 'modern-box',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS transcripts (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            engine TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            language TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS candidates (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            start_sec REAL NOT NULL,
            end_sec REAL NOT NULL,
            score REAL NOT NULL,
            hook TEXT NOT NULL,
            rationale TEXT NOT NULL,
            rank INTEGER NOT NULL,
            selected INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS clips (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            status TEXT NOT NULL,
            output_path TEXT,
            face_track_json TEXT,
            caption_ass_path TEXT,
            render_log TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)

def create_project(source_path: str, transcription_mode: str = "demo", caption_style: str = "modern-box", name: Optional[str] = None, source_duration: Optional[float] = None) -> Dict[str, Any]:
    project_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"
    if not name:
        name = Path(source_path).stem if source_path else f"Project {project_id[:8]}"

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO projects (id, name, source_path, source_duration, status, transcription_mode, caption_style, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (project_id, name, source_path, source_duration, "ingest", transcription_mode, caption_style, now, now)
        )
    return get_project(project_id)

def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None

def list_projects() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]

def update_project_status(project_id: str, status: str, duration: Optional[float] = None):
    now = datetime.utcnow().isoformat() + "Z"
    with get_connection() as conn:
        if duration is not None:
            conn.execute(
                "UPDATE projects SET status = ?, source_duration = ?, updated_at = ? WHERE id = ?",
                (status, duration, now, project_id)
            )
        else:
            conn.execute(
                "UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, project_id)
            )

def rename_project(project_id: str, name: str):
    now = datetime.utcnow().isoformat() + "Z"
    with get_connection() as conn:
        conn.execute("UPDATE projects SET name = ?, updated_at = ? WHERE id = ?", (name, now, project_id))

def delete_project(project_id: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

def save_transcript(project_id: str, engine: str, raw_json: str, language: Optional[str] = None) -> Dict[str, Any]:
    transcript_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"
    with get_connection() as conn:
        conn.execute("DELETE FROM transcripts WHERE project_id = ?", (project_id,))
        conn.execute(
            """INSERT INTO transcripts (id, project_id, engine, raw_json, language, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (transcript_id, project_id, engine, raw_json, language, now)
        )
    return {
        "id": transcript_id,
        "projectId": project_id,
        "engine": engine,
        "rawJson": raw_json,
        "language": language,
        "createdAt": now
    }

def get_latest_transcript(project_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM transcripts WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "engine": row["engine"],
            "rawJson": row["raw_json"],
            "language": row["language"],
            "createdAt": row["created_at"]
        }

def replace_candidates(project_id: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        conn.execute("DELETE FROM candidates WHERE project_id = ?", (project_id,))
        saved = []
        for i, c in enumerate(candidates):
            c_id = str(uuid.uuid4())
            rank = i + 1
            selected = 1 if rank <= 3 else 0
            conn.execute(
                """INSERT INTO candidates (id, project_id, start_sec, end_sec, score, hook, rationale, rank, selected)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (c_id, project_id, c["start"], c["end"], c.get("score", 0.9), c.get("hook", ""), c.get("rationale", ""), rank, selected)
            )
            # Create a corresponding empty clip entry
            clip_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO clips (id, candidate_id, status)
                   VALUES (?, ?, ?)""",
                (clip_id, c_id, "pending")
            )
            saved.append({
                "id": c_id,
                "projectId": project_id,
                "startSec": c["start"],
                "endSec": c["end"],
                "score": c.get("score", 0.9),
                "hook": c.get("hook", ""),
                "rationale": c.get("rationale", ""),
                "rank": rank,
                "selected": bool(selected)
            })
        return saved

def get_candidates(project_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM candidates WHERE project_id = ? ORDER BY rank ASC",
            (project_id,)
        ).fetchall()
        return [{
            "id": r["id"],
            "projectId": r["project_id"],
            "startSec": r["start_sec"],
            "endSec": r["end_sec"],
            "score": r["score"],
            "hook": r["hook"],
            "rationale": r["rationale"],
            "rank": r["rank"],
            "selected": bool(r["selected"])
        } for r in rows]

def set_selected_clip_count(project_id: str, count: int):
    with get_connection() as conn:
        conn.execute("UPDATE candidates SET selected = 0 WHERE project_id = ?", (project_id,))
        conn.execute(
            "UPDATE candidates SET selected = 1 WHERE project_id = ? AND rank <= ?",
            (project_id, count)
        )

def get_candidate(candidate_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "startSec": row["start_sec"],
            "endSec": row["end_sec"],
            "score": row["score"],
            "hook": row["hook"],
            "rationale": row["rationale"],
            "rank": row["rank"],
            "selected": bool(row["selected"])
        }

def update_clip_for_candidate(candidate_id: str, status: str, output_path: Optional[str] = None, srt_path: Optional[str] = None, render_log: Optional[str] = None):
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM clips WHERE candidate_id = ?", (candidate_id,)).fetchone()
        if row:
            conn.execute(
                """UPDATE clips SET status = ?, output_path = coalesce(?, output_path),
                   caption_ass_path = coalesce(?, caption_ass_path), render_log = coalesce(?, render_log)
                   WHERE candidate_id = ?""",
                (status, output_path, srt_path, render_log, candidate_id)
            )
        else:
            clip_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO clips (id, candidate_id, status, output_path, caption_ass_path, render_log)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (clip_id, candidate_id, status, output_path, srt_path, render_log)
            )

def get_clips_for_project(project_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT c.* FROM clips c
               JOIN candidates can ON c.candidate_id = can.id
               WHERE can.project_id = ?""",
            (project_id,)
        ).fetchall()
        return [{
            "id": r["id"],
            "candidateId": r["candidate_id"],
            "status": r["status"],
            "outputPath": r["output_path"],
            "faceTrackJson": r["face_track_json"],
            "captionAssPath": r["caption_ass_path"],
            "renderLog": r["render_log"]
        } for r in rows]

def get_clip_by_id(clip_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM clips WHERE id = ?", (clip_id,)).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "candidateId": row["candidate_id"],
            "status": row["status"],
            "outputPath": row["output_path"],
            "captionAssPath": row["caption_ass_path"],
            "renderLog": row["render_log"]
        }

def get_clip_for_candidate(candidate_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM clips WHERE candidate_id = ?", (candidate_id,)).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "candidateId": row["candidate_id"],
            "status": row["status"],
            "outputPath": row["output_path"],
            "captionAssPath": row["caption_ass_path"],
            "renderLog": row["render_log"]
        }

def get_project_detail(project_id: str) -> Optional[Dict[str, Any]]:
    project = get_project(project_id)
    if not project:
        return None
    transcript = get_latest_transcript(project_id)
    candidates = get_candidates(project_id)
    clips = get_clips_for_project(project_id)
    return {
        "project": {
            "id": project["id"],
            "name": project["name"],
            "sourcePath": project["source_path"],
            "sourceDuration": project["source_duration"],
            "status": project["status"],
            "transcriptionMode": project["transcription_mode"],
            "captionStyle": project["caption_style"],
            "createdAt": project["created_at"],
            "updatedAt": project["updated_at"]
        },
        "transcript": transcript,
        "candidates": candidates,
        "clips": clips
    }

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else os.getenv(key, default)

def set_setting(key: str, value: str):
    with get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

def get_all_settings() -> Dict[str, str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        settings = {r["key"]: r["value"] for r in rows}
    # Also overlay any env vars if not overridden
    env_keys = [
        "DEEPGRAM_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "LLM_PROVIDER"
    ]
    for k in env_keys:
        if k not in settings and os.getenv(k):
            settings[k] = os.getenv(k)
    return settings
