# 🎬 AutoShorts - AI Viral Short Video Generator

Turn long-form videos into viral 9:16 portrait shorts for Instagram Reels, TikTok, and YouTube Shorts automatically using AI speech recognition, viral moment detection, and hardware-accelerated video rendering.

---

## ✨ Features

- **🎯 Full-Video Viral Analysis**: Automatically extracts high-energy moments distributed across the entire duration of long videos (e.g. podcasts, interviews, lectures).
- **🎙️ 100% Offline Real Speech Transcription**: Powered by `faster-whisper` running locally on CPU with int8 quantization. No cloud API keys required.
- **✨ Social-Media-Ready Captions**:
  - Precision lower-third positioning ($Y \approx 80-85\%$ from top), keeping speakers' faces and actions 100% clear.
  - SubStation Alpha (`.ass`) formatting for crisp, modern typography.
  - Styles: **TikTok Viral** (Gold/Yellow), **Modern Box** (Translucent Pill), **Neon Cyan**, **Bold White**, and **Minimalist**.
- **⚡ Hardware-Accelerated Rendering**: Integrated FFmpeg with Intel Iris Xe QSV (`h264_qsv`) and multi-threaded CPU fallback for ultra-fast 9:16 vertical rendering.
- **🌐 Modern Web Interface**: Clean dark-mode dashboard with real-time video streaming, clip count and duration controls, smartphone mockup preview, and 1-click downloads.
- **📥 YouTube Downloader & File Uploader**: Import videos directly from YouTube links or upload local media files.
- **🤖 Multi-Provider AI Support**: Optional integration with DeepSeek, Google Gemini, OpenAI GPT-4o, Anthropic Claude, and Groq.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- FFmpeg (bundled or system-installed)

### 2. Installation
```bash
git clone https://github.com/doonatm/autoshorts.git
cd autoshorts
pip install -r requirements.txt
```

### 3. Launching
On Windows:
Double-click:
```
start_platform.bat
```
Or run in terminal:
```bash
python run.py
```
Open **http://127.0.0.1:8000** in your browser.

---

## 🐳 Docker Deployment

```bash
docker build -t autoshorts-platform .
docker run -p 8000:8000 autoshorts-platform
```

---

## 📄 License
MIT License
