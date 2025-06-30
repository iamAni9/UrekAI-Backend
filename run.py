import subprocess
import threading
import sys
import os
import signal
from colorama import init as colorama_init
from dotenv import load_dotenv

load_dotenv()
colorama_init()
port = os.getenv("ENV_PORT", "8000")
# ANSI colors
COLORS = {
    "api": "\033[96m",     # cyan
    "worker": "\033[92m",  # green
    "reset": "\033[0m"
}

def stream_output(process, name, color):
    for line in iter(process.stdout.readline, b''):
        sys.stdout.write(f"{color}[{name}]{COLORS['reset']} {line.decode(errors='replace')}")
    process.stdout.close()

def run_concurrently():
    try:
        # Define commands
        api_cmd = [
            "uvicorn",
            "app.main:create_app",
            "--factory",
            "--reload",
            "--log-level", "debug",
            "--port", port
        ]
        worker_cmd = [
            sys.executable,
            "-m",
            "app.workers.job_listener"
        ]

        print("...Starting API and Worker...\n")

        # Starting processes
        api_proc = subprocess.Popen(api_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        worker_proc = subprocess.Popen(worker_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Starting threaded output streaming
        threading.Thread(target=stream_output, args=(api_proc, "api", COLORS["api"]), daemon=True).start()
        threading.Thread(target=stream_output, args=(worker_proc, "Worker", COLORS["worker"]), daemon=True).start()

        # Waiting for both processes
        api_proc.wait()
        worker_proc.wait()

    except KeyboardInterrupt:
        print("\Shutting down processes...")
        api_proc.send_signal(signal.CTRL_C_EVENT)
        worker_proc.send_signal(signal.CTRL_C_EVENT)
        api_proc.terminate()
        worker_proc.terminate()
        print("Clean exit.")

if __name__ == "__main__":
    run_concurrently()
