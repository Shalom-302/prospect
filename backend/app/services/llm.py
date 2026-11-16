"""Client LLM générique compatible OpenAI (Mistral, DeepSeek, Groq, OpenRouter, Ollama, OpenAI…)."""
import json
import re

from openai import OpenAI

from ..config import get_settings


class LLMNotConfigured(RuntimeError):
    pass


def _client() -> OpenAI:
    s = get_settings()
    if not s.llm_configured:
        raise LLMNotConfigured("LLM non configuré : renseigner LLM_BASE_URL, LLM_API_KEY et LLM_MODEL dans .env")
    return OpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key, timeout=120)


def model_name() -> str:
    return get_settings().llm_model


def chat(system: str, user: str, temperature: float | None = None, max_tokens: int = 2500) -> str:
    s = get_settings()
    resp = _client().chat.completions.create(
        model=s.llm_model,
        temperature=s.llm_temperature if temperature is None else temperature,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return (resp.choices[0].message.content or "").strip()


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_json(text: str) -> dict:
    """Extrait un objet JSON d'une réponse, même entourée de texte ou de ```json."""
    m = _FENCE.search(text)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Réponse LLM sans JSON exploitable")
    return json.loads(text[start : end + 1])


def chat_json(system: str, user: str, max_tokens: int = 2000) -> dict:
    raw = chat(system + "\n\nRéponds UNIQUEMENT avec un objet JSON valide, sans texte autour.", user, temperature=0.1, max_tokens=max_tokens)
    try:
        return parse_json(raw)
    except (ValueError, json.JSONDecodeError):
        # Une seconde tentative en demandant explicitement de corriger
        raw = chat("Tu convertis une réponse en JSON strictement valide. Rien d'autre.", raw, temperature=0, max_tokens=max_tokens)
        return parse_json(raw)
