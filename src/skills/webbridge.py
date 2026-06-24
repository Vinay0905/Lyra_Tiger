import requests
from src.config import settings

class KimiWebBridgeClient:
    """
    Python client interfacing with the local Kimi WebBridge daemon API.
    Communicates via the default /command route and formats payloads
    according to the WebBridge JSON schema specification.
    """
    def __init__(self):
        self.base_url = f"http://{settings.webbridge_host}:{settings.webbridge_port}"
        
    def _send_command(self, action: str, args: dict = None) -> dict:
        """Sends action commands to the WebBridge daemon."""
        url = f"{self.base_url}/command"
        payload = {
            "action": action,
            "args": args or {}
        }
        try:
            response = requests.post(url, json=payload, timeout=15)
            if response.status_code != 200:
                raise RuntimeError(f"WebBridge command '{action}' failed (status {response.status_code}): {response.text}")
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Could not connect to Kimi WebBridge daemon: {e}")

    def navigate(self, url: str) -> dict:
        print(f"[WebBridge] Navigating to: {url}")
        res = self._send_command("navigate", {"url": url})
        if isinstance(res, dict):
            if "result" in res: return res["result"]
            if "data" in res: return res["data"]
        return res

    def get_snapshot(self) -> dict:
        print("[WebBridge] Requesting accessibility snapshot...")
        res = self._send_command("snapshot")
        if isinstance(res, dict):
            if "result" in res and isinstance(res["result"], dict):
                return res["result"]
            if "data" in res and isinstance(res["data"], dict):
                return res["data"]
        return res

    def click(self, selector: str) -> dict:
        print(f"[WebBridge] Clicking element: {selector}")
        res = self._send_command("click", {"selector": selector})
        if isinstance(res, dict):
            if "result" in res: return res["result"]
            if "data" in res: return res["data"]
        return res

    def fill(self, selector: str, text: str) -> dict:
        print(f"[WebBridge] Filling element {selector} with value: {text}")
        res = self._send_command("fill", {"selector": selector, "value": text})
        if isinstance(res, dict):
            if "result" in res: return res["result"]
            if "data" in res: return res["data"]
        return res

    def get_screenshot(self) -> str:
        print("[WebBridge] Capturing page screenshot...")
        res = self._send_command("screenshot")
        if isinstance(res, dict):
            if "result" in res and isinstance(res["result"], dict):
                return res["result"].get("base64") or res["result"].get("data") or ""
            if "data" in res and isinstance(res["data"], dict):
                return res["data"].get("base64") or res["data"].get("data") or ""
            return res.get("base64") or res.get("data") or ""
        return ""