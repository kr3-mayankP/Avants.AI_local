"""Employer company settings, membership, and public profile routes."""

import logging
import os
import secrets

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from PIL import Image

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

from email_utils import external_url, send_branded_email
from . import db
from .employer import (
    LOGO_ALLOWED_EXTENSIONS, LOGO_MAX_SIZE, employer, employer_required,
    get_owned_company,
)
from .models import (
    Application, Company, CompanyInvite, CompanyMember, INDUSTRIES,
    COMPANY_SIZES, JOB_CATEGORIES, Job, User, FREE_EMAIL_DOMAINS,
)

logger = logging.getLogger(__name__)


# Moved from employer.py: company_settings
@employer.route('/employer/company/settings', methods=['GET', 'POST'])
@login_required
@employer_required
def company_settings():
    company = get_owned_company()

    if request.method == 'POST':
        action = request.form.get('action', 'save_profile')

        if action == 'save_profile':
            name = request.form.get('name', '').strip()
            #new change: keep employer first and last names in their separate user columns.
            your_first_name = (request.form.get('your_first_name') or '').strip()
            your_last_name = (request.form.get('your_last_name') or '').strip()
            if your_first_name:
                current_user.first_name = your_first_name
            if your_last_name:
                current_user.last_name = your_last_name
            if not name:
                flash("Company name is required.", "error")
            else:
                company.name = name
                company.website = request.form.get('website', '').strip() or None
                company.description = request.form.get('description', '').strip() or None
                company.industry = request.form.get('industry', '').strip() or None
                company.size = request.form.get('size', '').strip() or None
                company.location = request.form.get('location', '').strip() or None
                company.blind_mode_enabled = request.form.get('blind_mode_enabled') == 'on'
                db.session.commit()
                flash("Company profile updated.", "success")

        elif action == 'remove_logo':
            if company.logo_filename:
                logos_dir = os.path.join(os.path.dirname(__file__), "static", "logos")
                filepath = os.path.join(logos_dir, company.logo_filename)
                try:
                    os.remove(filepath)
                except FileNotFoundError:
                    pass
                company.logo_filename = None
                company.logo_version = (company.logo_version or 0) + 1
                db.session.commit()
            flash("Logo removed.", "success")

        elif action == 'remove_member':
            member_id = request.form.get('member_id', type=int)
            if company.owner_user_id != current_user.id:
                flash("Only the company owner can remove team members.", "error")
            elif member_id:
                member = CompanyMember.query.filter_by(id=member_id, company_id=company.id).first()
                if member:
                    db.session.delete(member)
                    db.session.commit()
                    flash("Team member removed.", "success")

        return redirect(url_for('employer.company_settings'))

    owner = User.query.get(company.owner_user_id)
    members = CompanyMember.query.filter_by(company_id=company.id).all()
    pending_invites = CompanyInvite.query.filter_by(company_id=company.id, used=False).all()
    open_jobs_count = Job.query.filter_by(company_id=company.id, status='open').count()

    return render_template(
        "company_settings.html",
        company=company,
        owner=owner,
        members=members,
        pending_invites=pending_invites,
        sizes=COMPANY_SIZES,
        industries=INDUSTRIES,
        is_owner=(company.owner_user_id == current_user.id),
        open_jobs_count=open_jobs_count,
    )


# Moved from employer.py: _detect_image_format
def _detect_image_format(path):
    """Return detected format from magic bytes, or None if unrecognised."""
    try:
        with open(path, 'rb') as f:
            h = f.read(16)
        if h[:8] == b'\x89PNG\r\n\x1a\n':
            return 'PNG'
        if h[:3] == b'\xff\xd8\xff':
            return 'JPEG'
        if h[:6] in (b'GIF87a', b'GIF89a'):
            return 'GIF'
        if h[:4] == b'RIFF' and h[8:12] == b'WEBP':
            return 'WEBP'
        if h[:2] == b'BM':
            return 'BMP'
        if h[:4] in (b'II*\x00', b'MM\x00*'):
            return 'TIFF'
        # HEIC/HEIF: 'ftyp' box appears at offset 4
        if h[4:8] == b'ftyp':
            return 'HEIF'
        if h[:4] == b'\x00\x00\x00\x0c' and h[8:12] in (b'avif', b'avis'):
            return 'AVIF'
    except OSError:
        pass
    return None


# Moved from employer.py: upload_logo
@employer.route('/employer/company/logo', methods=['POST'])
@login_required
@employer_required
def upload_logo():
    company = get_owned_company()
    file = request.files.get('logo')

    if not file or not file.filename:
        flash("No file selected.", "error")
        return redirect(url_for('employer.company_settings'))

    ext = (file.filename.rsplit('.', 1)[-1] if '.' in file.filename else '').lower()
    if ext not in LOGO_ALLOWED_EXTENSIONS:
        flash("Unsupported file type. Use PNG, JPG, GIF, or WebP.", "error")
        return redirect(url_for('employer.company_settings'))
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size <= 0 or size > 5 * 1024 * 1024:
        flash("The logo must be a non-empty image smaller than 5 MB.", "error")
        return redirect(url_for('employer.company_settings'))

    logos_dir = os.path.join(os.path.dirname(__file__), "static", "logos")
    os.makedirs(logos_dir, exist_ok=True)

    tmp_path = os.path.join(logos_dir, f"_tmp_{company.id}.bin")
    final_path = os.path.join(logos_dir, f"company_{company.id}.png")

    try:
        file.save(tmp_path)

        # Guard: empty file
        if os.path.getsize(tmp_path) == 0:
            flash("The uploaded file was empty. Please try again.", "error")
            return redirect(url_for('employer.company_settings'))

        raw = Image.open(tmp_path)
        raw.load()  # force full decode so errors surface here, not later

        if raw.mode == 'RGBA':
            bg = Image.new("RGB", raw.size, (255, 255, 255))
            bg.paste(raw, mask=raw.split()[3])
            img = bg
        elif raw.mode == 'P':
            converted = raw.convert("RGBA")
            bg = Image.new("RGB", converted.size, (255, 255, 255))
            bg.paste(converted, mask=converted.split()[3])
            img = bg
        else:
            img = raw.convert("RGB")

        img.thumbnail(LOGO_MAX_SIZE, Image.LANCZOS)
        img.save(final_path, "PNG", optimize=True)
        company.logo_filename = f"company_{company.id}.png"
        company.logo_version = (company.logo_version or 0) + 1
        db.session.commit()
        flash("Logo updated.", "success")
    except Exception as e:
        flash(f"Could not process image: {e}", "error")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return redirect(url_for('employer.company_settings'))


# Moved from employer.py: invite_member
@employer.route('/employer/company/invite', methods=['POST'])
@login_required
@employer_required
def invite_member():
    company = get_owned_company()

    if company.owner_user_id != current_user.id:
        flash("Only the company owner can send invitations.", "error")
        return redirect(url_for('employer.company_settings'))

    email = request.form.get('email', '').strip().lower()
    if not email or '@' not in email:
        flash("A valid email address is required.", "error")
        return redirect(url_for('employer.company_settings'))

    from .models import FREE_EMAIL_DOMAINS, User
    domain = email.split('@')[-1]
    if domain in FREE_EMAIL_DOMAINS:
        flash("Please invite using a company email address - personal email providers like Gmail aren't accepted.", "error")
        return redirect(url_for('employer.company_settings'))

    owner = User.query.get(company.owner_user_id)
    owner_domain = owner.email.split('@')[-1].lower() if owner and owner.email else None
    if owner_domain and domain != owner_domain:
        flash(f"You can only invite teammates with an @{owner_domain} email address.", "error")
        return redirect(url_for('employer.company_settings'))

    # Don't invite someone already a member or the owner
    existing_user = User.query.filter(db.func.lower(User.email) == email).first()
    if existing_user:
        if existing_user.id == company.owner_user_id:
            flash("That person is already the company owner.", "error")
            return redirect(url_for('employer.company_settings'))
        already = CompanyMember.query.filter_by(company_id=company.id, user_id=existing_user.id).first()
        if already:
            flash("That person is already a team member.", "error")
            return redirect(url_for('employer.company_settings'))

        # Already has an account - add them immediately instead of making
        # them find and click an email link (that's what left someone stuck
        # as 'candidate' with an unused invite before this existed).
        existing_user.role = 'employer'
        db.session.add(CompanyMember(company_id=company.id, user_id=existing_user.id))
        CompanyInvite.query.filter_by(company_id=company.id, email=email, used=False).update({"used": True})
        db.session.commit()
        flash(f"{existing_user.email} added to {company.name}.", "success")
        return redirect(url_for('employer.company_settings'))

    # Delete any previous unused invite for this email + company
    CompanyInvite.query.filter_by(company_id=company.id, email=email, used=False).delete()
    db.session.commit()

    token = secrets.token_urlsafe(32)
    invite = CompanyInvite(
        company_id=company.id,
        invited_by_user_id=current_user.id,
        email=email,
        token=token,
    )
    db.session.add(invite)
    db.session.commit()

    invite_url = external_url('employer.accept_invite', token=token)
    #new change: show both stored name fields for the inviter.
    inviter_name = current_user.full_name or current_user.email
    try:
        send_branded_email(
            to_email=email,
            subject=f"You've been invited to join {company.name} on Avants AI",
            heading=f"Join {company.name} on Avants AI",
            body_html=(
                f"<strong>{inviter_name}</strong> has invited you to join "
                f"<strong>{company.name}</strong> as a team member on Avants AI. "
                f"As a team member, you'll be able to post jobs and manage applicants for {company.name}.<br><br>"
                f"This invite expires if not used."
            ),
            plain_text=(
                f"{inviter_name} has invited you to join {company.name} on Avants AI.\n\n"
                f"Accept the invite here: {invite_url}"
            ),
            cta_label="Accept Invitation",
            cta_url=invite_url,
        )
        flash(f"Invitation sent to {email}.", "success")
    except Exception as e:
        print("Invite email failed:", e)
        flash(f"Invite created but email delivery failed. Share this link manually: {invite_url}", "error")

    return redirect(url_for('employer.company_settings'))


# Moved from employer.py: sync_domain_members
@employer.route('/employer/company/sync-domain-members', methods=['POST'])
@login_required
@employer_required
def sync_domain_members():
    """One-click catch-up: adds every existing account whose email matches
    this company's verified domain but isn't a member yet - covers people who
    signed up before this domain had a hub, or whose account got stuck as a
    'candidate' by the case-sensitivity bug an earlier fix closed."""
    company = get_owned_company()

    if company.owner_user_id != current_user.id:
        flash("Only the company owner can do this.", "error")
        return redirect(url_for('employer.company_settings'))

    if not company.email_domain:
        flash("This company doesn't have a verified email domain on file.", "error")
        return redirect(url_for('employer.company_settings'))

    domain = company.email_domain.lower()
    matches = User.query.filter(User.email.ilike(f"%@{domain}")).all()
    existing_member_ids = {m.user_id for m in CompanyMember.query.filter_by(company_id=company.id).all()}

    added = []
    for user in matches:
        if user.id == company.owner_user_id or user.id in existing_member_ids:
            continue
        if not user.email or user.email.split('@')[-1].lower() != domain:
            continue
        user.role = 'employer'
        db.session.add(CompanyMember(company_id=company.id, user_id=user.id))
        CompanyInvite.query.filter_by(company_id=company.id, email=user.email.lower(), used=False).update({"used": True})
        added.append(user.email)

    db.session.commit()

    if added:
        flash(f"Added {len(added)} teammate(s) from @{domain}: {', '.join(added)}.", "success")
    else:
        flash(f"No additional @{domain} accounts found to add.", "info")
    return redirect(url_for('employer.company_settings'))


# Moved from employer.py: accept_invite
@employer.route('/employer/join/<token>')
@login_required
def accept_invite(token):
    invite = CompanyInvite.query.filter_by(token=token, used=False).first()

    if not invite:
        flash("This invitation is invalid or has already been used.", "error")
        return redirect(url_for('views.home'))

    if current_user.role != 'employer':
        flash("You need an employer account to accept this invitation.", "error")
        return redirect(url_for('views.home'))

    if invite.email.lower() != current_user.email.lower():
        flash("This invitation was sent to a different email address.", "error")
        return redirect(url_for('views.home'))

    company = Company.query.get_or_404(invite.company_id)

    # Check if already a member or owner
    if company.owner_user_id == current_user.id:
        flash("You are already the owner of this company.", "info")
        return redirect(url_for('employer.dashboard'))

    existing = CompanyMember.query.filter_by(company_id=company.id, user_id=current_user.id).first()
    if existing:
        flash(f"You're already a team member of {company.name}.", "info")
        return redirect(url_for('employer.dashboard'))

    member = CompanyMember(company_id=company.id, user_id=current_user.id)
    db.session.add(member)
    invite.used = True
    db.session.commit()

    flash(f"Welcome to {company.name}! You can now post jobs and manage applicants.", "success")
    return redirect(url_for('employer.dashboard'))


# Moved from employer.py: company_page
@employer.route('/companies/<int:company_id>')
def company_page(company_id):
    company = Company.query.get_or_404(company_id)
    open_jobs = Job.query.filter_by(company_id=company.id, status='open').order_by(Job.created_at.desc()).all()
    total_hires = Application.query.join(Job).filter(
        Job.company_id == company.id,
        Application.status == 'hired',
    ).count()
    member_count = CompanyMember.query.filter_by(company_id=company.id).count() + 1  # +1 for owner
    return render_template(
        "company_page.html",
        company=company,
        open_jobs=open_jobs,
        total_hires=total_hires,
        member_count=member_count,
    )
