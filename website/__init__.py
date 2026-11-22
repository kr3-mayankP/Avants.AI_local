# ----------------------------------------------------------------
# CHANGE BLOCK: 2026-11-22
# OLD IMPLEMENTATION - commented snapshot from Git HEAD
# ----------------------------------------------------------------
# OLD CODE: import os
# OLD CODE: from os import path
# OLD CODE: from flask import Flask, request
# OLD CODE: from flask_sqlalchemy import SQLAlchemy
# OLD CODE: from flask_login import LoginManager
# OLD CODE: from flask_mail import Mail
# OLD CODE: from flask_limiter import Limiter
# OLD CODE: from flask_limiter.util import get_remote_address
# OLD CODE: from sqlalchemy import text
# OLD CODE: from dotenv import load_dotenv
# OLD CODE: from config import Config
# OLD CODE:
# OLD CODE: # override=False (the dotenv default) so an env var already set in the process
# OLD CODE: # - e.g. a test/admin script deliberately pointing DATABASE_URL at a throwaway
# OLD CODE: # database before importing this package - always wins over .env. With
# OLD CODE: # override=True this silently clobbered that kind of safety override and once
# OLD CODE: # sent a script's db.drop_all()/create_all() at the real production database.
# OLD CODE: load_dotenv(override=False)
# OLD CODE:
# OLD CODE: db = SQLAlchemy()
# OLD CODE: mail = Mail()
# OLD CODE: limiter = Limiter(key_func=get_remote_address, default_limits=[])
# OLD CODE: DB_NAME = "database.db"
# OLD CODE:
# OLD CODE:
# OLD CODE: def _run_migrations(db):
# OLD CODE:     """Add columns that were introduced after the initial schema.
# OLD CODE:     Each ALTER TABLE is wrapped in try/except - safe to run on every
# OLD CODE:     startup, no-op when the column already exists."""
# OLD CODE:     new_columns = [
# OLD CODE:         # company - extended profile fields
# OLD CODE:         "ALTER TABLE company ADD COLUMN description TEXT",
# OLD CODE:         "ALTER TABLE company ADD COLUMN industry VARCHAR(100)",
# OLD CODE:         "ALTER TABLE company ADD COLUMN size VARCHAR(50)",
# OLD CODE:         "ALTER TABLE company ADD COLUMN location VARCHAR(200)",
# OLD CODE:         # job - salary + interview config
# OLD CODE:         "ALTER TABLE job ADD COLUMN salary_usd INTEGER",
# OLD CODE:         "ALTER TABLE job ADD COLUMN employment_type VARCHAR(50)",
# OLD CODE:         "ALTER TABLE job ADD COLUMN interview_length VARCHAR(20) NOT NULL DEFAULT 'standard'",
# OLD CODE:         "ALTER TABLE job ADD COLUMN interview_focus TEXT",
# OLD CODE:         "ALTER TABLE job ADD COLUMN interview_questions TEXT",
# OLD CODE:         # application - payment + interview fields
# OLD CODE:         "ALTER TABLE application ADD COLUMN work_authorization TEXT",
# OLD CODE:         "ALTER TABLE application ADD COLUMN scheduled_meeting TEXT",
# OLD CODE:         "ALTER TABLE application ADD COLUMN match_score INTEGER",
# OLD CODE:         "ALTER TABLE application ADD COLUMN match_explanation TEXT",
# OLD CODE:         "ALTER TABLE application ADD COLUMN interview_transcript TEXT",
# OLD CODE:         "ALTER TABLE application ADD COLUMN interview_audio_log TEXT",
# OLD CODE:         "ALTER TABLE application ADD COLUMN interview_verdict VARCHAR(20)",
# OLD CODE:         "ALTER TABLE application ADD COLUMN fee_paid BOOLEAN NOT NULL DEFAULT FALSE",
# OLD CODE:         "ALTER TABLE application ADD COLUMN stripe_payment_link VARCHAR(500)",
# OLD CODE:         # user - verification + notifications
# OLD CODE:         "ALTER TABLE \"user\" ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT TRUE",
# OLD CODE:         "ALTER TABLE \"user\" ADD COLUMN notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE",
# OLD CODE:         # company - logo
# OLD CODE:         "ALTER TABLE company ADD COLUMN logo_filename VARCHAR(200)",
# OLD CODE:         "ALTER TABLE company ADD COLUMN logo_version INTEGER NOT NULL DEFAULT 0",
# OLD CODE:         # application - employer notes + withdrawal
# OLD CODE:         "ALTER TABLE application ADD COLUMN employer_notes TEXT",
# OLD CODE:         "ALTER TABLE application ADD COLUMN withdrawn BOOLEAN NOT NULL DEFAULT FALSE",
# OLD CODE:         # job - salary range
# OLD CODE:         "ALTER TABLE job ADD COLUMN salary_max_usd INTEGER",
# OLD CODE:         "ALTER TABLE job ADD COLUMN pay_type VARCHAR(20) NOT NULL DEFAULT 'yearly'",
# OLD CODE:         # application - rejection feedback sent to candidate
# OLD CODE:         "ALTER TABLE application ADD COLUMN candidate_feedback TEXT",
# OLD CODE:         # application - AI-generated skills gap roadmap
# OLD CODE:         "ALTER TABLE application ADD COLUMN skills_roadmap TEXT",
# OLD CODE:         # company - blind hiring mode
# OLD CODE:         "ALTER TABLE company ADD COLUMN blind_mode_enabled BOOLEAN NOT NULL DEFAULT FALSE",
# OLD CODE:         # company - employer terms acceptance audit trail
# OLD CODE:         "ALTER TABLE company ADD COLUMN terms_accepted_at TIMESTAMP WITH TIME ZONE",
# OLD CODE:         "ALTER TABLE company ADD COLUMN terms_accepted_ip VARCHAR(45)",
# OLD CODE:         "ALTER TABLE company ADD COLUMN terms_version VARCHAR(10)",
# OLD CODE:         # application - saved interview session for resume-later
# OLD CODE:         "ALTER TABLE application ADD COLUMN interview_saved_session TEXT",
# OLD CODE:         # user - admin flag
# OLD CODE:         "ALTER TABLE \"user\" ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE",
# OLD CODE:         # application - AI-generation likelihood score for candidate interview answers
# OLD CODE:         "ALTER TABLE application ADD COLUMN ai_likelihood TEXT",
# OLD CODE:         # user - supabase auth uid for admin API calls
# OLD CODE:         "ALTER TABLE \"user\" ADD COLUMN supabase_uid VARCHAR(200)",
# OLD CODE:         # candidate_profile - profile basics
# OLD CODE:         "ALTER TABLE candidate_profile ADD COLUMN headline VARCHAR(200)",
# OLD CODE:         "ALTER TABLE candidate_profile ADD COLUMN target_roles VARCHAR(300)",
# OLD CODE:         # candidate_profile - talent pool opt-in fields
# OLD CODE:         "ALTER TABLE candidate_profile ADD COLUMN open_to_work BOOLEAN NOT NULL DEFAULT FALSE",
# OLD CODE:         "ALTER TABLE candidate_profile ADD COLUMN skills TEXT",
# OLD CODE:         "ALTER TABLE candidate_profile ADD COLUMN work_preference VARCHAR(50)",
# OLD CODE:         "ALTER TABLE candidate_profile ADD COLUMN availability VARCHAR(50)",
# OLD CODE:         "ALTER TABLE candidate_profile ADD COLUMN years_experience VARCHAR(20)",
# OLD CODE:         "ALTER TABLE candidate_profile ADD COLUMN location VARCHAR(200)",
# OLD CODE:         # earn_task - domain gating for contractor network
# OLD CODE:         "ALTER TABLE earn_task ADD COLUMN required_domains TEXT",
# OLD CODE:         # earn_task - consensus scoring
# OLD CODE:         "ALTER TABLE earn_task ADD COLUMN min_responses INTEGER NOT NULL DEFAULT 3",
# OLD CODE:         "ALTER TABLE earn_task ADD COLUMN consensus_answer TEXT",
# OLD CODE:         # task_submission - per-submission agreement with consensus
# OLD CODE:         "ALTER TABLE task_submission ADD COLUMN agreement_score REAL",
# OLD CODE:         # contractor_profile - Stripe Connect payout flag
# OLD CODE:         "ALTER TABLE contractor_profile ADD COLUMN payout_enabled BOOLEAN NOT NULL DEFAULT FALSE",
# OLD CODE:         # application - candidate must confirm a hire before the fee invoice fires
# OLD CODE:         "ALTER TABLE application ADD COLUMN candidate_confirmed_hire BOOLEAN NOT NULL DEFAULT FALSE",
# OLD CODE:         "ALTER TABLE application ADD COLUMN hire_confirmed_at TIMESTAMP WITH TIME ZONE",
# OLD CODE:         # user - werkzeug's scrypt password hashes run ~162 chars, longer than
# OLD CODE:         # the original 150-char cap, so every email/password signup was
# OLD CODE:         # failing with a StringDataRightTruncation error
# OLD CODE:         "ALTER TABLE \"user\" ALTER COLUMN password TYPE VARCHAR(255)",
# OLD CODE:         # user - link to a DataBuyer account (outside company subscribed to Earn task exports)
# OLD CODE:         "ALTER TABLE \"user\" ADD COLUMN data_buyer_id INTEGER REFERENCES data_buyer(id)",
# OLD CODE:         "ALTER TABLE \"user\" ADD COLUMN is_data_buyer_admin BOOLEAN NOT NULL DEFAULT FALSE",
# OLD CODE:         # company - work-email domain, so later employer signups from the same
# OLD CODE:         # company land in the same hub instead of each creating a new Company
# OLD CODE:         "ALTER TABLE company ADD COLUMN email_domain VARCHAR(150)",
# OLD CODE:         # company - typed e-signature on the Employer Platform Agreement
# OLD CODE:         "ALTER TABLE company ADD COLUMN terms_signature_name VARCHAR(200)",
# OLD CODE:         # application - actual hire compensation (fee basis), candidate dispute flag, evidence upload
# OLD CODE:         "ALTER TABLE application ADD COLUMN hire_salary_usd INTEGER",
# OLD CODE:         "ALTER TABLE application ADD COLUMN hire_pay_type VARCHAR(20)",
# OLD CODE:         "ALTER TABLE application ADD COLUMN hire_salary_disputed BOOLEAN NOT NULL DEFAULT FALSE",
# OLD CODE:         "ALTER TABLE application ADD COLUMN hire_evidence_filename VARCHAR(200)",
# OLD CODE:         # application - recurring monthly billing for hourly hires, instead of one lump sum
# OLD CODE:         "ALTER TABLE application ADD COLUMN hire_billing_subscription_id VARCHAR(100)",
# OLD CODE:         "ALTER TABLE application ADD COLUMN hire_engagement_ended_at TIMESTAMP WITH TIME ZONE",
# OLD CODE:         "ALTER TABLE application ADD COLUMN fee_reminder_sent_at TIMESTAMP WITH TIME ZONE",
# OLD CODE:         # job - currency the advertised salary is denominated in
# OLD CODE:         "ALTER TABLE job ADD COLUMN salary_currency VARCHAR(3) NOT NULL DEFAULT 'USD'",
# OLD CODE:         # user - referral program: own shareable code + who referred them
# OLD CODE:         "ALTER TABLE \"user\" ADD COLUMN referral_code VARCHAR(12)",
# OLD CODE:         "ALTER TABLE \"user\" ADD COLUMN referred_by_user_id INTEGER REFERENCES \"user\"(id)",
# OLD CODE:         # meeting_room - independent local-camera recordings captured client-side
# OLD CODE:         "ALTER TABLE meeting_room ADD COLUMN candidate_recording_path VARCHAR(300)",
# OLD CODE:         "ALTER TABLE meeting_room ADD COLUMN employer_recording_path VARCHAR(300)",
# OLD CODE:         # job - employer can require camera on, not just optional, for the AI interview
# OLD CODE:         "ALTER TABLE job ADD COLUMN camera_required BOOLEAN NOT NULL DEFAULT FALSE",
# OLD CODE:         # application - employer's own 0-100 rating after a live/manual interview
# OLD CODE:         "ALTER TABLE application ADD COLUMN manual_interview_score INTEGER",
# OLD CODE:     ]
# OLD CODE:     for stmt in new_columns:
# OLD CODE:         try:
# OLD CODE:             with db.engine.connect() as conn:
# OLD CODE:                 conn.execute(text(stmt))
# OLD CODE:                 conn.commit()
# OLD CODE:         except Exception:
# OLD CODE:             pass
# OLD CODE:
# OLD CODE:     _backfill_company_email_domains(db)
# OLD CODE:     _backfill_referral_codes(db)
# OLD CODE:
# OLD CODE:
# OLD CODE: def _backfill_referral_codes(db):
# OLD CODE:     """One-time backfill for users created before referral_code existed -
# OLD CODE:     ALTER TABLE ADD COLUMN leaves existing rows NULL since the model's
# OLD CODE:     default= only applies to new ORM inserts, not raw SQL. No-ops once every
# OLD CODE:     user already has a code."""
# OLD CODE:     import secrets
# OLD CODE:     from .models import User
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         users = User.query.filter(User.referral_code.is_(None)).all()
# OLD CODE:         for user in users:
# OLD CODE:             user.referral_code = secrets.token_urlsafe(6)
# OLD CODE:         db.session.commit()
# OLD CODE:     except Exception:
# OLD CODE:         db.session.rollback()
# OLD CODE:
# OLD CODE:
# OLD CODE: def _backfill_company_email_domains(db):
# OLD CODE:     """One-time backfill for companies created before email_domain existed -
# OLD CODE:     derives it from the owner's email so old companies also become joinable
# OLD CODE:     by domain. No-ops once every company already has a domain set."""
# OLD CODE:     from .models import Company, User, FREE_EMAIL_DOMAINS
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         companies = Company.query.filter(Company.email_domain.is_(None)).all()
# OLD CODE:         for company in companies:
# OLD CODE:             owner = User.query.get(company.owner_user_id)
# OLD CODE:             if not owner or not owner.email or '@' not in owner.email:
# OLD CODE:                 continue
# OLD CODE:             domain = owner.email.split('@')[-1].lower()
# OLD CODE:             if domain in FREE_EMAIL_DOMAINS:
# OLD CODE:                 continue
# OLD CODE:             company.email_domain = domain
# OLD CODE:         db.session.commit()
# OLD CODE:     except Exception:
# OLD CODE:         db.session.rollback()
# OLD CODE:
# OLD CODE: def create_app():
# OLD CODE:     app = Flask(__name__)
# OLD CODE:     app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ebsjkfbsdjkfbjkdfb')
# OLD CODE:
# OLD CODE:     database_url = os.environ.get('DATABASE_URL')
# OLD CODE:     if database_url:
# OLD CODE:         # Render/Heroku-style URLs sometimes use the old "postgres://" scheme,
# OLD CODE:         # which SQLAlchemy 1.4+ no longer accepts. Also force the psycopg2
# OLD CODE:         # driver explicitly rather than leaving it to SQLAlchemy's default
# OLD CODE:         # resolution for a bare "postgresql://" URL - that silently started
# OLD CODE:         # trying the psycopg (v3) driver instead, which isn't installed
# OLD CODE:         # (only psycopg2-binary is, per requirements.txt), crashing the app
# OLD CODE:         # at startup with "ModuleNotFoundError: No module named 'psycopg'".
# OLD CODE:         if database_url.startswith('postgres://'):
# OLD CODE:             database_url = database_url.replace('postgres://', 'postgresql://', 1)
# OLD CODE:         if database_url.startswith('postgresql://'):
# OLD CODE:             database_url = database_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
# OLD CODE:         app.config['SQLALCHEMY_DATABASE_URI'] = database_url
# OLD CODE:         if database_url.startswith('postgresql+psycopg2://'):
# OLD CODE:             # This connect_args is Postgres-only syntax - applying it
# OLD CODE:             # unconditionally also broke DATABASE_URL pointed at a sqlite
# OLD CODE:             # file (e.g. for local/isolated testing), since sqlite3.connect()
# OLD CODE:             # has no "options" kwarg and raises a TypeError at every query.
# OLD CODE:             app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
# OLD CODE:                 "pool_pre_ping": True,
# OLD CODE:                 "connect_args": {"options": "-c default_transaction_read_only=off"},
# OLD CODE:             }
# OLD CODE:     else:
# OLD CODE:         #sqlite is stored at this location - local dev fallback only
# OLD CODE:         app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
# OLD CODE:
# OLD CODE:     app.config.from_object(Config)
# OLD CODE:     db.init_app(app)
# OLD CODE:     mail.init_app(app)
# OLD CODE:     limiter.init_app(app)
# OLD CODE:
# OLD CODE:     BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# OLD CODE:     audio_path = os.path.join(BASE_DIR, "..", "audio")
# OLD CODE:     upload_path = os.path.join(BASE_DIR, "..", "uploads")
# OLD CODE:
# OLD CODE:     app.config["AUDIO_FOLDER"] = audio_path
# OLD CODE:     app.config["UPLOAD_FOLDER"] = upload_path
# OLD CODE:
# OLD CODE:     os.makedirs(audio_path, exist_ok=True)
# OLD CODE:     os.makedirs(upload_path, exist_ok=True)
# OLD CODE:
# OLD CODE:     from .models import User, Company, Job, CandidateProfile, Application, CompanyMember, CompanyInvite, EarnTask, TaskSubmission, SavedJob, ContractorProfile, MeetingRoom, Message, EmployerSubscription, MeetingProposal, DataBuyer, Feedback, FeedbackInsight, DeletedJob
# OLD CODE:
# OLD CODE:     with app.app_context():
# OLD CODE:         db.create_all()
# OLD CODE:         _run_migrations(db)
# OLD CODE:         from community_stats import initialize_counter
# OLD CODE:         initialize_counter(db.engine)
# OLD CODE:
# OLD CODE:     from .views import views
# OLD CODE:     from .auth import auth
# OLD CODE:     from .employer import employer
# OLD CODE:     from .candidate import candidate
# OLD CODE:     from .earn import earn
# OLD CODE:     from .admin import admin_bp
# OLD CODE:     from .data_market import data_market
# OLD CODE:
# OLD CODE:     app.register_blueprint(views, url_prefix='/')
# OLD CODE:     app.register_blueprint(auth, url_prefix='/')
# OLD CODE:     app.register_blueprint(employer, url_prefix='/')
# OLD CODE:     app.register_blueprint(candidate, url_prefix='/')
# OLD CODE:     app.register_blueprint(earn, url_prefix='/')
# OLD CODE:     app.register_blueprint(admin_bp, url_prefix='/')
# OLD CODE:     app.register_blueprint(data_market, url_prefix='/')
# OLD CODE:
# OLD CODE:     from datetime import datetime, timezone
# OLD CODE:     from flask_login import current_user as _cu
# OLD CODE:
# OLD CODE:     @app.after_request
# OLD CODE:     def stash_referral_code(response):
# OLD CODE:         """?ref=CODE on any page load gets stashed in a cookie so it survives
# OLD CODE:         the multi-step signup flow (including the Google/Supabase OAuth
# OLD CODE:         redirect chain) - read back in auth.py when the User row is actually
# OLD CODE:         created. Doesn't overwrite an existing cookie, so the first referrer
# OLD CODE:         wins if someone clicks multiple referral links before signing up."""
# OLD CODE:         ref = request.args.get('ref')
# OLD CODE:         if ref and not request.cookies.get('ref_code'):
# OLD CODE:             response.set_cookie('ref_code', ref, max_age=60 * 60 * 24 * 30, httponly=True, samesite='Lax')
# OLD CODE:         return response
# OLD CODE:
# OLD CODE:     @app.context_processor
# OLD CODE:     def inject_globals():
# OLD CODE:         if not _cu.is_authenticated:
# OLD CODE:             return {"unread_messages": 0}
# OLD CODE:         from .models import Message, Application, Job, Company, CompanyMember
# OLD CODE:         try:
# OLD CODE:             base_q = (
# OLD CODE:                 db.session.query(db.func.count(Message.id))
# OLD CODE:                 .join(Application, Application.id == Message.application_id)
# OLD CODE:                 .filter(Message.read == False, Message.sender_user_id != _cu.id)
# OLD CODE:             )
# OLD CODE:             if _cu.role == 'employer':
# OLD CODE:                 company = Company.query.filter_by(owner_user_id=_cu.id).first()
# OLD CODE:                 if not company:
# OLD CODE:                     membership = CompanyMember.query.filter_by(user_id=_cu.id).first()
# OLD CODE:                     company = membership.company if membership else None
# OLD CODE:                 count = (
# OLD CODE:                     base_q.join(Job, Job.id == Application.job_id)
# OLD CODE:                     .filter(Job.company_id == company.id)
# OLD CODE:                     .scalar() or 0
# OLD CODE:                 ) if company else 0
# OLD CODE:             else:
# OLD CODE:                 count = base_q.filter(Application.candidate_user_id == _cu.id).scalar() or 0
# OLD CODE:             return {"unread_messages": count}
# OLD CODE:         except Exception:
# OLD CODE:             db.session.rollback()
# OLD CODE:             return {"unread_messages": 0}
# OLD CODE:
# OLD CODE:     import json as _json
# OLD CODE:
# OLD CODE:     @app.template_filter('from_json')
# OLD CODE:     def from_json_filter(s):
# OLD CODE:         try:
# OLD CODE:             return _json.loads(s)
# OLD CODE:         except Exception:
# OLD CODE:             return []
# OLD CODE:
# OLD CODE:     @app.template_filter('time_ago')
# OLD CODE:     def time_ago_filter(dt):
# OLD CODE:         if not dt:
# OLD CODE:             return ''
# OLD CODE:         now = datetime.now(timezone.utc)
# OLD CODE:         if dt.tzinfo is None:
# OLD CODE:             dt = dt.replace(tzinfo=timezone.utc)
# OLD CODE:         diff = now - dt
# OLD CODE:         s = int(diff.total_seconds())
# OLD CODE:         if s < 60:
# OLD CODE:             return 'just now'
# OLD CODE:         if s < 3600:
# OLD CODE:             m = s // 60
# OLD CODE:             return f"{m} minute{'s' if m != 1 else ''} ago"
# OLD CODE:         if s < 86400:
# OLD CODE:             h = s // 3600
# OLD CODE:             return f"{h} hour{'s' if h != 1 else ''} ago"
# OLD CODE:         d = s // 86400
# OLD CODE:         if d < 30:
# OLD CODE:             return f"{d} day{'s' if d != 1 else ''} ago"
# OLD CODE:         mo = d // 30
# OLD CODE:         if mo < 12:
# OLD CODE:             return f"{mo} month{'s' if mo != 1 else ''} ago"
# OLD CODE:         yr = d // 365
# OLD CODE:         return f"{yr} year{'s' if yr != 1 else ''} ago"
# OLD CODE:
# OLD CODE:     @app.template_filter('salary_range')
# OLD CODE:     def salary_range_filter(job):
# OLD CODE:         if not job.salary_usd:
# OLD CODE:             return None
# OLD CODE:         from .models import SUPPORTED_CURRENCIES, DEFAULT_CURRENCY
# OLD CODE:         pay_type = getattr(job, 'pay_type', None) or 'yearly'
# OLD CODE:         currency = getattr(job, 'salary_currency', None) or DEFAULT_CURRENCY
# OLD CODE:         symbol = SUPPORTED_CURRENCIES.get(currency, SUPPORTED_CURRENCIES[DEFAULT_CURRENCY])['symbol']
# OLD CODE:
# OLD CODE:         # Formatting: hourly stays as raw number; everything else uses K if >= 1000
# OLD CODE:         def fmt(n, force_raw=False):
# OLD CODE:             if force_raw or n < 1000:
# OLD CODE:                 return f"{symbol}{n:,}"
# OLD CODE:             return f"{symbol}{round(n / 1000)}K"
# OLD CODE:
# OLD CODE:         hourly = pay_type == 'hourly'
# OLD CODE:         lo = fmt(job.salary_usd, force_raw=hourly)
# OLD CODE:         hi = fmt(job.salary_max_usd, force_raw=hourly) if job.salary_max_usd and job.salary_max_usd > job.salary_usd else None
# OLD CODE:
# OLD CODE:         suffixes = {
# OLD CODE:             'yearly':   '/yr',
# OLD CODE:             'hourly':   '/hr',
# OLD CODE:             'monthly':  '/mo',
# OLD CODE:             'stipend':  ' stipend',
# OLD CODE:             'contract': ' (project)',
# OLD CODE:         }
# OLD CODE:         suffix = suffixes.get(pay_type, '/yr')
# OLD CODE:
# OLD CODE:         if hi:
# OLD CODE:             return f"{lo}–{hi}{suffix}"
# OLD CODE:         return f"{lo}{suffix}"
# OLD CODE:
# OLD CODE:
# OLD CODE:     login_manager = LoginManager()
# OLD CODE:     login_manager.login_view = 'auth.login'
# OLD CODE:     login_manager.init_app(app)
# OLD CODE:
# OLD CODE:     @login_manager.user_loader
# OLD CODE:     def load_user(id):
# OLD CODE:         return User.query.get(int(id))
# OLD CODE:
# OLD CODE:     return app
# OLD CODE:
# OLD CODE: #function checks if the database exists
# OLD CODE: def create_database(app):
# OLD CODE:     if not path.exists('website/' + DB_NAME):      
# OLD CODE:         print('Created Database!')
# OLD CODE:
# ----------------------------------------------------------------
# NEW IMPLEMENTATION - active code starts below
# ----------------------------------------------------------------
import os
import secrets
import hmac
from os import path
from flask import Flask, abort, request, session
from urllib.parse import urlsplit
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import text
from dotenv import load_dotenv
from config import Config

# override=False (the dotenv default) so an env var already set in the process
# - e.g. a test/admin script deliberately pointing DATABASE_URL at a throwaway
# database before importing this package - always wins over .env. With
# override=True this silently clobbered that kind of safety override and once
# sent a script's db.drop_all()/create_all() at the real production database.
load_dotenv(override=False)

db = SQLAlchemy()
mail = Mail()
limiter = Limiter(key_func=get_remote_address, default_limits=[])
DB_NAME = "database.db"


def _run_migrations(db):
    """Add columns that were introduced after the initial schema.
    Each ALTER TABLE is wrapped in try/except - safe to run on every
    startup, no-op when the column already exists."""
    new_columns = [
        # company - extended profile fields
        "ALTER TABLE company ADD COLUMN description TEXT",
        "ALTER TABLE company ADD COLUMN industry VARCHAR(100)",
        "ALTER TABLE company ADD COLUMN size VARCHAR(50)",
        "ALTER TABLE company ADD COLUMN location VARCHAR(200)",
        # job - salary + interview config
        "ALTER TABLE job ADD COLUMN salary_usd INTEGER",
        "ALTER TABLE job ADD COLUMN employment_type VARCHAR(50)",
        "ALTER TABLE job ADD COLUMN interview_length VARCHAR(20) NOT NULL DEFAULT 'standard'",
        "ALTER TABLE job ADD COLUMN interview_focus TEXT",
        "ALTER TABLE job ADD COLUMN interview_questions TEXT",
        # application - payment + interview fields
        "ALTER TABLE application ADD COLUMN work_authorization TEXT",
        "ALTER TABLE application ADD COLUMN scheduled_meeting TEXT",
        "ALTER TABLE application ADD COLUMN match_score INTEGER",
        "ALTER TABLE application ADD COLUMN match_explanation TEXT",
        "ALTER TABLE application ADD COLUMN interview_transcript TEXT",
        "ALTER TABLE application ADD COLUMN interview_audio_log TEXT",
        "ALTER TABLE application ADD COLUMN interview_verdict VARCHAR(20)",
        "ALTER TABLE application ADD COLUMN fee_paid BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE application ADD COLUMN stripe_payment_link VARCHAR(500)",
        # user - verification + notifications
        "ALTER TABLE \"user\" ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE \"user\" ADD COLUMN notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE \"user\" ADD COLUMN last_name VARCHAR(150)", #new change for last name
        # company - logo
        "ALTER TABLE company ADD COLUMN logo_filename VARCHAR(200)",
        "ALTER TABLE company ADD COLUMN logo_version INTEGER NOT NULL DEFAULT 0",
        # application - employer notes + withdrawal
        "ALTER TABLE application ADD COLUMN employer_notes TEXT",
        "ALTER TABLE application ADD COLUMN withdrawn BOOLEAN NOT NULL DEFAULT FALSE",
        # job - salary range
        "ALTER TABLE job ADD COLUMN salary_max_usd INTEGER",
        "ALTER TABLE job ADD COLUMN pay_type VARCHAR(20) NOT NULL DEFAULT 'yearly'",
        # application - rejection feedback sent to candidate
        "ALTER TABLE application ADD COLUMN candidate_feedback TEXT",
        # application - AI-generated skills gap roadmap
        "ALTER TABLE application ADD COLUMN skills_roadmap TEXT",
        # company - blind hiring mode
        "ALTER TABLE company ADD COLUMN blind_mode_enabled BOOLEAN NOT NULL DEFAULT FALSE",
        # company - employer terms acceptance audit trail
        "ALTER TABLE company ADD COLUMN terms_accepted_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE company ADD COLUMN terms_accepted_ip VARCHAR(45)",
        "ALTER TABLE company ADD COLUMN terms_version VARCHAR(10)",
        # application - saved interview session for resume-later
        "ALTER TABLE application ADD COLUMN interview_saved_session TEXT",
        # user - admin flag
        "ALTER TABLE \"user\" ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE",
        # application - AI-generation likelihood score for candidate interview answers
        "ALTER TABLE application ADD COLUMN ai_likelihood TEXT",
        # user - supabase auth uid for admin API calls
        "ALTER TABLE \"user\" ADD COLUMN supabase_uid VARCHAR(200)",
        # candidate_profile - profile basics
        "ALTER TABLE candidate_profile ADD COLUMN headline VARCHAR(200)",
        "ALTER TABLE candidate_profile ADD COLUMN target_roles VARCHAR(300)",
        # candidate_profile - talent pool opt-in fields
        "ALTER TABLE candidate_profile ADD COLUMN open_to_work BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE candidate_profile ADD COLUMN skills TEXT",
        "ALTER TABLE candidate_profile ADD COLUMN work_preference VARCHAR(50)",
        "ALTER TABLE candidate_profile ADD COLUMN availability VARCHAR(50)",
        "ALTER TABLE candidate_profile ADD COLUMN years_experience VARCHAR(20)",
        "ALTER TABLE candidate_profile ADD COLUMN location VARCHAR(200)",
        # earn_task - domain gating for contractor network
        "ALTER TABLE earn_task ADD COLUMN required_domains TEXT",
        # earn_task - consensus scoring
        "ALTER TABLE earn_task ADD COLUMN min_responses INTEGER NOT NULL DEFAULT 3",
        "ALTER TABLE earn_task ADD COLUMN consensus_answer TEXT",
        # task_submission - per-submission agreement with consensus
        "ALTER TABLE task_submission ADD COLUMN agreement_score REAL",
        # contractor_profile - Stripe Connect payout flag
        "ALTER TABLE contractor_profile ADD COLUMN payout_enabled BOOLEAN NOT NULL DEFAULT FALSE",
        # application - candidate must confirm a hire before the fee invoice fires
        "ALTER TABLE application ADD COLUMN candidate_confirmed_hire BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE application ADD COLUMN hire_confirmed_at TIMESTAMP WITH TIME ZONE",
        # user - werkzeug's scrypt password hashes run ~162 chars, longer than
        # the original 150-char cap, so every email/password signup was
        # failing with a StringDataRightTruncation error
        "ALTER TABLE \"user\" ALTER COLUMN password TYPE VARCHAR(255)",
        # user - link to a DataBuyer account (outside company subscribed to Earn task exports)
        "ALTER TABLE \"user\" ADD COLUMN data_buyer_id INTEGER REFERENCES data_buyer(id)",
        "ALTER TABLE \"user\" ADD COLUMN is_data_buyer_admin BOOLEAN NOT NULL DEFAULT FALSE",
        # company - work-email domain, so later employer signups from the same
        # company land in the same hub instead of each creating a new Company
        "ALTER TABLE company ADD COLUMN email_domain VARCHAR(150)",
        # company - typed e-signature on the Employer Platform Agreement
        "ALTER TABLE company ADD COLUMN terms_signature_name VARCHAR(200)",
        # application - actual hire compensation (fee basis), candidate dispute flag, evidence upload
        "ALTER TABLE application ADD COLUMN hire_salary_usd INTEGER",
        "ALTER TABLE application ADD COLUMN hire_pay_type VARCHAR(20)",
        "ALTER TABLE application ADD COLUMN hire_salary_disputed BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE application ADD COLUMN hire_evidence_filename VARCHAR(200)",
        # application - recurring monthly billing for hourly hires, instead of one lump sum
        "ALTER TABLE application ADD COLUMN hire_billing_subscription_id VARCHAR(100)",
        "ALTER TABLE application ADD COLUMN hire_engagement_ended_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE application ADD COLUMN fee_reminder_sent_at TIMESTAMP WITH TIME ZONE",
        # job - currency the advertised salary is denominated in
        "ALTER TABLE job ADD COLUMN salary_currency VARCHAR(3) NOT NULL DEFAULT 'USD'",
        # user - referral program: own shareable code + who referred them
        "ALTER TABLE \"user\" ADD COLUMN referral_code VARCHAR(12)",
        "ALTER TABLE \"user\" ADD COLUMN referred_by_user_id INTEGER REFERENCES \"user\"(id)",
        # meeting_room - independent local-camera recordings captured client-side
        "ALTER TABLE meeting_room ADD COLUMN candidate_recording_path VARCHAR(300)",
        "ALTER TABLE meeting_room ADD COLUMN employer_recording_path VARCHAR(300)",
        # job - employer can require camera on, not just optional, for the AI interview
        "ALTER TABLE job ADD COLUMN camera_required BOOLEAN NOT NULL DEFAULT FALSE",
        # application - employer's own 0-100 rating after a live/manual interview
        "ALTER TABLE application ADD COLUMN manual_interview_score INTEGER",
    ]
    for stmt in new_columns:
        try:
            with db.engine.connect() as conn:
                conn.execute(text(stmt))
                conn.commit()
        except Exception:
            pass

    _backfill_company_email_domains(db)
    _backfill_referral_codes(db)


def _backfill_referral_codes(db):
    """One-time backfill for users created before referral_code existed -
    ALTER TABLE ADD COLUMN leaves existing rows NULL since the model's
    default= only applies to new ORM inserts, not raw SQL. No-ops once every
    user already has a code."""
    import secrets
    from .models import User

    try:
        users = User.query.filter(User.referral_code.is_(None)).all()
        for user in users:
            user.referral_code = secrets.token_urlsafe(6)
        db.session.commit()
    except Exception:
        db.session.rollback()


def _backfill_company_email_domains(db):
    """One-time backfill for companies created before email_domain existed -
    derives it from the owner's email so old companies also become joinable
    by domain. No-ops once every company already has a domain set."""
    from .models import Company, User, FREE_EMAIL_DOMAINS

    try:
        companies = Company.query.filter(Company.email_domain.is_(None)).all()
        for company in companies:
            owner = User.query.get(company.owner_user_id)
            if not owner or not owner.email or '@' not in owner.email:
                continue
            domain = owner.email.split('@')[-1].lower()
            if domain in FREE_EMAIL_DOMAINS:
                continue
            company.email_domain = domain
        db.session.commit()
    except Exception:
        db.session.rollback()

def create_app():
    app = Flask(__name__)
    secret_key = os.environ.get('SECRET_KEY', '')
    insecure_secrets = {'ebsjkfbsdjkfbjkdfb', 'your-local-secret', 'change-me'}
    if len(secret_key) < 32 or secret_key.lower() in insecure_secrets:
        if os.environ.get('FLASK_ENV') == 'production' or os.environ.get('RENDER'):
            raise RuntimeError("A strong SECRET_KEY is required in production.")
        secret_file = path.abspath(path.join(path.dirname(__file__), '..', 'instance', '.secret_key'))
        os.makedirs(path.dirname(secret_file), exist_ok=True)
        try:
            with open(secret_file, 'r', encoding='ascii') as file:
                secret_key = file.read().strip()
        except (FileNotFoundError, OSError):
            secret_key = ''
        if len(secret_key) < 32:
            secret_key = secrets.token_hex(32)
            with open(secret_file, 'w', encoding='ascii') as file:
                file.write(secret_key)
    app.config['SECRET_KEY'] = secret_key
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=(
            os.environ.get('COOKIE_SECURE', 'false').lower() == 'true'
            or bool(os.environ.get('RENDER'))
        ),
        PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    )

    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Render/Heroku-style URLs sometimes use the old "postgres://" scheme,
        # which SQLAlchemy 1.4+ no longer accepts. Also force the psycopg2
        # driver explicitly rather than leaving it to SQLAlchemy's default
        # resolution for a bare "postgresql://" URL - that silently started
        # trying the psycopg (v3) driver instead, which isn't installed
        # (only psycopg2-binary is, per requirements.txt), crashing the app
        # at startup with "ModuleNotFoundError: No module named 'psycopg'".
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        if database_url.startswith('postgresql://'):
            database_url = database_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        if database_url.startswith('postgresql+psycopg2://'):
            # This connect_args is Postgres-only syntax - applying it
            # unconditionally also broke DATABASE_URL pointed at a sqlite
            # file (e.g. for local/isolated testing), since sqlite3.connect()
            # has no "options" kwarg and raises a TypeError at every query.
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                "pool_pre_ping": True,
                "connect_args": {"options": "-c default_transaction_read_only=off"},
            }
    else:
        #sqlite is stored at this location - local dev fallback only
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'

    app.config.from_object(Config)
    db.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    csrf_exempt_paths = (
        '/stripe/webhook',
        '/data/stripe/webhook',
    )

    @app.before_request
    def enforce_csrf_and_request_safety():
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if request.path in csrf_exempt_paths:
                return None
            if app.config.get('TESTING'):
                return None

            token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
            if not token and request.is_json:
                body = request.get_json(silent=True) or {}
                token = body.get('csrf_token') if isinstance(body, dict) else None
            session_token = session.get('_csrf_token')
            if not session_token or not token or not hmac.compare_digest(session_token, token):
                abort(403, description='CSRF validation failed.')

            origin = request.headers.get('Origin')
            referer = request.headers.get('Referer')
            if origin:
                allowed_origin = f"{request.scheme}://{request.host}"
                if origin.rstrip('/') != allowed_origin.rstrip('/'):
                    abort(403, description='Cross-origin request blocked.')
            elif referer:
                referer_origin = f"{urlsplit(referer).scheme}://{urlsplit(referer).netloc}"
                allowed_origin = f"{request.scheme}://{request.host}"
                if referer_origin != allowed_origin:
                    abort(403, description='Cross-origin request blocked.')
        return None

    @app.context_processor
    def inject_csrf_token():
        if '_csrf_token' not in session:
            session['_csrf_token'] = secrets.token_urlsafe(32)
        return {'csrf_token': session['_csrf_token']}

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(self), microphone=(self), geolocation=()')
        response.headers.setdefault(
            'Content-Security-Policy',
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://www.googletagmanager.com https://www.google.com https://translate.google.com https://translate.googleapis.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com https://translate.googleapis.com; "
            "img-src 'self' data: blob: https://*; "
            "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "connect-src 'self' https://analytics.google.com https://www.google-analytics.com https://openrouter.ai; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'",
        )
        if request.is_secure:
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains',
            )
        return response

    # BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    # audio_path = os.path.join(BASE_DIR, "..", "audio")
    # upload_path = os.path.join(BASE_DIR, "..", "uploads")

    # app.config["AUDIO_FOLDER"] = audio_path
    # app.config["UPLOAD_FOLDER"] = upload_path

    # os.makedirs(audio_path, exist_ok=True)
    # os.makedirs(upload_path, exist_ok=True)
    #---------------------------------------------------------------------------


    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # Use writable temporary directories on Vercel
    if os.environ.get("VERCEL"):
        audio_path = os.path.join("/tmp", "avants_audio")
        upload_path = os.path.join("/tmp", "avants_uploads")
    else:
        # Keep existing folders for local development and Render
        audio_path = os.path.join(BASE_DIR, "..", "audio")
        upload_path = os.path.join(BASE_DIR, "..", "uploads")

    app.config["AUDIO_FOLDER"] = audio_path
    app.config["UPLOAD_FOLDER"] = upload_path

    os.makedirs(audio_path, exist_ok=True)
    os.makedirs(upload_path, exist_ok=True)

#---------------------------------------------------------------------------

    from .models import User, Company, Job, CandidateProfile, Application, CompanyMember, CompanyInvite, EarnTask, TaskSubmission, SavedJob, ContractorProfile, MeetingRoom, Message, EmployerSubscription, MeetingProposal, DataBuyer, Feedback, FeedbackInsight, DeletedJob

    with app.app_context():
        db.create_all()
        _run_migrations(db)
        from community_stats import initialize_counter
        initialize_counter(db.engine)

    from .views import views
    from .auth import auth
    from .employer import employer
    from . import employer_applications as _employer_applications
    from . import employer_meetings as _employer_meetings
    from . import employer_company as _employer_company
    from . import employer_talent as _employer_talent
    from . import employer_jobs as _employer_jobs
    from . import employer_billing as _employer_billing
    from .candidate import candidate
    from .earn import earn
    from .admin import admin_bp
    from .data_market import data_market

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(employer, url_prefix='/')
    app.register_blueprint(candidate, url_prefix='/')
    app.register_blueprint(earn, url_prefix='/')
    app.register_blueprint(admin_bp, url_prefix='/')
    app.register_blueprint(data_market, url_prefix='/')

    from datetime import datetime, timezone
    from flask_login import current_user as _cu

    @app.after_request
    def stash_referral_code(response):
        """?ref=CODE on any page load gets stashed in a cookie so it survives
        the multi-step signup flow (including the Google/Supabase OAuth
        redirect chain) - read back in auth.py when the User row is actually
        created. Doesn't overwrite an existing cookie, so the first referrer
        wins if someone clicks multiple referral links before signing up."""
        ref = request.args.get('ref')
        if ref and not request.cookies.get('ref_code'):
            response.set_cookie('ref_code', ref, max_age=60 * 60 * 24 * 30, httponly=True, samesite='Lax')
        return response

    @app.context_processor
    def inject_globals():
        if not _cu.is_authenticated:
            return {"unread_messages": 0}
        from .models import Message, Application, Job, Company, CompanyMember
        try:
            base_q = (
                db.session.query(db.func.count(Message.id))
                .join(Application, Application.id == Message.application_id)
                .filter(Message.read == False, Message.sender_user_id != _cu.id)
            )
            if _cu.role == 'employer':
                company = Company.query.filter_by(owner_user_id=_cu.id).first()
                if not company:
                    membership = CompanyMember.query.filter_by(user_id=_cu.id).first()
                    company = membership.company if membership else None
                count = (
                    base_q.join(Job, Job.id == Application.job_id)
                    .filter(Job.company_id == company.id)
                    .scalar() or 0
                ) if company else 0
            else:
                count = base_q.filter(Application.candidate_user_id == _cu.id).scalar() or 0
            return {"unread_messages": count}
        except Exception:
            db.session.rollback()
            return {"unread_messages": 0}

    import json as _json

    @app.template_filter('from_json')
    def from_json_filter(s):
        try:
            return _json.loads(s)
        except Exception:
            return []

    @app.template_filter('time_ago')
    def time_ago_filter(dt):
        if not dt:
            return ''
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = now - dt
        s = int(diff.total_seconds())
        if s < 60:
            return 'just now'
        if s < 3600:
            m = s // 60
            return f"{m} minute{'s' if m != 1 else ''} ago"
        if s < 86400:
            h = s // 3600
            return f"{h} hour{'s' if h != 1 else ''} ago"
        d = s // 86400
        if d < 30:
            return f"{d} day{'s' if d != 1 else ''} ago"
        mo = d // 30
        if mo < 12:
            return f"{mo} month{'s' if mo != 1 else ''} ago"
        yr = d // 365
        return f"{yr} year{'s' if yr != 1 else ''} ago"

    @app.template_filter('salary_range')
    def salary_range_filter(job):
        if not job.salary_usd:
            return None
        from .models import SUPPORTED_CURRENCIES, DEFAULT_CURRENCY
        pay_type = getattr(job, 'pay_type', None) or 'yearly'
        currency = getattr(job, 'salary_currency', None) or DEFAULT_CURRENCY
        symbol = SUPPORTED_CURRENCIES.get(currency, SUPPORTED_CURRENCIES[DEFAULT_CURRENCY])['symbol']

        # Formatting: hourly stays as raw number; everything else uses K if >= 1000
        def fmt(n, force_raw=False):
            if force_raw or n < 1000:
                return f"{symbol}{n:,}"
            return f"{symbol}{round(n / 1000)}K"

        hourly = pay_type == 'hourly'
        lo = fmt(job.salary_usd, force_raw=hourly)
        hi = fmt(job.salary_max_usd, force_raw=hourly) if job.salary_max_usd and job.salary_max_usd > job.salary_usd else None

        suffixes = {
            'yearly':   '/yr',
            'hourly':   '/hr',
            'monthly':  '/mo',
            'stipend':  ' stipend',
            'contract': ' (project)',
        }
        suffix = suffixes.get(pay_type, '/yr')

        if hi:
            return f"{lo}–{hi}{suffix}"
        return f"{lo}{suffix}"


    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    return app

#function checks if the database exists
def create_database(app):
    if not path.exists('website/' + DB_NAME):      
        print('Created Database!')
