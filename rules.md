# Avants AI Coding Rules

## 1. Product and Database Safety

- Never manipulate the live/production database or user records through ad hoc scripts.
- Use real application routes and reviewed UI/form flows for data changes.
- Verify `app.config["SQLALCHEMY_DATABASE_URI"]` before running any script that imports the app or may touch the database.
- Prefer `sqlite:///:memory:` or an explicitly resolved scratch SQLite path for isolated tests.
- Never redirect or blank `DATABASE_URL` inside a script.
- Do not use `db.drop_all()`, bulk deletes, or raw production writes for maintenance.
- Preserve the `load_dotenv(override=False)` behavior in app and package configuration.
- Treat existing users and nullable fields as valid states.

## 2. Change Discipline

- Read the relevant route, model, template, and helper before editing.
- Make surgical changes that address the request without unrelated cleanup.
- Preserve existing behavior unless the requirement intentionally changes it.
- Update directly related tests and documentation.
- Do not amend commits unless the user explicitly asks.
- Never revert unrelated worktree changes.
- Use non-destructive, targeted cleanup only.

## 3. Python and Flask

- Keep route handlers thin: validate input, authorize access, call service/model helpers, and render or redirect.
- Use Flask-SQLAlchemy models rather than raw SQL for normal application behavior.
- Use `@login_required` and explicit role/ownership checks for protected routes.
- Return appropriate HTTP status codes and JSON shapes for XHR/fetch endpoints.
- Use the existing app factory and blueprints rather than creating new app instances.
- Register all blueprints from `website/__init__.py`.
- Preserve URL prefixes: blueprints are generally registered at `/`.
- Close database sessions and roll back expected failures after exceptions.
- Add new startup columns through `_run_migrations()` as additive statements.
- Wrap startup migration statements safely for idempotent startup.

## 4. AI Services

- Route all OpenAI/OpenRouter calls through `ai_services.py` or the `ai_service_*.py` modules.
- Do not create provider clients independently inside route handlers.
- Apply a route-level limit to expensive AI and upload operations.
- Log provider failures at the server level.
- Send generic, recoverable error text to users.
- Handle `RateLimitError`, `AuthenticationError`, `APIConnectionError`, and unexpected exceptions separately when behavior differs.
- Preserve Post/Redirect/Get for costly matching flows where reload could repeat AI calls.

## 5. Templates and Frontend

- Continue using Jinja2 server rendering and Bootstrap 5.
- Reuse `website/templates/base.html` and `website/static/css/base.css`.
- Use `/` or absolute filesystem paths correctly in response and documentation, respectively.
- Keep the fixed navbar, Inter typography, 10px card radius, and existing surface palette consistent.
- Use Font Awesome for icons and Bootstrap components for standard controls.
- Avoid adding a frontend build system unless the architecture intentionally changes.
- Keep Jinja expressions out of JavaScript source where possible if they cause editor/parser ambiguity.
- Preserve accessible labels, form names, button types, keyboard focus, and image alt text.
- Use null-safe combined-name properties for human-facing full names; use first names only for greetings or avatar initials.

## 6. Validation and Testing

- No linter or build framework is configured; do not introduce one without a manifest change.
- Existing tests use `unittest` and AST-extracted route functions.
- Run the smallest relevant test command:

```bash
python -m unittest discover -s tests -v
```

- Validate Python syntax with `python -m py_compile` or `compileall` for changed modules.
- Validate Jinja syntax where templates change.
- Use a throwaway SQLite database for route/model tests.
- Never include real credentials or production URLs in test fixtures.
- Add focused tests only for behavior introduced or repaired.

## 7. External Integrations

- Read credentials from environment variables.
- Use `PUBLIC_BASE_URL` or `email_utils.external_url()` for links in emails.
- Never build transactional links with `url_for(_external=True)`.
- Use `send_branded_email()` for shared transactional email formatting.
- Store Stripe webhook verification state only through the existing reviewed webhook flow.
- Keep placement fees, employer subscriptions, and data subscriptions logically separate.
- Tie Daily rooms and proposals to the expected application and parties.
- Treat `uploads/` and `audio/` as scratch storage.

## 8. Naming and Style

- Use descriptive snake_case names for Python variables and functions.
- Use role-oriented blueprint names and endpoint names consistently.
- Keep constants in `models.py` or `config.py` where they are shared.
- Use four-space indentation and clear line breaks.
- Avoid unnecessary comments.
- Add comments only where startup migrations, safety constraints, provider behavior, or non-obvious compatibility need explanation.
- Use `#new change` comments only when required by an explicit existing project convention or request.

## 9. Git and Commits

- When creating a commit, include:

```text
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```
- Do not use destructive Git commands such as reset/checkout without explicit approval.
- Do not amend existing commits unless explicitly requested.
- Inspect diff and status before finalizing.

## 10. Documentation

- Keep `prd.md`, `architecture.md`, `rules.md`, `design.md`, `tasks.md`, and `memory.md` synchronized with major product decisions.
- Use Mermaid diagrams for architecture, flows, or state relationships.
- Record completed work and remaining risks in `tasks.md`.
- Record durable project context and recent decisions in `memory.md`.
- Do not create planning-only Markdown files outside the requested project documents.
