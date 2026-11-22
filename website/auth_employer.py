"""Routes moved from auth.py."""

from .auth import (
    Company,
    CompanyMember,
    FREE_EMAIL_DOMAINS,
    User,
    _apply_referral,
    _auto_join_matching_hub,
    _clear_pending_invite,
    _safe_next,
    auth,
    current_user,
    datetime,
    db,
    flash,
    login_required,
    login_user,
    redirect,
    render_template,
    request,
    session,
    supabase,
    timezone,
    url_for,
)

# Moved from auth.py: login_google
@auth.route('/login/google')
def login_google():
    next_url = _safe_next(request.args.get("next"))

    # Employers sign up with their company email/password only - Google gives
    # no chance to collect a company name or verify a work domain up front,
    # so a fresh employer account can't be created through this route.
    if request.args.get("role") == "employer":
        flash("Employer accounts sign up with a work email and password - Google sign-up is for candidates only.", "error")
        return redirect(url_for("auth.sign_up", next=next_url) if next_url else url_for("auth.sign_up"))

    session["oauth_role"] = "candidate"
    session["oauth_next"] = next_url

    # Redirect user to Supabase Google OAuth
    res = supabase.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {
            # This must match your route that serves the JS
            "redirect_to": request.host_url.rstrip("/") + "/login/google/finish"
        }
    })
    return redirect(res.url)

# Moved from auth.py: login_google_finish
@auth.route("/login/google/finish")
def login_google_finish():
    code = request.args.get("code")

    if not code:
        flash("Google login failed.", "error")
        return redirect(url_for("auth.login"))

    try:
        # Exchange code for session
        res = supabase.auth.exchange_code_for_session({"auth_code": code})

        supa_user = res.user

        if not supa_user:
            flash("Google login failed.", "error")
            return redirect(url_for("auth.login"))

        email = (supa_user.email or '').lower()
        #new change: preserve provider first/last metadata when Google supplies it.
        meta = supa_user.user_metadata or {}
        first_name = meta.get("first_name") or meta.get("given_name") or meta.get("full_name") or "Google User"
        last_name = meta.get("last_name") or meta.get("family_name") or ""

        local_user = User.query.filter(db.func.lower(User.email) == email).first()
        is_new_user = local_user is None

        if not local_user:
            role = session.pop("oauth_role", "candidate")
            email_domain = email.split('@')[-1].lower() if '@' in email else ''

            if role == 'employer' and email_domain in FREE_EMAIL_DOMAINS:
                # Don't silently create the wrong kind of account - Google only
                # gave us a personal-domain email, but they asked for employer.
                # Let them explicitly choose instead of trapping them as a
                # candidate with no way back.
                session['oauth_pending_email'] = email
                #new change: retain separate name fields through the OAuth role-choice screen.
                session['oauth_pending_first_name'] = first_name
                session['oauth_pending_last_name'] = last_name
                return redirect(url_for('auth.employer_email_conflict'))

            local_user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,  #new change: save provider surname when available.
                password=None,
                role=role,
                email_verified=True,
            )
            db.session.add(local_user)
            db.session.commit()
            _apply_referral(local_user)

        joined_hub = _auto_join_matching_hub(local_user)

        login_user(local_user, remember=True)
        next_url = _safe_next(session.pop("oauth_next", None))

        if is_new_user and local_user.role == 'employer':
            return redirect(url_for("auth.complete_employer_profile"))

        if joined_hub:
            flash(f"You've joined {joined_hub.name} on Avants AI.", "success")
            return redirect(url_for('employer.dashboard'))

        return redirect(next_url or url_for("views.home"))

    except Exception as e:
        print("Google OAuth error:", e)
        flash("Google login failed.", "error")
        return redirect(url_for("auth.login"))

# Moved from auth.py: employer_email_conflict
@auth.route("/employer-email-conflict", methods=["GET", "POST"])
def employer_email_conflict():
    """Landing spot for a Google sign-up that asked for an employer account
    but only offered a personal-domain email - see login_google_finish."""
    email = session.get('oauth_pending_email')
    first_name = session.get('oauth_pending_first_name')
    last_name = session.get('oauth_pending_last_name', '')
    if not email:
        return redirect(url_for('auth.sign_up'))

    if request.method == "POST":
        choice = request.form.get('choice')
        session.pop('oauth_pending_email', None)
        first_name = session.pop('oauth_pending_first_name', first_name)
        last_name = session.pop('oauth_pending_last_name', last_name)
        next_url = _safe_next(session.pop('oauth_next', None))

        if choice == 'candidate':
            local_user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
            if not local_user:
                #new change: save available Google name fields for candidate role choices.
                local_user = User(
                    email=email,
                    first_name=first_name or "Google User",
                    last_name=last_name,
                    password=None,
                    role='candidate',
                    email_verified=True,
                )
                db.session.add(local_user)
                db.session.commit()
                _apply_referral(local_user)
            login_user(local_user, remember=True)
            flash("Signed up as a candidate account.", "success")
            return redirect(next_url or url_for('views.home'))

        return redirect(url_for('auth.sign_up', next=next_url) if next_url else url_for('auth.sign_up'))

    return render_template("employer_email_conflict.html", email=email)

# Moved from auth.py: complete_employer_profile
@auth.route("/complete-employer-profile", methods=["GET", "POST"])
@login_required
def complete_employer_profile():
    """Google OAuth has no form step, so a brand-new employer signup lands
    here to give their company a name before they can post jobs."""
    if current_user.role != 'employer':
        return redirect(url_for("views.home"))

    if Company.query.filter_by(owner_user_id=current_user.id).first():
        return redirect(url_for("views.home"))

    if CompanyMember.query.filter_by(user_id=current_user.id).first():
        return redirect(url_for("views.home"))

    email_domain = current_user.email.split('@')[-1].lower() if current_user.email and '@' in current_user.email else ''
    existing_hub = None
    if email_domain and email_domain not in FREE_EMAIL_DOMAINS:
        existing_hub = Company.query.filter_by(email_domain=email_domain).first()

    if existing_hub:
        db.session.add(CompanyMember(company_id=existing_hub.id, user_id=current_user.id))
        _clear_pending_invite(existing_hub.id, current_user.email)
        db.session.commit()
        flash(f"You've joined {existing_hub.name} - your teammates are already set up here.", "success")
        return redirect(url_for("views.home"))

    if request.method == "POST":
        company_name = request.form.get("companyName", "").strip()
        signature_name = request.form.get("signatureName", "").strip()
        agreed = request.form.get("agreement") == "on"

        if not company_name:
            flash("Company name is required.", "error")
            return render_template("complete_employer_profile.html")
        if not signature_name or not agreed:
            flash("Type your full legal name and agree to the Employer Platform Agreement to continue.", "error")
            return render_template("complete_employer_profile.html")

        company = Company(
            owner_user_id=current_user.id,
            name=company_name,
            email_domain=email_domain or None,
            terms_accepted_at=datetime.now(timezone.utc),
            terms_accepted_ip=request.remote_addr,
            terms_version='1.0',
            terms_signature_name=signature_name,
        )
        db.session.add(company)
        db.session.commit()

        flash("Company profile saved! You're all set.", "success")
        return redirect(url_for("views.home"))

    return render_template("complete_employer_profile.html")

