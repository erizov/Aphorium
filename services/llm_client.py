"""Chat-completions helper for local or OpenAI-backed news generation."""

import re
from typing import Dict, List, Optional, Sequence

import requests
from openai import APIError, OpenAI

from config import settings
from logger_config import logger


def _strip_code_fence(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def _sanitize_error(value: object) -> str:
    """Avoid leaking API keys in logs or HTTP responses."""
    text = str(value)
    return re.sub(r"sk-[^\s'\",}]+", "sk-***", text)


def _provider_order() -> List[str]:
    """
    Decide which LLM backend(s) to try.

    `auto` intentionally uses OpenAI first when OPENAI_API_KEY is present so
    users can enable news generation by adding one env var.
    """
    provider = (settings.llm_provider or "auto").strip().lower()
    has_openai = bool(settings.openai_api_key)

    if provider == "openai":
        return ["openai", "openai_direct"]
    if provider == "local":
        order = ["local"]
        if settings.llm_cloud_fallback_enabled and has_openai:
            order.extend(["openai", "openai_direct"])
        return order
    if provider != "auto":
        logger.warning("Unknown llm_provider=%s; using auto", provider)

    if has_openai:
        return ["openai", "openai_direct"]
    return ["local"]


def _chat_with_local(
    messages: Sequence[Dict[str, str]],
    *,
    max_tokens: int,
    temperature: float,
) -> str:
    local_key = settings.local_llm_api_key or "ollama"
    local_client = OpenAI(
        base_url=settings.local_llm_base_url,
        api_key=local_key,
        timeout=settings.llm_timeout_seconds,
    )
    resp = local_client.chat.completions.create(
        model=settings.local_llm_model,
        messages=list(messages),
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()


def _chat_with_openai(
    messages: Sequence[Dict[str, str]],
    *,
    max_tokens: int,
    temperature: float,
) -> str:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    cloud = OpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.llm_timeout_seconds,
    )
    resp = cloud.chat.completions.create(
        model=settings.openai_model,
        messages=list(messages),
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()


def _chat_with_openai_direct(
    messages: Sequence[Dict[str, str]],
    *,
    max_tokens: int,
    temperature: float,
) -> str:
    """
    Call OpenAI REST directly with proxy env vars ignored.

    This helps when a local proxy or SDK transport configuration fails. It
    cannot recover from an invalid API key.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    session = requests.Session()
    session.trust_env = False
    resp = session.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.openai_model,
            "messages": list(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=settings.llm_timeout_seconds,
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"OpenAI direct HTTP {resp.status_code}: {resp.text[:500]}"
        )
    data = resp.json()
    return (data["choices"][0]["message"]["content"] or "").strip()


def chat_complete(
    messages: List[Dict[str, str]],
    *,
    max_tokens: Optional[int] = None,
    temperature: float = 0.6,
) -> str:
    """
    Run a chat completion against the configured LLM.

    Uses OpenAI when OPENAI_API_KEY is present (`LLM_PROVIDER=auto`), or the
    configured local OpenAI-compatible endpoint when no cloud key is present.

    Args:
        messages: OpenAI-style chat messages.
        max_tokens: Upper bound on completion tokens.
        temperature: Sampling temperature.

    Returns:
        Assistant message content (stripped).

    Raises:
        RuntimeError: If every configured backend fails.
    """
    cap = max_tokens or settings.llm_max_output_tokens
    errors: List[str] = []

    for provider in _provider_order():
        try:
            if provider == "openai":
                content = _chat_with_openai(
                    messages,
                    max_tokens=cap,
                    temperature=temperature,
                )
            elif provider == "openai_direct":
                content = _chat_with_openai_direct(
                    messages,
                    max_tokens=cap,
                    temperature=temperature,
                )
            else:
                content = _chat_with_local(
                    messages,
                    max_tokens=cap,
                    temperature=temperature,
                )
            if content:
                return content
            errors.append(f"{provider} LLM returned empty content")
        except APIError as exc:
            clean = _sanitize_error(exc)
            errors.append(f"{provider} LLM APIError: {clean}")
            logger.warning("%s LLM request failed: %s", provider, clean)
        except Exception as exc:
            clean = _sanitize_error(exc)
            errors.append(f"{provider} LLM error: {clean}")
            logger.warning(
                "%s LLM request failed: %s",
                provider,
                clean,
            )

    raise RuntimeError("; ".join(errors) or "LLM completion failed")


def chat_complete_json(
    messages: List[Dict[str, str]],
    *,
    max_tokens: Optional[int] = None,
    temperature: float = 0.2,
) -> str:
    """
    Like chat_complete but encourages JSON-only output for downstream parsing.
    """
    raw = chat_complete(
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return _strip_code_fence(raw)
