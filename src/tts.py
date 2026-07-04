import os
import sys
import urllib.request

from kokoro_onnx import Kokoro

from src.config import settings


class TTSEngine:
    """
    Text-to-Speech Engine using the local Kokoro-82M ONNX model.

    Resolution order for model weights:
      1. ``LYRA_KOKORO_DIR`` env var (used by packaged/bundled builds).
      2. ``src/resources`` alongside this module.
    Weights are downloaded once on first run only if they are not already
    present, so a bundled release ships them and never hits the network.
    """

    MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
    VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

    def __init__(self, voice: str = None):
        self.voice = voice or settings.tts_voice
        self.resources_dir = os.environ.get(
            "LYRA_KOKORO_DIR",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources"),
        )
        self.model_path = os.path.join(self.resources_dir, "kokoro-v1.0.onnx")
        self.voices_path = os.path.join(self.resources_dir, "voices-v1.0.bin")
        self._kokoro = None
        self._load_engine()

    def _ensure_model_files(self):
        if not os.path.exists(self.model_path):
            print(f"[TTS] Model weights missing at {self.model_path}")
            self._download(self.MODEL_URL, self.model_path)
        if not os.path.exists(self.voices_path):
            print(f"[TTS] Voice templates missing at {self.voices_path}")
            self._download(self.VOICES_URL, self.voices_path)

    def _download(self, url: str, dest: str):
        print(f"[TTS] Downloading: {url}")
        os.makedirs(self.resources_dir, exist_ok=True)

        def progress_callback(count, block_size, total_size):
            if total_size > 0:
                percent = min(100, int(count * block_size * 100 / total_size))
                sys.stdout.write(f"\r[TTS] Download progress: {percent}%")
                sys.stdout.flush()

        urllib.request.urlretrieve(url, dest, reporthook=progress_callback)
        sys.stdout.write("\n")
        sys.stdout.flush()

    def _load_engine(self):
        if self._kokoro is None:
            self._ensure_model_files()
            print("[TTS] Loading local Kokoro ONNX engine...")
            self._kokoro = Kokoro(self.model_path, self.voices_path)
            print("[TTS] Kokoro engine initialized successfully.")

    def generate(self, text: str, voice: str = None):
        """Synthesize text to raw audio PCM float samples."""
        self._load_engine()
        selected_voice = voice or self.voice
        print(f"[TTS] Generating local voice samples ({selected_voice}) for: '{text}'")
        clean_text = text.replace('"', '').replace("'", "").replace("*", "")
        samples, sample_rate = self._kokoro.create(
            clean_text,
            voice=selected_voice,
            speed=1.0,
            lang="en-us",
        )
        return samples, sample_rate

    def speak(self, text: str):
        """Legacy compatibility method; speech is now streamed to frontend."""
        print(f"[TTS] Client streaming requested for: '{text}'")
