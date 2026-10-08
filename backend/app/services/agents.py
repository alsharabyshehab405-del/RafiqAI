import asyncio, uuid
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class AgentStepSpec:
    name: str
    tool: str
    args: dict

@dataclass
class AgentLimits:
    max_steps: int=8
    max_tool_calls: int=12
    max_seconds: int=90
    max_tokens: int=12000

class AgentBudgetExceeded(RuntimeError): pass

class AgentEngine:
    def __init__(self, tools: dict): self.tools=tools

    async def execute_step(self, step:AgentStepSpec, timeout:int):
        spec=self.tools.get(step.tool)
        if spec is None: raise ValueError(f"unsupported tool: {step.tool}")
        return await asyncio.wait_for(spec.execute(**step.args), timeout=min(timeout,spec.timeout_seconds))

    async def execute(self, plan, limits, start_index=0, cancel_check=None, on_event=None, initial_tool_calls=0, initial_tokens=0):
        started=datetime.now(timezone.utc); calls=initial_tool_calls; total_tokens=initial_tokens; events=[]
        for index,step in enumerate(plan[start_index:limits.max_steps],start_index+1):
            if cancel_check and await cancel_check():
                event={"step":index,"status":"cancelled","tool":step.tool}; events.append(event)
                if on_event: await on_event(event)
                return {"run_id":uuid.uuid4().hex,"events":events,"status":"cancelled","last_step":index-1,"tool_calls":calls,"total_tokens":total_tokens}
            elapsed=(datetime.now(timezone.utc)-started).total_seconds()
            if elapsed>limits.max_seconds: raise TimeoutError("agent execution budget exceeded")
            spec=self.tools.get(step.tool)
            if spec is None: raise ValueError(f"unsupported tool: {step.tool}")
            step_event={"step":index,"status":"running","tool":step.tool,"attempt":0}; events.append(step_event)
            if on_event: await on_event(step_event)
            result=None; succeeded=False
            max_attempts=3 if getattr(spec,'safe_to_retry',False) and getattr(spec,'idempotent',False) else 1
            for attempt in range(1,max_attempts+1):
                calls += 1
                if calls>limits.max_tool_calls: raise AgentBudgetExceeded("tool call budget exceeded")
                step_event["attempt"]=attempt
                if on_event: await on_event({**step_event})
                try:
                    result=await self.execute_step(step,max(1,limits.max_seconds-int((datetime.now(timezone.utc)-started).total_seconds())))
                    succeeded=True; break
                except Exception as exc:
                    if attempt>=max_attempts: raise
                    await asyncio.sleep(0.5*(2**(attempt-1)))
            if succeeded:
                estimated=max(1,len(str(result))//4)
                total_tokens += estimated
                if total_tokens>limits.max_tokens: raise AgentBudgetExceeded("token budget exceeded")
                done={"step":index,"status":"completed","tool":step.tool,"result":result,"attempt":step_event["attempt"],"estimated_tokens":estimated}
                events[-1]=done
                if on_event: await on_event(done)
        return {"run_id":uuid.uuid4().hex,"events":events,"status":"completed","last_step":events[-1]["step"] if events else start_index,"tool_calls":calls,"total_tokens":total_tokens}
