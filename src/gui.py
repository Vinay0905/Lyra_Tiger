import os
import time
import threading
from pathlib import Path
import requests
import webview
from src.config import settings
from src.hotkey import GlobalHotkeyManager

app_window = None
is_visible = True
is_expanded = False

def get_screen_dimensions():
    """Gets screen width and height safely with fallbacks."""
    try:
        screens = webview.screens
        if screens:
            return screens[0].width, screens[0].height
    except Exception:
        pass
    return 1920, 1080

class WindowAPI:
    """Python functions exposed directly to PyWebview frontend."""
    def toggle_expand(self, expand: bool):
        """Resizes the borderless window dynamically on-screen."""
        global app_window, is_expanded
        if not app_window:
            return
            
        sw, sh = get_screen_dimensions()
        is_expanded = expand
        
        if expand:
            # Expand container bounds to fit slide-out text banner
            app_window.resize(550, 380)
            app_window.move(sw - 570, sh - 420)
        else:
            # Collapse back to small corner circle
            app_window.resize(80, 80)
            app_window.move(sw - 100, sh - 120)

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
        
        # Safely escape backslashes, single quotes, and double quotes for JS execution
        safe_reply = reply.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace("\n", " ")
        
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
    html_uri = Path(html_path).as_uri()
    
    sw, sh = get_screen_dimensions()

    app_window = webview.create_window(
        title="Lyra Assistant",
        url=html_uri,
        js_api=api,
        width=80,
        height=80,
        x=sw - 100,
        y=sh - 120,
        resizable=False,
        frameless=True,
        transparent=True,
        on_top=True
    )

    # Boot keyboard listener thread
    hotkeys = GlobalHotkeyManager(summon_callback=toggle_window)
    hotkeys.start()

    webview.start(debug=settings.debug)

if __name__ == "__main__":
    start_gui()