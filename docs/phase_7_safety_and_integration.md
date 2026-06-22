# Phase 7: Safety Gates, Global Hotkey, and Final Integration

In this phase, we connect all our modules into a single execution context. You will write the background key combination listener, implement hotkey window toggles, and use the PyWebview interface to execute JavaScript code dynamically inside the browser window to synchronize the star orb animations with active voice recording.

---

## 1. Directory Structure

At the end of this phase, your project tree should look exactly like this:
```text
AI_Assistant/
├── .env
├── pyproject.toml
├── uv.lock
├── run.py
├── ui/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── src/
    ├── __init__.py
    ├── agent_state.py
    ├── audio.py
    ├── config.py
    ├── gui.py
    ├── llm.py
    ├── main.py
    ├── orchestrator.py
    ├── tts.py
    ├── nodes/
    │   ├── __init__.py
    │   ├── browser.py
    │   ├── classifier.py
    │   ├── developer.py
    │   ├── formatter.py
    │   └── vision.py
    └── skills/
        ├── __init__.py
        ├── developer.py
        ├── vision.py
        └── webbridge.py
```

---

## 2. Step-by-Step File Creation

### Step 1: Create `src/hotkey.py`
Create a file named `src/hotkey.py` to establish the OS keyboard hook:
```python
import threading
from pynput import keyboard

class GlobalHotkeyManager:
    """
    Monitors global key inputs on the host OS in a background thread.
    Summons the pywebview UI window upon Option + Space shortcut triggers.
    """
    def __init__(self, summon_callback):
        self.summon_callback = summon_callback
        self.listener = None

    def start(self):
        hotkey_str = "<alt>+<space>"
        
        def on_activate():
            print("[Hotkey] Option + Space detected! Toggling window...")
            self.summon_callback()

        self.listener = keyboard.GlobalHotkeys({
            hotkey_str: on_activate
        })
        
        threading.Thread(target=self.listener.start, daemon=True).start()
        print(f"[Hotkey] Listening globally for: {hotkey_str}")
```

### Step 2: Create `src/gui.py`
Create a file named `src/gui.py` to handle the PyWebview renderer and run JS commands to sync orb animations and resize the floating overlay during voice input:
```python
import os
import time
import threading
import requests
import webview
from src.config import settings
from src.hotkey import GlobalHotkeyManager

app_window = None
is_visible = True
is_expanded = False

class WindowAPI:
    """Python functions exposed directly to PyWebview frontend."""
    def toggle_expand(self, expand: bool):
        """Resizes the borderless window dynamically on-screen."""
        global app_window, is_expanded
        if not app_window:
            return
            
        screen = webview.screens[0]
        is_expanded = expand
        
        if expand:
            # Expand container bounds to fit slide-out text banner
            app_window.resize(550, 380)
            app_window.move(screen.width - 570, screen.height - 420)
        else:
            # Collapse back to small corner circle
            app_window.resize(80, 80)
            app_window.move(screen.width - 100, screen.height - 120)

    def send_command(self, text: str) -> dict:
        try:
            res = requests.post("http://127.0.0.1:8000/command", json={"text": text}, timeout=30)
            return res.json()
        except Exception as e:
            return {"reply": f"API Connection failed: {e}", "route": "chat", "status": "error"}

    def close_app(self):
        print("[GUI] Exit requested.")
        os._exit(0)

def trigger_voice_capture():
    """
    Expands the UI banner, listens to mic input, transcribes, runs the agent graph,
    and collapses back to a corner orb when completed.
    """
    global app_window
    if not app_window:
        return
    
    api = WindowAPI()
    
    # 1. Expand screen boundaries and show active container class
    api.toggle_expand(True)
    app_window.evaluate_js("document.getElementById('main-container').classList.add('expanded');")
    
    # 2. Update UI orb to listening (rippling orange/rose-gold WebGL animation)
    app_window.evaluate_js("setOrbState('listening');")
    app_window.evaluate_js("document.getElementById('output-box').innerText = 'Listening to your voice...';")
    
    try:
        # Step 3: Trigger recording & reasoning backend API
        res = requests.post("http://127.0.0.1:8000/voice_command", timeout=60)
        data = res.json()
        
        reply = data.get("reply", "Resonance lost. Try again.")
        route = data.get("route", "chat")
        
        safe_reply = reply.replace("'", "\\'").replace('"', '\\"').replace("\n", " ")
        
        # Step 4: Display reply and transition orb to speaking (glowing indigo-purple ripples)
        app_window.evaluate_js(f"document.getElementById('output-box').innerText = '{safe_reply}';")
        app_window.evaluate_js("setOrbState('speaking');")
        app_window.evaluate_js(f"addAuditLog('Voice execution completed [{route}].');")
        
        # Let speech finish playing before collapsing
        time.sleep(5.0)
        app_window.evaluate_js("setOrbState('idle');")
        
    except Exception as e:
        print(f"[GUI Voice Loop Error] {str(e)}")
        app_window.evaluate_js("setOrbState('idle');")
        app_window.evaluate_js("document.getElementById('output-box').innerText = 'Voice connection error.';")
    finally:
        # 5. Collapse window back to corner circle bubble
        app_window.evaluate_js("document.getElementById('main-container').classList.remove('expanded');")
        api.toggle_expand(False)

def toggle_window():
    """Toggle visibility when summoning Lyra."""
    global is_visible, app_window
    if app_window:
        if is_visible:
            print("[GUI] Hiding overlay window.")
            app_window.hide()
            is_visible = False
        else:
            print("[GUI] Summoning overlay window.")
            app_window.show()
            app_window.restore()
            is_visible = True
            
            # Start automatic voice capture thread on summon
            threading.Thread(target=trigger_voice_capture, daemon=True).start()

def start_gui():
    global app_window
    api = WindowAPI()
    
    ui_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui"))
    html_path = os.path.join(ui_dir, "index.html")
    screen = webview.screens[0]

    app_window = webview.create_window(
        title="Lyra Assistant",
        url=f"file://{html_path}",
        js_api=api,
        width=80,
        height=80,
        x=screen.width - 100,
        y=screen.height - 120,
        resizable=False,
        frameless=True,
        background_color="#00000000",
        on_top=True
    )

    # Boot keyboard listener thread
    hotkeys = GlobalHotkeyManager(summon_callback=toggle_window)
    hotkeys.start()

    webview.start(debug=settings.debug)

if __name__ == "__main__":
    start_gui()
```

### Step 3: Create `run.py`
Create a file named `run.py` in your project root directory to orchestrate booting and terminating systems:
```python
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
```

---

## 3. Running & Verifying the Application
Execute the bootstrap runner from your project root:
```bash
uv run python run.py
```
*   **Corner Anchor:** A small borderless circle containing the glowing, liquid 3D orb floats in the bottom-right corner of your screen.
*   **Manual Trigger:** Click on the orb to toggle it manually. It expands into a horizontal glassmorphic panel. In Python, the window expands to `550x380` and relocates itself to offset the expanded banner.
*   **Summon & Speak Loop:** Press `Option + Space`. The window is toggled to visible, automatically resizing and sliding out the banner. The WebGL 3D orb shifts to its liquid rippling *Listening* state. Once you stop speaking, it runs through Whisper/LangGraph, speaks the response, displays the captions, and automatically collapses back down to the small corner circle bubble.
