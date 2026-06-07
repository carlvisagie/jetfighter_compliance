# GitHub Branch Protection — `main`

**Repository:** `carlvisagie/jetfighter_compliance`  
**Canonical branch:** `main`

Configure in GitHub → **Settings → Branches → Branch protection rules** for `main`.

## Required settings

| Rule | Setting | Rationale |
|------|---------|-----------|
| Require pull request | **On** — at least 1 approval recommended | No direct-to-main feature drift |
| Require status checks | **On** — `kyc_guardrails` workflow | pytest + guardrail tests must pass |
| Require branches up to date | **On** | Merge base tested |
| Disable force push | **On** | Prevent history rewrite on production line |
| Disable branch deletion | **On** | `main` is the deploy source |
| Restrict who can push | Owner / designated operators | Reduces accidental production commits |

## Status checks to require

From [`.github/workflows/kyc_guardrails.yml`](../.github/workflows/kyc_guardrails.yml):

- Full or workflow-defined pytest + guardrail suite (must be green before merge).

## Agent / operator rules

- Agents must **not** force-push `main`.
- Agents must **not** bypass failing CI.
- Production deploys trace to merge commits on `main` — record SHA in [`RESTORE_POINT.md`](RESTORE_POINT.md) after each production cut.

## Verification

```bash
gh api repos/carlvisagie/jetfighter_compliance/branches/main/protection
```

If protection is not yet enabled in GitHub UI, treat this document as the **target state** for Patch 11 fortress.
