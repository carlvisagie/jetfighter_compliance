# Pilot Restore Point

**Release Tag**: `pilot-ready-v1`
**Commit SHA**: `9d7d0a1269891573d52b55c9084fd9f31d93b13e`

## Rollback Command
If the pilot environment experiences instability, instantly revert the codebase to this baseline using:
```bash
git reset --hard 9d7d0a1269891573d52b55c9084fd9f31d93b13e
```

## Recovery Steps
1. Stop the application services.
2. Execute the rollback command.
3. Verify test suite: `python -m pytest` (Must be exactly 1046/1046 passed).
4. Restart services.

## Critical Files
* `services/cognition/reasoning.py` (Identity Anchor Rules)
* `services/evidence_intelligence/ocr.py` (OCR Safety Harness)
* `tests/test_cognition_reasoning.py` (Cognition Guardrails)
* `tests/test_stripe_ban_guardrail.py` (Payment Guardrail)