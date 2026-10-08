import os
import sys
import webbrowser
import threading
import time
from pathlib import Path

# Add current directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

def print_banner():
    print("=" * 65)
    print("      🎬 AutoShorts - AI Short Video Web Platform 🚀")
    print("=" * 65)
    print("  • Web Interface:    http://127.0.0.1:8000")
    print("  • API Documentation: http://127.0.0.1:8000/docs")
    print("  • Mode:              Direct In-Browser Platform")
    print("=" * 65)
    print("Starting AutoShorts Web Server... Press Ctrl+C to stop.\n")

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")

def main():
    print_banner()

    # Launch browser automatically in background
    threading.Thread(target=open_browser, daemon=True).start()

    # Run Uvicorn
    import uvicorn
    uvicorn.run("server.app:app", host="127.0.0.1", port=8000, reload=False, log_level="info")

if __name__ == "__main__":
    main()
