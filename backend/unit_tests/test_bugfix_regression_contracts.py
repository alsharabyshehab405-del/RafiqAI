from pathlib import Path
ROOT=Path(__file__).parents[1]
MAIN=(ROOT/'app/main.py').read_text(); WORKER=(ROOT/'app/worker.py').read_text(); RAG=(ROOT/'app/services/rag.py').read_text(); RESEARCH=(ROOT/'app/services/research.py').read_text(); PROVIDERS=(ROOT/'app/services/providers.py').read_text(); TOOLS=(ROOT/'app/services/tools.py').read_text(); API=(ROOT.parent/'app/src/main/java/com/rafiqai/app/data/network/ApiClient.kt').read_text(); MIG=(ROOT/'migrations/versions/0008_bugfix_hardening.py').read_text()

def test_qdrant_file_delete(): assert 'delete_points' in MAIN and 'VectorChunk.file_id==fid' in MAIN
def test_qdrant_project_delete(): assert 'delete_collection(f"{settings.qdrant_collection_prefix}_project_{pid}")' in MAIN
def test_qdrant_account_delete(): assert 'for project in projects:' in MAIN and 'delete_collection(f"{settings.qdrant_collection_prefix}_project_{project.id}")' in MAIN
def test_qdrant_reindex(): assert 'reindex_file' in MAIN and 'await reindex_file(QdrantStore()' in MAIN
def test_agent_step_lifecycle(): assert 'finished_at=now()' in WORKER and 'status="running"' in WORKER
def test_agent_token_budget(): assert 'max_tokens' in WORKER and 'total_tokens' in WORKER and 'token budget exceeded' in (ROOT/'app/services/agents.py').read_text()
def test_agent_tool_budget(): assert 'calls += 1' in (ROOT/'app/services/agents.py').read_text() and 'max_tool_calls' in WORKER
def test_agent_stale_worker(): assert 'lease_until' in WORKER and 'worker_id' in WORKER and 'attempt_id' in WORKER
def test_agent_idempotency_race(): assert 'unique=True' in (ROOT/'app/models.py').read_text() and 'Idempotency-Key' in MAIN
def test_provider_fallback(): assert 'profiles' in (ROOT/'app/ai.py').read_text() and 'for profile in candidates' in (ROOT/'app/ai.py').read_text()
def test_provider_streaming(): assert '.adapter().stream' in (ROOT/'app/ai.py').read_text() and 'streamGenerateContent' in PROVIDERS and 'messages' in PROVIDERS
def test_gemini_config(): assert 'generationConfig' in PROVIDERS and 'maxOutputTokens' in PROVIDERS and 'topP' in PROVIDERS and 'topK' in PROVIDERS
def test_hybrid_rag(): assert 'semantic_hits' in RAG and 'candidates=list(chunks)' in RAG and 'for hit in semantic_hits' in RAG
def test_embedding_dimension(): assert 'embedding dimension mismatch' in RAG and 'len(x.get(\'vector\',[]))!=dim' in RAG
def test_file_upload_mime():
    k=(ROOT.parent/'app/src/main/java/com/rafiqai/app/MainActivity.kt').read_text(); assert 'OpenableColumns.DISPLAY_NAME' in k and 'getType' in k and 'toMediaType()' in k
def test_project_memory_api(): assert '@app.post("/projects/{pid}/memory")' in MAIN and 'projectMemory' in (ROOT.parent/'app/src/main/java/com/rafiqai/app/data/network/Api.kt').read_text()
def test_automation_retry(): assert 'retry_at' in WORKER and 'attempts < 3' in WORKER and 'run_automation_job' in WORKER
def test_automation_trigger(): assert 'data.trigger_type != "schedule"' in MAIN and 'action.get("type") != "research"' in MAIN
def test_research_parallel(): assert 'asyncio.gather' in RESEARCH and 'Semaphore' in RESEARCH
def test_research_source_ids(): assert "source_id'" in RESEARCH and "source_hash=item.get('source_id')" in WORKER
def test_ssrf_redirect(): assert 'follow_redirects=False' in RESEARCH and 'is_private' in RESEARCH and 'redirect_limit' in RESEARCH
def test_prompt_injection(): assert 'INJECTION_PATTERNS' in (ROOT/'app/ai.py').read_text() and 'untrusted' in (ROOT/'app/ai.py').read_text().lower()
def test_migration_hardening(): assert 'agent_runs' in MIG and 'automation_executions' in MIG and 'agent_steps' in MIG
