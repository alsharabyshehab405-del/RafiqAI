import re
from dataclasses import dataclass

@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reasons: list[str]
    redacted_text: str

_INJECTION = re.compile(r"(?i)(ignore\s+(?:all|any|previous|prior)(?:\s+(?:all|any|previous|prior))?\s+instructions|system\s+prompt|developer\s+message|reveal\s+(your|the)\s+instructions|jailbreak|disable\s+safety)")
_SECRET = re.compile(r"(?i)\b(sk-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,})\b")
_EMAIL = re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")

def inspect_input(text: str) -> SafetyDecision:
    reasons=[]
    if _INJECTION.search(text): reasons.append("prompt_injection_signal")
    redacted=_SECRET.sub("[REDACTED_SECRET]",text)
    redacted=_EMAIL.sub("[REDACTED_EMAIL]",redacted)
    if redacted != text: reasons.append("sensitive_data_detected")
    return SafetyDecision(not any(r == "prompt_injection_signal" for r in reasons),reasons,redacted)

def validate_tool_url(url: str, allowed_domains: list[str]) -> None:
    from urllib.parse import urlparse
    p=urlparse(url)
    if p.scheme not in {"http","https"}: raise ValueError("unsupported URL scheme")
    host=(p.hostname or "").lower()
    if not host: raise ValueError("missing host")
    if allowed_domains and not any(host == d or host.endswith("."+d) for d in allowed_domains):
        raise PermissionError("domain not allowlisted")
