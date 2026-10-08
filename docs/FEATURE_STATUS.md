# RafiqAI Feature Status — Final Engineering Completion

| Feature | Implementation | Android UI | Backend | External dependency | Tests | Production status |
|---|---|---|---|---|---|---|
| Chat | Implemented | Yes | Yes | AI provider | Existing + compile | REQUIRES REAL ENVIRONMENT |
| Projects | Implemented | Yes | Yes | PostgreSQL | Contract tests | REQUIRES REAL ENVIRONMENT |
| Project memory | Implemented | Yes | Yes | PostgreSQL | API contract | REQUIRES REAL ENVIRONMENT |
| File upload | Implemented | Yes | Yes | Object storage/AV scanning as configured | MIME contract | REQUIRES REAL ENVIRONMENT |
| Qdrant lifecycle | Implemented | Via RAG | Yes | Qdrant | Unit/contract | REQUIRES REAL ENVIRONMENT |
| Semantic/Hybrid RAG | Implemented conditionally | Yes | Yes | Embedding provider + Qdrant | Hybrid unit tests | CONFIGURATION REQUIRED |
| RAG citations | Implemented | Yes | Yes | Parser metadata for page/section | Contract tests | REQUIRES REAL ENVIRONMENT |
| Async Agent runtime | Implemented | Yes | Yes | Redis + ARQ + PostgreSQL | Unit/contract | REQUIRES REAL ENVIRONMENT |
| Agent leases/recovery | Implemented | Status UI | Yes | PostgreSQL + Redis | Contract tests | REQUIRES REAL ENVIRONMENT |
| Provider adapters | Implemented | Indirect | Yes | Provider credentials | Contract tests | EXTERNAL PROVIDER REQUIRED |
| Provider streaming | Implemented | Existing stream UI | Yes | Live provider | Contract only | EXTERNAL PROVIDER REQUIRED |
| Gemini native configuration | Implemented | Indirect | Yes | Gemini API | Contract | EXTERNAL PROVIDER REQUIRED |
| Deep Research | Implemented conditionally | Yes | Yes | Search + AI provider | Contract | EXTERNAL PROVIDER REQUIRED |
| Research citation IDs | Implemented | Yes | Yes | Search | Unit/contract | REQUIRES REAL ENVIRONMENT |
| Automation | Implemented conditionally | Yes | Yes | Redis + ARQ | Contract | REQUIRES REAL ENVIRONMENT |
| Memory | Implemented | Yes | Yes | PostgreSQL | Existing tests | REQUIRES REAL ENVIRONMENT |
| Billing | Implemented conditionally | Yes | Yes | Google Play | Existing tests | EXTERNAL PROVIDER REQUIRED |
| Voice | Not implemented as production streaming voice | Partial legacy TTS/STT | Partial | Real streaming voice provider | Not applicable | NOT IMPLEMENTED |
| Image generation | Not implemented | No | No | Provider | Not applicable | NOT IMPLEMENTED |
| Browser Agent | Intentionally not enabled | No | No | Secure sandbox | Not applicable | NOT IMPLEMENTED |
| 2FA / Passkeys / OAuth | Not complete | No | No | Identity providers | Not applicable | NOT IMPLEMENTED |

### Allowed status vocabulary
- IMPLEMENTED + USER ACCESSIBLE
- IMPLEMENTED BACKEND ONLY
- CONFIGURATION REQUIRED
- EXTERNAL PROVIDER REQUIRED
- NOT IMPLEMENTED
- TESTED PASSED
- TESTED FAILED
- REQUIRES REAL ENVIRONMENT
