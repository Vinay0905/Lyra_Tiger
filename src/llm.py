import requests
from src.config import settings

class ModularLLMClient:
    """
    Unified client wrapper that routes completions through your preferred providers,
    falling back dynamically if keys are missing or requests fail.
    """
    def __init__(self):
        self.chain = settings.llm_fallback_providers

    def _is_valid_key(self, key: str) -> bool:
        if not key:
            return False
        k = key.strip().lower()
        return k != "" and "your_" not in k

    def chat_completion(self, prompt: str, system_instruction: str = "") -> str:
        """Runs inference through fallback chain list until a success occurs."""
        errors = []
        for provider in self.chain:
            try:
                if provider == "groq" and self._is_valid_key(settings.groq_api_key):
                    return self._call_groq(prompt, system_instruction)
                elif provider == "openai" and self._is_valid_key(settings.openai_api_key):
                    return self._call_openai(prompt, system_instruction)
                elif provider == "gemini" and self._is_valid_key(settings.gemini_api_key):
                    return self._call_gemini(prompt, system_instruction)
                elif provider == "openrouter" and self._is_valid_key(settings.openrouter_api_key):
                    return self._call_openrouter(prompt, system_instruction)
            except Exception as e:
                err_msg = f"{provider.upper()} call failed: {str(e)}"
                print(f"[LLM Fallback] Warning: {err_msg}")
                errors.append(err_msg)
        
        raise RuntimeError(f"All LLM providers in chain failed: {'; '.join(errors)}")

    def _call_groq(self, prompt: str, system: str) -> str:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"}
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        payload = {"model": settings.groq_model, "messages": messages, "temperature": 0.2}
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()

    def _call_openai(self, prompt: str, system: str) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": settings.openai_model, "messages": messages, "temperature": 0.2}
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()

    def _call_gemini(self, prompt: str, system: str) -> str:
        # Google Gemini REST completion endpoint
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        headers = {"Content-Type": "application/json"}
        
        # Structure systemInstruction block
        contents = [{"parts": [{"text": prompt}]}]
        payload = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    def _call_openrouter(self, prompt: str, system: str) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": settings.openrouter_model, "messages": messages, "temperature": 0.2}
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()

# Global LLM instance
llm = ModularLLMClient()
