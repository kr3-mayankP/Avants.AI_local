"""Employer placement-fee billing helpers."""

from datetime import datetime, timedelta, timezone

import stripe
from flask import current_app, url_for

from email_utils import external_url, send_branded_email
from . import db
from .employer import (
    PLATFORM_FEE_PERCENT,
    STANDARD_ANNUAL_HOURS,
    _placement_fee_basis,
)
from .models import Application, Job, Notification, User

OVERDUE_FEE_DAYS = 30
FEE_REMINDER_THROTTLE_DAYS = 4

def overdue_fee_applications(company):
    """Hired applications whose placement fee invoice went out (candidate
    confirmed) but was never paid, past the 30-day ToS deadline. Excludes
    engagements already marked ended - once billing has legitimately stopped
    there's nothing to chase. Note: for hourly roles this only catches a
    first payment that was never made - fee_paid flips True on the first
    successful Stripe charge and nothing here currently detects a later
    monthly subscription payment failing (no invoice.payment_failed webhook
    handler exists yet), so a lapsed recurring subscription won't show up."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=OVERDUE_FEE_DAYS)
    return (
        Application.query.join(Job)
        .filter(
            Job.company_id == company.id,
            Application.status == 'hired',
            Application.candidate_confirmed_hire.is_(True),
            Application.fee_paid.is_(False),
            Application.hire_engagement_ended_at.is_(None),
            Application.hire_confirmed_at.isnot(None),
            Application.hire_confirmed_at <= cutoff,
        )
        .order_by(Application.hire_confirmed_at.asc())
        .all()
    )

def send_overdue_fee_reminder(application, job, company, employer_user):
    """Email + in-app warning for an overdue placement fee, throttled so it
    fires at most once every FEE_REMINDER_THROTTLE_DAYS regardless of how
    often the employer loads their dashboard."""
    now = datetime.now(timezone.utc)
    if application.fee_reminder_sent_at:
        last = application.fee_reminder_sent_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if now - last < timedelta(days=FEE_REMINDER_THROTTLE_DAYS):
            return

    days_overdue = (now - application.hire_confirmed_at.replace(tzinfo=timezone.utc)).days
    basis_amount, fee_percent = _placement_fee_basis(application, job)
    fee_amount = int(basis_amount * fee_percent / 100) if basis_amount else None
    candidate = User.query.get(application.candidate_user_id)
    #new change: use the full candidate name in billing notices.
    candidate_name = (candidate.full_name or candidate.email) if candidate else 'your hire'
    pay_link = application.stripe_payment_link or external_url('employer.applicants', job_id=job.id)

    db.session.add(Notification(
        user_id=employer_user.id,
        message=(
            f"Overdue: the placement fee for {candidate_name} "
            f"({job.title}) is {days_overdue} days past due. Your account may be suspended or your "
            f"company removed from Avants AI if this isn't resolved."
        ),
        link=url_for('employer.applicants', job_id=job.id),
    ))

    try:
        send_branded_email(
            to_email=employer_user.email,
            subject=f"Overdue placement fee - {job.title} - action required",
            heading="Placement fee overdue",
            body_html=(
                f"The placement fee for <strong>{candidate_name}</strong> "
                f"(<strong>{job.title}</strong>) is <strong>{days_overdue} days overdue</strong> - "
                f"{f'${fee_amount:,} ' if fee_amount else ''}was due within 30 days of the candidate's start date "
                f"per the Employer Platform Agreement.<br><br>"
                f"Unpaid invoices accrue interest at 1.5% per month after 30 days. "
                f"<strong>Continued non-payment may result in your account being suspended or your "
                f"company profile being removed from Avants AI.</strong><br><br>"
                f"Please pay now to avoid any disruption, or reply to this email if you believe this is in error."
            ),
            plain_text=(
                f"The placement fee for {candidate_name} ({job.title}) is "
                f"{days_overdue} days overdue"
                f"{f' (${fee_amount:,})' if fee_amount else ''} - due within 30 days of the candidate's start date "
                f"per the Employer Platform Agreement.\n\n"
                f"Unpaid invoices accrue interest at 1.5%/month after 30 days. Continued non-payment may result "
                f"in your account being suspended or your company profile being removed from Avants AI.\n\n"
                f"Pay here: {pay_link}"
            ),
            cta_label="Pay Now",
            cta_url=pay_link,
        )
    except Exception as e:
        print(f"Overdue fee reminder email failed: {e}")

    application.fee_reminder_sent_at = now

def send_hire_fee_invoice(application, job, company, candidate, employer_user):
    """Create the Stripe placement-fee payment link and invoice the employer.
    Only called once the candidate has confirmed the hire - see candidate.confirm_hire."""
    hire_salary = application.hire_salary_usd or job.salary_usd
    hire_pay_type = application.hire_pay_type or job.pay_type
    is_hourly = hire_pay_type == 'hourly'

    payment_link_url = None
    if not application.stripe_payment_link:
        payment_link_url = (
            _create_stripe_subscription_link(application, job, company, candidate) if is_hourly
            else _create_stripe_payment_link(application, job, company, candidate)
        )
        if payment_link_url:
            application.stripe_payment_link = payment_link_url
            db.session.commit()

    basis_amount, fee_percent = _placement_fee_basis(application, job)
    fee_amount = int(basis_amount * fee_percent / 100) if basis_amount else None
    monthly_fee_amount = int(fee_amount / 12) if is_hourly and fee_amount else None
    #new change: reuse the candidate's combined name throughout the invoice email.
    candidate_name = candidate.full_name or candidate.email
    basis_label = (
        f"annualized rate of ${basis_amount:,}/yr (${hire_salary:,}/hr x {STANDARD_ANNUAL_HOURS:,} hrs)"
        if is_hourly else f"first-year compensation of ${basis_amount:,}"
    )
    try:
        if payment_link_url and fee_amount and is_hourly:
            send_branded_email(
                to_email=employer_user.email,
                subject=f"Placement fee billing set up - {candidate_name} / {job.title}",
                heading="Monthly placement fee billing",
                body_html=(
                    f"<strong>{candidate_name}</strong> has confirmed their hire for "
                    f"<strong>{job.title}</strong> through Avants AI.<br><br>"
                    f"Since this is an hourly role, the placement fee bills monthly for as long as the "
                    f"engagement is active - <strong>${monthly_fee_amount:,}/month</strong> "
                    f"({fee_percent}% of the {basis_label}, split across 12 months), rather than one lump sum. "
                    f"Billing stops automatically once you mark the engagement ended on your dashboard.<br><br>"
                    f"Click below to set up billing securely via Stripe."
                ),
                plain_text=(
                    f"{candidate_name} has confirmed their hire for {job.title} through Avants AI.\n\n"
                    f"Since this is an hourly role, the placement fee bills monthly for as long as the "
                    f"engagement is active: ${monthly_fee_amount:,}/month ({fee_percent}% of the {basis_label}, "
                    f"split across 12 months). Billing stops once you mark the engagement ended on your dashboard.\n"
                    f"Set up billing here: {payment_link_url}"
                ),
                cta_label="Set Up Monthly Billing",
                cta_url=payment_link_url,
            )
        elif payment_link_url and fee_amount:
            send_branded_email(
                to_email=employer_user.email,
                subject=f"Placement fee invoice - {candidate_name} / {job.title}",
                heading="Placement fee due",
                body_html=(
                    f"<strong>{candidate_name}</strong> has confirmed their hire for "
                    f"<strong>{job.title}</strong> through Avants AI.<br><br>"
                    f"The platform placement fee is <strong>${fee_amount:,}</strong> "
                    f"({fee_percent}% of {basis_label}).<br><br>"
                    f"This is due within 30 days of the candidate's start date. "
                    f"Click below to pay securely via Stripe."
                ),
                plain_text=(
                    f"{candidate_name} has confirmed their hire for {job.title} through Avants AI.\n\n"
                    f"Placement fee: ${fee_amount:,} ({fee_percent}% of {basis_label}).\n"
                    f"Pay here: {payment_link_url}"
                ),
                cta_label="Pay Placement Fee",
                cta_url=payment_link_url,
            )
        else:
            fee_percent_display = fee_percent or PLATFORM_FEE_PERCENT
            send_branded_email(
                to_email=employer_user.email,
                subject=f"Placement fee - {candidate_name} / {job.title}",
                heading="Placement fee due",
                body_html=(
                    f"<strong>{candidate_name}</strong> has confirmed their hire for "
                    f"<strong>{job.title}</strong> through Avants AI.<br><br>"
                    f"A placement fee of <strong>{fee_percent_display}% of first-year compensation</strong> "
                    f"is due within 30 days of the candidate's start date. "
                    f"Our team will follow up with an invoice."
                ),
                plain_text=(
                    f"{candidate_name} has confirmed their hire for {job.title} through Avants AI.\n\n"
                    f"A {fee_percent_display}% placement fee will be invoiced to you within 30 days of the start date."
                ),
                cta_label="View Dashboard",
                cta_url=external_url('employer.dashboard'),
            )
    except Exception as e:
        print(f"Hire fee invoice email failed: {e}")

def _create_stripe_payment_link(application, job, company, candidate):
    """One-time placement fee for salaried/monthly/stipend/contract hires.
    Hourly hires use _create_stripe_subscription_link instead - see there
    for why."""
    stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
    basis_amount, fee_percent = _placement_fee_basis(application, job)
    if not stripe.api_key or not basis_amount:
        return None
    fee_cents = int(basis_amount * fee_percent / 100 * 100)
    if fee_cents <= 0:
        return None
    try:
        product = stripe.Product.create(
            name=f"Avants AI Placement Fee - {job.title} at {company.name}",
            metadata={"application_id": str(application.id)},
        )
        price = stripe.Price.create(product=product.id, unit_amount=fee_cents, currency="usd")
        link = stripe.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}],
            metadata={"application_id": str(application.id)},
            customer_creation="always",
        )
        return link.url
    except Exception as e:
        print("Stripe payment link creation failed:", e)
        return None

def _create_stripe_subscription_link(application, job, company, candidate):
    """Recurring monthly placement fee for hourly hires.

    The fee basis is the hourly rate annualized to a full 2,080-hour year
    (see _placement_fee_basis), but an hourly engagement might only last a
    few weeks - charging the full annualized fee up front the moment
    someone's hired would bill the employer for a full year of work that
    may never happen. Instead this bills 1/12th of that annualized fee
    every month, for as long as the engagement is actually active, so total
    revenue tracks actual engagement length instead of a one-time guess.
    Stops the moment the employer marks the engagement ended - see
    employer.end_hourly_engagement.
    """
    stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
    basis_amount, fee_percent = _placement_fee_basis(application, job)
    if not stripe.api_key or not basis_amount:
        return None
    monthly_fee_cents = int(basis_amount * fee_percent / 100 / 12 * 100)
    if monthly_fee_cents <= 0:
        return None
    try:
        product = stripe.Product.create(
            name=f"Avants AI Placement Fee (monthly) - {job.title} at {company.name}",
            metadata={"application_id": str(application.id)},
        )
        price = stripe.Price.create(
            product=product.id,
            unit_amount=monthly_fee_cents,
            currency="usd",
            recurring={"interval": "month"},
        )
        link = stripe.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}],
            metadata={"application_id": str(application.id)},
            customer_creation="always",
        )
        return link.url
    except Exception as e:
        print("Stripe subscription link creation failed:", e)
        return None
