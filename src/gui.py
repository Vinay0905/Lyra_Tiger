import os
from pathlib import Path
import webview
from src.config import settings

# Global window references
app_window = None
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
    """Python methods exposed to the frontend JavaScript runtime."""
    def toggle_expand(self, expand: bool):
        """Resizes the borderless pywebview window shell dynamically."""
        global app_window, is_expanded
        if not app_window:
            return
            
        sw, sh = get_screen_dimensions()
        is_expanded = expand
        
        if expand:
            # Expand window to fit text captions and logs
            app_window.resize(550, 380)
            # Move to bottom right coordinates
            app_window.move(sw - 570, sh - 420)
        else:
            # Collapse back to small corner circle
            app_window.resize(80, 80)
            app_window.move(sw - 100, sh - 120)

    def send_command(self, text: str) -> dict:
        print(f"[GUI API] Received Text Command: {text}")
        return {
            "reply": f"Lyra: Processing resonance check for '{text}'",
            "route": "chat",
            "status": "success"
        }

    def close_app(self):
        os._exit(0)

def start_gui():
    global app_window
    api = WindowAPI()
    
    ui_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui"))
    html_path = os.path.join(ui_dir, "index.html")
    html_uri = Path(html_path).as_uri()
    
    sw, sh = get_screen_dimensions()
    
    # Initialize the small collapsed window in the bottom-right corner
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
    
    webview.start(debug=settings.debug)

if __name__ == "__main__":
    start_gui()