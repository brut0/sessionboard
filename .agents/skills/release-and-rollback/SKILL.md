---
name: release-and-rollback
description: >-
  Use this skill when promoting SessionBoard from dev to prod, rolling back an environment, checking
  which version is deployed, or running the synthetic probe. Covers the GitHub Actions workflows
  deploy-prod.yml, rollback.yml, synthetic-probe.yml and how to pick the right commit SHA.
---

# Release and rollback

Requires `gh` authenticated and repository variables `DEV_URL`, `PROD_URL`.

## What is deployed?
```bash
curl -fsS "$DEV_URL/api/version"     # {"version":"<sha>","env":"dev"}
curl -fsS "$PROD_URL/api/version"
```
On Render free, the first request after idle may take up to ~60 s (cold start). Retry before concluding the service is down.

## Promote dev → prod
1. Take the SHA currently on dev (above) and confirm its `cd-dev.yml` run is green: `gh run list --workflow cd-dev.yml --limit 5`.
2. `gh workflow run deploy-prod.yml -f sha=<sha>`
3. The human approves the `production` environment in the Actions UI.
4. `gh run watch` until success; then check `$PROD_URL/api/version` shows `<sha>`.

## Roll back
1. Find the target: the previous main commit whose image exists.
   ```bash
   CUR=<currently deployed sha>
   git fetch origin main
   for SHA in $(git rev-list --first-parent --max-count=6 "$CUR" | tail -n +2); do
     docker manifest inspect "ghcr.io/<owner>/sessionboard:$SHA" >/dev/null 2>&1 && { echo "$SHA"; break; }
   done
   ```
2. `gh workflow run rollback.yml -f env=dev -f sha=<target>` (prod requires approval).
3. Verify `/api/version` shows `<target>` and comment the rollback on the related issue.
4. Rollback is mitigation, not a fix: open/track a fix issue. The next merge to main redeploys dev.

## Synthetic probe
- Once: `gh workflow run synthetic-probe.yml -f mode=once`
- Load for alert testing (15 min): `gh workflow run synthetic-probe.yml -f mode=burst`
- Locally: `python scripts/synthetic_probe.py --base-url http://localhost:8000 --mode once`

## Never
- Never deploy an image that has not passed CI.
- Never run destructive SQL or down-migrations as part of a rollback.
- Never print deploy-hook URLs or tokens in logs or comments.
