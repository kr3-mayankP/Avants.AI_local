import json
import io
import logging

import stripe
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, Response, current_app
from flask_login import login_required, current_user
from . import db
from .models import (
    EarnTask, TaskSubmission, User, EARN_DOMAINS, ContractorProfile, Company, Job, CompanyMember,
    Application, Feedback, FeedbackInsight, SavedJob, MeetingProposal, MeetingRoom, Message,
    EmployerSubscription, CompanyInvite, DeletedJob, Referral,
)
from .dataset_export import shape_submission
from ai_services import analyze_platform_feedback
from video_storage import delete_interview_videos

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin_bp', __name__)


def _require_admin():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


# ------------------------------------------------ #
# -------------------- DASHBOARD ----------------- #
# ------------------------------------------------ #



# ------------------------------------------------ #
# ------------------- COMPANIES ------------------ #
# ------------------------------------------------ #





def _cascade_delete_applications(application_ids):
    """Delete every row that hangs off a set of applications - meetings,
    messages, feedback, and stored interview videos - before the
    applications themselves."""
    if not application_ids:
        return
    for app_id in application_ids:
        delete_interview_videos(app_id)
    MeetingProposal.query.filter(MeetingProposal.application_id.in_(application_ids)).delete(synchronize_session=False)
    Message.query.filter(Message.application_id.in_(application_ids)).delete(synchronize_session=False)
    MeetingRoom.query.filter(MeetingRoom.application_id.in_(application_ids)).delete(synchronize_session=False)
    Feedback.query.filter(Feedback.application_id.in_(application_ids)).delete(synchronize_session=False)
    Application.query.filter(Application.id.in_(application_ids)).delete(synchronize_session=False)


def _cascade_delete_jobs(job_ids, source='admin'):
    """Snapshot each job into DeletedJob, then delete every application under
    it (and everything under those, via _cascade_delete_applications), then
    the job itself. Restoring a DeletedJob only recreates the job listing -
    the applications/messages/videos wiped out here are gone for good."""
    if not job_ids:
        return
    jobs = Job.query.filter(Job.id.in_(job_ids)).all()
    application_counts = dict(
        db.session.query(Application.job_id, db.func.count(Application.id))
        .filter(Application.job_id.in_(job_ids))
        .group_by(Application.job_id).all()
    )
    for job in jobs:
        db.session.add(DeletedJob(
            original_job_id=job.id,
            company_id=job.company_id,
            company_name=job.company.name,
            title=job.title,
            snapshot=json.dumps(job.to_snapshot_dict()),
            applicant_count=application_counts.get(job.id, 0),
            deleted_by_user_id=current_user.id,
            deleted_source=source,
        ))

    application_ids = [a.id for a in Application.query.filter(Application.job_id.in_(job_ids)).all()]
    _cascade_delete_applications(application_ids)
    SavedJob.query.filter(SavedJob.job_id.in_(job_ids)).delete(synchronize_session=False)
    Job.query.filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
















# ------------------------------------------------ #
# -------------------- FEEDBACK ------------------ #
# ------------------------------------------------ #





# ------------------------------------------------ #
# ------------------- CREATE TASK ---------------- #
# ------------------------------------------------ #



# ------------------------------------------------ #
# ------------------- CLOSE TASK ----------------- #
# ------------------------------------------------ #



# ------------------------------------------------ #
# --------- EXPORT TRAINING DATA (JSONL) --------- #
# ------------------------------------------------ #



# ------------------------------------------------ #
# ------------- VIEW TASK SUBMISSIONS ------------ #
# ------------------------------------------------ #



# ------------------------------------------------ #
# ------------------- PAYOUTS -------------------- #
# ------------------------------------------------ #





# ------------------------------------------------ #
# -------------------- REFERRALS ------------------ #
# ------------------------------------------------ #

from . import admin_companies as _admin_companies
from . import admin_operations as _admin_operations
