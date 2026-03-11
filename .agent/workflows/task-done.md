---
description: Finalize a completed task - update docs, commit, and push to GitHub
---

# Task Done Workflow

Run this workflow every time a task or significant feature is completed.
Replace `[TASK_NUMBER]` and `[SHORT_DESCRIPTION]` with the actual task info.

## What This Does
1. Updates CHANGELOG.md with the changes made
2. Commits all changes with a structured message
3. Pushes to GitHub for backup

---

## Steps

1. Update CHANGELOG.md with the completed task changes (add a new version entry or update the current one with Added/Changed/Deprecated/Security/Fixed sections as appropriate). Use today's date from the system.

2. Update `docs/AI_DEVELOPMENT_RULES.md` if any new architectural constraints were introduced.

3. Create an ADR file in `docs/adr/` if a major architectural decision was made (e.g., technology choice, security policy, data model decision).

4. Stage all changed files:
```bash
cd /Users/irshadiwardhana/Antigravity/AikrutProtoV0-staging3-pdffeature && git add -A
```

5. Commit with a structured message:
```bash
cd /Users/irshadiwardhana/Antigravity/AikrutProtoV0-staging3-pdffeature && git commit -m "feat(task-N): [SHORT_DESCRIPTION]

- Bullet point summary of key changes
- Any BREAKING CHANGES noted explicitly"
```

6. Push to GitHub:
```bash
cd /Users/irshadiwardhana/Antigravity/AikrutProtoV0-staging3-pdffeature && git push origin main
```

7. Confirm to the user with a summary: what was committed, commit hash, and what's next.

---

## Commit Message Format
```
type(scope): short description (max 72 chars)

- Detail 1
- Detail 2
- BREAKING CHANGE: description if applicable
```

**Types:** `feat` | `fix` | `docs` | `refactor` | `chore` | `security`
**Scopes:** `task-N` | `auth` | `api` | `frontend` | `infra` | `docs`

## Notes
- NEVER commit secrets, `.env` files, or `backend/venv/`
- Always check `git status` before committing to avoid surprises
- If `git push` fails due to no remote, notify the user to set up GitHub first
