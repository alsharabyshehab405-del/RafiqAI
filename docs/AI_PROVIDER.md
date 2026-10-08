# AI Provider Strategy

Required server variables:

- `AI_BASE_URL`
- `AI_API_KEY`
- `AI_MODEL`
- `AI_PRO_MODEL`
- `AI_PREMIUM_MODEL`
- optional fallback provider variables

The Android app never receives provider credentials.

## Routing

`ModelRouter` selects a profile using plan, task type and speed/quality preference. Simple Free requests use the cheapest configured model; Pro/Premium can use higher-quality models.

## Reliability

- exponential retry for transient provider failures
- circuit breaker
- timeout
- provider fallback
- streaming without fallback after content has already been emitted

## Structured output and tools

`structured_chat()` requests JSON Schema output when supported. `tool_call_chat()` returns tool calls without executing them. The Agent Engine performs allowlist checks and budget enforcement before execution.

## Cost

Provider usage is recorded in `UsageLedger`. Configure `AI_INPUT_COST_PER_1K` and `AI_OUTPUT_COST_PER_1K` with the actual provider prices used by production.
