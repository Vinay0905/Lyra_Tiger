import os
import base64
import asyncio

import httpx
from mss import mss

from src.config import settings


class DesktopVisionClient:
    """
    Captures screenshots using mss and interacts with the
    Groq Llama 3.2 Vision API (async, non-blocking).
    """

    def __init__(self):
        self.screenshot_file = "temp_screen.png"

    def capture_screen(self) -> str:
        print("[Vision] Capturing primary monitor...")
        with mss() as sct:
            sct_img = sct.shot(output=self.screenshot_file)
            return os.path.abspath(sct_img)

    async def analyze_screenshot(self, filepath: str, prompt: str) -> str:
        # File read is small and local; offload to a thread to stay non-blocking.
        img_b64 = await asyncio.to_thread(self._read_b64, filepath)

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.groq_vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    ],
                }
            ],
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _read_b64(filepath: str) -> str:
        with open(filepath, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")

    def cleanup(self):
        if os.path.exists(self.screenshot_file):
            os.remove(self.screenshot_file)
