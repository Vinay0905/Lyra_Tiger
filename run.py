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
        ["uv", "run", "python", "-m", "src.main"]
    )
    
    print("[Launcher] Starting backend server...")
    time.sleep(2.5) # Wait for server bindings
    
    if backend_proc.poll() is not None:
        print("[Launcher Error] Backend failed to start. See logs above.")
        sys.exit(1)
        
    print("[Launcher] Server active. Booting Tauri desktop window...")
    
    try:
        # Launch Tauri dev mode (which also starts the Vite frontend dev server)
        subprocess.run(["npx", "@tauri-apps/cli", "dev"])
    finally:
        print("[Launcher] Shutdown triggered. Cleaning backend processes...")
        backend_proc.terminate()
        if sys.platform == "darwin":
            subprocess.run(["killall", "say"], stderr=subprocess.DEVNULL)
        try:
            backend_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
        print("[Launcher] Systems shutdown complete.")

if __name__ == "__main__":
    main()
