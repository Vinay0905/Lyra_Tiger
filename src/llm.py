import json
from typing import AsyncGenerator, Optional

import httpx

from src.config import settings
from src.resilience import resilient_call


class ModularLLMClient:
    """
    Unified async client wrapper that routes completions through your preferred
    providers, falling back dynamically if keys are missing or requests fail.

    Uses a single shared ``httpx.AsyncClient`` so requests never block the
    FastAPI event loop, and exposes both a buffered ``achat_completion`` and a
    token-level ``astream_chat_completion`` used by the streaming pipeline.
    """

    def __init__(self):
        self.chain = settings.llm_fallback_providers
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
        return self._client

    async def aclose(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _is_valid_key(self, key: str) -> bool:
        if not key:
            return False
        k = key.strip().lower()
        return k != "" and "your_" not in k

    async def achat_completion(
        self, prompt: str, system_instruction: str = "", model: Optional[str] = None
    ) -> str:
        """Runs inference through the fallback chain until a success occurs."""
        errors = []
        for provider in self.chain:
            try:
                # Each provider call is wrapped with timeout + retry + circuit
                # breaker so a degraded provider fast-fails to the next (L3).
                if provider == "groq" and self._is_valid_key(settings.groq_api_key):
                    return await resilient_call(
                        "llm.groq", lambda: self._call_groq(prompt, system_instruction, model)
                    )
                elif provider == "openai" and self._is_valid_key(settings.openai_api_key):
                    return await resilient_call(
                        "llm.openai", lambda: self._call_openai(prompt, system_instruction, model)
                    )
                elif provider == "gemini" and self._is_valid_key(settings.gemini_api_key):
                    return await resilient_call(
                        "llm.gemini", lambda: self._call_gemini(prompt, system_instruction)
                    )
                elif provider == "openrouter" and self._is_valid_key(settings.openrouter_api_key):
                    return await resilient_call(
                        "llm.openrouter",
                        lambda: self._call_openrouter(prompt, system_instruction, model),
                    )
            except Exception as e:
                err_msg = f"{provider.upper()} call failed: {str(e)}"
                print(f"[LLM Fallback] Warning: {err_msg}")
                errors.append(err_msg)

        raise RuntimeError(f"All LLM providers in chain failed: {'; '.join(errors)}")

    async def astream_chat_completion(
        self, prompt: str, system_instruction: str = "", model: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Yields response tokens incrementally. Currently streams from the first
        healthy OpenAI-compatible provider (Groq / OpenAI / OpenRouter). If no
        streaming-capable provider is available, falls back to yielding the full
        buffered completion as a single chunk.
        """
        for provider in self.chain:
            try:
                if provider == "groq" and self._is_valid_key(settings.groq_api_key):
                    async for tok in self._stream_openai_compatible(
                        "https://api.groq.com/openai/v1/chat/completions",
                        settings.groq_api_key,
                        model or settings.primary_chat_model,
                        prompt,
                        system_instruction,
                    ):
                        yield tok
                    return
                elif provider == "openai" and self._is_valid_key(settings.openai_api_key):
                    async for tok in self._stream_openai_compatible(
                        "https://api.openai.com/v1/chat/completions",
                        settings.openai_api_key,
                        model or settings.openai_model,
                        prompt,
                        system_instruction,
                    ):
                        yield tok
                    return
                elif provider == "openrouter" and self._is_valid_key(settings.openrouter_api_key):
                    async for tok in self._stream_openai_compatible(
                        "https://openrouter.ai/api/v1/chat/completions",
                        settings.openrouter_api_key,
                        model or settings.openrouter_model,
                        prompt,
                        system_instruction,
                    ):
                        yield tok
                    return
            except Exception as e:
                print(f"[LLM Stream] {provider.upper()} streaming failed: {e}")
                continue

        # No streaming provider succeeded — degrade to a single buffered chunk.
        full = await self.achat_completion(prompt, system_instruction, model)
        yield full

    # ── OpenAI-compatible helpers ──────────────────────────────────────────
    def _build_messages(self, prompt: str, system: str) -> list[dict]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    async def _call_openai_compatible(
        self, url: str, api_key: str, model: str, prompt: str, system: str
    ) -> str:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": self._build_messages(prompt, system), "temperature": 0.2}
        res = await self._get_client().post(url, headers=headers, json=payload)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()

    async def _stream_openai_compatible(
        self, url: str, api_key: str, model: str, prompt: str, system: str
    ) -> AsyncGenerator[str, None]:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": self._build_messages(prompt, system),
            "temperature": 0.2,
            "stream": True,
        }
        async with self._get_client().stream("POST", url, headers=headers, json=payload) as res:
            res.raise_for_status()
            async for line in res.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    async def _call_groq(self, prompt: str, system: str, model: Optional[str]) -> str:
        return await self._call_openai_compatible(
            "https://api.groq.com/openai/v1/chat/completions",
            settings.groq_api_key,
            model or settings.primary_chat_model,
            prompt,
            system,
        )

    async def _call_openai(self, prompt: str, system: str, model: Optional[str]) -> str:
        return await self._call_openai_compatible(
            "https://api.openai.com/v1/chat/completions",
            settings.openai_api_key,
            model or settings.openai_model,
            prompt,
            system,
        )

    async def _call_openrouter(self, prompt: str, system: str, model: Optional[str]) -> str:
        return await self._call_openai_compatible(
            "https://openrouter.ai/api/v1/chat/completions",
            settings.openrouter_api_key,
            model or settings.openrouter_model,
            prompt,
            system,
        )

    async def _call_gemini(self, prompt: str, system: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        )
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        res = await self._get_client().post(url, headers=headers, json=payload)
        res.raise_for_status()
        return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


# Global LLM instance
llm = ModularLLMClient()
