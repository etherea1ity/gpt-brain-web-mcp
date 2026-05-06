from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTION = "[REDACTED]"
PATTERNS = [
    re.compile(r"(?i)(Authorization\s*:\s*Bearer\s+)[A-Za-z0-9._\-+/=]+"),
    re.compile(r"(?i)(Authorization\s*:\s*Basic\s+)[A-Za-z0-9._\-+/=]+"),
    re.compile(r"(?im)^(\s*(?:Cookie|Set-Cookie)\s*:\s*)[^\r\n]+"),
    re.compile(r"(?i)\b((?:__Secure-|__Host-)?[A-Za-z0-9_.-]*(?:session|sess|csrf|xsrf|auth)[A-Za-z0-9_.-]*\s*=\s*)[^;\s]+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]+"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9_]{8,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{12,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{12,20}\b"),
    re.compile(r"(?im)^\s*(OPENAI_API_KEY|ANTHROPIC_API_KEY|GITHUB_TOKEN|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|API_KEY|ACCESS_TOKEN|SECRET_KEY|PASSWORD|PRIVATE_KEY)\s*=\s*.+$"),
    re.compile(r"(?i)\b(openai_api_key|anthropic_api_key|github_token|aws_secret_access_key|api_key|access_token|secret_key|password|private_key)\b\s*[:=]\s*['\"]?[^'\"\s]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
]
KEY_HINTS = ("token", "secret", "password", "api_key", "authorization", "private_key", "cookie")
URL_RE = re.compile(r"https?://[^\s)\]>\"']+")
SENSITIVE_QUERY_HINTS = (
    "token",
    "secret",
    "signature",
    "sig",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "access_key",
    "auth",
    "session",
    "credential",
    "client_secret",
    "code",
)


def _redact_url(raw_url: str) -> str:
    trailing = ""
    while raw_url and raw_url[-1] in ".,;":
        trailing = raw_url[-1] + trailing
        raw_url = raw_url[:-1]
    try:
        parts = urlsplit(raw_url)
    except ValueError:
        return raw_url + trailing
    netloc = parts.netloc
    if "@" in netloc:
        # Avoid leaking userinfo embedded in URLs.
        host = netloc.rsplit("@", 1)[1]
        netloc = f"{REDACTION}@{host}"
    query = parse_qsl(parts.query, keep_blank_values=True)
    changed = False
    redacted_query: list[tuple[str, str]] = []
    for key, value in query:
        key_l = key.lower()
        if any(h in key_l for h in SENSITIVE_QUERY_HINTS) or key_l.startswith(("x-amz-", "x-goog-", "x-oss-")):
            redacted_query.append((key, REDACTION))
            changed = True
        else:
            redacted_query.append((key, value))
    if not changed and netloc == parts.netloc:
        return raw_url + trailing
    return urlunsplit((parts.scheme, netloc, parts.path, urlencode(redacted_query, doseq=True), parts.fragment)) + trailing


def redact_text(text: str | None) -> str:
    out = "" if text is None else str(text)
    for pat in PATTERNS:
        def repl(m: re.Match[str]) -> str:
            if m.lastindex:
                return f"{m.group(1)}{REDACTION}"
            raw = m.group(0)
            if "=" in raw or ":" in raw:
                sep = "=" if "=" in raw else ":"
                return raw.split(sep, 1)[0] + sep + REDACTION
            return REDACTION
        out = pat.sub(repl, out)
    out = URL_RE.sub(lambda m: _redact_url(m.group(0)), out)
    return out


def redact_obj(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {k: (REDACTION if any(h in str(k).lower() for h in KEY_HINTS) else redact_obj(v)) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_obj(v) for v in value]
    return value
