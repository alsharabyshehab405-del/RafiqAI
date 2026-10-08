from dataclasses import dataclass
from typing import Any, Awaitable, Callable
import httpx, socket, ipaddress
from urllib.parse import urlparse
from ..config import settings
from .safety import validate_tool_url
from .search import web_search

@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    schema: dict
    permissions: tuple[str,...]
    risk_level: str
    timeout_seconds: int
    execute: Callable[..., Awaitable[dict]]
    idempotent: bool = True
    safe_to_retry: bool = True
    side_effect_level: str = "LOW"

async def search_tool(query: str, limit: int = 5):
    return {"results": await web_search(query, limit)}

async def fetch_tool(url: str):
    allowed=[x.strip().lower() for x in settings.browser_allowed_domains.split(',') if x.strip()]
    validate_tool_url(url,allowed)
    host=(urlparse(url).hostname or '').lower()
    try:
        for item in socket.getaddrinfo(host,None):
            ip=ipaddress.ip_address(item[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved: raise PermissionError("private network target blocked")
    except socket.gaierror as exc: raise ValueError("host resolution failed") from exc
    async with httpx.AsyncClient(timeout=10, follow_redirects=False, headers={"User-Agent":"RafiqAI/1.0"}) as client:
        r=await client.get(url); r.raise_for_status(); return {"url":str(r.url),"status":r.status_code,"content":r.text[:20000]}

def safe_tool_registry():
    return {
      "search": ToolSpec("search","Search the web",{"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"integer"}}},("web.search",),"LOW",15,search_tool,True,True,"LOW"),
      "fetch": ToolSpec("fetch","Fetch an allowlisted public URL",{"type":"object","properties":{"url":{"type":"string","format":"uri"}}},("web.fetch",),"MEDIUM",15,fetch_tool,True,True,"LOW"),
    }
