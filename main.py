import os
import sys
import subprocess
from pathlib import Path


def check_env():
    # load .env settings if the file exists
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

    if not os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY").startswith("your_"):
        print("Error: GEMINI_API_KEY is not set or has placeholder value in environment.")
        sys.exit(1)

    print("Environment successfully loaded.")


if __name__ == "__main__":
    check_env()
    print()
    print("CodeSentinel - AI Code Review")
    print()
    print(f"  Server:    http://localhost:8000")
    print(f"  Dashboard: http://localhost:8000")
    print(f"  API Docs:  http://localhost:8000/docs")
    print()
    print("  Press Ctrl+C to stop.")
    print()

    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "backend.api:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ])
