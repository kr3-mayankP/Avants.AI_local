# ----------------------------------------------------------------
# CHANGE BLOCK: 2026-11-22
# OLD IMPLEMENTATION - commented snapshot from Git HEAD
# ----------------------------------------------------------------
# OLD CODE: # from dot is the same as from website since it imports from the current package
# OLD CODE: from . import db
# OLD CODE: from flask_login import UserMixin
# OLD CODE: from sqlalchemy.sql import func
# OLD CODE: import json as _json
# OLD CODE: import secrets
# OLD CODE:
# OLD CODE: COMPANY_SIZES = [
# OLD CODE:     "1–10",
# OLD CODE:     "11–50",
# OLD CODE:     "51–200",
# OLD CODE:     "201–500",
# OLD CODE:     "501–1,000",
# OLD CODE:     "1,000+",
# OLD CODE: ]
# OLD CODE:
# OLD CODE: INDUSTRIES = [
# OLD CODE:     "Technology",
# OLD CODE:     "Healthcare",
# OLD CODE:     "Finance & Banking",
# OLD CODE:     "Marketing & Advertising",
# OLD CODE:     "Sales",
# OLD CODE:     "Design & Creative",
# OLD CODE:     "Operations & Logistics",
# OLD CODE:     "Education",
# OLD CODE:     "Legal",
# OLD CODE:     "Real Estate",
# OLD CODE:     "Manufacturing",
# OLD CODE:     "Retail & E-commerce",
# OLD CODE:     "Media & Entertainment",
# OLD CODE:     "Non-profit",
# OLD CODE:     "Government",
# OLD CODE:     "Other",
# OLD CODE: ]
# OLD CODE:
# OLD CODE: SUPPORTED_CURRENCIES = {
# OLD CODE:     "USD": {"symbol": "$", "label": "USD ($)"},
# OLD CODE:     "EUR": {"symbol": "€", "label": "EUR (€)"},
# OLD CODE:     "GBP": {"symbol": "£", "label": "GBP (£)"},
# OLD CODE:     "INR": {"symbol": "₹", "label": "INR (₹)"},
# OLD CODE:     "CAD": {"symbol": "C$", "label": "CAD (C$)"},
# OLD CODE:     "AUD": {"symbol": "A$", "label": "AUD (A$)"},
# OLD CODE:     "SGD": {"symbol": "S$", "label": "SGD (S$)"},
# OLD CODE:     "AED": {"symbol": "AED", "label": "AED"},
# OLD CODE:     "JPY": {"symbol": "¥", "label": "JPY (¥)"},
# OLD CODE:     "CNY": {"symbol": "¥", "label": "CNY (¥)"},
# OLD CODE:     "CHF": {"symbol": "CHF", "label": "CHF"},
# OLD CODE: }
# OLD CODE: DEFAULT_CURRENCY = "USD"
# OLD CODE:
# OLD CODE: JOB_CATEGORIES = [
# OLD CODE:     "Software",
# OLD CODE:     "Healthcare",
# OLD CODE:     "Finance",
# OLD CODE:     "Marketing",
# OLD CODE:     "Sales",
# OLD CODE:     "Design",
# OLD CODE:     "Operations",
# OLD CODE:     "Other",
# OLD CODE: ]
# OLD CODE:
# OLD CODE: JOB_LOCATIONS = [
# OLD CODE:     "Remote",
# OLD CODE:     "Remote - US Only",
# OLD CODE:     "Hybrid",
# OLD CODE:     "New York, NY",
# OLD CODE:     "San Francisco, CA",
# OLD CODE:     "Los Angeles, CA",
# OLD CODE:     "Chicago, IL",
# OLD CODE:     "Austin, TX",
# OLD CODE:     "Seattle, WA",
# OLD CODE:     "Boston, MA",
# OLD CODE:     "Denver, CO",
# OLD CODE:     "Atlanta, GA",
# OLD CODE:     "Miami, FL",
# OLD CODE:     "Washington, DC",
# OLD CODE:     "Toronto, Canada",
# OLD CODE:     "London, UK",
# OLD CODE:     "Other",
# OLD CODE: ]
# OLD CODE:
# OLD CODE: EARN_DOMAINS = [
# OLD CODE:     "Software",
# OLD CODE:     "Healthcare",
# OLD CODE:     "Legal",
# OLD CODE:     "Finance",
# OLD CODE:     "Marketing",
# OLD CODE:     "Sales",
# OLD CODE:     "Design",
# OLD CODE:     "Operations",
# OLD CODE:     "Education",
# OLD CODE:     "Science",
# OLD CODE:     "Other",
# OLD CODE: ]
# OLD CODE:
# OLD CODE: COUNTRIES = [
# OLD CODE:     "United States", "Canada", "United Kingdom", "Ireland", "Australia",
# OLD CODE:     "New Zealand", "Germany", "France", "Spain", "Italy", "Netherlands",
# OLD CODE:     "Portugal", "Poland", "Sweden", "Norway", "Switzerland", "India",
# OLD CODE:     "Pakistan", "Philippines", "Singapore", "Mexico", "Brazil", "Argentina",
# OLD CODE:     "South Africa", "Nigeria", "Kenya", "United Arab Emirates", "Other",
# OLD CODE: ]
# OLD CODE:
# OLD CODE: # Consumer/free webmail providers - employers must sign up with a company email instead.
# OLD CODE: FREE_EMAIL_DOMAINS = {
# OLD CODE:     "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com",
# OLD CODE:     "aol.com", "icloud.com", "protonmail.com", "proton.me", "mail.com",
# OLD CODE:     "gmx.com", "yandex.com", "zoho.com", "msn.com", "me.com",
# OLD CODE: }
# OLD CODE:
# OLD CODE:
# OLD CODE: class User(db.Model, UserMixin):
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     email = db.Column(db.String(150), unique=True)
# OLD CODE:     password = db.Column(db.String(255))  # werkzeug's scrypt hashes run ~162 chars, longer than the old 150 cap
# OLD CODE:     first_name = db.Column(db.String(150))
# OLD CODE:     role = db.Column(db.String(20), nullable=False, default="candidate")  # "candidate" | "employer"
# OLD CODE:     email_verified = db.Column(db.Boolean, nullable=False, default=True)
# OLD CODE:     notifications_enabled = db.Column(db.Boolean, nullable=False, default=True)
# OLD CODE:     is_admin = db.Column(db.Boolean, nullable=False, default=False)
# OLD CODE:     supabase_uid = db.Column(db.String(200), unique=True)
# OLD CODE:     data_buyer_id = db.Column(db.Integer, db.ForeignKey("data_buyer.id"))
# OLD CODE:     is_data_buyer_admin = db.Column(db.Boolean, nullable=False, default=False)
# OLD CODE:     # Referral program: this user's own shareable code, and who referred them (if anyone)
# OLD CODE:     referral_code = db.Column(db.String(12), unique=True, default=lambda: secrets.token_urlsafe(6))
# OLD CODE:     referred_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
# OLD CODE:
# OLD CODE:
# OLD CODE: class Company(db.Model):
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     owner_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
# OLD CODE:     name = db.Column(db.String(200), nullable=False)
# OLD CODE:     # Domain of the founding employer's work email (e.g. "acme.com") - lets later
# OLD CODE:     # signups from the same company email land in this same hub instead of each
# OLD CODE:     # getting their own Company. Null for companies created before this existed,
# OLD CODE:     # or whose founder signed up via a free-webmail-flagged edge case.
# OLD CODE:     email_domain = db.Column(db.String(150))
# OLD CODE:     website = db.Column(db.String(300))
# OLD CODE:     description = db.Column(db.Text)
# OLD CODE:     industry = db.Column(db.String(100))
# OLD CODE:     size = db.Column(db.String(50))
# OLD CODE:     location = db.Column(db.String(200))
# OLD CODE:     logo_filename = db.Column(db.String(200))
# OLD CODE:     logo_version = db.Column(db.Integer, default=0)
# OLD CODE:     blind_mode_enabled = db.Column(db.Boolean, nullable=False, default=False)
# OLD CODE:     terms_accepted_at = db.Column(db.DateTime(timezone=True))
# OLD CODE:     terms_accepted_ip = db.Column(db.String(45))
# OLD CODE:     terms_version = db.Column(db.String(10))
# OLD CODE:     # Typed full legal name of the authorised rep who signed the Employer
# OLD CODE:     # Platform Agreement - an e-signature alongside the checkbox, so the
# OLD CODE:     # placement-fee obligation reads as an actually-signed contract.
# OLD CODE:     terms_signature_name = db.Column(db.String(200))
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:
# OLD CODE: class Job(db.Model):
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
# OLD CODE:     title = db.Column(db.String(200), nullable=False)
# OLD CODE:     description = db.Column(db.Text, nullable=False)
# OLD CODE:     location = db.Column(db.String(200))
# OLD CODE:     employment_type = db.Column(db.String(50))  # e.g. "Full-time", "Contract"
# OLD CODE:     category = db.Column(db.String(50), nullable=False, default="Other")  # see JOB_CATEGORIES
# OLD CODE:     status = db.Column(db.String(20), nullable=False, default="open")  # "open" | "closed"
# OLD CODE:     interview_length = db.Column(db.String(20), nullable=False, default="standard")  # short | standard | thorough
# OLD CODE:     interview_focus = db.Column(db.Text)  # optional employer instructions on what the AI should cover
# OLD CODE:     interview_questions = db.Column(db.Text)  # JSON list of employer-curated questions the AI should make sure to ask
# OLD CODE:     camera_required = db.Column(db.Boolean, nullable=False, default=False)  # candidate must enable their camera for the AI interview, not just optional
# OLD CODE:     # Column names predate multi-currency support - the amount is in
# OLD CODE:     # salary_currency's units, not necessarily actual USD. See SUPPORTED_CURRENCIES.
# OLD CODE:     salary_usd = db.Column(db.Integer)
# OLD CODE:     salary_max_usd = db.Column(db.Integer)
# OLD CODE:     pay_type = db.Column(db.String(20), default='yearly')
# OLD CODE:     salary_currency = db.Column(db.String(3), nullable=False, default=DEFAULT_CURRENCY)
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:     company = db.relationship("Company", backref="jobs")
# OLD CODE:
# OLD CODE:     _SECTION_LABELS = [
# OLD CODE:         ('about', 'About the Role'),
# OLD CODE:         ('requirements', 'Requirements'),
# OLD CODE:         ('preferred', 'Preferred Qualifications'),
# OLD CODE:         ('what_you_do', "What You'll Do"),
# OLD CODE:         ('contract_terms', 'Contract & Payment Terms'),
# OLD CODE:     ]
# OLD CODE:
# OLD CODE:     @property
# OLD CODE:     def description_sections(self):
# OLD CODE:         """Return structured dict if description is JSON, else None."""
# OLD CODE:         try:
# OLD CODE:             data = _json.loads(self.description)
# OLD CODE:             if isinstance(data, dict):
# OLD CODE:                 return data
# OLD CODE:         except (ValueError, TypeError):
# OLD CODE:             pass
# OLD CODE:         return None
# OLD CODE:
# OLD CODE:     @property
# OLD CODE:     def description_text(self):
# OLD CODE:         """Return plain-text description suitable for AI calls."""
# OLD CODE:         sections = self.description_sections
# OLD CODE:         if sections:
# OLD CODE:             parts = []
# OLD CODE:             for key, label in self._SECTION_LABELS:
# OLD CODE:                 val = (sections.get(key) or '').strip()
# OLD CODE:                 if val:
# OLD CODE:                     parts.append(f"{label}:\n{val}")
# OLD CODE:             return '\n\n'.join(parts) if parts else self.description
# OLD CODE:         return self.description
# OLD CODE:
# OLD CODE:     def to_snapshot_dict(self):
# OLD CODE:         """Every re-creatable field, for stashing in DeletedJob.snapshot."""
# OLD CODE:         return {
# OLD CODE:             "title": self.title,
# OLD CODE:             "description": self.description,
# OLD CODE:             "location": self.location,
# OLD CODE:             "employment_type": self.employment_type,
# OLD CODE:             "category": self.category,
# OLD CODE:             "status": self.status,
# OLD CODE:             "interview_length": self.interview_length,
# OLD CODE:             "interview_focus": self.interview_focus,
# OLD CODE:             "interview_questions": self.interview_questions,
# OLD CODE:             "salary_usd": self.salary_usd,
# OLD CODE:             "salary_max_usd": self.salary_max_usd,
# OLD CODE:             "pay_type": self.pay_type,
# OLD CODE:             "salary_currency": self.salary_currency,
# OLD CODE:         }
# OLD CODE:
# OLD CODE:
# OLD CODE: class DeletedJob(db.Model):
# OLD CODE:     """Snapshot of a Job taken right before it's deleted, so an accidental
# OLD CODE:     delete can be undone. company_id is deliberately not a ForeignKey - when
# OLD CODE:     a whole Company is deleted (admin.delete_company), its jobs are snapshotted
# OLD CODE:     here first but the Company row itself is gone by the time this survives it,
# OLD CODE:     so a hard FK would leave a dangling reference. Restoring only recreates the
# OLD CODE:     job listing itself; applications/messages/videos already cascade-deleted
# OLD CODE:     alongside it are not recoverable."""
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     original_job_id = db.Column(db.Integer, nullable=False)
# OLD CODE:     company_id = db.Column(db.Integer, nullable=False)
# OLD CODE:     company_name = db.Column(db.String(200), nullable=False)
# OLD CODE:     title = db.Column(db.String(200), nullable=False)
# OLD CODE:     snapshot = db.Column(db.Text, nullable=False)  # JSON of Job.to_snapshot_dict()
# OLD CODE:     applicant_count = db.Column(db.Integer, nullable=False, default=0)
# OLD CODE:     deleted_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
# OLD CODE:     deleted_source = db.Column(db.String(20), nullable=False)  # "employer" | "admin"
# OLD CODE:     restored_job_id = db.Column(db.Integer)  # set once restored, so it can't be restored twice
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:     deleted_by = db.relationship("User")
# OLD CODE:
# OLD CODE:
# OLD CODE: class CandidateProfile(db.Model):
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
# OLD CODE:     headline = db.Column(db.String(200))
# OLD CODE:     resume_text = db.Column(db.Text)
# OLD CODE:     linkedin_url = db.Column(db.String(300))
# OLD CODE:     target_roles = db.Column(db.String(300))
# OLD CODE:     # Talent pool fields
# OLD CODE:     open_to_work = db.Column(db.Boolean, nullable=False, default=False)
# OLD CODE:     skills = db.Column(db.Text)           # comma-separated
# OLD CODE:     work_preference = db.Column(db.String(50))   # Remote / Hybrid / On-site / Any
# OLD CODE:     availability = db.Column(db.String(50))      # Immediately / 2 weeks / 1 month / 3 months
# OLD CODE:     years_experience = db.Column(db.String(20))  # 0-1 / 1-3 / 3-5 / 5-10 / 10+
# OLD CODE:     location = db.Column(db.String(200))         # city / country they're based in
# OLD CODE:
# OLD CODE:     user = db.relationship("User", backref=db.backref("candidate_profile", uselist=False))
# OLD CODE:
# OLD CODE:
# OLD CODE: class Application(db.Model):
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
# OLD CODE:     candidate_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
# OLD CODE:     resume_text = db.Column(db.Text, nullable=False)
# OLD CODE:     work_authorization = db.Column(db.Text)  # JSON: DOB, residence, attestations, signature
# OLD CODE:     scheduled_meeting = db.Column(db.Text)  # JSON: type, datetime, location_or_url, notes
# OLD CODE:     match_score = db.Column(db.Integer)
# OLD CODE:     match_explanation = db.Column(db.Text)
# OLD CODE:     interview_transcript = db.Column(db.Text)
# OLD CODE:     interview_audio_log = db.Column(db.Text)  # JSON list of {role, text, audio_filename}
# OLD CODE:     interview_verdict = db.Column(db.String(20))  # "Strong Yes" | "Yes" | "No" | "Strong No"
# OLD CODE:     manual_interview_score = db.Column(db.Integer)  # 0-100, employer's own rating after a live/manual interview
# OLD CODE:     status = db.Column(db.String(20), nullable=False, default="applied")  # applied | interviewing | rejected | hired
# OLD CODE:     candidate_confirmed_hire = db.Column(db.Boolean, nullable=False, default=False)  # candidate must confirm before the fee invoice fires
# OLD CODE:     hire_confirmed_at = db.Column(db.DateTime(timezone=True))
# OLD CODE:     # Actual negotiated compensation at hire time, entered by the employer -
# OLD CODE:     # the placement fee is calculated from this, not the job posting's
# OLD CODE:     # advertised salary, which the employer has no incentive to keep
# OLD CODE:     # accurate once someone's actually hired.
# OLD CODE:     hire_salary_usd = db.Column(db.Integer)
# OLD CODE:     hire_pay_type = db.Column(db.String(20))  # yearly | hourly | monthly | stipend | contract
# OLD CODE:     hire_salary_disputed = db.Column(db.Boolean, nullable=False, default=False)  # candidate says the entered figure is wrong
# OLD CODE:     hire_evidence_filename = db.Column(db.String(200))  # optional offer-letter/screenshot upload
# OLD CODE:     fee_paid = db.Column(db.Boolean, nullable=False, default=False)
# OLD CODE:     stripe_payment_link = db.Column(db.String(500))  # Stripe Payment Link URL sent to employer on hire
# OLD CODE:     # Hourly hires bill monthly for as long as the engagement actually runs,
# OLD CODE:     # instead of one lump sum assuming a full 2,080-hour year up front -
# OLD CODE:     # stripe_payment_link above is a subscription-mode link in this case.
# OLD CODE:     hire_billing_subscription_id = db.Column(db.String(100))
# OLD CODE:     hire_engagement_ended_at = db.Column(db.DateTime(timezone=True))  # set when the employer stops billing
# OLD CODE:     fee_reminder_sent_at = db.Column(db.DateTime(timezone=True))  # last overdue-fee reminder email, throttles re-sends
# OLD CODE:     employer_notes = db.Column(db.Text)  # private notes visible only to employer
# OLD CODE:     withdrawn = db.Column(db.Boolean, nullable=False, default=False)
# OLD CODE:     candidate_feedback = db.Column(db.Text)  # employer-approved AI feedback sent to candidate on rejection
# OLD CODE:     skills_roadmap = db.Column(db.Text)  # JSON: AI-generated skill gap action plan (generated when score < 65)
# OLD CODE:     interview_saved_session = db.Column(db.Text)  # JSON: partial history saved for later resumption
# OLD CODE:     ai_likelihood = db.Column(db.Text)  # JSON: {score, label, reasons} - AI-generation probability for candidate answers
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:     job = db.relationship("Job", backref="applications")
# OLD CODE:     candidate = db.relationship("User", backref="applications")
# OLD CODE:
# OLD CODE:
# OLD CODE: class SavedJob(db.Model):
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
# OLD CODE:     job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:     __table_args__ = (db.UniqueConstraint("user_id", "job_id"),)
# OLD CODE:
# OLD CODE:
# OLD CODE: class Notification(db.Model):
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
# OLD CODE:     message = db.Column(db.String(300), nullable=False)
# OLD CODE:     link = db.Column(db.String(300))
# OLD CODE:     read = db.Column(db.Boolean, nullable=False, default=False)
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:
# OLD CODE: class CompanyMember(db.Model):
# OLD CODE:     """Additional employer users who can manage a company's jobs and applicants."""
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
# OLD CODE:     user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
# OLD CODE:     joined_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:     company = db.relationship("Company", backref="members")
# OLD CODE:     user = db.relationship("User", backref="company_memberships")
# OLD CODE:
# OLD CODE:     __table_args__ = (db.UniqueConstraint("company_id", "user_id"),)
# OLD CODE:
# OLD CODE:
# OLD CODE: class Referral(db.Model):
# OLD CODE:     """A commission owed to whoever referred a candidate, once that
# OLD CODE:     candidate is hired and the employer's placement fee is actually paid.
# OLD CODE:     Created once per Application (see views.stripe_webhook) - commission is
# OLD CODE:     10% of the platform's 15% placement fee, tracked here and paid out
# OLD CODE:     manually by an admin (see admin.referrals / admin.mark_referral_paid)."""
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     referrer_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
# OLD CODE:     referred_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
# OLD CODE:     application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False, unique=True)
# OLD CODE:     commission_usd = db.Column(db.Integer, nullable=False)
# OLD CODE:     status = db.Column(db.String(20), nullable=False, default="owed")  # owed | paid
# OLD CODE:     paid_at = db.Column(db.DateTime(timezone=True))
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:     referrer = db.relationship("User", foreign_keys=[referrer_user_id])
# OLD CODE:     referred = db.relationship("User", foreign_keys=[referred_user_id])
# OLD CODE:     application = db.relationship("Application", backref=db.backref("referral", uselist=False))
# OLD CODE:
# OLD CODE:
# OLD CODE: class EarnTask(db.Model):
# OLD CODE:     """A task posted for professionals to complete and earn money."""
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     title = db.Column(db.String(200), nullable=False)
# OLD CODE:     description = db.Column(db.Text, nullable=False)
# OLD CODE:     task_type = db.Column(db.String(30), nullable=False, default='ranking')  # ranking | rating | factcheck | writing
# OLD CODE:     domain = db.Column(db.String(100))  # e.g. "Legal", "Software", "Healthcare"
# OLD CODE:     pay_cents = db.Column(db.Integer, nullable=False, default=500)  # payment in cents
# OLD CODE:     estimated_minutes = db.Column(db.Integer, default=5)
# OLD CODE:     status = db.Column(db.String(20), nullable=False, default='open')  # open | closed
# OLD CODE:     required_domains = db.Column(db.Text)   # JSON list; None means open to all domains
# OLD CODE:     min_responses = db.Column(db.Integer, nullable=False, default=3)  # workers needed before consensus
# OLD CODE:     consensus_answer = db.Column(db.Text)   # JSON {answer, total, distribution} - set once min_responses hit
# OLD CODE:     # For ranking tasks: two AI responses to compare
# OLD CODE:     option_a = db.Column(db.Text)
# OLD CODE:     option_b = db.Column(db.Text)
# OLD CODE:     # For rating/factcheck tasks: single AI response
# OLD CODE:     content = db.Column(db.Text)
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:     submissions = db.relationship('TaskSubmission', backref='task', lazy=True)
# OLD CODE:
# OLD CODE:
# OLD CODE: class TaskSubmission(db.Model):
# OLD CODE:     """A professional's completed response to an EarnTask."""
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     task_id = db.Column(db.Integer, db.ForeignKey('earn_task.id'), nullable=False)
# OLD CODE:     user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
# OLD CODE:     response = db.Column(db.Text)        # chosen option / rating / written response
# OLD CODE:     explanation = db.Column(db.Text)     # optional explanation
# OLD CODE:     agreement_score = db.Column(db.Float)  # 0–1; set when consensus is computed for this task
# OLD CODE:     earnings_cents = db.Column(db.Integer, nullable=False, default=0)
# OLD CODE:     paid_out = db.Column(db.Boolean, nullable=False, default=False)
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:     user = db.relationship('User', backref='task_submissions')
# OLD CODE:
# OLD CODE:
# OLD CODE: class ContractorProfile(db.Model):
# OLD CODE:     """Tracks a user's expertise domains and earn stats for the AI training contractor network."""
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
# OLD CODE:     domains = db.Column(db.Text, nullable=False)         # JSON list of EARN_DOMAINS values
# OLD CODE:     quality_score = db.Column(db.Float, nullable=False, default=1.0)   # 0–1; updated by consensus
# OLD CODE:     tasks_completed = db.Column(db.Integer, nullable=False, default=0)
# OLD CODE:     stripe_account_id = db.Column(db.String(100))        # Stripe Connect Express account ID
# OLD CODE:     payout_enabled = db.Column(db.Boolean, nullable=False, default=False)  # True once Stripe onboarding complete
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:     user = db.relationship("User", backref=db.backref("contractor_profile", uselist=False))
# OLD CODE:
# OLD CODE:
# OLD CODE: class MeetingProposal(db.Model):
# OLD CODE:     """Employer proposes 2-3 time slots; candidate picks one and the room is created."""
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False)
# OLD CODE:     employer_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
# OLD CODE:     slots = db.Column(db.Text, nullable=False)        # JSON list of {date, time} dicts
# OLD CODE:     notes = db.Column(db.Text)
# OLD CODE:     status = db.Column(db.String(20), nullable=False, default='pending')  # pending | accepted | expired
# OLD CODE:     accepted_slot = db.Column(db.Text)               # JSON {date, time} chosen by candidate
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:     application = db.relationship("Application", backref=db.backref("meeting_proposals", lazy=True))
# OLD CODE:     employer = db.relationship("User", foreign_keys=[employer_user_id])
# OLD CODE:
# OLD CODE:
# OLD CODE: PLAN_LIMITS = {
# OLD CODE:     'free':    {'jobs': 3,    'interviews_per_month': 20,  'talent_search': False},
# OLD CODE:     'starter': {'jobs': 10,   'interviews_per_month': 150, 'talent_search': True},
# OLD CODE:     'pro':     {'jobs': 9999, 'interviews_per_month': 9999, 'talent_search': True},
# OLD CODE: }
# OLD CODE:
# OLD CODE:
# OLD CODE: class Message(db.Model):
# OLD CODE:     """In-app message between employer and candidate on a specific application."""
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False)
# OLD CODE:     sender_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
# OLD CODE:     body = db.Column(db.Text, nullable=False)
# OLD CODE:     read = db.Column(db.Boolean, nullable=False, default=False)
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:     sender = db.relationship("User", foreign_keys=[sender_user_id])
# OLD CODE:     application = db.relationship("Application", backref=db.backref("messages", lazy=True, order_by="Message.created_at"))
# OLD CODE:
# OLD CODE:
# OLD CODE: class EmployerSubscription(db.Model):
# OLD CODE:     """Stripe subscription plan for an employer company."""
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False, unique=True)
# OLD CODE:     plan = db.Column(db.String(20), nullable=False, default='free')   # free | starter | pro
# OLD CODE:     stripe_customer_id = db.Column(db.String(100))
# OLD CODE:     stripe_subscription_id = db.Column(db.String(100))
# OLD CODE:     status = db.Column(db.String(20), nullable=False, default='active')  # active | canceled | past_due
# OLD CODE:     current_period_end = db.Column(db.DateTime(timezone=True))
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:     company = db.relationship("Company", backref=db.backref("subscription", uselist=False))
# OLD CODE:
# OLD CODE:
# OLD CODE: class MeetingRoom(db.Model):
# OLD CODE:     """An in-app video meeting room created via Daily.co for a specific application."""
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False)
# OLD CODE:     employer_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
# OLD CODE:     room_name = db.Column(db.String(200), nullable=False, unique=True)
# OLD CODE:     room_url = db.Column(db.String(500), nullable=False)
# OLD CODE:     scheduled_date = db.Column(db.String(20))   # YYYY-MM-DD
# OLD CODE:     scheduled_time = db.Column(db.String(10))   # HH:MM
# OLD CODE:     notes = db.Column(db.Text)
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:     # Independent local-camera recordings captured client-side in the call
# OLD CODE:     # page itself, not Daily.co's cloud recording - see meeting_room.html.
# OLD CODE:     # Storage paths (Supabase Storage), not URLs - resolved to a signed URL
# OLD CODE:     # at playback time.
# OLD CODE:     candidate_recording_path = db.Column(db.String(300))
# OLD CODE:     employer_recording_path = db.Column(db.String(300))
# OLD CODE:
# OLD CODE:     application = db.relationship("Application", backref=db.backref("meeting_rooms", lazy=True))
# OLD CODE:     employer = db.relationship("User", foreign_keys=[employer_user_id])
# OLD CODE:
# OLD CODE:
# OLD CODE: class CompanyInvite(db.Model):
# OLD CODE:     """Pending invitation for someone to join a company as a team member."""
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
# OLD CODE:     invited_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
# OLD CODE:     email = db.Column(db.String(150), nullable=False)
# OLD CODE:     token = db.Column(db.String(100), nullable=False, unique=True)
# OLD CODE:     used = db.Column(db.Boolean, nullable=False, default=False)
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:     company = db.relationship("Company", backref="invites")
# OLD CODE:
# OLD CODE:
# OLD CODE: class DataBuyer(db.Model):
# OLD CODE:     """An outside company subscribed to download the Earn marketplace's
# OLD CODE:     graded task data (rankings, ratings, factchecks, writing) as training data."""
# OLD CODE:     __tablename__ = "data_buyer"
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     name = db.Column(db.String(200), nullable=False)
# OLD CODE:     contact_email = db.Column(db.String(150), nullable=False)
# OLD CODE:     stripe_customer_id = db.Column(db.String(100))
# OLD CODE:     stripe_subscription_id = db.Column(db.String(100))
# OLD CODE:     subscription_status = db.Column(db.String(20), nullable=False, default="inactive")  # inactive | active | canceled
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:     members = db.relationship("User", backref="data_buyer", foreign_keys="User.data_buyer_id")
# OLD CODE:
# OLD CODE:
# OLD CODE: class Feedback(db.Model):
# OLD CODE:     """A rating + comment left by a candidate or employer about their
# OLD CODE:     experience, collected at key moments (interview completion, hire
# OLD CODE:     resolution) rather than through a generic always-on form."""
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
# OLD CODE:     application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False)
# OLD CODE:     role = db.Column(db.String(20), nullable=False)  # candidate | employer
# OLD CODE:     context = db.Column(db.String(30), nullable=False)  # interview_completed | application_resolved | hire_closed
# OLD CODE:     rating = db.Column(db.Integer, nullable=False)  # 1-5
# OLD CODE:     comment = db.Column(db.Text)
# OLD CODE:     created_at = db.Column(db.DateTime(timezone=True), default=func.now())
# OLD CODE:
# OLD CODE:     user = db.relationship("User")
# OLD CODE:     application = db.relationship("Application", backref="feedback_entries")
# OLD CODE:
# OLD CODE:     __table_args__ = (db.UniqueConstraint("user_id", "application_id", "context"),)
# OLD CODE:
# OLD CODE:
# OLD CODE: class FeedbackInsight(db.Model):
# OLD CODE:     """Cached AI-generated summary + actionable recommendations from analyzing
# OLD CODE:     Feedback rows - regenerated on demand by an admin, not on every page view,
# OLD CODE:     since it's a real OpenAI call and feedback doesn't change that fast."""
# OLD CODE:     id = db.Column(db.Integer, primary_key=True)
# OLD CODE:     summary = db.Column(db.Text, nullable=False)
# OLD CODE:     recommendations = db.Column(db.Text)  # JSON list of {title, detail}
# OLD CODE:     feedback_count = db.Column(db.Integer, nullable=False, default=0)
# OLD CODE:     generated_at = db.Column(db.DateTime(timezone=True), default=func.now())
# ----------------------------------------------------------------
# NEW IMPLEMENTATION - active code starts below
# ----------------------------------------------------------------
# from dot is the same as from website since it imports from the current package
from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func
import json as _json
import secrets

COMPANY_SIZES = [
    "1–10",
    "11–50",
    "51–200",
    "201–500",
    "501–1,000",
    "1,000+",
]

INDUSTRIES = [
    "Technology",
    "Healthcare",
    "Finance & Banking",
    "Marketing & Advertising",
    "Sales",
    "Design & Creative",
    "Operations & Logistics",
    "Education",
    "Legal",
    "Real Estate",
    "Manufacturing",
    "Retail & E-commerce",
    "Media & Entertainment",
    "Non-profit",
    "Government",
    "Other",
]

SUPPORTED_CURRENCIES = {
    "USD": {"symbol": "$", "label": "USD ($)"},
    "EUR": {"symbol": "€", "label": "EUR (€)"},
    "GBP": {"symbol": "£", "label": "GBP (£)"},
    "INR": {"symbol": "₹", "label": "INR (₹)"},
    "CAD": {"symbol": "C$", "label": "CAD (C$)"},
    "AUD": {"symbol": "A$", "label": "AUD (A$)"},
    "SGD": {"symbol": "S$", "label": "SGD (S$)"},
    "AED": {"symbol": "AED", "label": "AED"},
    "JPY": {"symbol": "¥", "label": "JPY (¥)"},
    "CNY": {"symbol": "¥", "label": "CNY (¥)"},
    "CHF": {"symbol": "CHF", "label": "CHF"},
}
DEFAULT_CURRENCY = "USD"

JOB_CATEGORIES = [
    "Software",
    "Healthcare",
    "Finance",
    "Marketing",
    "Sales",
    "Design",
    "Operations",
    "Other",
]

JOB_LOCATIONS = [
    "Remote",
    "Remote - US Only",
    "Hybrid",
    "New York, NY",
    "San Francisco, CA",
    "Los Angeles, CA",
    "Chicago, IL",
    "Austin, TX",
    "Seattle, WA",
    "Boston, MA",
    "Denver, CO",
    "Atlanta, GA",
    "Miami, FL",
    "Washington, DC",
    "Toronto, Canada",
    "London, UK",
    "Other",
]

EARN_DOMAINS = [
    "Software",
    "Healthcare",
    "Legal",
    "Finance",
    "Marketing",
    "Sales",
    "Design",
    "Operations",
    "Education",
    "Science",
    "Other",
]

COUNTRIES = [
    "United States", "Canada", "United Kingdom", "Ireland", "Australia",
    "New Zealand", "Germany", "France", "Spain", "Italy", "Netherlands",
    "Portugal", "Poland", "Sweden", "Norway", "Switzerland", "India",
    "Pakistan", "Philippines", "Singapore", "Mexico", "Brazil", "Argentina",
    "South Africa", "Nigeria", "Kenya", "United Arab Emirates", "Other",
]

# Consumer/free webmail providers - employers must sign up with a company email instead.
FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com",
    "aol.com", "icloud.com", "protonmail.com", "proton.me", "mail.com",
    "gmx.com", "yandex.com", "zoho.com", "msn.com", "me.com",
}


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(255))  # werkzeug's scrypt hashes run ~162 chars, longer than the old 150 cap
    first_name = db.Column(db.String(150))
    last_name = db.Column(db.String(150)) #new change for last name
    role = db.Column(db.String(20), nullable=False, default="candidate")  # "candidate" | "employer"
    email_verified = db.Column(db.Boolean, nullable=False, default=True)
    notifications_enabled = db.Column(db.Boolean, nullable=False, default=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    supabase_uid = db.Column(db.String(200), unique=True)
    data_buyer_id = db.Column(db.Integer, db.ForeignKey("data_buyer.id"))
    is_data_buyer_admin = db.Column(db.Boolean, nullable=False, default=False)
    # Referral program: this user's own shareable code, and who referred them (if anyone)
    referral_code = db.Column(db.String(12), unique=True, default=lambda: secrets.token_urlsafe(6))
    referred_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    @property
    def full_name(self):
        #new change: provide one null-safe name for profile and candidate displays.
        return " ".join(
            part.strip() for part in (self.first_name, self.last_name) if part and part.strip()
        )


class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    # Domain of the founding employer's work email (e.g. "acme.com") - lets later
    # signups from the same company email land in this same hub instead of each
    # getting their own Company. Null for companies created before this existed,
    # or whose founder signed up via a free-webmail-flagged edge case.
    email_domain = db.Column(db.String(150))
    website = db.Column(db.String(300))
    description = db.Column(db.Text)
    industry = db.Column(db.String(100))
    size = db.Column(db.String(50))
    location = db.Column(db.String(200))
    logo_filename = db.Column(db.String(200))
    logo_version = db.Column(db.Integer, default=0)
    blind_mode_enabled = db.Column(db.Boolean, nullable=False, default=False)
    terms_accepted_at = db.Column(db.DateTime(timezone=True))
    terms_accepted_ip = db.Column(db.String(45))
    terms_version = db.Column(db.String(10))
    # Typed full legal name of the authorised rep who signed the Employer
    # Platform Agreement - an e-signature alongside the checkbox, so the
    # placement-fee obligation reads as an actually-signed contract.
    terms_signature_name = db.Column(db.String(200))
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200))
    employment_type = db.Column(db.String(50))  # e.g. "Full-time", "Contract"
    category = db.Column(db.String(50), nullable=False, default="Other")  # see JOB_CATEGORIES
    status = db.Column(db.String(20), nullable=False, default="open")  # "open" | "closed"
    interview_length = db.Column(db.String(20), nullable=False, default="standard")  # short | standard | thorough
    interview_focus = db.Column(db.Text)  # optional employer instructions on what the AI should cover
    interview_questions = db.Column(db.Text)  # JSON list of employer-curated questions the AI should make sure to ask
    camera_required = db.Column(db.Boolean, nullable=False, default=False)  # candidate must enable their camera for the AI interview, not just optional
    # Column names predate multi-currency support - the amount is in
    # salary_currency's units, not necessarily actual USD. See SUPPORTED_CURRENCIES.
    salary_usd = db.Column(db.Integer)
    salary_max_usd = db.Column(db.Integer)
    pay_type = db.Column(db.String(20), default='yearly')
    salary_currency = db.Column(db.String(3), nullable=False, default=DEFAULT_CURRENCY)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    company = db.relationship("Company", backref="jobs")

    _SECTION_LABELS = [
        ('about', 'About the Role'),
        ('requirements', 'Requirements'),
        ('preferred', 'Preferred Qualifications'),
        ('what_you_do', "What You'll Do"),
        ('contract_terms', 'Contract & Payment Terms'),
    ]

    @property
    def description_sections(self):
        """Return structured dict if description is JSON, else None."""
        try:
            data = _json.loads(self.description)
            if isinstance(data, dict):
                return data
        except (ValueError, TypeError):
            pass
        return None

    @property
    def description_text(self):
        """Return plain-text description suitable for AI calls."""
        sections = self.description_sections
        if sections:
            parts = []
            for key, label in self._SECTION_LABELS:
                val = (sections.get(key) or '').strip()
                if val:
                    parts.append(f"{label}:\n{val}")
            return '\n\n'.join(parts) if parts else self.description
        return self.description

    def to_snapshot_dict(self):
        """Every re-creatable field, for stashing in DeletedJob.snapshot."""
        return {
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "employment_type": self.employment_type,
            "category": self.category,
            "status": self.status,
            "interview_length": self.interview_length,
            "interview_focus": self.interview_focus,
            "interview_questions": self.interview_questions,
            "salary_usd": self.salary_usd,
            "salary_max_usd": self.salary_max_usd,
            "pay_type": self.pay_type,
            "salary_currency": self.salary_currency,
        }


class DeletedJob(db.Model):
    """Snapshot of a Job taken right before it's deleted, so an accidental
    delete can be undone. company_id is deliberately not a ForeignKey - when
    a whole Company is deleted (admin.delete_company), its jobs are snapshotted
    here first but the Company row itself is gone by the time this survives it,
    so a hard FK would leave a dangling reference. Restoring only recreates the
    job listing itself; applications/messages/videos already cascade-deleted
    alongside it are not recoverable."""
    id = db.Column(db.Integer, primary_key=True)
    original_job_id = db.Column(db.Integer, nullable=False)
    company_id = db.Column(db.Integer, nullable=False)
    company_name = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    snapshot = db.Column(db.Text, nullable=False)  # JSON of Job.to_snapshot_dict()
    applicant_count = db.Column(db.Integer, nullable=False, default=0)
    deleted_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    deleted_source = db.Column(db.String(20), nullable=False)  # "employer" | "admin"
    restored_job_id = db.Column(db.Integer)  # set once restored, so it can't be restored twice
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    deleted_by = db.relationship("User")


class CandidateProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    headline = db.Column(db.String(200))
    resume_text = db.Column(db.Text)
    linkedin_url = db.Column(db.String(300))
    target_roles = db.Column(db.String(300))
    # Talent pool fields
    open_to_work = db.Column(db.Boolean, nullable=False, default=False)
    skills = db.Column(db.Text)           # comma-separated
    work_preference = db.Column(db.String(50))   # Remote / Hybrid / On-site / Any
    availability = db.Column(db.String(50))      # Immediately / 2 weeks / 1 month / 3 months
    years_experience = db.Column(db.String(20))  # 0-1 / 1-3 / 3-5 / 5-10 / 10+
    location = db.Column(db.String(200))         # city / country they're based in

    user = db.relationship("User", backref=db.backref("candidate_profile", uselist=False))


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    candidate_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    resume_text = db.Column(db.Text, nullable=False)
    work_authorization = db.Column(db.Text)  # JSON: DOB, residence, attestations, signature
    scheduled_meeting = db.Column(db.Text)  # JSON: type, datetime, location_or_url, notes
    match_score = db.Column(db.Integer)
    match_explanation = db.Column(db.Text)
    interview_transcript = db.Column(db.Text)
    interview_audio_log = db.Column(db.Text)  # JSON list of {role, text, audio_filename}
    interview_verdict = db.Column(db.String(20))  # "Strong Yes" | "Yes" | "No" | "Strong No"
    manual_interview_score = db.Column(db.Integer)  # 0-100, employer's own rating after a live/manual interview
    status = db.Column(db.String(20), nullable=False, default="applied")  # applied | interviewing | rejected | hired
    candidate_confirmed_hire = db.Column(db.Boolean, nullable=False, default=False)  # candidate must confirm before the fee invoice fires
    hire_confirmed_at = db.Column(db.DateTime(timezone=True))
    # Actual negotiated compensation at hire time, entered by the employer -
    # the placement fee is calculated from this, not the job posting's
    # advertised salary, which the employer has no incentive to keep
    # accurate once someone's actually hired.
    hire_salary_usd = db.Column(db.Integer)
    hire_pay_type = db.Column(db.String(20))  # yearly | hourly | monthly | stipend | contract
    hire_salary_disputed = db.Column(db.Boolean, nullable=False, default=False)  # candidate says the entered figure is wrong
    hire_evidence_filename = db.Column(db.String(200))  # optional offer-letter/screenshot upload
    fee_paid = db.Column(db.Boolean, nullable=False, default=False)
    stripe_payment_link = db.Column(db.String(500))  # Stripe Payment Link URL sent to employer on hire
    # Hourly hires bill monthly for as long as the engagement actually runs,
    # instead of one lump sum assuming a full 2,080-hour year up front -
    # stripe_payment_link above is a subscription-mode link in this case.
    hire_billing_subscription_id = db.Column(db.String(100))
    hire_engagement_ended_at = db.Column(db.DateTime(timezone=True))  # set when the employer stops billing
    fee_reminder_sent_at = db.Column(db.DateTime(timezone=True))  # last overdue-fee reminder email, throttles re-sends
    employer_notes = db.Column(db.Text)  # private notes visible only to employer
    withdrawn = db.Column(db.Boolean, nullable=False, default=False)
    candidate_feedback = db.Column(db.Text)  # employer-approved AI feedback sent to candidate on rejection
    skills_roadmap = db.Column(db.Text)  # JSON: AI-generated skill gap action plan (generated when score < 65)
    interview_saved_session = db.Column(db.Text)  # JSON: partial history saved for later resumption
    ai_likelihood = db.Column(db.Text)  # JSON: {score, label, reasons} - AI-generation probability for candidate answers
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    job = db.relationship("Job", backref="applications")
    candidate = db.relationship("User", backref="applications")


class JobActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    detail = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    job = db.relationship("Job", backref="activity_log")


class SavedJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    __table_args__ = (db.UniqueConstraint("user_id", "job_id"),)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    link = db.Column(db.String(300))
    read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())


class CompanyMember(db.Model):
    """Additional employer users who can manage a company's jobs and applicants."""
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    joined_at = db.Column(db.DateTime(timezone=True), default=func.now())

    company = db.relationship("Company", backref="members")
    user = db.relationship("User", backref="company_memberships")

    __table_args__ = (db.UniqueConstraint("company_id", "user_id"),)


class StripeWebhookEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(255), nullable=False, unique=True)
    processed_at = db.Column(db.DateTime(timezone=True), default=func.now())


class Referral(db.Model):
    """A commission owed to whoever referred a candidate, once that
    candidate is hired and the employer's placement fee is actually paid.
    Created once per Application (see views.stripe_webhook) - commission is
    10% of the platform's 15% placement fee, tracked here and paid out
    manually by an admin (see admin.referrals / admin.mark_referral_paid)."""
    id = db.Column(db.Integer, primary_key=True)
    referrer_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    referred_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False, unique=True)
    commission_usd = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="owed")  # owed | paid
    paid_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    referrer = db.relationship("User", foreign_keys=[referrer_user_id])
    referred = db.relationship("User", foreign_keys=[referred_user_id])
    application = db.relationship("Application", backref=db.backref("referral", uselist=False))


class EarnTask(db.Model):
    """A task posted for professionals to complete and earn money."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    task_type = db.Column(db.String(30), nullable=False, default='ranking')  # ranking | rating | factcheck | writing
    domain = db.Column(db.String(100))  # e.g. "Legal", "Software", "Healthcare"
    pay_cents = db.Column(db.Integer, nullable=False, default=500)  # payment in cents
    estimated_minutes = db.Column(db.Integer, default=5)
    status = db.Column(db.String(20), nullable=False, default='open')  # open | closed
    required_domains = db.Column(db.Text)   # JSON list; None means open to all domains
    min_responses = db.Column(db.Integer, nullable=False, default=3)  # workers needed before consensus
    consensus_answer = db.Column(db.Text)   # JSON {answer, total, distribution} - set once min_responses hit
    # For ranking tasks: two AI responses to compare
    option_a = db.Column(db.Text)
    option_b = db.Column(db.Text)
    # For rating/factcheck tasks: single AI response
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    submissions = db.relationship('TaskSubmission', backref='task', lazy=True)


class TaskSubmission(db.Model):
    """A professional's completed response to an EarnTask."""
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('earn_task.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    response = db.Column(db.Text)        # chosen option / rating / written response
    explanation = db.Column(db.Text)     # optional explanation
    agreement_score = db.Column(db.Float)  # 0–1; set when consensus is computed for this task
    earnings_cents = db.Column(db.Integer, nullable=False, default=0)
    paid_out = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    user = db.relationship('User', backref='task_submissions')


class ContractorProfile(db.Model):
    """Tracks a user's expertise domains and earn stats for the AI training contractor network."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    domains = db.Column(db.Text, nullable=False)         # JSON list of EARN_DOMAINS values
    quality_score = db.Column(db.Float, nullable=False, default=1.0)   # 0–1; updated by consensus
    tasks_completed = db.Column(db.Integer, nullable=False, default=0)
    stripe_account_id = db.Column(db.String(100))        # Stripe Connect Express account ID
    payout_enabled = db.Column(db.Boolean, nullable=False, default=False)  # True once Stripe onboarding complete
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    user = db.relationship("User", backref=db.backref("contractor_profile", uselist=False))


class MeetingProposal(db.Model):
    """Employer proposes 2-3 time slots; candidate picks one and the room is created."""
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False)
    employer_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    slots = db.Column(db.Text, nullable=False)        # JSON list of {date, time} dicts
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | accepted | expired
    accepted_slot = db.Column(db.Text)               # JSON {date, time} chosen by candidate
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    application = db.relationship("Application", backref=db.backref("meeting_proposals", lazy=True))
    employer = db.relationship("User", foreign_keys=[employer_user_id])


PLAN_LIMITS = {
    'free':    {'jobs': 3,    'interviews_per_month': 20,  'talent_search': False},
    'starter': {'jobs': 10,   'interviews_per_month': 150, 'talent_search': True},
    'pro':     {'jobs': 9999, 'interviews_per_month': 9999, 'talent_search': True},
}


class Message(db.Model):
    """In-app message between employer and candidate on a specific application."""
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False)
    sender_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    sender = db.relationship("User", foreign_keys=[sender_user_id])
    application = db.relationship("Application", backref=db.backref("messages", lazy=True, order_by="Message.created_at"))


class EmployerSubscription(db.Model):
    """Stripe subscription plan for an employer company."""
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False, unique=True)
    plan = db.Column(db.String(20), nullable=False, default='free')   # free | starter | pro
    stripe_customer_id = db.Column(db.String(100))
    stripe_subscription_id = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False, default='active')  # active | canceled | past_due
    current_period_end = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    company = db.relationship("Company", backref=db.backref("subscription", uselist=False))


class MeetingRoom(db.Model):
    """An in-app video meeting room created via Daily.co for a specific application."""
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False)
    employer_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    room_name = db.Column(db.String(200), nullable=False, unique=True)
    room_url = db.Column(db.String(500), nullable=False)
    scheduled_date = db.Column(db.String(20))   # YYYY-MM-DD
    scheduled_time = db.Column(db.String(10))   # HH:MM
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    # Independent local-camera recordings captured client-side in the call
    # page itself, not Daily.co's cloud recording - see meeting_room.html.
    # Storage paths (Supabase Storage), not URLs - resolved to a signed URL
    # at playback time.
    candidate_recording_path = db.Column(db.String(300))
    employer_recording_path = db.Column(db.String(300))

    application = db.relationship("Application", backref=db.backref("meeting_rooms", lazy=True))
    employer = db.relationship("User", foreign_keys=[employer_user_id])


class CompanyInvite(db.Model):
    """Pending invitation for someone to join a company as a team member."""
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    invited_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    token = db.Column(db.String(100), nullable=False, unique=True)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    company = db.relationship("Company", backref="invites")


class DataBuyer(db.Model):
    """An outside company subscribed to download the Earn marketplace's
    graded task data (rankings, ratings, factchecks, writing) as training data."""
    __tablename__ = "data_buyer"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    contact_email = db.Column(db.String(150), nullable=False)
    stripe_customer_id = db.Column(db.String(100))
    stripe_subscription_id = db.Column(db.String(100))
    subscription_status = db.Column(db.String(20), nullable=False, default="inactive")  # inactive | active | canceled
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    members = db.relationship("User", backref="data_buyer", foreign_keys="User.data_buyer_id")


class Feedback(db.Model):
    """A rating + comment left by a candidate or employer about their
    experience, collected at key moments (interview completion, hire
    resolution) rather than through a generic always-on form."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # candidate | employer
    context = db.Column(db.String(30), nullable=False)  # interview_completed | application_resolved | hire_closed
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    user = db.relationship("User")
    application = db.relationship("Application", backref="feedback_entries")

    __table_args__ = (db.UniqueConstraint("user_id", "application_id", "context"),)


class FeedbackInsight(db.Model):
    """Cached AI-generated summary + actionable recommendations from analyzing
    Feedback rows - regenerated on demand by an admin, not on every page view,
    since it's a real OpenAI call and feedback doesn't change that fast."""
    id = db.Column(db.Integer, primary_key=True)
    summary = db.Column(db.Text, nullable=False)
    recommendations = db.Column(db.Text)  # JSON list of {title, detail}
    feedback_count = db.Column(db.Integer, nullable=False, default=0)
    generated_at = db.Column(db.DateTime(timezone=True), default=func.now())
