import os
import time
import threading
from pathlib import Path
import sys
import requests
import webview
from src.config import settings
from src.hotkey import GlobalHotkeyManager

# Set macOS process name early so the Dock displays "Lyra"
if sys.platform == "darwin":
    try:
        from Foundation import NSProcessInfo
        NSProcessInfo.processInfo().setProcessName_("Lyra")
        print("[GUI] macOS process name set to Lyra.")
    except Exception as e:
        print(f"[GUI Warning] Failed to set process name early: {e}")

# Monkeypatch macOS-specific WKWebView click-through behavior early
if sys.platform == "darwin":
    try:
        from WebKit import WKWebView
        WKWebView.acceptsFirstMouse_ = lambda self, event: True
        print("[GUI] macOS click-through monkeypatch applied.")
    except Exception as e:
        print(f"[GUI Warning] Failed to apply acceptsFirstMouse patch: {e}")

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
        if sys.platform == "darwin":
            import subprocess
            subprocess.run(["killall", "say"], stderr=subprocess.DEVNULL)
        os._exit(0)

    def start_voice_capture(self):
        print("[GUI] Voice capture triggered via JS API.")
        threading.Thread(target=trigger_voice_capture, daemon=True).start()

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
        
        # Safely convert reply to JSON string representation to prevent escape/newline errors
        import json
        safe_json = json.dumps(reply)
        
        # Step 4: Display reply and transition orb to speaking (glowing indigo-purple ripples)
        app_window.evaluate_js(f"document.getElementById('output-box').innerText = {safe_json};")
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

    def setup_app():
        if sys.platform == "darwin":
            try:
                from Foundation import NSBundle
                from AppKit import NSApplication, NSImage, NSApplicationActivationPolicyRegular
                
                # 1. Force the activation policy to Regular so it appears in the Dock properly
                app_inst = NSApplication.sharedApplication()
                app_inst.setActivationPolicy_(NSApplicationActivationPolicyRegular)
                
                # 2. Update bundle information in memory
                bundle = NSBundle.mainBundle()
                if bundle:
                    info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                    info['CFBundleName'] = "Lyra"
                    info['CFBundleDisplayName'] = "Lyra"
                    
                # 3. Load and set application Dock icon
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                icon_path = os.path.join(project_root, "LyraLogo.png")
                if os.path.exists(icon_path):
                    icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
                    app_inst.setApplicationIconImage_(icon)
                    print("[GUI] macOS Dock icon set successfully in callback.")
                else:
                    print(f"[GUI Warning] Logo not found at path: {icon_path}")
                
                # 4. Wait for menu to be ready and rename it dynamically
                def rename_menu():
                    time.sleep(0.3)
                    menu = app_inst.mainMenu()
                    if menu:
                        items = menu.itemArray()
                        if len(items) > 0:
                            app_menu_item = items[0]
                            app_menu_item.setTitle_("Lyra")
                            app_menu = app_menu_item.submenu()
                            if app_menu:
                                for sub_item in app_menu.itemArray():
                                    title = sub_item.title()
                                    if "Python" in title:
                                        sub_item.setTitle_(title.replace("Python", "Lyra"))
                                    elif "python" in title:
                                        sub_item.setTitle_(title.replace("python", "Lyra"))
                            print("[GUI] Renamed Menu Bar items and submenus successfully.")
                
                threading.Thread(target=rename_menu, daemon=True).start()

            except Exception as e:
                print(f"[GUI Warning] Failed to initialize macOS custom branding in callback: {e}")

    try:
        webview.start(setup_app, debug=settings.debug)
    finally:
        print("[GUI] Window closed. Cleaning up processes...")
        if sys.platform == "darwin":
            import subprocess
            subprocess.run(["killall", "say"], stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    start_gui()