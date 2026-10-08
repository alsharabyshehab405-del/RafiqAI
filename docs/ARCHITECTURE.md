# RafiqAI Architecture

RafiqAI is upgraded incrementally over the existing Android/FastAPI/PostgreSQL/Redis architecture.

```text
Android (Compose / Room / Repository)
        |
        v
API / Auth / Rate Limit / Observability
        |
        +--> Conversation + Memory + Tasks + Projects
        +--> AI Platform -> Model Router -> Provider Adapters -> AI providers
        +--> Agent Engine -> allowlisted tools -> Search / Fetch / future Browser
        +--> Research -> Search -> Fetch -> Deduplicate -> Rank -> Sources
        +--> Files -> Object Storage -> Parse -> Chunk -> RAG index
        +--> Billing -> Google Play verification -> Server entitlement
        +--> Automation -> Redis/ARQ worker -> notifications
        +--> Analytics / Usage Ledger / Audit
        |
        +--> PostgreSQL / Redis / Object Storage / optional Vector DB
```

## Trust boundaries

Web pages, retrieved files, memories, search results and tool output are untrusted context. They are never treated as system instructions. Sensitive actions require explicit user approval in the agent engine.

## Provider abstraction

AI providers use an OpenAI-compatible adapter today; the interface is intentionally replaceable. Search, storage, billing, notifications and vector storage are also isolated behind service modules.

## Scaling

API instances are stateless. PostgreSQL is the source of truth. Redis handles distributed rate limits/queue coordination. Background jobs run in workers. Files live in object storage, not PostgreSQL blobs. A managed vector database can be enabled through `QDRANT_URL` without changing the application contract.
