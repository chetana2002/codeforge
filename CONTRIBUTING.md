# Contributing to CodeForge

CodeForge is a portfolio project built to demonstrate production-grade software
engineering practices. Contributions, issues, and suggestions are welcome.

## Development workflow

1. Fork and clone the repository.
2. `cp .env.example .env` and adjust values if needed.
3. `docker compose up --build` to start the full stack, or run individual
   services locally (see [README.md](README.md#local-development)).
4. Make your change in the relevant service (`frontend/`, `backend/`, `worker/`).
5. Run the checks for that service before opening a PR:

   ```bash
   # backend / worker
   ruff check .
   black --check .
   mypy app          # backend only
   pytest -v

   # frontend
   npm run lint
   npx tsc --noEmit
   npm run build
   ```

6. Open a pull request against `main`. CI (`.github/workflows/ci.yml`) runs the
   same checks automatically.

## Code style

- **Python**: type hints everywhere, `ruff` + `black` for formatting, `mypy --strict`
  on the backend. Follow the existing clean-architecture layering
  (`api/` → `application/` → `domain/` / `infrastructure/`) — keep business logic
  out of route handlers.
- **TypeScript**: strict mode, ESLint + the Next.js config. Prefer small,
  composable components under `features/<domain>/`.

## Commit messages

Keep them focused and descriptive of *why*, not just *what*. Reference the
relevant phase or feature area where useful (e.g. `execution: add timeout enforcement to sandbox runner`).

## Reporting issues

Please include: what you expected, what happened instead, and steps to
reproduce (including whether you're running via Docker Compose or standalone).
