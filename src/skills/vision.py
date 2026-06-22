import os
import base64
import requests
from mss import mss
from src.config import settings

class DesktopVisionClient:
    """
    Captures screenshots using mss and interacts with the
    Groq Llama 3.2 Vision API.
    """
    def __init__(self):
        self.screenshot_file = "temp_screen.png"

    def capture_screen(self) -> str:
        print("[Vision] Capturing primary monitor...")
        with mss() as sct:
            # Capturing the primary screen
            monitor = sct.monitors[1]
            sct_img = sct.shot(output=self.screenshot_file)
            return os.path.abspath(sct_img)

    def analyze_screenshot(self, filepath: str, prompt: str) -> str:
        with open(filepath, "rb") as img_file:
            img_b64 = base64.b64encode(img_file.read()).decode("utf-8")

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": settings.groq_vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_b64}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.2
        }

        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def cleanup(self):
        if os.path.exists(self.screenshot_file):
            os.remove(self.screenshot_file)
