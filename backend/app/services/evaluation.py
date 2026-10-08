from dataclasses import dataclass, asdict
import json, re
from pathlib import Path

@dataclass
class EvalCase:
    id: str
    category: str
    prompt: str
    expected: str
    checks: list[str]

@dataclass
class EvalResult:
    passed: bool
    score: float
    case_id: str
    category: str
    reasons: list[str]

def load_golden(path: str) -> list[EvalCase]:
    rows=json.loads(Path(path).read_text(encoding="utf-8"))
    return [EvalCase(**r) for r in rows]

def evaluate_text(case: EvalCase, actual: str) -> EvalResult:
    reasons=[]; checks=case.checks or []
    low=actual.lower()
    for check in checks:
        if check.startswith("contains:"):
            needle=check.split(":",1)[1].strip().lower()
            if needle not in low: reasons.append("missing_required_phrase")
        elif check == "nonempty" and not actual.strip(): reasons.append("empty_output")
        elif check == "no_fake_citation" and re.search(r"\[[0-9]+\]\([^)]*\)",actual):
            reasons.append("citation_requires_source_validation")
    score=max(0.0,1.0-len(reasons)/max(1,len(checks)))
    return EvalResult(not reasons,score,case.id,case.category,reasons)

def aggregate(results):
    score=sum(x.score for x in results)/max(1,len(results))
    return {"status":"PASSED" if all(x.passed for x in results) else "FAILED","score":round(score,4),"cases":len(results),"results":[asdict(x) for x in results]}
