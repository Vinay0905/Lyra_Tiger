import os
import time

import httpx
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav

from src.config import settings


class AudioRecorder:
    """
    Handles recording audio from the default system microphone.
    Supports auto-termination using sound amplitude threshold metrics.
    (Server-side capture path; the desktop UI records in the browser instead.)
    """

    def __init__(self, sample_rate=16000, silence_threshold=0.03, silence_duration=1.5):
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.temp_file = "temp_voice.wav"

    def record(self) -> str:
        print("[Audio] Initializing recording. Speak now...")
        audio_data = []
        last_sound_time = time.time()
        block_size = int(self.sample_rate * 0.1)

        def callback(indata, frames, time_info, status):
            nonlocal last_sound_time
            rms = np.sqrt(np.mean(indata ** 2))
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
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)


async def transcribe_audio(file_path: str) -> str:
    """
    Transcribe WAV files using the configured Groq Whisper model (async).
    """
    if not settings.groq_api_key:
        raise ValueError("Missing GROQ_API_KEY. Configure it inside your .env file.")

    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    files = {"file": (os.path.basename(file_path), file_bytes, "audio/wav")}
    data = {"model": settings.groq_stt_model, "temperature": "0.0", "language": "en"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, files=files, data=data)

    if response.status_code != 200:
        raise RuntimeError(f"Whisper API call failed: {response.text}")

    return response.json().get("text", "").strip()
