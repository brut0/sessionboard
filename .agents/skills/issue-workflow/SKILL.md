---
name: issue-workflow
description: >-
  Use this skill whenever an agent starts, progresses, or finishes work on a SessionBoard GitHub issue:
  claiming the issue, creating the branch, committing with agent trailers, opening the PR with the
  template, and leaving tracker evidence. Required for every code or docs change in this repository.
---

# Issue workflow

All commands run from the repository root with an authenticated `gh` CLI.

## 1. Claim
```bash
gh issue view <N>                      # read ACs, spec refs, role label
gh issue comment <N> --body "[<role>-agent] Starting. Plan: <3-5 bullets>. Branch: <branch>"
git switch main && git pull --ff-only
git switch -c <type>/<N>-<slug>         # type: feat|test|ci|docs|fix
```
If the issue's `agent:*` label is not your role, stop and report to the orchestrator.

## 2. Work
- TDD: commit the failing test, then the implementation.
- Commit message format (Conventional Commits + trailers):
  ```
  feat: detect room conflicts

  Agent: <role>-agent
  Refs: #<N>
  ```
- Before pushing: run the gate commands from skill `phase-gate` that apply to the files you touched.

## 3. Open the PR
```bash
git push -u origin HEAD
gh pr create --title "<type>: <summary> (#<N>)" --body-file .pr-body.md --label agent:<role>
```
`.pr-body.md` follows `.github/pull_request_template.md` and must contain `Closes #<N>`, the AC checklist
(all checked), tests added, spec/contract changes, and the gate output. Delete `.pr-body.md` after use (never commit it).

## 4. Finish
```bash
gh issue comment <N> --body "[<role>-agent] Done. PR #<M>. Evidence: <tests passed x/y, lint ok, hygiene ok>"
```
Then hand the PR to the Reviewer agent. After "request changes": fix on the same branch, push, comment on the PR what changed.

## 5. Blocked
```bash
gh issue comment <N> --body "[<role>-agent] Blocked: <reason>. Need: <decision or credential>"
```
Stop and report to the orchestrator. Do not work around missing credentials or spec gaps.

## Verify
`gh pr view <M> --json body,labels,closingIssuesReferences` shows the issue in `closingIssuesReferences`.
