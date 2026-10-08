from dataclasses import dataclass
from ..config import settings

@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    cost_usd: float

def usage_from_provider(data: dict) -> Usage:
    i=int(data.get("prompt_tokens", data.get("input_tokens", 0))); o=int(data.get("completion_tokens", data.get("output_tokens", 0)))
    return Usage(i,o,(i/1000)*settings.ai_input_cost_per_1k+(o/1000)*settings.ai_output_cost_per_1k)
