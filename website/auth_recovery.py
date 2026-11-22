"""Routes moved from auth.py."""

from .auth import (
    User,
    _email_rate_key,
    auth,
    check_password_hash,
    create_client,
    db,
    flash,
    limiter,
    os,
    public_base_url,
    redirect,
    render_template,
    request,
    session,
    supabase,
    url_for,
)


# Moved from auth.py: reset_password
@auth.route("/reset-password", methods=["GET"])
def reset_password():
    return render_template(
        "reset_password.html",
        supabase_url=os.environ["SUPABASE_URL"],
        supabase_anon_key=os.environ["SUPABASE_ANON_KEY"],
    )

# Moved from auth.py: store_reset_token
@auth.route("/reset-password/store", methods=["POST"])
def store_reset_token():
    data = request.get_json()
    session["supabase_access_token"] = data.get("access_token")
    session["supabase_refresh_token"] = data.get("refresh_token")
    return {"status": "ok"}

# Moved from auth.py: reset_password_form
@auth.route("/reset-password/form", methods=["GET", "POST"])
def reset_password_form():
    if request.method == "POST":
        new_password = request.form.get("password")
        access_token = session.get("supabase_access_token")
        refresh_token = session.get("supabase_refresh_token")

        if not access_token:
            flash("Reset session expired. Try again.", "error")
            return redirect(url_for("auth.login"))

        if len(new_password) < 7:
            flash("Password must be at least 7 characters.", "error")
            return redirect(request.url)
        
        

        try:
            admin_supabase = create_client(
                os.environ["SUPABASE_URL"],
                os.environ["SUPABASE_SERVICE_ROLE_KEY"],
            )

            authed_supabase = create_client(
                os.environ["SUPABASE_URL"],
                os.environ["SUPABASE_ANON_KEY"],
            )
            authed_supabase.auth.set_session(
                access_token,
                refresh_token
            )
            
            
              # Get Supabase user
            user_response = authed_supabase.auth.get_user(access_token)
            supa_user = user_response.user
            email = (supa_user.email or '').lower()

            # Get local user
            user = User.query.filter(db.func.lower(User.email) == email).first()

            if user:
                # Block reusing old password
                if check_password_hash(user.password, new_password):
                    flash("You cannot use your old password.", "error")
                    return redirect(request.url)

            admin_supabase.auth.admin.update_user_by_id(
                supa_user.id,
                {"password": new_password}
            )

        except Exception as e:
            print("Password update error:", e)
            flash("Error updating password.", "error")
            return redirect(request.url)

        session.pop("supabase_access_token", None)
        flash("Password updated successfully!", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password_form.html")

