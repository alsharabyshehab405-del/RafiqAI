# RafiqAI Security

## Threat model

RafiqAI treats user content, files, web pages, retrieved sources and model output as untrusted. Provider credentials and database credentials remain server-side.

## Controls

- Argon2 password hashing.
- Short-lived access JWTs.
- Rotating/revocable refresh tokens.
- Resource ownership checks and admin RBAC.
- Distributed rate limiting through Redis in production.
- Strict CORS and security headers.
- Request IDs and audit events.
- File size/type/signature validation and ZIP expansion limits.
- Optional ClamAV scanning.
- Object storage instead of database BLOBs.
- Gitleaks, pip-audit and Trivy in CI.
- Prompt-injection defenses and untrusted-context labeling.
- Agent tool allowlists and execution budgets.

## Security acceptance tests

Before production, run API DAST/penetration testing for SSRF, IDOR, broken authorization, credential stuffing, token replay, file upload abuse, XSS/CSRF where applicable, rate-limit bypass, prompt injection and data exfiltration.

## Logging

Never log passwords, access/refresh tokens, provider API keys, service-account JSON, private file contents or sensitive personal data.
