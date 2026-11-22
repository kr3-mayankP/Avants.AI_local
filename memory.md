# Avants AI Project Memory

## 1. Project Identity

Avants AI is a Flask recruiting platform with candidate and employer surfaces, plus an Earn marketplace for paid AI-training micro-tasks and a separate data-buyer/export product.

## 2. Durable Technical Facts

- Primary app entry point: `app.py`.
- App factory: `website.create_app()` in `website/__init__.py`.
- The app is server-rendered Jinja2 with Bootstrap 5 and Font Awesome.
- Python target in production: 3.12.11.
- Production server: Gunicorn, gthread, 4 threads, 300-second timeout.
- No Alembic or Flask-Migrate setup exists.
- Schema changes are startup `ALTER TABLE` statements in `_run_migrations()`.
- PostgreSQL is configured through `DATABASE_URL`; SQLite is the fallback.
- `uploads/` and `audio/` are ephemeral local storage.
- Flask-Login's local `User` table is the primary session identity.
- `supabase_uid` links local users to Supabase identities.
- OpenAI/OpenRouter calls should remain in `ai_services.py` or `ai_service_*.py`.
- Placement fees, employer plans, and data subscriptions are separate Stripe flows.
- Daily.co is used for meeting rooms and cloud recordings.
- Email links must use `PUBLIC_BASE_URL` and `email_utils.external_url()`, not request-host URLs.

## 3. Integration and Configuration

Important environment variables include:

- `SECRET_KEY`
- `DATABASE_URL`
- `PUBLIC_BASE_URL`
- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `OPENROUTER_CHAT_MODEL`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `MAIL_SERVER`
- `MAIL_PORT`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_DATA_PRICE_ID`
- `STRIPE_DATA_WEBHOOK_SECRET`
- `DAILY_API_KEY`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `GOOGLE_CREDENTIALS_JSON`
- `GOOGLE_DRIVE_BACKUP_FOLDER_ID`
- `RESET_REDIRECT_URL`

## 4. Database Safety Memory

The `.env` database URL can point at the real production Supabase/PostgreSQL database. It must never be assumed to be local.

Before a database-touching script:

1. Set a throwaway SQLite path explicitly.
2. Import the app.
3. Print and verify `app.config["SQLALCHEMY_DATABASE_URI"]`.
4. Only then run schema or data operations.

Never run `db.drop_all()`, `db.create_all()`, bulk deletes, or ad hoc row updates against production. `load_dotenv(override=False)` is intentional and must remain unchanged.

## 5. Product Decisions

- Candidate and employer roles use the same `User` table.
- Employer and candidate authentication flows may converge on shared auth verification logic.
- A full name is now derived as first name plus last name through `User.full_name`.
- First-name-only greetings and avatar initials remain intentional.
- Blind hiring should remain a company-level setting.
- Employer plans are represented by `EmployerSubscription` and `PLAN_LIMITS`, but route enforcement must be checked rather than assumed.
- Placement fees are confirmed by candidate hiring confirmation and then represented by Stripe link/payment state.
- Recurring hourly-hire billing is stored on `Application`.
- The Earn marketplace is separate from core hiring and uses task, submission, and contractor models.
- Data-buyer subscription/export behavior is separate from placement fees and employer billing.

## 6. UI Memory

- Base palette uses neutral gray/white surfaces with indigo primary.
- Inter is loaded through Google Fonts.
- Navbar is fixed and 64px tall.
- Main content defaults to 1200px.
- Cards use 10px radius and small neutral shadows.
- Primary actions use indigo; success green; warning amber; error/danger red.
- Shared styling lives in `website/static/css/base.css`.
- Shared navigation and flash-alert markup lives in `website/templates/base.html`.

## 7. Recent Changes

### 2026-11-17

- Added `last_name` to the `User` model and startup migration list.
- Updated signup and profile forms to collect separate names.
- Updated OAuth metadata handling and login fallback name fields.
- Added `User.full_name` as a null-safe combined-name property.
- Updated candidate/public, talent, applicant, meeting, employer, notification, billing, message, and admin name displays.
- Updated employer company settings to edit first and last names separately.
- Updated deletion anonymization and Google OAuth first/family-name handling.
- Removed a broken `from curses import meta` import from auth verification.
- Improved Supabase signup logging to keep browser errors generic.
- Kept the existing first-name-only greeting and avatar behavior.

### 2026-11-19

- Created repository-level project documentation:
  - `prd.md`
  - `architecture.md`
  - `rules.md`
  - `design.md`
  - `tasks.md`
  - `memory.md`

### 2026-11-22

- Replaced the employer dashboard display with a recruiter-focused dashboard. The old template and CSS are retained in comment blocks for review.
- Dashboard KPI cards, application chart, recent activity, open-job list, candidate matches, notifications, and hiring insights use company-scoped database records; candidate names are masked when company blind mode is enabled.
- Added `/employer/dashboard/assistant`, a rate-limited employer-only endpoint. Its AI service receives aggregate hiring context and no candidate personal information.
- Added `tests/test_employer_dashboard.py` using an in-memory SQLite database. Route, blind-mode display, assistant response, and invalid input are covered. Browser/responsive visual verification is still pending.

## 8. Testing Memory

- Existing tests live in `tests/test_community_stats.py`, `tests/test_email_limits.py`, and `tests/test_employer_dashboard.py`.
- Tests use `unittest`.
- The community stats test reads route AST and executes selected functions.
- The email limits test uses an in-memory Flask-Limiter backend.
- No pytest or lint configuration is present.
- The previous app.py test issue involved Windows `cp1252` decoding Unicode text; use UTF-8-safe file reads when editing or adding tests.
- A browser interaction test suite has not been established.
- The existing test command is:

```bash
python -m unittest discover -s tests -v
```

## 9. Open Risks

- PLAN limits may not be enforced in every route.
- Full-name consistency may still need display-by-display verification.
- The additive migration list swallows exceptions, so a migration can appear successful even when a statement failed for a real issue.
- PostgreSQL and SQLite migration syntax is not identical.
- In-process caches assume a single Gunicorn process/memory space.
- Email, provider, Stripe, Daily, backup, and AI integrations require credential and end-to-end verification.
- Local file storage is not durable.
- Existing tests provide narrow coverage and do not replace browser and integration tests.
