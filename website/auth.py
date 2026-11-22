from datetime import datetime, timezone
from flask import Blueprint, current_app, render_template, request, flash, redirect, url_for, session, make_response
from .models import User, Company, CompanyMember, CompanyInvite, FREE_EMAIL_DOMAINS
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, limiter
from flask_login import login_user, login_required, logout_user, current_user
from supabase import create_client
import os
import hashlib

from email_utils import send_verification_email, verify_verification_token, public_base_url

# ---------------- Supabase Client ---------------- #
# Anon-role client for user-facing auth flows (login, sign-up, password reset request).

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_ANON_KEY"],
)

auth = Blueprint('auth', __name__)

def _email_rate_key():
    email = request.form.get("email", "").strip().casefold()
    return hashlib.sha256(email.encode("utf-8")).hexdigest()



def _apply_referral(new_user):
    """If this signup arrived via a referral link (?ref=CODE, stashed as a
    cookie by website/__init__.py's stash_referral_code), credit the
    referrer. Call right after a brand-new User is committed (needs new_user.id)."""
    code = request.cookies.get('ref_code')
    if not code:
        return
    referrer = User.query.filter_by(referral_code=code).first()
    if referrer and referrer.id != new_user.id:
        new_user.referred_by_user_id = referrer.id
        db.session.commit()


def _safe_next(next_url):
    """Only allow same-site relative redirects for ?next= - rejects absolute/
    protocol-relative URLs so this can't be used as an open redirect."""
    if not next_url or not next_url.startswith('/') or next_url.startswith('//'):
        return None
    return next_url


def _provision_employer(user, email_domain, company_name, signature_name=None):
    """Get-or-join a Company for a brand-new employer user. Coworkers signing
    up from the same work email domain land in the same hub (as a
    CompanyMember) instead of each spinning up a separate company - only the
    first signup from a domain actually creates the Company, and only that
    founding signup signs the Employer Platform Agreement on the Company's
    behalf."""
    existing = None
    if email_domain and email_domain not in FREE_EMAIL_DOMAINS:
        existing = Company.query.filter_by(email_domain=email_domain).first()

    if existing:
        if not CompanyMember.query.filter_by(company_id=existing.id, user_id=user.id).first():
            db.session.add(CompanyMember(company_id=existing.id, user_id=user.id))
        _clear_pending_invite(existing.id, user.email)
        db.session.commit()
        return existing

    signature_name = (signature_name or '').strip()
    if not company_name or not signature_name:
        # No real e-signature collected yet (e.g. a Supabase session syncing
        # in via login()/auth_confirm() without ever hitting the sign-up
        # form's checkbox) - don't stamp acceptance on a Company that was
        # never actually signed for. employer_required's existing redirect to
        # complete_employer_profile is the only path that creates the Company
        # from here, and that route already collects the checkbox + signature.
        return None

    company = Company(
        owner_user_id=user.id,
        name=company_name,
        email_domain=email_domain or None,
        terms_accepted_at=datetime.now(timezone.utc),
        terms_accepted_ip=request.remote_addr,
        terms_version='1.0',
        terms_signature_name=signature_name,
    )
    db.session.add(company)
    db.session.commit()
    return company


def _clear_pending_invite(company_id, email):
    """A CompanyInvite left 'pending' after the person already became a member
    some other way (domain auto-join, an admin adding them directly) would
    otherwise sit forever in the company's Pending Invitations list."""
    if not email:
        return
    CompanyInvite.query.filter_by(company_id=company_id, email=email.lower(), used=False).update({"used": True})


def _auto_join_matching_hub(user):
    """If a candidate's email domain matches an existing employer hub, promote
    them to employer and add them as a team member automatically - no
    confirmation step, since matching the same verified work-email domain is
    the same trust signal _provision_employer already uses to auto-join
    brand-new employer signups into the same hub. Returns the Company they
    joined, or None."""
    if user.role != 'candidate' or not user.email or '@' not in user.email:
        return None
    domain = user.email.split('@')[-1].lower()
    if domain in FREE_EMAIL_DOMAINS:
        return None
    hub = Company.query.filter_by(email_domain=domain).first()
    if not hub:
        return None
    user.role = 'employer'
    if not CompanyMember.query.filter_by(company_id=hub.id, user_id=user.id).first():
        db.session.add(CompanyMember(company_id=hub.id, user_id=user.id))
    _clear_pending_invite(hub.id, user.email)
    db.session.commit()
    return hub

# ------------------------------------------------ #
# ---------------- PASSWORD RESET ---------------- #
# ------------------------------------------------ #













# ------------------------------------------------ #
# ---------------- EMAIL LOGIN ------------------- #
# ------------------------------------------------ #



# ---------------- SIGN-UP ----------------

# ------------------------------------------------ #
# ----------- VERIFY EMAIL PROMPT PAGE ------------ #
# ------------------------------------------------ #




# ------------------------------------------------ #
# --------- SUPABASE EMAIL CONFIRMATION ----------- #
# ------------------------------------------------ #



# ------------------------------------------------ #
# ------------- EMAIL VERIFICATION ---------------- #
# ------------------------------------------------ #



# ------------------------------------------------ #
# ---------------- GOOGLE OAUTH ------------------ #
# ------------------------------------------------ #

@auth.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
@limiter.shared_limit("3 per hour", scope="account-email-resends", key_func=_email_rate_key, methods=["POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")

        supabase.auth.reset_password_for_email(
            email,
            {"redirect_to": public_base_url() + "/reset-password"}
        )

        flash("Password reset email sent!", "success")
        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")


@auth.route("/resend-verification", methods=["POST"])
@limiter.limit("5 per hour", methods=["POST"])
@limiter.shared_limit("3 per hour", scope="account-email-resends", key_func=_email_rate_key, methods=["POST"])
def resend_verification():
    email = request.form.get("email", "").strip().lower()
    if email:
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user and not user.email_verified:
            try:
                send_verification_email(user)
            except Exception:
                current_app.logger.exception("Verification email resend failed")
                flash("We couldn't send the confirmation email. Check the mail settings and try again.", "error")
                sent = "0"
            else:
                flash("A new confirmation email has been sent. Check your inbox and spam folder.", "success")
                sent = "1"
        else:
            flash("If an unverified account exists for that address, a confirmation email will be sent.", "success")
            sent = ""
    else:
        flash("Enter the email address you used to sign up.", "error")
        sent = ""
    resp = make_response(redirect(url_for("auth.verify_email_prompt", sent=sent) if sent else url_for("auth.verify_email_prompt")))
    resp.set_cookie("pending_verify_email", email, max_age=900, httponly=True, samesite="Lax")
    return resp

from . import auth_recovery as _auth_recovery
from . import auth_login as _auth_login
from . import auth_verification as _auth_verification
from . import auth_employer as _auth_employer
