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

        self.listener = keyboard.GlobalHotKeys({
            hotkey_str: on_activate
        })
        
        threading.Thread(target=self.listener.start, daemon=True).start()
        print(f"[Hotkey] Listening globally for: {hotkey_str}")