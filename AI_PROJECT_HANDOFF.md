# Avants AI - AI/Developer Handoff

**Document date:** 2026-11-22
**Purpose:** Paste this file into a new AI coding session or coding app so it can understand the project, current implementation state, remaining work, and safe modification rules.

---

## 1. Paste-ready instruction

You are working on **Avants AI**, a monolithic Flask recruiting and AI-training marketplace.

Before changing code:

1. Read `AGENTS.md`, `rules.md`, `architecture.md`, `prd.md`, and this file.
2. Determine whether the change belongs to Candidate, Employer, Auth, Earn, Admin, Data Marketplace, AI, Billing, Meetings, or shared infrastructure.
3. Use the existing Flask app factory and blueprints.
4. Keep route handlers thin and place shared/provider logic in `ai_services.py` or the `ai_service_*.py` modules.
5. Never modify the production database or production user records through ad hoc scripts.
6. Use an explicit throwaway SQLite database for database-touching tests.
7. Preserve existing behavior and verify only the smallest relevant scope.
8. Do not assume that a model field, Stripe branch, or route means that it has been browser-tested.
9. Do not expose API keys, database URLs, tokens, webhook secrets, or credential values in code or chat.
10. Update directly related documentation and tests after implementation.

The expected code style is Python/Flask/Jinja, server-rendered HTML, Bootstrap 5, and no frontend framework build step.

---

## 2. Product summary

Avants AI combines four connected products:

1. **Candidate recruiting platform**
   - Candidate signup/login
   - Profile and resume management
   - Job discovery and application
   - Resume-to-job matching
   - AI text/voice interviews
   - Interview practice and coaching
   - Saved interview sessions
   - Meetings, messaging, notifications, and referrals

2. **Employer recruiting platform**
   - Employer/company signup
   - Job posting and editing
   - Applicant review and resume scoring
   - Employer notes and candidate feedback
   - Blind hiring
   - Meeting proposals and Daily.co rooms
   - Talent pool and candidate search
   - Hire confirmation, compensation evidence, and placement fees

3. **Earn/AI-training marketplace**
   - Domain-gated professional tasks
   - Ranking, rating, fact-checking, and writing tasks
   - Consensus scoring and agreement calculation
   - Contractor profiles and Stripe payout setup
   - Admin task management and payout operations

4. **Data marketplace**
   - External data-buyer signup
   - Separate Stripe subscription
   - Dataset export/download flows

---

## 3. Current implementation status

### Overall estimate

| Area | Source status | Overall confidence |
|---|---|---|
| Core product implementation | Substantial and feature-rich | High |
| Candidate end-to-end flow | Implemented, partially verified | Medium |
| Employer end-to-end flow | Implemented, partially verified | Medium |
| AI resume/interview features | Implemented and centralized | Medium |
| Earn and admin marketplace | Implemented | Medium |
| Data marketplace | Implemented | Low-Medium |
| Payments and subscriptions | Implemented in code, not end-to-end verified | Low-Medium |
| Live integrations | Configuration and route code exists | Low-Medium |
| Automated test coverage | Minimal | Low |
| Browser/end-to-end verification | Not established | Low |
| Deployment readiness | Deploy configuration exists | Medium |

**Practical estimate:** the repository is approximately a **working beta / late MVP**, not a fully production-verified SaaS. A reasonable implementation-completion range is **70-85%** for source-level features, but production confidence is lower because integrations and browser flows have limited verification.

Do not describe every implemented feature as “fully tested” unless runtime evidence exists.

---

## 4. Verified repository structure

The repository snapshot contains:

- 50 project Python files outside virtual environments
- 76 Jinja HTML templates
- 39 CSS files
- 2 project JavaScript source files
- 22 SQLAlchemy model classes
- 159 route functions discovered from decorators
- 2 existing unittest test modules

Main entry points:

- `app.py` - standalone resume tools and top-level routes
- `website/__init__.py` - app factory, configuration, migrations, blueprint registration
- `website/models.py` - primary database models
- `ai_services.py` - compatibility exports for split AI modules
- `ai_service_documents.py` - document extraction and resume analysis
- `ai_service_matching.py` - job/candidate matching
- `ai_service_interview.py` - interview turns, coaching, verdict, roadmap
- `ai_service_audio.py` - transcription and text-to-speech
- `ai_service_analysis.py` - AI-likelihood and platform-feedback analysis
- `_ai_service_common.py` - shared AI constants and configuration

Runtime entry:

```text
app.py
  -> website.create_app()
  -> website/__init__.py
  -> SQLAlchemy setup
  -> startup migrations
  -> blueprint registration
  -> Flask routes
```

Production server:

```text
Gunicorn
  worker-class: gthread
  threads: 4
  timeout: 300 seconds
  Python: 3.12.11
```

---

## 5. Authentication and accounts

### Implemented

- Flask-Login session authentication
- Candidate/employer role separation
- Email/password signup and login
- Supabase provider authentication
- Google OAuth candidate/employer flows
- Email verification
- Password reset
- Separate first-name and last-name fields
- Null-safe `User.full_name` property
- Account deletion/anonymization routes
- Notification preferences
- Referral codes and first-referrer cookie behavior

### Primary files

- `website/auth.py`
- `website/auth_login.py`
- `website/auth_employer.py`
- `website/auth_verification.py`
- `website/auth_recovery.py`
- `website/candidate_account.py`
- `website/models.py`

### Known verification gaps

- Email/password callback edge cases require browser testing.
- OAuth metadata fallback behavior should be tested with different provider payloads.
- Account deletion and related entity cleanup need broader data-integrity testing.
- Admin and role checks need an authorization/IDOR audit.
- Login abuse controls are weak or not established.

---

## 6. Candidate feature state

### Implemented

- Candidate dashboard
- Candidate profile and public profile
- Headline, target roles, resume text, skills, location, availability, experience, work preference
- Resume PDF/DOCX/text upload support
- Resume extraction and text generation
- Job browsing, category/location filtering, detail pages
- Job application and next-steps page
- Resume-to-job preview and match scoring
- Saved jobs
- Application withdrawal
- Application status display
- Interview text/chat flow
- Interview audio handling
- Interview video answer upload URLs
- Saved interview-session resume
- AI interview verdict
- AI-likelihood analysis
- Skills-roadmap generation
- Practice interview questions and coaching
- Candidate-employer messages
- Meeting slot acceptance
- Notifications
- Hire confirmation/dispute/evidence flows
- Platform feedback

### Primary files

- `website/candidate.py`
- `website/candidate_account.py`
- `website/candidate_dashboard.py`
- `website/candidate_interviews.py`
- `website/candidate_jobs.py`
- `website/candidate_practice.py`
- `website/candidate_profile.py`
- `website/templates/candidate_*.html`
- `website/templates/profile.html`

### Remaining verification and product work

- Browser-test signup, profile save, job apply, interview, meeting, withdrawal, and hire confirmation.
- Verify profile first/last-name consistency across every public and employer-facing display.
- Audit resume-upload MIME validation and file-size behavior.
- Add timeout/retry/partial-result behavior for long media or AI calls.
- Test saved-session expiration and resume behavior.
- Verify public-profile privacy and blind-hiring rules.

---

## 7. Employer feature state

### Implemented

- Employer dashboard
- Company creation, joining, and domain-based team sync
- Company settings and logo upload
- Team member invite/remove/owner flows
- Job creation/edit/publish/delete/restore
- Employment type, category, location, salary range, currency, pay type
- AI-analyzed job description
- Employer-curated interview questions
- Interview length/focus/camera requirements
- Applicant list and resume scoring
- Candidate match explanation
- Employer notes
- Rejection with candidate feedback
- Manual interview score
- Blind hiring
- Candidate talent pool
- Candidate similarity/suggestion features
- Analytics
- Meeting proposals with 2-3 slots
- Candidate meeting slot acceptance
- Daily.co room creation
- Employer/candidate in-app messaging
- Local-camera recording upload and signed playback
- Recruiter dashboard with company-scoped hiring metrics, application chart, job actions, activity, candidate matches, notifications, and hiring insights
- Rate-limited recruiter dashboard AI assistant using aggregate company context without candidate personal information
- Company platform agreement/signature fields
- Hire compensation, evidence upload, dispute handling
- Recurring hourly engagement end flow

### Primary files

- `website/employer.py`
- `website/employer_applications.py`
- `website/employer_billing.py`
- `website/employer_company.py`
- `website/employer_jobs.py`
- `website/employer_meetings.py`
- `website/employer_talent.py`
- `website/templates/employer_*.html`

### Remaining verification and product work

- Enforce `PLAN_LIMITS` in job posting, interview, and talent-search routes.
- Verify blind-hiring redaction across list pages, exports, emails, and JSON endpoints.
- Test company-domain joining and team invitations.
- Test meeting lifecycle and room cleanup.
- Audit ownership checks on all employer routes.
- Verify salary/currency formatting on every page and email.
- Verify post-hire compensation and placement-fee evidence workflows.
- Browser-test the recruiter dashboard at desktop, tablet, and mobile widths; verify the assistant with configured provider credentials.

---

## 8. AI feature state

All intended AI calls should use `ai_services.py` or split `ai_service_*.py` modules rather than provider clients embedded in route handlers.

### Implemented capabilities

- PDF text extraction
- DOCX text extraction
- TXT extraction
- Resume text extraction
- Resume/job comparison
- Resume summary
- Basic resume analysis
- Resume generation from profile/LinkedIn-style text
- Job-description analysis
- Job/candidate suggestions
- Similar-job lookup
- Rejection feedback generation
- Interview turn execution
- Interview question preview
- Interview coaching
- Practice questions
- Job-fit verdict
- Skills-roadmap generation
- AI-generated-answer likelihood
- Audio extraction/transcription
- Text-to-speech
- Video scan and coaching job flow

### AI safety and reliability

- Route-level Flask-Limiter coverage for selected expensive operations
- Separate provider exception handling in selected routes
- Generic user-facing failures
- Server-side logging
- Post/Redirect/Get cache for resume matching
- 300-second production request timeout for long processing

### Known gaps

- Provider credential/end-to-end tests are not established.
- Timeout/retry behavior should be tested with real provider failures.
- In-memory resume/video caches assume one shared app process.
- Expanding to multiple Gunicorn workers/processes would require external cache/storage.
- Add partial-result and reconnection behavior for long video/interview processing.
- Test token/latency/cost behavior with large resumes and transcripts.

---

## 9. Earn and admin marketplace

### Implemented

- Earn task discovery
- Domain-gated tasks
- Ranking/rating/fact-check/writing task types
- Task submission
- Explanation text
- Agreement/consensus score
- Minimum response threshold
- Consensus answer storage
- Contractor profile
- Expertise domains
- Quality score and task counters
- Stripe payout setup/retry/refresh routes
- Admin task creation/export/close
- Admin payouts
- Referral reward operations
- Feedback analysis
- Data-buyer exports

### Primary files

- `website/earn.py`
- `website/admin.py`
- `website/admin_operations.py`
- `website/admin_companies.py`
- `website/data_market.py`
- `website/dataset_export.py`
- `website/models.py`

### Remaining work

- Test domain gating and consensus scoring.
- Verify payout onboarding, payout completion, and account status refresh.
- Test duplicate submissions and one-submission-per-user behavior.
- Add payout/task audit logs.
- Add automated tests for export permissions and subscription gates.
- Test admin deletion/cascade behavior against isolated data.

---

## 10. Payments and billing

The project has three logically separate payment flows:

1. **Employer placement fee**
   - Candidate confirms hire.
   - Employer enters actual compensation/evidence.
   - Stripe Payment Link is generated.
   - Webhook marks `Application.fee_paid`.

2. **Employer subscription**
   - `free`, `starter`, and `pro` plan values
   - `PLAN_LIMITS` are defined
   - Stripe subscription fields are stored
   - Route-level enforcement is not established

3. **Data-buyer subscription**
   - Separate Stripe price ID
   - Separate webhook secret
   - Subscription status and export access

### Primary files

- `website/employer_billing.py`
- `website/views.py`
- `website/data_market.py`
- `website/models.py`

### Verification status

- Placement-fee Payment Link code exists.
- Stripe webhook routes exist.
- Recurring hourly-hire subscription fields exist.
- End-to-end Stripe testing is not established.
- Webhook idempotency must be checked and tested.
- Subscription upgrade/downgrade/expiry behavior must be browser-tested.
- Monthly hourly-hire billing must be tested with real Stripe test-mode events.

---

## 11. Meetings and media

### Implemented

- Meeting proposals
- Candidate slot selection
- Daily.co room creation
- Meeting room URLs
- Candidate/employer meeting views
- Daily.co recording discovery
- Recording signed links
- Local client-side camera recording
- Supabase Storage upload helpers
- Application-linked meeting records

### Primary files

- `daily_utils.py`
- `video_storage.py`
- `website/employer_meetings.py`
- `website/candidate_dashboard.py`
- `website/views.py`
- `website/templates/meeting_room.html`

### Remaining work

- Browser-test camera permission, upload, playback, denial, and retry cases.
- Test room expiration and cleanup.
- Verify candidate/employer authorization for room access.
- Verify recording ownership and signed URL behavior.
- Confirm ephemeral local-storage paths are not used as durable evidence.
- Test mobile camera capture and file size limits.

---

## 12. Database architecture

Primary persistence:

- PostgreSQL in production when `DATABASE_URL` is set
- SQLite fallback for local development
- SQLAlchemy/Flask-SQLAlchemy
- Flask-Login session identity

Schema evolution:

- No Alembic or Flask-Migrate
- `website/__init__.py::_run_migrations()` contains additive `ALTER TABLE` statements
- Statements are wrapped independently in try/except
- Backfills exist for company email domains and referral codes
- Startup migrations are rerun safely on startup in intended cases

Important models include:

- `User`
- `CandidateProfile`
- `Company`
- `CompanyMember`
- `CompanyInvite`
- `Job`
- `DeletedJob`
- `Application`
- `SavedJob`
- `Notification`
- `Message`
- `MeetingProposal`
- `MeetingRoom`
- `EmployerSubscription`
- `EarnTask`
- `TaskSubmission`
- `ContractorProfile`
- `DataBuyer`
- `Feedback`
- `FeedbackInsight`
- `Referral`

### Database safety

Before importing/using database code, verify:

```python
app.config["SQLALCHEMY_DATABASE_URI"]
```

Use:

```text
sqlite:///:memory:
```

or an explicitly resolved throwaway SQLite file.

Never use `db.drop_all()`, broad deletes, or ad hoc writes against production.

---

## 13. External integrations

| Integration | Purpose | Key modules |
|---|---|---|
| OpenAI/OpenRouter | Resume, matching, interview, coaching, analysis | `ai_services.py`, `ai_service_*.py` |
| PostgreSQL/SQLite | Persistence | `website/__init__.py`, `website/models.py` |
| Supabase | Provider auth and storage | `auth_*.py`, `supabase_client.py`, `video_storage.py` |
| Stripe | Placement fees, employer plans, data subscriptions | `employer_billing.py`, `views.py`, `data_market.py` |
| Daily.co | Meeting rooms and recordings | `daily_utils.py`, `employer_meetings.py`, `views.py` |
| Gmail SMTP | Transactional email | `email_utils.py` |
| Google Cloud TTS/credentials | Speech and file/integration support | `app.py`, `config.py` |
| Google Drive | Daily database backups | `backup_database.py` |

Important environment variables:

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

Do not print or log secret values.

---

## 14. Testing state

Existing tests:

- `tests/test_community_stats.py`
- `tests/test_email_limits.py`
- `tests/test_employer_dashboard.py`

Test framework:

- Python `unittest`
- Narrow AST-based route testing
- In-memory SQLAlchemy and Flask-Limiter tests
- No pytest configuration
- No lint configuration
- No browser Playwright/Selenium suite
- No established app-factory integration fixture

Current validation result on 2026-11-22:

- `test_concurrent_increments_and_restart` - passed
- `test_recipient_limit_across_ips_and_both_forms` - passed
- Recruiter dashboard render, blind-mode masking, assistant response, and invalid input checks - passed on an in-memory SQLite database
- `test_routes_only_count_successful_processing` - currently fails before application behavior because `app.py` is read using the platform default `cp1252` encoding instead of UTF-8
- Python source compile check completed without a compile-all error

Run the existing suite with:

```powershell
python -m unittest discover -s tests -v
```

Compile source with:

```powershell
python -m compileall -q app.py website ai_services.py ai_service_documents.py ai_service_matching.py ai_service_interview.py ai_service_audio.py ai_service_analysis.py _ai_service_common.py
```

Browser test setup has not been established.

---

## 15. Known risks and open issues

### High priority

1. No broad end-to-end or browser test suite.
2. Plan limits are data-model/config values only unless route enforcement is added and verified.
3. Stripe placement, subscription, webhook, and refund/idempotency behavior needs test-mode verification.
4. Supabase, Google, Daily, Gmail, Stripe, OpenAI, and OpenRouter credentials need end-to-end verification.
5. Startup migration exceptions are swallowed, so failures can be hidden.

### Medium priority

6. Full-name consistency should be audited across all candidate/employer/admin displays.
7. Ownership and role checks need an IDOR/security review.
8. In-process caches assume a single application process.
9. `uploads/` and `audio/` are local/ephemeral storage.
10. Public, mobile, accessibility, and responsive behavior need systematic browser checks.
11. Email and auth callback URLs depend on public base URL correctness.
12. Account deletion, anonymization, and cascade data integrity need focused tests.
13. Existing test file reading is not UTF-8-safe.

### Lower/operational priority

14. Database backup restore has not been validated.
15. Health/readiness monitoring is limited.
16. Dependency versions should be reviewed and pinned carefully.
17. Production logs need a secrets/sensitive-payload audit.
18. Migration framework may be considered later if schema complexity grows.

---

## 16. Recommended implementation priority

### Phase 1 - Stabilize and verify

1. Fix the Unicode decode issue in `test_routes_only_count_successful_processing` by reading `app.py` with UTF-8.
2. Add a dedicated isolated SQLite app-factory test fixture.
3. Write browser smoke tests:
   - Signup/login
   - Profile save
   - Job browse/apply
   - Interview start/continue/save
   - Employer job publish/applicant review
   - Meeting proposal/accept/create
   - Stripe test-mode webhooks
4. Test auth, role, and object ownership for every protected route.
5. Verify startup migrations on an isolated SQLite and PostgreSQL test database.

### Phase 2 - Core billing and limits

1. Enforce free/starter/pro limits in posting and AI interview routes.
2. Add clear limit/upgrade UX.
3. Test Stripe placement fee Payment Links and webhooks.
4. Test hourly-hire recurring billing and engagement termination.
5. Test data-marketplace subscription and export access.
6. Add webhook idempotency and audit records.

### Phase 3 - Reliability

1. Replace or externalize in-process caches if multiple processes are used.
2. Add durable media storage rules and cleanup.
3. Add health/readiness checks.
4. Restore/backup validation.
5. Add provider failure, timeout, and partial-result tests.
6. Add structured logging and secret-payload checks.

### Phase 4 - UX and accessibility

1. Run desktop/mobile visual checks.
2. Audit forms, labels, focus, keyboard navigation, and status color.
3. Standardize empty states and status badges.
4. Verify blind-hiring privacy and public-profile copy.
5. Improve loading, retry, validation, and service-error states.

---

## 17. Safe change workflow

For a normal feature change:

1. Identify the route/module/template/model involved.
2. Read the route, model, template, and service helper.
3. Check authentication, role, and ownership.
4. Make the smallest coherent source change.
5. Update migrations only as additive startup columns.
6. Add one or more focused tests for behavior that is new or repaired.
7. Run the smallest relevant validation command.
8. Report actual verified behavior separately from source-level implementation.

For database work:

1. Set a throwaway `DATABASE_URL`.
2. Import the app.
3. Verify `app.config["SQLALCHEMY_DATABASE_URI"]`.
4. Use isolated SQLite or a throwaway database.
5. Never run destructive operations against shared/production data.

For integration work:

1. Use test credentials or test-mode services.
2. Keep provider-specific exceptions generic to users.
3. Log server-side details safely.
4. Build external URLs from `PUBLIC_BASE_URL` or `email_utils.external_url()`.
5. Verify callbacks and webhooks in a test deployment.

---

## 18. Existing project documents

Read these first for deeper context:

- `AGENTS.md` - repository operating guidance
- `rules.md` - coding/database/integration rules
- `architecture.md` - architecture and diagrams
- `prd.md` - product requirements
- `design.md` - UI/UX direction
- `tasks.md` - current tasks/backlog
- `memory.md` - durable project facts
- `MANUAL_PROGRESS.md` - historical manual changes and explanations

This handoff should be updated after major implementation milestones, successful browser verification, or deployment changes.
