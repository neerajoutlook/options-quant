#!/usr/bin/env python3
import sys
import os
import subprocess
from watchfiles import run_process

def run_app():
    """Run the main application script."""
    # Kill any existing process on port 8001
    try:
        print("🧹 Cleaning up port 8001...")
        subprocess.run(
            "lsof -ti:8001 | xargs kill -9 2>/dev/null || true",
            shell=True,
            check=False
        )
    except Exception as e:
        print(f"⚠️ Port cleanup warning: {e}")
    
    # Use the same python interpreter as this script
    python = sys.executable
    cmd = [python, "launch_web.py"]
    print(f"🔄 Starting app: {' '.join(cmd)}")
    subprocess.run(cmd)

if __name__ == "__main__":
    print("👀 Watching for file changes in current directory...")
    print("📂 Ignoring .git, __pycache__, logs, .env")
    
    # Define filter function
    def custom_filter(change, path):
        # Ignore directories matching these names
        ignored = {'.git', '__pycache__', 'logs', '.venv', 'env', 'venv', '.EQ', '.DS_Store'}
        for part in path.split(os.sep):
            if part in ignored:
                return False
        
        # Only trigger on specific file types
        return path.endswith(('.py', '.html', '.js', '.css'))

    try:
        run_process(
            ".", 
            target=run_app,
            watch_filter=custom_filter
        )
    except KeyboardInterrupt:
        print("\n👋 Stopped watcher.")
