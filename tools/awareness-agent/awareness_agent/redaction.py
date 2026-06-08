from __future__ import annotations

import re
from typing import Any

_KEY_VALUE = re.compile(
    r"(?i)\b(api[_-]?key|token|password|passwd|secret|credential)\b"
    r"(\s*[:=]\s*)"
    r"([\"']?)"
    r"([^\"'\s]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+\b")
_GITHUB_PAT = re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")
_OPENAI_LIKE = re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")
_ANTHROPIC_LIKE = re.compile(r"\bsk-ant-[A-Za-z0-9._-]{20,}\b")
_URL_CREDS = re.compile(r"\b(https?://)([^/\s:@]+):([^/\s@]+)@")


def redact_text(value: object) -> str:
    """Conservative local redaction before persistence/logging."""
    if value is None:
        return ""

    text = str(value)
    text = _URL_CREDS.sub(lambda m: f"{m.group(1)}{m.group(2)}:***@", text)
    text = _KEY_VALUE.sub(lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}***", text)
    text = _BEARER.sub("Bearer ***", text)
    text = _GITHUB_PAT.sub("gh*_***", text)
    text = _ANTHROPIC_LIKE.sub("sk-ant-***", text)
    text = _OPENAI_LIKE.sub("sk-***", text)
    return text


def redact_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): redact_mapping(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_mapping(v) for v in value]
    if isinstance(value, tuple):
        return [redact_mapping(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
