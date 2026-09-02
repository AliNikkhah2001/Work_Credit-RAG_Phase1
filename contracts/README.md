# Cross-Component Contracts

This directory contains versioned JSON Schema contracts for the MVP integration.
Each component should validate requests/responses against these schemas.

## Contracts

| File | Description | Used By |
|------|-------------|---------|
| `rail_check_request.json` | Input/output rail check request | Orchestrator → Guardrails |
| `rail_check_response.json` | Rail check response | Guardrails → Orchestrator |
| `kb_retrieval_request.json` | KB search request | Orchestrator → KB Manager |
| `kb_retrieval_result.json` | Normalized KB result | KB Manager → Orchestrator |
| `orchestrator_chat_response.json` | Public chat API response | Orchestrator → Open WebUI |

## Versioning

Contracts are versioned with the policy version (e.g., `mvp-1`). When contracts change:
1. Update the schema file
2. Update the policy version in component configs
3. Run contract tests in all affected components
4. Update submodule pins in parent repository

## Testing

Each component should have contract tests that validate:
- Requests sent to downstream services match the schema
- Responses received from downstream services match the schema
- Own API responses match the schema

Run contract tests:
```bash
# In each component
pytest tests/contract/ -v
```