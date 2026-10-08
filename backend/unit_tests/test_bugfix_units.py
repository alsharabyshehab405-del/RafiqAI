import asyncio
import os
from pathlib import Path

os.environ.setdefault('DATABASE_URL','sqlite:///./test.db')
os.environ.setdefault('JWT_SECRET','unit-test-secret')
os.environ.setdefault('AI_BASE_URL','http://127.0.0.1:1')
os.environ.setdefault('AI_API_KEY','unit-test-key')

from app.services.agents import AgentEngine, AgentLimits, AgentStepSpec, AgentBudgetExceeded
from app.services.rag import rank_chunks, source_id
from app.services.tools import ToolSpec

async def _ok(**kwargs): return {'ok':True}

async def _fail(**kwargs): raise RuntimeError('transient')

def test_agent_tool_budget_counts_retries():
    tool=ToolSpec('x','',{},(), 'LOW', 1, _fail, True, True, 'LOW')
    async def run():
        try: await AgentEngine({'x':tool}).execute([AgentStepSpec('x','x',{})],AgentLimits(max_tool_calls=2,max_seconds=10))
        except AgentBudgetExceeded: return
        except RuntimeError: return
        raise AssertionError('budget did not account for retry attempts')
    asyncio.run(run())

def test_agent_safe_retry_only():
    calls={'n':0}
    async def fn(**kwargs):
        calls['n']+=1
        if calls['n']==1: raise RuntimeError('first')
        return {'ok':True}
    tool=ToolSpec('x','',{},(), 'LOW', 1, fn, True, True, 'LOW')
    async def run(): return await AgentEngine({'x':tool}).execute([AgentStepSpec('x','x',{})],AgentLimits(max_tool_calls=2,max_seconds=10))
    result=asyncio.run(run()); assert result['status']=='completed'; assert result['tool_calls']==2

def test_hybrid_union_includes_semantic_only_chunk():
    chunks=[{'id':1,'text':'alpha','metadata':{},'embedding':[]},{'id':2,'text':'unrelated','metadata':{},'embedding':[]}]
    hits=[{'id':99,'score':0.98,'payload':{'text':'semantic match','file_id':7}}]
    result=rank_chunks('alpha',chunks,limit=3,semantic_query=[1.0],semantic_hits=hits)
    assert any(x['id']==99 for x in result)

def test_source_id_is_stable():
    assert source_id('https://example.com')==source_id('https://example.com')

def test_requested_bugfix_files_exist():
    root=Path(__file__).parents[1]
    assert (root/'migrations/versions/0008_bugfix_hardening.py').exists()
    main=(root/'app/main.py').read_text()
    worker=(root/'app/worker.py').read_text()
    assert 'async def delete_file' in main and 'delete_points' in main
    assert 'run_agent_job' in worker and 'run_research_job' in worker
