import subprocess
import threading
import sys
import os
import signal
from colorama import init as colorama_init

colorama_init()

# ANSI colors
COLORS = {
    "api": "\033[96m",     # cyan
    "csv worker": "\033[92m",  # green
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
            "--log-level", "debug"
        ]
        worker_cmd = [
            sys.executable,
            "-m",
            "app.workers.csv_worker"
        ]

        print("🚀 Starting API and Worker...\n")

        # Start processes
        api_proc = subprocess.Popen(api_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        worker_proc = subprocess.Popen(worker_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Start threaded output streaming
        threading.Thread(target=stream_output, args=(api_proc, "api", COLORS["api"]), daemon=True).start()
        threading.Thread(target=stream_output, args=(worker_proc, "CSV worker", COLORS["csv worker"]), daemon=True).start()

        # Wait for both processes
        api_proc.wait()
        worker_proc.wait()

    except KeyboardInterrupt:
        print("\n🛑 Shutting down processes...")
        api_proc.send_signal(signal.SIGINT)
        worker_proc.send_signal(signal.SIGINT)
        api_proc.terminate()
        worker_proc.terminate()
        print("✅ Clean exit.")

if __name__ == "__main__":
    run_concurrently()
