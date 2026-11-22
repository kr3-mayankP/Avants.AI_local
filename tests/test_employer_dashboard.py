# ----------------------------------------------------------------
# CHANGE BLOCK: 2026-11-22
# NEW FILE - active implementation
# ----------------------------------------------------------------
import importlib
import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4


class EmployerDashboardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_environment = patch.dict(os.environ, {
            "DATABASE_URL": "sqlite:///:memory:",
            "RATELIMIT_ENABLED": "false",
            "SECRET_KEY": "employer-dashboard-test",
        })
        test_environment.start()
        try:
            cls.app_module = importlib.import_module("app")
        finally:
            test_environment.stop()

        cls.app = cls.app_module.app
        cls.app.config["TESTING"] = True
        from website import db
        from website import employer_jobs
        from website.models import (
            Application, CandidateProfile, Company, Job, MeetingRoom, Message, User,
        )

        cls.db = db
        cls.employer_jobs = employer_jobs
        cls.Application = Application
        cls.CandidateProfile = CandidateProfile
        cls.Company = Company
        cls.Job = Job
        cls.MeetingRoom = MeetingRoom
        cls.Message = Message
        cls.User = User

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.db.session.remove()
            cls.db.engine.dispose()

    def test_unsigned_stripe_webhook_is_rejected(self):
        client = self.app.test_client()
        response = client.post(
            "/stripe/webhook",
            data='{"type":"checkout.session.completed","data":{"object":{"metadata":{"application_id":"1"}}}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)

    def test_security_headers_are_added(self):
        client = self.app.test_client()
        response = client.get("/")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertIn("frame-ancestors 'none'", response.headers.get("Content-Security-Policy", ""))

    def test_dashboard_uses_live_data_and_assistant_route(self):
        suffix = uuid4().hex
        with self.app.app_context():
            recruiter = self.User(
                email=f"recruiter-{suffix}@example.invalid",
                first_name="Jordan",
                last_name="Recruiter",
                role="employer",
            )
            candidate = self.User(
                email=f"candidate-{suffix}@example.invalid",
                first_name="Casey",
                last_name="Candidate",
                role="candidate",
            )
            self.db.session.add_all([recruiter, candidate])
            self.db.session.flush()

            company = self.Company(owner_user_id=recruiter.id, name="Test Recruiting")
            self.db.session.add(company)
            self.db.session.flush()

            job = self.Job(
                company_id=company.id,
                title="Platform Engineer",
                description="Build reliable systems",
                category="Engineering",
                status="open",
                created_at=datetime.now(timezone.utc),
            )
            self.db.session.add(job)
            self.db.session.add_all([
                self.Job(
                    company_id=company.id,
                    title="Closed Designer Role",
                    description="Closed role",
                    category="Design",
                    status="closed",
                ),
                self.Job(
                    company_id=company.id,
                    title="Draft Analyst Role",
                    description="Draft role",
                    category="Operations",
                    status="draft",
                ),
            ])
            self.db.session.flush()

            application = self.Application(
                job_id=job.id,
                candidate_user_id=candidate.id,
                resume_text="Test resume",
                status="interviewing",
                match_score=92,
                interview_transcript="Interview completed",
                created_at=datetime.now(timezone.utc),
            )
            self.db.session.add_all([
                self.CandidateProfile(
                    user_id=candidate.id,
                    headline="Backend engineer",
                    years_experience="5 years",
                    skills="Python, SQL, Flask",
                ),
                application,
            ])
            self.db.session.flush()
            self.db.session.add_all([
                self.MeetingRoom(
                    application_id=application.id,
                    employer_user_id=recruiter.id,
                    room_name=f"room-{suffix}",
                    room_url="https://example.invalid/room",
                    scheduled_date="2026-11-23",
                    scheduled_time="10:00",
                    created_at=datetime.now(timezone.utc),
                ),
                self.Message(
                    application_id=application.id,
                    sender_user_id=candidate.id,
                    body="Hello",
                    read=False,
                    created_at=datetime.now(timezone.utc),
                ),
            ])
            self.db.session.commit()
            recruiter_id = recruiter.id
            company_id = company.id

        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(recruiter_id)
            session["_fresh"] = True

        dashboard = client.get("/employer/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        page = dashboard.get_data(as_text=True)
        self.assertIn("AI Hiring Assistant", page)
        self.assertIn("Platform Engineer", page)
        self.assertIn("Casey Candidate", page)
        self.assertIn("Recent Activity", page)
        self.assertIn("Closed jobs and drafts", page)
        self.assertIn("Draft Analyst Role", page)

        with self.app.app_context():
            company = self.db.session.get(self.Company, company_id)
            company.blind_mode_enabled = True
            self.db.session.commit()

        blind_dashboard = client.get("/employer/dashboard").get_data(as_text=True)
        self.assertNotIn("Casey Candidate", blind_dashboard)
        self.assertIn("Candidate #1", blind_dashboard)

        with patch.object(
            self.employer_jobs,
            "generate_employer_dashboard_answer",
            return_value="Review the open role and shortlist.",
        ) as assistant:
            response = client.post(
                "/employer/dashboard/assistant",
                json={"message": "What should I review?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["reply"], "Review the open role and shortlist.")
        assistant.assert_called_once()

        invalid_response = client.post(
            "/employer/dashboard/assistant",
            json={"message": ""},
        )
        self.assertEqual(invalid_response.status_code, 400)

    def test_manage_jobs_status_search_and_bulk_actions(self):
        suffix = uuid4().hex
        with self.app.app_context():
            recruiter = self.User(
                email=f"jobs-recruiter-{suffix}@example.invalid",
                first_name="Jobs",
                role="employer",
            )
            self.db.session.add(recruiter)
            self.db.session.flush()
            company = self.Company(owner_user_id=recruiter.id, name="Jobs Test Company")
            self.db.session.add(company)
            self.db.session.flush()
            open_job = self.Job(
                company_id=company.id,
                title="Senior DevOps Engineer",
                description="Operate cloud infrastructure",
                location="Remote (Worldwide)",
                employment_type="Full-time",
                category="IT / Operations",
                status="open",
            )
            draft_job = self.Job(
                company_id=company.id,
                title="Draft Designer",
                description="Create product experiences",
                location="Hybrid - London",
                employment_type="Contract",
                category="Design",
                status="draft",
            )
            self.db.session.add_all([open_job, draft_job])
            self.db.session.commit()
            recruiter_id = recruiter.id
            open_job_id = open_job.id
            draft_job_id = draft_job.id

        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(recruiter_id)
            session["_fresh"] = True

        page = client.get("/employer/jobs?status=all&q=Engineer")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Senior DevOps Engineer", page.data)
        detail = client.get(f"/employer/jobs/{open_job_id}/detail")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"Senior DevOps Engineer", detail.data)
        self.assertIn(b"Applications", detail.data)
        self.assertIn(b"Hiring Pipeline", detail.data)

        paused = client.post(f"/employer/jobs/{open_job_id}/pause")
        self.assertIn(paused.status_code, (302, 303))
        with self.app.app_context():
            self.assertEqual(self.db.session.get(self.Job, open_job_id).status, "paused")

        duplicate = client.post(f"/employer/jobs/{draft_job_id}/duplicate")
        self.assertIn(duplicate.status_code, (302, 303))
        with self.app.app_context():
            company = self.Company.query.filter_by(name="Jobs Test Company").first()
            copy = self.Job.query.filter_by(company_id=company.id, status="draft").filter(self.Job.title.endswith("(Copy)")).first()
            self.assertEqual(copy.status, "draft")

        bulk = client.post("/employer/jobs/bulk-close", data={"job_ids": [str(open_job_id)]})
        self.assertIn(bulk.status_code, (302, 303))

    def test_job_post_ai_assist_route(self):
        suffix = uuid4().hex
        with self.app.app_context():
            recruiter = self.User(
                email=f"ai-recruiter-{suffix}@example.invalid",
                first_name="AI",
                role="employer",
            )
            self.db.session.add(recruiter)
            self.db.session.flush()
            self.db.session.add(
                self.Company(owner_user_id=recruiter.id, name="AI Test Company")
            )
            self.db.session.commit()
            recruiter_id = recruiter.id

        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(recruiter_id)
            session["_fresh"] = True

        generated = {
            "title": "Senior Backend Engineer",
            "about": "Build reliable production services.",
            "responsibilities": "Design APIs\nOperate services",
            "requirements": "3+ years of backend experience",
            "required_skills": ["Java", "Spring Boot"],
            "preferred_skills": ["Docker"],
            "quality_score": 92,
        }
        with patch.object(
            self.employer_jobs,
            "generate_job_post_assistant",
            return_value=generated,
        ) as assistant:
            response = client.post(
                "/employer/jobs/ai-assist",
                json={
                    "action": "generate",
                    "prompt": "Senior Java backend engineer",
                    "current_job": {},
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["generated"]["title"], "Senior Backend Engineer")
        assistant.assert_called_once()

    def test_dashboard_shows_empty_company_state(self):
        suffix = uuid4().hex
        with self.app.app_context():
            recruiter = self.User(
                email=f"empty-recruiter-{suffix}@example.invalid",
                first_name="Alex",
                role="employer",
            )
            self.db.session.add(recruiter)
            self.db.session.flush()
            self.db.session.add(
                self.Company(owner_user_id=recruiter.id, name="New Company")
            )
            self.db.session.commit()
            recruiter_id = recruiter.id

        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(recruiter_id)
            session["_fresh"] = True

        response = client.get("/employer/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No active jobs yet.", response.data)
        self.assertIn(b"No new notifications.", response.data)

    def test_dashboard_assistant_service_uses_context_and_returns_text(self):
        import ai_service_matching
        from unittest.mock import Mock

        fake_client = Mock()
        fake_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="  Review open roles.  ")
                )
            ]
        )
        context = {"company": "Test Recruiting", "applications_for_open_jobs": 4}

        with patch.object(ai_service_matching, "openrouter_client", fake_client):
            answer = ai_service_matching.generate_employer_dashboard_answer(
                "What should I review?",
                context,
            )

        self.assertEqual(answer, "Review open roles.")
        ai_call = fake_client.chat.completions.create.call_args.kwargs
        self.assertEqual(ai_call["messages"][0]["role"], "system")
        self.assertIn("Test Recruiting", ai_call["messages"][1]["content"])


if __name__ == "__main__":
    unittest.main()
