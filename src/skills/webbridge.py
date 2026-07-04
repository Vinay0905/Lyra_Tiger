import httpx

from src.config import settings


class KimiWebBridgeClient:
    """
    Async client interfacing with the local Kimi WebBridge daemon API.
    Communicates via the default /command route and formats payloads
    according to the WebBridge JSON schema specification.
    """

    def __init__(self):
        self.base_url = f"http://{settings.webbridge_host}:{settings.webbridge_port}"

    async def _send_command(self, action: str, args: dict = None) -> dict:
        url = f"{self.base_url}/command"
        payload = {"action": action, "args": args or {}}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload)
            if response.status_code != 200:
                raise RuntimeError(
                    f"WebBridge command '{action}' failed (status {response.status_code}): {response.text}"
                )
            return response.json()
        except httpx.HTTPError as e:
            raise ConnectionError(f"Could not connect to Kimi WebBridge daemon: {e}")

    @staticmethod
    def _unwrap(res: dict):
        if isinstance(res, dict):
            if "result" in res:
                return res["result"]
            if "data" in res:
                return res["data"]
        return res

    async def navigate(self, url: str) -> dict:
        print(f"[WebBridge] Navigating to: {url}")
        return self._unwrap(await self._send_command("navigate", {"url": url}))

    async def get_snapshot(self) -> dict:
        print("[WebBridge] Requesting accessibility snapshot...")
        res = self._unwrap(await self._send_command("snapshot"))
        return res if isinstance(res, dict) else {}

    async def click(self, selector: str) -> dict:
        print(f"[WebBridge] Clicking element: {selector}")
        return self._unwrap(await self._send_command("click", {"selector": selector}))

    async def fill(self, selector: str, text: str) -> dict:
        print(f"[WebBridge] Filling element {selector} with value: {text}")
        return self._unwrap(await self._send_command("fill", {"selector": selector, "value": text}))

    async def get_screenshot(self) -> str:
        print("[WebBridge] Capturing page screenshot...")
        res = self._unwrap(await self._send_command("screenshot"))
        if isinstance(res, dict):
            return res.get("base64") or res.get("data") or ""
        return ""
