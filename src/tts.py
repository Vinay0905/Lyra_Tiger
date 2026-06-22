import sys
import subprocess

class TTSEngine:
    """
    Text-to-Speech Engine. Defaults to native OS utilities to minimize delay.
    """
    def __init__(self, rate=175):
        self.rate = rate
        self.is_mac = sys.platform == "darwin"

    def speak(self, text: str):
        print(f"[TTS] Speaking: {text}")
        clean_text = text.replace('"', '').replace("'", "").replace("*", "")
        
        if self.is_mac:
            # macOS built-in command 'say' runs locally and is near-instantaneous
            subprocess.run(["say", "-r", str(self.rate), clean_text])
        else:
            # Fallback for Windows/Linux
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty('rate', self.rate)
                engine.say(clean_text)
                engine.runAndWait()
            except ImportError:
                print("[TTS Warning] pyttsx3 not installed. Speech output disabled.")