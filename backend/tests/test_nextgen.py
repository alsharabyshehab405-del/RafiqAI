import pytest
from app.services.rag import chunk_text, lexical_score, rank_chunks, source_id
from app.services.cost import usage_from_provider
from app.services.ai_platform import ModelRouter
from app.services.agents import AgentEngine, AgentStepSpec, AgentLimits


def test_rag_chunking_and_ranking():
    chunks=chunk_text("alpha beta gamma "*200,size=100,overlap=10)
    assert len(chunks)>1
    ranked=rank_chunks("alpha beta",[{"text":"zeta"},{"text":"alpha beta"}],2)
    assert ranked[0]["text"]=="alpha beta"
    assert source_id("abc")!=source_id("def")


def test_usage_cost(monkeypatch):
    u=usage_from_provider({"prompt_tokens":1000,"completion_tokens":500})
    assert u.input_tokens==1000 and u.output_tokens==500
    assert u.cost_usd>=0

@pytest.mark.asyncio
async def test_agent_executor_budget_and_tools():
    async def search(query): return {"query":query,"ok":True}
    engine=AgentEngine({"search":search})
    result=await engine.execute([AgentStepSpec("find","search",{"query":"rafiq"})],AgentLimits(max_steps=2,max_tool_calls=2,max_seconds=5))
    assert result["events"][0]["status"]=="completed"


def test_model_router_has_plan_profiles():
    r=ModelRouter()
    assert r.choose("free").name
    assert r.choose("premium","analysis").quality>=r.choose("free").quality
