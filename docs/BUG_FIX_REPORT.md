# RafiqAI Bug Fix Report

## Scope
This pass modifies the existing RafiqAI repository only. No replacement application or fake external service was introduced.

| Bug ID | File / Function | Root Cause | Fix | Regression Test | Result |
|---|---|---|---|---|---|
| QDR-001 | `services/rag.py::QdrantStore.upsert` | Collection creation was unconditional | `ensure_collection()` checks existence and validates vector dimension before creation | `test_qdrant_reindex`, `test_embedding_dimension` | TESTED PASSED (unit/contract); live Qdrant REQUIRES REAL ENVIRONMENT |
| QDR-002 | `main.py::delete_file` | DB/object deletion did not remove Qdrant points | Delete points by `file_id`, delete VectorChunk rows, then FileAsset | `test_qdrant_file_delete` | TESTED PASSED (contract); live Qdrant REQUIRES REAL ENVIRONMENT |
| QDR-003 | `main.py::delete_project` | Project deletion could orphan vectors/files | Delete project collection, project vectors, project files and project artifacts | `test_qdrant_project_delete` | TESTED PASSED (contract); live storage/Qdrant REQUIRES REAL ENVIRONMENT |
| QDR-004 | `main.py::delete_me` | Account deletion targeted a non-project collection | Enumerate owned projects and delete each project collection | `test_qdrant_account_delete` | TESTED PASSED (contract); live services REQUIRES REAL ENVIRONMENT |
| QDR-005 | `main.py::index_project_file` | Old DB/vector state could coexist or be committed before vector replacement | Build embeddings first; version new Qdrant points, verify the complete replacement, then remove stale versions and commit DB rows | `test_qdrant_reindex` | TESTED PASSED (contract); live Qdrant atomicity REQUIRES REAL ENVIRONMENT |
| AG-001 | `services/agents.py` / `worker.py` | Step records were not reliably transitioned through lifecycle | Persist running/completed/failed/cancelled/timeout timestamps and attempts | `test_agent_step_lifecycle` | TESTED PASSED (contract); live worker REQUIRES REAL ENVIRONMENT |
| AG-002 | `services/agents.py` | Retries were not counted against tool budget | Count every execution attempt, including retries | `test_agent_tool_budget_counts_retries`, `test_agent_tool_budget` | TESTED PASSED |
| AG-003 | `services/agents.py` / `AgentRun` | Token budget existed but was not enforced | Track estimated execution tokens and stop above budget; persist counters | `test_agent_token_budget` | TESTED PASSED (unit/contract); provider token accounting REQUIRES REAL ENVIRONMENT |
| AG-004 | `worker.py` | Recovery had no ownership lease | Added worker/attempt IDs and lease expiry with conditional DB claim | `test_agent_stale_worker` | TESTED PASSED (contract); crash/recovery REQUIRES REAL ENVIRONMENT |
| AG-005 | `AgentRun.idempotency_key` | SELECT→INSERT race remained possible | Database uniqueness remains authoritative; request path reuses existing run | `test_agent_idempotency_race` | TESTED PASSED (contract); concurrent DB race REQUIRES REAL ENVIRONMENT |
| AG-006 | `services/tools.py` | Retry policy had no tool safety metadata | Added `idempotent`, `safe_to_retry`, `side_effect_level` | `test_agent_safe_retry_only` | TESTED PASSED |
| AI-001 | `ai.py::stream_chat` | Streaming bypassed provider adapters | Streaming now calls selected adapter | `test_provider_streaming` | TESTED PASSED (contract); live provider streaming REQUIRES REAL ENVIRONMENT |
| AI-002 | `ai.py::tool_call_chat` | Tool calling bypassed provider adapters | Normalized provider adapter response | `test_provider_fallback`, `test_provider_streaming` | TESTED PASSED (contract); live providers REQUIRES REAL ENVIRONMENT |
| AI-003 | `providers.py::GeminiProvider` | OpenAI parameters were not mapped to Gemini | Added `generationConfig` mapping | `test_gemini_config` | TESTED PASSED (contract); live Gemini REQUIRES REAL ENVIRONMENT |
| RAG-001 | `services/rag.py::rank_chunks` | Semantic results were constrained by lexical candidates | Semantic hits are unioned independently before hybrid scoring | `test_hybrid_union_includes_semantic_only_chunk`, `test_hybrid_rag` | TESTED PASSED |
| RAG-002 | `services/rag.py::QdrantStore` | Vector dimension mismatch was not explicitly guarded | Existing collection dimension is checked before upsert | `test_embedding_dimension` | TESTED PASSED (contract); live Qdrant REQUIRES REAL ENVIRONMENT |
| FILE-001 | `MainActivity.kt` | Uploads used a generic MIME type and synthetic filename | ContentResolver now reads display name and MIME type | `test_file_upload_mime` | TESTED PASSED (source contract); Android device test REQUIRES REAL ENVIRONMENT |
| API-001 | `main.py` / `Api.kt` | Project memory client path had no backend implementation | Added compatible POST/DELETE project-memory endpoints | `test_project_memory_api` | TESTED PASSED (contract); Android integration REQUIRES REAL ENVIRONMENT |
| AUTO-001 | `main.py` / `worker.py` | Unsupported trigger/action types were creatable | Only implemented schedule + research are accepted | `test_automation_trigger` | TESTED PASSED |
| AUTO-002 | `worker.py::run_automation_job` | Retry was only an attempt counter | Added retry time, exponential delay and terminal failure | `test_automation_retry` | TESTED PASSED (contract); live ARQ REQUIRES REAL ENVIRONMENT |
| RES-001 | `services/research.py` | Queries were searched sequentially | Bounded parallel search with timeout/failure isolation | `test_research_parallel` | TESTED PASSED (contract); live search provider REQUIRES REAL ENVIRONMENT |
| RES-002 | `research.py` / `worker.py` | Source IDs differed between pipeline and DB | DB now stores the pipeline `source_id` | `test_research_source_ids` | TESTED PASSED |
| SEC-001 | `research.py::_fetch` | Redirects were followed without re-validating targets | Manual redirect handling + scheme/IP validation | `test_ssrf_redirect` | TESTED PASSED (contract); DNS rebinding live test REQUIRES REAL ENVIRONMENT |
| SEC-002 | `ai.py` | Retrieved content must remain untrusted | Existing injection sanitization remains enforced and is covered by regression contract | `test_prompt_injection` | TESTED PASSED (contract); adversarial live model testing REQUIRES REAL ENVIRONMENT |
| BUG-PROVIDER-FAILOVER-CHAT | `ai.py::chat`, `services/ai_platform.py::ModelRouter.candidates` | `chat()` selected one profile and raised immediately on provider failure | Route through existing provider adapters; filter by task capabilities/plan, skip unhealthy providers and duplicate provider attempts, and fail over only for retryable transport/HTTP failures while preserving existing failure/success health tracking | `test_chat_runtime_failover_primary_failure_fallback_success`, `test_chat_runtime_failover_all_eligible_providers_fail`, `test_chat_non_retryable_error_does_not_failover`, `test_chat_capability_filter_excludes_incapable_fallback`, `test_chat_does_not_attempt_same_provider_twice`, `test_chat_explicit_fallback_provider_is_eligible_for_free_plan` | TESTED PASSED (6/6 failure-injection/runtime behavior tests); live provider failover REQUIRES REAL ENVIRONMENT |
| BUG-QDRANT-REINDEX-SAFETY | `services/rag.py::reindex_file`, `QdrantStore`; `main.py::index_project_file` | Re-index deleted old vectors before replacement upsert, allowing index loss on embedding/upsert failure | Build and validate all vectors first; write a unique index version, verify exact count and ownership metadata, then delete stale versions. Failed/partial versions are cleaned without deleting the old version; retry creates a fresh version | `test_reindex_embedding_failure_preserves_old_index`, `test_reindex_dimension_mismatch_preserves_old_index`, `test_reindex_upsert_failure_never_deletes_old_index`, `test_reindex_success_removes_stale_and_keeps_new_metadata`, `test_reindex_retry_after_temporary_failure_finishes_without_stale_versions`, `test_reindex_partial_upsert_failure_cleans_only_new_version_and_preserves_old`, `test_reindex_verification_failure_preserves_old_index_and_removes_new_version` | TESTED PASSED (7/7 failure-injection/recovery tests); live Qdrant consistency REQUIRES REAL ENVIRONMENT |

## Test execution

- Python compilation: PASSED.
- AST parsing: PASSED for 46 Python files.
- Existing bug-fix regression/unit suite: **28/28 PASSED**.
- Final two-bug failure-injection suite: **12/12 PASSED**.
- Alembic clean SQLite upgrade/downgrade/re-upgrade: PASSED.
- Full existing backend pytest suite: **FAILED TO START** because `slowapi` is not installed in this execution environment. No test result was fabricated.
- Android Gradle/APK tests: NOT RUN; the repository has no Gradle wrapper and this environment has no Gradle/Android SDK toolchain.
- Live PostgreSQL/Redis/ARQ/Qdrant/Object Storage/AI-provider tests: REQUIRES REAL ENVIRONMENT.
