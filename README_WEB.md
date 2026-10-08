# AutoShorts - Online Web Platform

Welcome to the **AutoShorts Online Web Platform**! This allows you to turn long-form videos into viral 9:16 portrait shorts directly in your web browser.

---

## 🚀 How to Launch the Platform

### Option 1: One-Click Launch (Windows)
Double-click:
```
start_platform.bat
```
This automatically starts the backend server and opens **http://127.0.0.1:8000** in your browser.

---

### Option 2: Command Line (Windows / macOS / Linux)
Run:
```bash
python run.py
```
Or directly with Uvicorn:
```bash
uvicorn server.app:app --host 127.0.0.1 --port 8000
```
Then navigate to **http://127.0.0.1:8000** in any browser.

---

## 🌟 Key Features

1. **Direct In-Browser Platform**: No Rust compiler or desktop app setup needed. Works instantly in Chrome, Edge, Safari, Firefox.
2. **Instant Demo Test Drive**: Click the **Instant Demo** button to test the entire pipeline with a sample video and AI-ranked moments in 1 second.
3. **Upload Media**: Drag-and-drop video/audio files (MP4, MOV, MP3, WAV, M4A) with live percentage upload progress.
4. **YouTube Downloader**: Paste any YouTube link to auto-download and process with `yt-dlp`.
5. **AI Speech Transcription**:
   - Deepgram Nova-2
   - OpenAI Whisper / Groq Whisper
   - Built-in Demo mode (zero keys required)
6. **AI Viral Moment & Hook Detection**:
   - DeepSeek Chat (recommended, cheap & smart)
   - Google Gemini (Flash / Pro)
   - OpenAI GPT-4o
   - Anthropic Claude 3.5 Sonnet
   - Groq Llama 3.3
   - Built-in Smart Heuristic (offline / demo)
7. **FFmpeg 9:16 Vertical Video Renderer**:
   - High-quality center-crop to 1080x1920 portrait format.
   - Generates `.srt` subtitle files with precise word timestamps.
   - Dynamic burned captions (Modern Box, Neon Punch, or Clean).
8. **In-Browser Vertical Video Player**:
   - Interactive smartphone mockup player to watch the rendered 9:16 shorts directly in the browser.
9. **1-Click Downloads**:
   - Download the final vertical MP4 clip.
   - Download the generated `.srt` subtitle file.
10. **Interactive Transcript**:
   - Word-by-word timestamped transcript synchronized with video. Click any sentence to jump the player to that timestamp.

---

## ⚙️ Configuration & API Keys

You can use the platform **completely free in Demo mode without any API keys**.

Whenever you want to use cloud AI engines:
1. Click the **API Settings** (gear icon) in the top-right corner of the web interface.
2. Enter your API key for Deepgram, DeepSeek, Gemini, OpenAI, Claude, or Groq.
3. Click **Save Changes**. Your credentials are saved locally in `data/autoshorts.db`.

---

## 🐳 Cloud Deployment (Docker)

To deploy AutoShorts online (Render, Railway, Fly.io, Hugging Face Spaces, or a VPS):
```bash
docker build -t autoshorts-platform .
docker run -p 8000:8000 autoshorts-platform
```
Open `http://your-server-ip:8000`.
