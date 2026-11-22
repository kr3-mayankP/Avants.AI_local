"""Routes moved from auth.py."""

from .auth import (
    Company,
    CompanyMember,
    FREE_EMAIL_DOMAINS,
    User,
    _apply_referral,
    _email_rate_key,
    _provision_employer,
    _safe_next,
    auth,
    create_client,
    current_app,
    db,
    flash,
    limiter,
    login_user,
    make_response,
    os,
    redirect,
    render_template,
    request,
    send_verification_email,
    supabase,
    url_for,
    verify_verification_token,
)
from supabase import create_client
import os

# Moved from auth.py: verify_email_prompt
@auth.route("/verify-email")
def verify_email_prompt():
    email = request.cookies.get("pending_verify_email", "")
    return render_template(
        "verify_email.html",
        email=email,
        email_sent=request.args.get("sent") == "1",
        email_send_failed=request.args.get("sent") == "0",
    )


# Moved from auth.py: auth_confirm
@auth.route("/auth/confirm")
def auth_confirm():
    code = request.args.get("code")
    if not code:
        flash("Invalid confirmation link.", "error")
        return redirect(url_for("auth.login"))

    try:
        res = supabase.auth.exchange_code_for_session({"auth_code": code})
        supa_user = res.user
        if not supa_user:
            flash("Confirmation failed. Please try signing up again.", "error")
            return redirect(url_for("auth.sign_up"))

        email = (supa_user.email or '').lower()
        #new change: get account metadata from Supabase; the curses module is unrelated.
        meta = supa_user.user_metadata or {}
        role = meta.get("role", "candidate")
        #first_name = meta.get("full_name", "")
        first_name = meta.get("first_name") or meta.get("full_name", "")    #new change for first name
        last_name = meta.get("last_name", "")                               #new change for last name
        company_name = meta.get("company_name", "").strip()
        email_domain = email.split('@')[-1].lower() if '@' in email else ''

        local_user = User.query.filter(db.func.lower(User.email) == email).first()
        is_new = local_user is None

        if not local_user:
            if role == 'employer' and email_domain in FREE_EMAIL_DOMAINS:
                role = 'candidate'

            local_user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,    #new change for last name
                password=None,
                role=role,
                email_verified=True,
            )
            db.session.add(local_user)
            db.session.commit()
            _apply_referral(local_user)

            if role == 'employer':
                _provision_employer(local_user, email_domain, company_name)
        else:
            local_user.email_verified = True
#----------------------------------------------------------------
            if not local_user.first_name and first_name:
                local_user.first_name = first_name
            if not local_user.last_name and last_name:
                local_user.last_name = last_name
#---------------------------------------------------------------
            db.session.commit()

        login_user(local_user, remember=True)
        flash("Email confirmed! Welcome to Avants.", "success")

        has_company = (
            Company.query.filter_by(owner_user_id=local_user.id).first()
            or CompanyMember.query.filter_by(user_id=local_user.id).first()
        )
        if is_new and local_user.role == 'employer' and not has_company:
            return redirect(url_for("auth.complete_employer_profile"))

        return redirect(url_for("views.home"))

    except Exception as e:
        print("Email confirmation error:", e)
        flash("Confirmation failed. Try signing in directly.", "error")
        return redirect(url_for("auth.login"))

# Moved from auth.py: verify_email
@auth.route("/verify-email/<token>")
def verify_email(token):
    email = verify_verification_token(token)
    if not email:
        flash("That verification link is invalid or has expired.", "error")
        return redirect(url_for("auth.verify_email_prompt"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Account not found.", "error")
        return redirect(url_for("auth.login"))

    if not user.email_verified:
        try:
            if not user.supabase_uid:
                raise RuntimeError("Account is missing its Supabase user ID")
            admin_supa = create_client(
                os.environ["SUPABASE_URL"],
                os.environ["SUPABASE_SERVICE_ROLE_KEY"],
            )
            admin_supa.auth.admin.update_user_by_id(
                user.supabase_uid, {"email_confirm": True}
            )
        except Exception:
            current_app.logger.exception("Supabase email confirmation failed")
            flash("We couldn't confirm your account with the authentication service. Please try the link again.", "error")
            return redirect(url_for("auth.verify_email_prompt"))

        user.email_verified = True
        db.session.commit()

    login_user(user, remember=True)
    flash("Email verified! Welcome to Avants.", "success")

    next_url = _safe_next(request.cookies.get("pending_next"))

    has_company = (
        Company.query.filter_by(owner_user_id=user.id).first()
        or CompanyMember.query.filter_by(user_id=user.id).first()
    )
    if user.role == 'employer' and not has_company:
        target = url_for("auth.complete_employer_profile")
    else:
        target = next_url or url_for("views.home")

    resp = make_response(redirect(target))
    resp.delete_cookie("pending_next")
    return resp

