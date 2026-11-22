"""Routes moved from auth.py."""

from .auth import (
    Company,
    FREE_EMAIL_DOMAINS,
    User,
    _apply_referral,
    _auto_join_matching_hub,
    _provision_employer,
    _safe_next,
    auth,
    create_client,
    current_app,
    current_user,
    db,
    flash,
    generate_password_hash,
    limiter,
    login_required,
    login_user,
    logout_user,
    make_response,
    os,
    redirect,
    render_template,
    request,
    send_verification_email,
    supabase,
    url_for,
)

# Moved from auth.py: login
@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("20 per minute; 5 per 10 seconds")
def login():
    next_url = _safe_next(request.values.get('next'))

    if current_user.is_authenticated:
        return redirect(next_url or url_for('views.home'))

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password')

        try:
            res = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
        except Exception as e:
            err = str(e).lower()
            print("Supabase login error:", e)
            if "email not confirmed" in err or "not confirmed" in err:
                flash("Please verify your email before signing in. Check your inbox for a confirmation link.", "error")
                resp = make_response(redirect(url_for("auth.verify_email_prompt")))
                resp.set_cookie("pending_verify_email", email, max_age=900, httponly=True, samesite="Lax")
                if next_url:
                    resp.set_cookie("pending_next", next_url, max_age=900, httponly=True, samesite="Lax")
                return resp
            flash("Invalid email or password.", "error")
            return render_template("login.html", next=next_url)

        if not hasattr(res, 'user') or not res.user:
            flash("Invalid email or password.", "error")
            return render_template("login.html", next=next_url)

        if not res.user.email_confirmed_at:
            flash("Please verify your email before signing in. Check your inbox for a confirmation link.", "error")
            resp = make_response(redirect(url_for("auth.verify_email_prompt")))
            resp.set_cookie("pending_verify_email", email, max_age=900, httponly=True, samesite="Lax")
            if next_url:
                resp.set_cookie("pending_next", next_url, max_age=900, httponly=True, samesite="Lax")
            return resp

        # Ensure local user exists for Flask-Login - matched case-insensitively
        # since older rows may have been stored with whatever case the person
        # originally typed at signup.
        local_user = User.query.filter(db.func.lower(User.email) == email).first()
        if not local_user:
            meta = res.user.user_metadata or {}
            role = meta.get("role", "candidate")
            company_name = meta.get("company_name", "").strip()
            email_domain = email.split('@')[-1].lower() if '@' in email else ''

            if role == 'employer' and email_domain in FREE_EMAIL_DOMAINS:
                role = 'candidate'

            local_user = User(
                email=email,
                #first_name=meta.get("full_name", ""),
                first_name=meta.get("first_name") or meta.get("full_name", ""), #new change for first name
                last_name=meta.get("last_name", ""),                            #new change for last name
                password=None,
                role=role,
                email_verified=True,
            )
            db.session.add(local_user)
            db.session.commit()
            _apply_referral(local_user)

            if role == 'employer':
                _provision_employer(local_user, email_domain, company_name)

        joined_hub = _auto_join_matching_hub(local_user)

        login_user(local_user, remember=True)
        flash("Logged in successfully!", "success")
        if joined_hub:
            flash(f"You've joined {joined_hub.name} on Avants AI.", "success")
            return redirect(url_for('employer.dashboard'))
        return redirect(next_url or url_for('views.home'))

    return render_template("login.html", next=next_url)

# Moved from auth.py: logout
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

# Moved from auth.py: sign_up
@auth.route('/sign-up', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def sign_up():
    next_url = _safe_next(request.values.get('next'))

    if current_user.is_authenticated:
        return redirect(next_url or url_for('views.home'))

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        first_name = (request.form.get('firstName') or '').strip()  #new change for first name
        last_name = (request.form.get('lastName') or '').strip()    #new change for last name
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')
        role = request.form.get('role', 'candidate')
        company_name = request.form.get('companyName', '').strip()
        signature_name = request.form.get('signatureName', '').strip()
        employer_agreement = request.form.get('employer_agreement') == 'on'

        email_domain = email.split('@')[-1].lower() if email and '@' in email else ''

        existing_hub = None
        if role == 'employer' and email_domain and email_domain not in FREE_EMAIL_DOMAINS:
            existing_hub = Company.query.filter_by(email_domain=email_domain).first()

        if not email:
            flash("Email is required.", "error")
        elif not first_name or not last_name:                       #new change for first and last name
            flash("First and last name are required.", "error")     #new change for first and last name
        elif password1 != password2:
            flash("Passwords do not match.", "error")
        elif len(password1) < 7:
            flash("Password must be at least 7 characters.", "error")
        elif role == 'employer' and not company_name and not existing_hub:
            flash("Company name is required for employer accounts.", "error")
        elif role == 'employer' and email_domain in FREE_EMAIL_DOMAINS:
            flash("Please sign up with your company email address, not a personal email provider.", "error")
        elif role == 'employer' and not existing_hub and not signature_name:
            flash("Type your full legal name to sign the Employer Platform Agreement.", "error")
        elif role == 'employer' and not existing_hub and not employer_agreement:
            flash("You must agree to the Employer Platform Agreement to create an employer account.", "error")
        else:
            try:
                admin_supa = create_client(
                    os.environ["SUPABASE_URL"],
                    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
                )
                res = admin_supa.auth.admin.create_user({
                    "email": email,
                    "password": password1,
                    #"user_metadata": {"full_name": first_name, "role": role, "company_name": company_name},
#-------------------------------------------------------------------------------------------------------------------
                    "user_metadata": {
                        "first_name": first_name,
                        "last_name": last_name,
                        "full_name": f"{first_name} {last_name}",
                        "role": role,
                        "company_name": company_name,
                    },
#-------------------------------------------------------------------------------------------------------------------
                    #"email_confirm": False,
                    "email_confirm": True,
                })

                if not res.user:
                    #new change: log an unexpected empty Supabase response for diagnosis.
                    current_app.logger.error("Supabase signup returned no user object.")
                    flash("Something went wrong. Try again.", "error")
                    return redirect(url_for("auth.sign_up"))

                # Reuse an existing local row for this email rather than always
                # inserting a new one - covers re-signing up after the local
                # Supabase auth account was lost/deleted while our own User
                # row survived (it has no FK enforcing the two stay in sync).
                # Without this, re-signup after that kind of drift just piles
                # up another disconnected duplicate instead of fixing anything.
                existing_local = User.query.filter(db.func.lower(User.email) == email).order_by(User.id.asc()).first()
                is_new_local = existing_local is None

                if existing_local:
                    local_user = existing_local
                    local_user.first_name = first_name or local_user.first_name
                    local_user.last_name = last_name or local_user.last_name    #new change for last name
                    local_user.password = generate_password_hash(password1)
                    local_user.role = role
                    local_user.email_verified = False
                    local_user.supabase_uid = res.user.id
                else:
                    local_user = User(
                        email=email,
                        first_name=first_name,
                        last_name=last_name,    #new change for last name
                        password=generate_password_hash(password1),
                        role=role,
                        email_verified=False,
                        supabase_uid=res.user.id,
                    )
                    db.session.add(local_user)
                db.session.commit()
                if is_new_local:
                    _apply_referral(local_user)

                if role == 'employer':
                    _provision_employer(local_user, email_domain, company_name, signature_name)
                else:
                    _auto_join_matching_hub(local_user)

                try:
                    send_verification_email(local_user)
                except Exception:
                    current_app.logger.exception("Verification email send failed for signup")
                    flash(
                        "Your account was created, but we couldn't send the confirmation email. "
                        "Check the mail settings and use the resend button.",
                        "error",
                    )
                    sent = "0"
                else:
                    sent = "1"

                resp = make_response(redirect(url_for("auth.verify_email_prompt", sent=sent)))
                resp.set_cookie("pending_verify_email", email, max_age=900, httponly=True, samesite="Lax")
                if next_url:
                    resp.set_cookie("pending_next", next_url, max_age=900, httponly=True, samesite="Lax")
                return resp

            except Exception as e:
                err = str(e).lower()
                if "already registered" in err or "already been registered" in err or "duplicate" in err:
                    flash("Email already exists. Try logging in instead.", "error")
                    return redirect(url_for("auth.login", next=next_url) if next_url else url_for("auth.login"))

                #new change: include the traceback in the server terminal without exposing internals in the UI.
                current_app.logger.exception("Signup failed unexpectedly.")
                flash("Something went wrong. Try again.", "error")
                return redirect(url_for("auth.sign_up", next=next_url) if next_url else url_for("auth.sign_up"))

    return render_template("sign_up.html", next=next_url)

