import time
import subprocess
import sys
import os

def main():
    print("====================================================")
    print("            Launching Lyra Desktop Resonator        ")
    print("====================================================")

    # Start FastAPI server process
    backend_proc = subprocess.Popen(
        ["uv", "run", "python", "-m", "src.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    print("[Launcher] Starting backend server...")
    time.sleep(2.5) # Wait for server bindings
    
    if backend_proc.poll() is not None:
        print("[Launcher Error] Backend failed to bind. Output logs:")
        out, _ = backend_proc.communicate()
        print(out)
        sys.exit(1)
        
    print("[Launcher] Server active. Booting desktop window...")
    
    try:
        subprocess.run(["uv", "run", "python", "-m", "src.gui"])
    finally:
        print("[Launcher] Shutdown triggered. Cleaning backend processes...")
        backend_proc.terminate()
        try:
            backend_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
        print("[Launcher] Systems shutdown complete.")

if __name__ == "__main__":
    main()
