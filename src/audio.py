import os
import time
import requests
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
from src.config import settings

class AudioRecorder:
    """
    Handles recording audio from the default system microphone.
    Supports auto-termination using sound amplitude threshold metrics.
    """
    def __init__(self, sample_rate=16000, silence_threshold=0.03, silence_duration=1.5):
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.temp_file = "temp_voice.wav"

    def record(self) -> str:
        """
        Record audio from the microphone until silence is detected.
        Returns the absolute path to the recorded WAV file.
        """
        print("[Audio] Initializing recording. Speak now...")
        audio_data = []
        last_sound_time = time.time()
        block_size = int(self.sample_rate * 0.1) # 100ms blocks
        
        def callback(indata, frames, time_info, status):
            nonlocal last_sound_time
            rms = np.sqrt(np.mean(indata**2))
            audio_data.append(indata.copy())
            if rms > self.silence_threshold:
                last_sound_time = time.time()

        with sd.InputStream(samplerate=self.sample_rate, channels=1, 
                            blocksize=block_size, callback=callback):
            while True:
                sd.sleep(100)
                elapsed_silence = time.time() - last_sound_time
                if elapsed_silence > self.silence_duration:
                    print("[Audio] Silence detected. Finalizing recording...")
                    break
        
        if len(audio_data) > 0:
            recording = np.concatenate(audio_data, axis=0)
            wav.write(self.temp_file, self.sample_rate, recording)
            return os.path.abspath(self.temp_file)
        else:
            raise ValueError("No audio signals captured.")
            
    def cleanup(self):
        """Delete temporary voice files."""
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)

def transcribe_audio(file_path: str) -> str:
    """
    Transcribe WAV files using the Groq Whisper model (whisper-large-v3).
    """
    if not settings.groq_api_key:
        raise ValueError("Missing GROQ_API_KEY. Configure it inside your .env file.")
        
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, "audio/wav")}
        data = {
            "model": "whisper-large-v3",
            "temperature": "0.0",
            "language": "en"
        }
        response = requests.post(url, headers=headers, files=files, data=data, timeout=15)
        
    if response.status_code != 200:
        raise RuntimeError(f"Whisper API call failed: {response.text}")
        
    return response.json().get("text", "").strip()