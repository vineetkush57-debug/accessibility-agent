#!/usr/bin/env python3
"""Cross-platform development and automation script for A11y Pilot.

Usage:
    python scripts/dev.py <setup|run|demo|test|test-all|eval|lint>
"""

import os
import shutil
import subprocess
import sys
import urllib.request
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

AXE_CDN_URL = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"


def ensure_axe_vendored():
    """Ensure axe.min.js is vendored in backend/vendor/axe.min.js."""
    vendor_dir = ROOT_DIR / "backend" / "vendor"
    vendor_dir.mkdir(parents=True, exist_ok=True)
    axe_path = vendor_dir / "axe.min.js"

    if not axe_path.exists() or axe_path.stat().st_size == 0:
        print("Vendoring axe-core (downloading axe.min.js)...")
        try:
            req = urllib.request.Request(AXE_CDN_URL, headers={"User-Agent": "A11yPilot/1.0"})
            with urllib.request.urlopen(req) as resp, open(axe_path, "wb") as f:
                f.write(resp.read())
            print(f"axe.min.js saved to {axe_path} ({axe_path.stat().st_size} bytes)")
        except Exception as e:
            print(f"Warning: Failed to download axe.min.js: {e}")
            print("Please ensure backend/vendor/axe.min.js exists.")


def cmd_setup():
    """Setup environment: install dependencies, download browsers, vendor axe."""
    print("Setting up A11y Pilot...")

    # Copy .env.example to .env if missing
    env_example = ROOT_DIR / ".env.example"
    env_file = ROOT_DIR / ".env"
    if not env_file.exists() and env_example.exists():
        shutil.copy(env_example, env_file)
        print("Created .env from .env.example")

    # Install Python packages
    req_file = ROOT_DIR / "requirements.txt"
    req_dev = ROOT_DIR / "requirements-dev.txt"
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req_file)])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req_dev)])

    # Install Playwright Chromium
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])

    # Vendor axe.min.js
    ensure_axe_vendored()
    print("Setup completed successfully!")


def cmd_run(provider: str = "mock", open_browser: bool = False):
    """Run the FastAPI application."""
    os.environ["LLM_PROVIDER"] = provider
    ensure_axe_vendored()

    if open_browser:
        import threading
        import time

        def _open():
            time.sleep(1.5)
            webbrowser.open("http://127.0.0.1:8000")

        threading.Thread(target=_open, daemon=True).start()

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--reload",
    ]
    subprocess.run(cmd, cwd=str(ROOT_DIR))


def cmd_demo():
    """Start app with LLM_PROVIDER=mock and open the browser."""
    print("Starting A11y Pilot Demo mode (mock LLM)...")
    cmd_run(provider="mock", open_browser=True)


def cmd_test():
    """Run unit tests excluding browser-dependent tests."""
    ensure_axe_vendored()
    cmd = [sys.executable, "-m", "pytest", "-m", "not browser", "-v"]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    sys.exit(res.returncode)


def cmd_test_all():
    """Run all tests including browser-dependent tests."""
    ensure_axe_vendored()
    cmd = [sys.executable, "-m", "pytest", "-v"]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    sys.exit(res.returncode)


def cmd_eval():
    """Run the evaluation benchmark harness."""
    eval_script = ROOT_DIR / "eval" / "run_eval.py"
    if not eval_script.exists():
        print(f"Error: {eval_script} does not exist yet.")
        sys.exit(1)
    cmd = [sys.executable, str(eval_script)]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    sys.exit(res.returncode)


def cmd_lint():
    """Run ruff lint and format check."""
    print("Running ruff check...")
    res1 = subprocess.run(["ruff", "check", "."], cwd=str(ROOT_DIR))
    print("Running ruff format check...")
    res2 = subprocess.run(["ruff", "format", "--check", "."], cwd=str(ROOT_DIR))
    sys.exit(res1.returncode or res2.returncode)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()
    if command == "setup":
        cmd_setup()
    elif command == "run":
        cmd_run()
    elif command == "demo":
        cmd_demo()
    elif command == "test":
        cmd_test()
    elif command == "test-all":
        cmd_test_all()
    elif command == "eval":
        cmd_eval()
    elif command == "lint":
        cmd_lint()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
