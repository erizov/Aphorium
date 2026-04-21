"""
Chat-completions helper: local OpenAI-compatible API first, optional cloud.
"""

from typing import Dict, List, Optional

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


def chat_complete(
    messages: List[Dict[str, str]],
    *,
    max_tokens: Optional[int] = None,
    temperature: float = 0.6,
) -> str:
    """
    Run a chat completion against the configured LLM.

    Tries local OpenAI-compatible endpoint first; optionally OpenAI cloud.

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
    timeout = settings.llm_timeout_seconds
    errors: List[str] = []

    local_key = settings.local_llm_api_key or "ollama"
    local_client = OpenAI(
        base_url=settings.local_llm_base_url,
        api_key=local_key,
        timeout=timeout,
    )
    try:
        resp = local_client.chat.completions.create(
            model=settings.local_llm_model,
            messages=messages,
            max_tokens=cap,
            temperature=temperature,
        )
        content = (resp.choices[0].message.content or "").strip()
        if content:
            return content
        errors.append("local LLM returned empty content")
    except APIError as exc:
        errors.append(f"local LLM APIError: {exc}")
        logger.warning("Local LLM request failed: %s", exc)
    except Exception as exc:
        errors.append(f"local LLM error: {exc}")
        logger.warning("Local LLM request failed: %s", exc)

    if (
        settings.llm_cloud_fallback_enabled
        and settings.openai_api_key
    ):
        cloud = OpenAI(
            api_key=settings.openai_api_key,
            timeout=timeout,
        )
        try:
            resp = cloud.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=cap,
                temperature=temperature,
            )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return content
            errors.append("cloud LLM returned empty content")
        except Exception as exc:
            errors.append(f"cloud LLM error: {exc}")
            logger.warning("Cloud LLM request failed: %s", exc)

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
