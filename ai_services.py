# ----------------------------------------------------------------
# CHANGE BLOCK: 2026-11-22
# OLD IMPLEMENTATION - commented snapshot from Git HEAD
# ----------------------------------------------------------------
# OLD CODE: """Shared OpenAI-backed helpers used by both app.py (top-level routes) and the
# OLD CODE: website/ blueprints. Pulled out of app.py so blueprints can import these
# OLD CODE: without circular-importing the Flask app itself."""
# OLD CODE: import io
# OLD CODE: import os
# OLD CODE: import logging
# OLD CODE: import re
# OLD CODE: from collections import Counter
# OLD CODE:
# OLD CODE: import openai
# OLD CODE: from PyPDF2 import PdfReader
# OLD CODE: from docx import Document
# OLD CODE: from openai._exceptions import RateLimitError, APIConnectionError
# OLD CODE: from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
# OLD CODE:
# OLD CODE: from config import Config
# OLD CODE:
# OLD CODE: logger = logging.getLogger(__name__)
# OLD CODE:
# OLD CODE: client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# OLD CODE:
# OLD CODE:
# OLD CODE: def extract_pdf_text(file_stream):
# OLD CODE:     reader = PdfReader(file_stream)
# OLD CODE:     text = ""
# OLD CODE:     for page in reader.pages:
# OLD CODE:         text += page.extract_text() or ""
# OLD CODE:     return text
# OLD CODE:
# OLD CODE:
# OLD CODE: def extract_docx_text(file_stream):
# OLD CODE:     try:
# OLD CODE:         file_stream.seek(0)
# OLD CODE:         document = Document(file_stream)
# OLD CODE:         text = "\n".join(para.text for para in document.paragraphs if para.text.strip())
# OLD CODE:         return text if text.strip() else "No text found in DOCX file."
# OLD CODE:     except Exception as e:
# OLD CODE:         logger.error(f"Error reading DOCX: {e}", exc_info=True)
# OLD CODE:         return f"Error reading DOCX: {str(e)}"
# OLD CODE:
# OLD CODE:
# OLD CODE: def extract_text_from_file(filename: str, resume_bytes: bytes):
# OLD CODE:     file_stream = io.BytesIO(resume_bytes)
# OLD CODE:     if filename.endswith('.pdf'):
# OLD CODE:         return extract_pdf_text(file_stream)
# OLD CODE:     elif filename.endswith('.docx'):
# OLD CODE:         return extract_docx_text(file_stream)
# OLD CODE:     elif filename.endswith('.txt'):
# OLD CODE:         return file_stream.getvalue().decode('utf-8')
# OLD CODE:     return ""
# OLD CODE:
# OLD CODE:
# OLD CODE: def compare_resume_to_job(job_description, resume):
# OLD CODE:     prompt = f"""
# OLD CODE: Given the following job description and resume, rate how well the resume matches the job description.
# OLD CODE:
# OLD CODE: Job Description:
# OLD CODE: {job_description}
# OLD CODE:
# OLD CODE: Resume:
# OLD CODE: {resume}
# OLD CODE:
# OLD CODE: Respond EXACTLY in this format (no asterisks, no markdown bold):
# OLD CODE:
# OLD CODE: Score: <number 0-100> (<Poor / Fair / Good / Excellent>)
# OLD CODE:
# OLD CODE: Explanation:
# OLD CODE:
# OLD CODE: What the resume MATCHES (prefix each bullet with +):
# OLD CODE: + <specific match>
# OLD CODE: + <specific match>
# OLD CODE:
# OLD CODE: What the resume is MISSING or does not match (prefix each bullet with -):
# OLD CODE: - <specific gap>
# OLD CODE: - <specific gap>
# OLD CODE:
# OLD CODE: Education:
# OLD CODE: + or - <education match/gap>
# OLD CODE:
# OLD CODE: Skills / Technical:
# OLD CODE: + or - <skill match or gap>
# OLD CODE:
# OLD CODE: Experience / Internships:
# OLD CODE: + or - <experience match or gap>
# OLD CODE:
# OLD CODE: Project Links (list ALL links found in the resume, no duplicates):
# OLD CODE: <link>
# OLD CODE:
# OLD CODE: Rules:
# OLD CODE: - Use + at the start of every line that is a STRENGTH or MATCH
# OLD CODE: - Use - at the start of every line that is a GAP or MISSING requirement
# OLD CODE: - Remove all asterisks
# OLD CODE: - Be specific — mention exact skills, tools, and requirements from the job description
# OLD CODE: """
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=[{"role": "user", "content": prompt}]
# OLD CODE:     )
# OLD CODE:     return response.choices[0].message.content
# OLD CODE:
# OLD CODE:
# OLD CODE: @retry(
# OLD CODE:     stop=stop_after_attempt(3),
# OLD CODE:     wait=wait_exponential(multiplier=1, min=4, max=10),
# OLD CODE:     retry=(
# OLD CODE:         retry_if_exception_type(RateLimitError)
# OLD CODE:         | retry_if_exception_type(APIConnectionError)
# OLD CODE:     ),
# OLD CODE: )
# OLD CODE: def generate_summary(text):
# OLD CODE:     """Generate AI resume summary with retry logic."""
# OLD CODE:     try:
# OLD CODE:         response = client.chat.completions.create(
# OLD CODE:             model="gpt-3.5-turbo",
# OLD CODE:             messages=[
# OLD CODE:                 {
# OLD CODE:                     "role": "system",
# OLD CODE:                     "content": (
# OLD CODE:                         "You're a professional resume analyst. Create a 9-11 sentence summary "
# OLD CODE:                         "focusing on skills, experience, education, and other notable mentions. "
# OLD CODE:                         "Highlight KEY details and technical experience specifically. Be concise."
# OLD CODE:                     ),
# OLD CODE:                 },
# OLD CODE:                 {
# OLD CODE:                     "role": "user",
# OLD CODE:                     "content": f"Summarize this resume:\n\n{text[:Config.MAX_TEXT_LENGTH]}",
# OLD CODE:                 },
# OLD CODE:             ],
# OLD CODE:             max_tokens=600,
# OLD CODE:             timeout=Config.OPENAI_TIMEOUT,
# OLD CODE:         )
# OLD CODE:         return response.choices[0].message.content
# OLD CODE:     except Exception as e:
# OLD CODE:         logger.error(f"OpenAI API error: {str(e)}")
# OLD CODE:         raise
# OLD CODE:
# OLD CODE:
# OLD CODE: def generate_basic_analysis(text):
# OLD CODE:     """Fallback analysis when AI is unavailable."""
# OLD CODE:     try:
# OLD CODE:         words = [w for w in text.split() if len(w) > 3]
# OLD CODE:         word_counts = Counter(words)
# OLD CODE:         top_terms = [w[0] for w in word_counts.most_common(5)]
# OLD CODE:         return {
# OLD CODE:             "analysis": "Basic Text Analysis",
# OLD CODE:             "word_count": len(words),
# OLD CODE:             "top_terms": top_terms,
# OLD CODE:             "estimated_experience": "Junior" if len(words) < 300 else "Senior",
# OLD CODE:         }
# OLD CODE:     except Exception as e:
# OLD CODE:         logger.error(f"Basic analysis failed: {str(e)}")
# OLD CODE:         return {"error": "Could not generate basic analysis"}
# OLD CODE:
# OLD CODE:
# OLD CODE: @retry(
# OLD CODE:     stop=stop_after_attempt(3),
# OLD CODE:     wait=wait_exponential(multiplier=1, min=4, max=10),
# OLD CODE:     retry=(
# OLD CODE:         retry_if_exception_type(RateLimitError)
# OLD CODE:         | retry_if_exception_type(APIConnectionError)
# OLD CODE:     ),
# OLD CODE: )
# OLD CODE: def generate_resume_from_profile(linkedin_url, profile_text):
# OLD CODE:     """Turn pasted LinkedIn profile content into a structured resume — for
# OLD CODE:     candidates who have a LinkedIn presence but no resume on hand."""
# OLD CODE:     prompt = f"""
# OLD CODE: A candidate has no resume but has pasted their LinkedIn profile content below.
# OLD CODE: Turn this into a clean, professional resume.
# OLD CODE:
# OLD CODE: LinkedIn URL: {linkedin_url or "Not provided"}
# OLD CODE:
# OLD CODE: Pasted profile content (About / Experience / Education / Skills, in whatever
# OLD CODE: order the candidate pasted it):
# OLD CODE: {profile_text[:Config.MAX_TEXT_LENGTH]}
# OLD CODE:
# OLD CODE: Respond EXACTLY in this format (no asterisks, no markdown bold):
# OLD CODE:
# OLD CODE: [Name / Title]
# OLD CODE: <best-guess professional title based on experience>
# OLD CODE:
# OLD CODE: [Professional Summary]
# OLD CODE: <3-4 sentence summary>
# OLD CODE:
# OLD CODE: [Experience]
# OLD CODE: <Company — Role — Dates>
# OLD CODE: <2-3 bullet points per role, prefixed with ->
# OLD CODE:
# OLD CODE: [Education]
# OLD CODE: <Degree, Institution, Dates>
# OLD CODE:
# OLD CODE: [Skills]
# OLD CODE: <comma-separated list>
# OLD CODE:
# OLD CODE: Rules:
# OLD CODE: - Only use information present in the pasted content — never invent companies, dates, or credentials.
# OLD CODE: - If a section has no information, write "Not provided" under that heading instead of guessing.
# OLD CODE: """
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=[{"role": "user", "content": prompt}],
# OLD CODE:         max_tokens=900,
# OLD CODE:         temperature=0.3,
# OLD CODE:     )
# OLD CODE:     return response.choices[0].message.content.strip()
# OLD CODE:
# OLD CODE:
# OLD CODE: def suggest_jobs_for_profile(profile_text, target_roles, jobs):
# OLD CODE:     """Rank a candidate's profile/resume against the platform's open job
# OLD CODE:     postings and return the best-fitting ones. `jobs` is a list of dicts with
# OLD CODE:     id/title/company/category/description. Returns a list of dicts (id, score,
# OLD CODE:     reason), best match first, capped to the jobs the model considers a real fit."""
# OLD CODE:     if not jobs:
# OLD CODE:         return []
# OLD CODE:
# OLD CODE:     listings_block = "\n\n".join(
# OLD CODE:         f"[Job ID: {job['id']}] {job['title']} — {job['company']} ({job['category']})\n"
# OLD CODE:         f"{job['description'][:500]}"
# OLD CODE:         for job in jobs
# OLD CODE:     )
# OLD CODE:     target_roles_block = f"\nThe candidate also says they're interested in: {target_roles[:300]}\n" if target_roles else ""
# OLD CODE:
# OLD CODE:     prompt = f"""
# OLD CODE: A candidate is looking for their next role. Here is their profile/resume:
# OLD CODE: {profile_text[:Config.MAX_TEXT_LENGTH]}
# OLD CODE: {target_roles_block}
# OLD CODE: Here are the open job postings on the platform:
# OLD CODE: {listings_block}
# OLD CODE:
# OLD CODE: Identify which of these jobs are a genuinely good fit for this candidate. Only include jobs that are a
# OLD CODE: reasonable match — do not pad the list with poor fits just to fill space.
# OLD CODE:
# OLD CODE: Respond with one block per recommended job, ranked best fit first, EXACTLY in this format (no asterisks,
# OLD CODE: no markdown bold, no extra commentary):
# OLD CODE:
# OLD CODE: Job ID: <id>
# OLD CODE: Score: <number 0-100>
# OLD CODE: Reason: <1-2 sentences, specific to this candidate's actual background and this job's requirements>
# OLD CODE: """
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=[{"role": "user", "content": prompt}],
# OLD CODE:         max_tokens=900,
# OLD CODE:         temperature=0.3,
# OLD CODE:     )
# OLD CODE:     content = response.choices[0].message.content.strip()
# OLD CODE:
# OLD CODE:     results = []
# OLD CODE:     for block in re.split(r"\n(?=Job ID:)", content):
# OLD CODE:         id_match = re.search(r"Job ID:\s*(\d+)", block)
# OLD CODE:         score_match = re.search(r"Score:\s*(\d{1,3})", block)
# OLD CODE:         reason_match = re.search(r"Reason:\s*(.+)", block, re.DOTALL)
# OLD CODE:         if not id_match:
# OLD CODE:             continue
# OLD CODE:         results.append({
# OLD CODE:             "job_id": int(id_match.group(1)),
# OLD CODE:             "score": int(score_match.group(1)) if score_match else 0,
# OLD CODE:             "reason": reason_match.group(1).strip() if reason_match else "",
# OLD CODE:         })
# OLD CODE:     return results
# OLD CODE:
# OLD CODE:
# OLD CODE: def suggest_candidates_for_jobs(jobs, candidates):
# OLD CODE:     """Reverse of suggest_jobs_for_profile: rank a company's open-to-work talent
# OLD CODE:     pool against its own open job postings and return the best-fitting
# OLD CODE:     candidates. `jobs` is a list of dicts with id/title/category/description.
# OLD CODE:     `candidates` is a list of dicts with id/headline/skills/target_roles/
# OLD CODE:     years_experience. Returns a list of dicts (candidate_id, score, reason),
# OLD CODE:     best match first, capped to candidates the model considers a real fit."""
# OLD CODE:     if not jobs or not candidates:
# OLD CODE:         return []
# OLD CODE:
# OLD CODE:     jobs_block = "\n\n".join(
# OLD CODE:         f"- {job['title']} ({job['category']}): {job['description'][:400]}"
# OLD CODE:         for job in jobs
# OLD CODE:     )
# OLD CODE:     candidates_block = "\n\n".join(
# OLD CODE:         f"[Candidate ID: {c['id']}] {c.get('headline') or 'No headline given'}\n"
# OLD CODE:         f"Skills: {c.get('skills') or 'none listed'}\n"
# OLD CODE:         f"Target roles: {c.get('target_roles') or 'none listed'}\n"
# OLD CODE:         f"Experience: {c.get('years_experience') or 'unspecified'}"
# OLD CODE:         for c in candidates
# OLD CODE:     )
# OLD CODE:
# OLD CODE:     prompt = f"""
# OLD CODE: A company has these open job postings:
# OLD CODE: {jobs_block}
# OLD CODE:
# OLD CODE: Here is a pool of candidates who are currently open to work:
# OLD CODE: {candidates_block}
# OLD CODE:
# OLD CODE: Identify which candidates are a genuinely good fit for at least one of these open roles. Only include
# OLD CODE: candidates who are a reasonable match - do not pad the list with poor fits just to fill space.
# OLD CODE:
# OLD CODE: Respond with one block per recommended candidate, ranked best fit first, EXACTLY in this format (no
# OLD CODE: asterisks, no markdown bold, no extra commentary):
# OLD CODE:
# OLD CODE: Candidate ID: <id>
# OLD CODE: Score: <number 0-100>
# OLD CODE: Reason: <1-2 sentences, specific to this candidate's actual background and which role they fit>
# OLD CODE: """
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=[{"role": "user", "content": prompt}],
# OLD CODE:         max_tokens=900,
# OLD CODE:         temperature=0.3,
# OLD CODE:     )
# OLD CODE:     content = response.choices[0].message.content.strip()
# OLD CODE:
# OLD CODE:     results = []
# OLD CODE:     for block in re.split(r"\n(?=Candidate ID:)", content):
# OLD CODE:         id_match = re.search(r"Candidate ID:\s*(\d+)", block)
# OLD CODE:         score_match = re.search(r"Score:\s*(\d{1,3})", block)
# OLD CODE:         reason_match = re.search(r"Reason:\s*(.+)", block, re.DOTALL)
# OLD CODE:         if not id_match:
# OLD CODE:             continue
# OLD CODE:         results.append({
# OLD CODE:             "candidate_id": int(id_match.group(1)),
# OLD CODE:             "score": int(score_match.group(1)) if score_match else 0,
# OLD CODE:             "reason": reason_match.group(1).strip() if reason_match else "",
# OLD CODE:         })
# OLD CODE:     return results
# OLD CODE:
# OLD CODE:
# OLD CODE: def find_similar_jobs(current_job, other_jobs):
# OLD CODE:     """Given a job dict (id, title, description) and a list of other open jobs,
# OLD CODE:     return the 3 most semantically similar ones. Similarity is based on role
# OLD CODE:     responsibilities and required skills, not category labels.
# OLD CODE:
# OLD CODE:     Returns list of dicts: {job_id, similarity, reason}"""
# OLD CODE:     if not other_jobs:
# OLD CODE:         return []
# OLD CODE:
# OLD CODE:     current_block = (
# OLD CODE:         f"Title: {current_job['title']}\n"
# OLD CODE:         f"Description: {current_job['description'][:800]}"
# OLD CODE:     )
# OLD CODE:     candidates_block = "\n\n".join(
# OLD CODE:         f"[Job ID: {j['id']}] {j['title']} — {j['company']}\n{j['description'][:500]}"
# OLD CODE:         for j in other_jobs
# OLD CODE:     )
# OLD CODE:
# OLD CODE:     prompt = f"""You are a job similarity engine. Given a reference job and a list of other open roles, identify the 3 most similar jobs based on the actual role responsibilities, required skills, and seniority level — NOT by job category label.
# OLD CODE:
# OLD CODE: Reference job:
# OLD CODE: {current_block}
# OLD CODE:
# OLD CODE: Other open jobs:
# OLD CODE: {candidates_block}
# OLD CODE:
# OLD CODE: Pick the 3 most similar jobs and respond EXACTLY in this format (no extra text, no markdown):
# OLD CODE:
# OLD CODE: Job ID: <id>
# OLD CODE: Similarity: <number 0-100>
# OLD CODE: Reason: <one short sentence explaining the similarity>
# OLD CODE:
# OLD CODE: Job ID: <id>
# OLD CODE: Similarity: <number 0-100>
# OLD CODE: Reason: <one short sentence>
# OLD CODE:
# OLD CODE: Job ID: <id>
# OLD CODE: Similarity: <number 0-100>
# OLD CODE: Reason: <one short sentence>"""
# OLD CODE:
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=[{"role": "user", "content": prompt}],
# OLD CODE:         max_tokens=400,
# OLD CODE:         temperature=0.2,
# OLD CODE:     )
# OLD CODE:     content = response.choices[0].message.content.strip()
# OLD CODE:
# OLD CODE:     results = []
# OLD CODE:     for block in re.split(r"\n(?=Job ID:)", content):
# OLD CODE:         id_match = re.search(r"Job ID:\s*(\d+)", block)
# OLD CODE:         sim_match = re.search(r"Similarity:\s*(\d{1,3})", block)
# OLD CODE:         reason_match = re.search(r"Reason:\s*(.+)", block, re.DOTALL)
# OLD CODE:         if not id_match:
# OLD CODE:             continue
# OLD CODE:         results.append({
# OLD CODE:             "job_id": int(id_match.group(1)),
# OLD CODE:             "similarity": int(sim_match.group(1)) if sim_match else 0,
# OLD CODE:             "reason": reason_match.group(1).strip() if reason_match else "",
# OLD CODE:         })
# OLD CODE:     return results[:3]
# OLD CODE:
# OLD CODE:
# OLD CODE: def generate_rejection_feedback(job_title, company_name, match_score, match_explanation, interview_verdict, interview_transcript):
# OLD CODE:     """Draft a short, honest, encouraging rejection feedback note from employer to candidate.
# OLD CODE:     The employer will review and optionally edit before sending."""
# OLD CODE:     score_context = f"Their match score was {match_score}/100." if match_score is not None else ""
# OLD CODE:     verdict_context = f"The AI interview verdict was: {interview_verdict}." if interview_verdict else "They did not complete an AI interview."
# OLD CODE:     explanation_context = match_explanation[:600] if match_explanation else ""
# OLD CODE:     transcript_snippet = (interview_transcript or "")[:800]
# OLD CODE:
# OLD CODE:     prompt = f"""You are writing a brief, honest rejection feedback note on behalf of a hiring company to a job candidate. The note should:
# OLD CODE: - Be 3-5 sentences maximum
# OLD CODE: - Be warm and encouraging in tone
# OLD CODE: - Give specific, actionable feedback (what gaps existed, what would strengthen future applications)
# OLD CODE: - NOT be generic (avoid "we had many strong candidates")
# OLD CODE: - NOT mention the AI interview or match scoring system by name
# OLD CODE: - Be written as if from the employer directly to the candidate
# OLD CODE:
# OLD CODE: Context:
# OLD CODE: - Role: {job_title} at {company_name}
# OLD CODE: - {score_context}
# OLD CODE: - {verdict_context}
# OLD CODE: - Match analysis: {explanation_context}
# OLD CODE: - Interview highlights: {transcript_snippet}
# OLD CODE:
# OLD CODE: Write only the feedback message text. No subject line, no greeting, no sign-off."""
# OLD CODE:
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=[{"role": "user", "content": prompt}],
# OLD CODE:         max_tokens=250,
# OLD CODE:         temperature=0.5,
# OLD CODE:     )
# OLD CODE:     return response.choices[0].message.content.strip()
# OLD CODE:
# OLD CODE:
# OLD CODE: def analyze_job_description(title, about, requirements, preferred, what_you_do, contract_terms, salary_provided, category):
# OLD CODE:     """Analyze a job description and return a quality score + specific improvement suggestions.
# OLD CODE:     Returns {score: int, issues: [{level: 'error'|'warning'|'tip', text: str}]}"""
# OLD CODE:
# OLD CODE:     salary_note = "Salary range: NOT provided." if not salary_provided else "Salary range: provided."
# OLD CODE:     desc_block = "\n".join(filter(None, [
# OLD CODE:         f"Title: {title}",
# OLD CODE:         f"Category: {category}",
# OLD CODE:         salary_note,
# OLD CODE:         f"About the role:\n{about[:600]}" if about else "",
# OLD CODE:         f"Requirements:\n{requirements[:600]}" if requirements else "",
# OLD CODE:         f"Preferred:\n{preferred[:400]}" if preferred else "",
# OLD CODE:         f"What you'll do:\n{what_you_do[:400]}" if what_you_do else "",
# OLD CODE:         f"Contract terms:\n{contract_terms[:300]}" if contract_terms else "",
# OLD CODE:     ]))
# OLD CODE:
# OLD CODE:     prompt = f"""You are an expert recruiter reviewing a job posting for quality and candidate appeal. Analyze the posting below and return:
# OLD CODE: 1. An overall quality score from 0-100
# OLD CODE: 2. A list of specific, actionable issues (errors, warnings, or tips)
# OLD CODE:
# OLD CODE: Scoring guide:
# OLD CODE: - 85-100: Excellent — clear, complete, specific, competitive
# OLD CODE: - 70-84: Good — minor gaps
# OLD CODE: - 50-69: Fair — missing important elements
# OLD CODE: - Below 50: Needs work — major issues
# OLD CODE:
# OLD CODE: Issue levels:
# OLD CODE: - error: Missing or critically wrong (e.g., no description at all, discriminatory language)
# OLD CODE: - warning: Important gap that reduces applications (e.g., no salary, vague requirements)
# OLD CODE: - tip: Improvement opportunity (e.g., requirements list too long, could be more specific)
# OLD CODE:
# OLD CODE: Job posting to analyze:
# OLD CODE: {desc_block}
# OLD CODE:
# OLD CODE: Respond EXACTLY in this format (no extra text):
# OLD CODE: Score: <number>
# OLD CODE: Issue: <level> | <specific actionable feedback, 1 sentence>
# OLD CODE: Issue: <level> | <specific actionable feedback, 1 sentence>
# OLD CODE: ...
# OLD CODE:
# OLD CODE: Include 3-7 issues total. Be specific to this actual posting — do not give generic advice."""
# OLD CODE:
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=[{"role": "user", "content": prompt}],
# OLD CODE:         max_tokens=500,
# OLD CODE:         temperature=0.2,
# OLD CODE:     )
# OLD CODE:     content = response.choices[0].message.content.strip()
# OLD CODE:
# OLD CODE:     score = 70
# OLD CODE:     issues = []
# OLD CODE:     for line in content.splitlines():
# OLD CODE:         line = line.strip()
# OLD CODE:         if line.startswith("Score:"):
# OLD CODE:             try:
# OLD CODE:                 score = int(re.search(r"\d+", line).group())
# OLD CODE:             except Exception:
# OLD CODE:                 pass
# OLD CODE:         elif line.startswith("Issue:"):
# OLD CODE:             rest = line[6:].strip()
# OLD CODE:             if "|" in rest:
# OLD CODE:                 level, text = rest.split("|", 1)
# OLD CODE:                 level = level.strip().lower()
# OLD CODE:                 if level not in ("error", "warning", "tip"):
# OLD CODE:                     level = "tip"
# OLD CODE:                 issues.append({"level": level, "text": text.strip()})
# OLD CODE:
# OLD CODE:     return {"score": min(100, max(0, score)), "issues": issues}
# OLD CODE:
# OLD CODE:
# OLD CODE: def generate_interview_coaching(transcript, job_title, requirements, verdict, match_score, resume=None):
# OLD CODE:     """Analyze a candidate's interview transcript and produce a private coaching report.
# OLD CODE:     Returns a dict with: communication_score, strengths (list), improvements (list), tips (list).
# OLD CODE:     Raises ValueError if the model's output doesn't parse into a usable report - callers
# OLD CODE:     should treat that as "temporarily unavailable," not silently show a fabricated score.
# OLD CODE:
# OLD CODE:     When a resume is supplied, the model is also asked to cross-check what was actually
# OLD CODE:     said against what the resume claims - flagging unsupported or inflated claims as an
# OLD CODE:     Improvement rather than just grading communication style in isolation."""
# OLD CODE:     resume_block = (
# OLD CODE:         f"\nCandidate's resume (verify their answers against this - flag anything they "
# OLD CODE:         f"claimed in the interview that isn't backed up here, or that contradicts it):\n"
# OLD CODE:         f"{resume[:2000]}\n"
# OLD CODE:     ) if resume else ""
# OLD CODE:
# OLD CODE:     prompt = f"""You are a strict, critical communication coach analyzing a job interview. Your report is private and shown only to the candidate who gave this interview - address THEM directly throughout as "you"/"your", never in the third person as "the candidate" or "they". Grade rigorously: most real candidates should NOT score above 75. Do not be encouraging or generous — an unspecific, rambling, or filler-heavy answer is a weak answer regardless of confidence or tone.
# OLD CODE:
# OLD CODE: Job: {job_title}
# OLD CODE: Requirements: {(requirements or '')[:400]}
# OLD CODE: AI verdict: {verdict or 'Not yet determined'}
# OLD CODE: Match score: {match_score}/100 (0–100 scale)
# OLD CODE: {resume_block}
# OLD CODE: Interview transcript:
# OLD CODE: {transcript[:3000]}
# OLD CODE:
# OLD CODE: Produce a coaching report with:
# OLD CODE: 1. A Communication Score (0–100) based on confidence, clarity, depth, and specificity. Score anchors:
# OLD CODE:    - 90-100: exceptional — every answer specific, quantified, and directly relevant. Rare.
# OLD CODE:    - 70-89: solid — mostly specific with concrete examples, a few vague moments.
# OLD CODE:    - 50-69: mixed — some substance but noticeably vague, generic, or unfocused answers.
# OLD CODE:    - Below 50: weak — mostly vague, evasive, filler-heavy, or off-topic answers.
# OLD CODE: 2. A Detailed Analysis - 4-6 sentences of real prose (not bullets), written directly to the candidate as "you", giving a fuller narrative assessment: what your answer(s) actually covered, how specific vs. generic you were, and how that lines up with what this role needs.
# OLD CODE: 3. Exactly 2-3 Strengths — each MUST quote or closely paraphrase a specific moment from the transcript, addressed to "you" (e.g. "You gave a concrete example when you described..."). Do not invent generic strengths ("good communicator") with no textual basis.
# OLD CODE: 4. Exactly 2-3 Improvements — concrete, specific gaps tied to your actual answers, addressed to "you", not generic advice like "be more confident."{" At least one Improvement MUST address any claim in the transcript that your resume doesn't support or contradicts, if one exists." if resume else ""}
# OLD CODE: 5. Exactly 2-3 actionable Tips for your next interview, addressed to "you", specific to the gaps identified above.
# OLD CODE:
# OLD CODE: If the transcript is too short or low-effort to support a real assessment, say so honestly to the candidate with a low score rather than padding the report.
# OLD CODE:
# OLD CODE: Respond EXACTLY in this format, with no extra commentary:
# OLD CODE: CommunicationScore: <number>
# OLD CODE: DetailedAnalysis: <4-6 sentences of prose, addressed to "you">
# OLD CODE: Strength: <1 sentence referencing something specific you said>
# OLD CODE: Strength: <1 sentence>
# OLD CODE: Improvement: <1 sentence identifying a specific gap>
# OLD CODE: Improvement: <1 sentence>
# OLD CODE: Tip: <1 sentence, concrete and actionable>
# OLD CODE: Tip: <1 sentence>
# OLD CODE: Tip: <1 sentence>"""
# OLD CODE:
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=[{"role": "user", "content": prompt}],
# OLD CODE:         max_tokens=800,
# OLD CODE:         temperature=0.2,
# OLD CODE:     )
# OLD CODE:     content = response.choices[0].message.content.strip()
# OLD CODE:
# OLD CODE:     result = {
# OLD CODE:         "communication_score": None,
# OLD CODE:         "detailed_analysis": None,
# OLD CODE:         "strengths": [],
# OLD CODE:         "improvements": [],
# OLD CODE:         "tips": [],
# OLD CODE:     }
# OLD CODE:     for line in content.splitlines():
# OLD CODE:         line = line.strip()
# OLD CODE:         if line.startswith("CommunicationScore:"):
# OLD CODE:             match = re.search(r"\d+", line)
# OLD CODE:             if match:
# OLD CODE:                 result["communication_score"] = max(0, min(100, int(match.group())))
# OLD CODE:         elif line.startswith("DetailedAnalysis:"):
# OLD CODE:             result["detailed_analysis"] = line[18:].strip()
# OLD CODE:         elif line.startswith("Strength:"):
# OLD CODE:             result["strengths"].append(line[9:].strip())
# OLD CODE:         elif line.startswith("Improvement:"):
# OLD CODE:             result["improvements"].append(line[12:].strip())
# OLD CODE:         elif line.startswith("Tip:"):
# OLD CODE:             result["tips"].append(line[4:].strip())
# OLD CODE:
# OLD CODE:     if (result["communication_score"] is None or not result["strengths"]
# OLD CODE:             or not result["improvements"] or not result["tips"]):
# OLD CODE:         raise ValueError(f"Coaching report did not parse into a complete result: {content[:200]!r}")
# OLD CODE:
# OLD CODE:     return result
# OLD CODE:
# OLD CODE:
# OLD CODE: def generate_practice_questions(job_description, resume=None):
# OLD CODE:     """Exactly 10 interview questions tailored to a job description (and,
# OLD CODE:     when provided, a candidate's resume) for the resume job-match page's
# OLD CODE:     video scan - shown after a scan completes so the candidate has
# OLD CODE:     something concrete to practice next, not a generic question bank."""
# OLD CODE:     resume_block = (
# OLD CODE:         f"\nCandidate's resume - tailor several questions to probe specific "
# OLD CODE:         f"experience it lists (depth, not just restating it):\n{resume[:2000]}\n"
# OLD CODE:     ) if resume else ""
# OLD CODE:
# OLD CODE:     prompt = f"""Draft exactly 10 interview questions for this role, the kind a candidate should practice answering before a real interview.
# OLD CODE:
# OLD CODE: Job Description: {(job_description or '')[:2000]}
# OLD CODE: {resume_block}
# OLD CODE: Cover a mix: a few background/motivation questions, several hands-on experience questions tied to specifics in the job description{" and the candidate's resume" if resume else ""}, at least one behavioral/situational question, and at least one question probing a likely weak spot relative to the role's requirements.
# OLD CODE:
# OLD CODE: Respond with ONLY the 10 questions, one per line, no numbering, no extra commentary."""
# OLD CODE:
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=[{"role": "user", "content": prompt}],
# OLD CODE:         max_tokens=500,
# OLD CODE:         temperature=0.7,
# OLD CODE:     )
# OLD CODE:     lines = response.choices[0].message.content.strip().split("\n")
# OLD CODE:     questions = [line.strip().lstrip("-•0123456789. ").strip() for line in lines if line.strip()]
# OLD CODE:     return questions[:10]
# OLD CODE:
# OLD CODE:
# OLD CODE: JOB_FIT_VERDICTS = ("Strong Yes", "Yes", "No", "Strong No")
# OLD CODE: JOB_FIT_VERDICT_SCORE = {"Strong Yes": 100, "Yes": 75, "No": 25, "Strong No": 0}
# OLD CODE:
# OLD CODE:
# OLD CODE: def generate_job_fit_verdict(transcript, job_description):
# OLD CODE:     """One-shot assessment of whether what a candidate actually SAID in an
# OLD CODE:     interview answer demonstrates fit for a job description - distinct from
# OLD CODE:     generate_interview_coaching's communication-style score, this judges the
# OLD CODE:     content/substance against the role's requirements, not how well they
# OLD CODE:     spoke. Returns {"verdict": one of JOB_FIT_VERDICTS, "reasoning": str,
# OLD CODE:     "missed_requirements": list[str]} - missed_requirements names specific
# OLD CODE:     things the job description asks for that the answer never addressed at
# OLD CODE:     all (as opposed to reasoning, which explains the overall verdict).
# OLD CODE:     Raises ValueError if the model's output doesn't parse - same
# OLD CODE:     treat-as-unavailable contract as generate_interview_coaching."""
# OLD CODE:     prompt = f"""You are assessing whether a candidate's interview answer demonstrates they'd be a good fit for this specific job, based only on what they actually said - not how well or confidently they said it. This assessment is shown directly to the candidate themselves - address THEM as "you"/"your" throughout, never in the third person as "the candidate" or "they".
# OLD CODE:
# OLD CODE: Job Description:
# OLD CODE: {(job_description or '')[:2000]}
# OLD CODE:
# OLD CODE: Candidate's interview answer(s):
# OLD CODE: {transcript[:3000]}
# OLD CODE:
# OLD CODE: Judge strictly: does the SUBSTANCE of what you said show relevant experience, skills, or understanding that matches this job's requirements? A well-spoken but generic or irrelevant answer should NOT score well here. A specific, relevant answer that directly addresses the role should score well even if communication style is plain.
# OLD CODE:
# OLD CODE: Also identify specific requirements, skills, or responsibilities named in the job description that this answer never addressed at all - not weaknesses in how you answered, but concrete things the JD asks for that simply never came up. List 1-3; if the answer genuinely covers everything the JD calls for, say so with zero items rather than inventing gaps.
# OLD CODE:
# OLD CODE: Respond EXACTLY in this format, no extra commentary:
# OLD CODE: Verdict: <Strong Yes|Yes|No|Strong No>
# OLD CODE: Reasoning: <3-5 sentences, addressed to "you", going into specific detail - what in your answer worked for this role, what specifically fell short, and why, citing concrete phrases from both the job description and what you said>
# OLD CODE: Missed: <a specific JD requirement/skill never addressed, or omit this line entirely if there are none>
# OLD CODE: Missed: <another, if applicable>"""
# OLD CODE:
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=[{"role": "user", "content": prompt}],
# OLD CODE:         max_tokens=450,
# OLD CODE:         temperature=0.2,
# OLD CODE:     )
# OLD CODE:     content = response.choices[0].message.content.strip()
# OLD CODE:
# OLD CODE:     verdict, reasoning = None, None
# OLD CODE:     missed_requirements = []
# OLD CODE:     for line in content.splitlines():
# OLD CODE:         line = line.strip()
# OLD CODE:         if line.startswith("Verdict:"):
# OLD CODE:             candidate = line[8:].strip()
# OLD CODE:             if candidate in JOB_FIT_VERDICTS:
# OLD CODE:                 verdict = candidate
# OLD CODE:         elif line.startswith("Reasoning:"):
# OLD CODE:             reasoning = line[10:].strip()
# OLD CODE:         elif line.startswith("Missed:"):
# OLD CODE:             item = line[7:].strip()
# OLD CODE:             if item:
# OLD CODE:                 missed_requirements.append(item)
# OLD CODE:
# OLD CODE:     if not verdict or not reasoning:
# OLD CODE:         raise ValueError(f"Job fit verdict did not parse into a complete result: {content[:200]!r}")
# OLD CODE:
# OLD CODE:     return {"verdict": verdict, "reasoning": reasoning, "missed_requirements": missed_requirements}
# OLD CODE:
# OLD CODE:
# OLD CODE: def generate_skills_roadmap(job_title, match_explanation, match_score, requirements):
# OLD CODE:     """Generate a specific 30-day action plan to close the skills gap for a role.
# OLD CODE:     Returns a list of {step, description, timeline} dicts."""
# OLD CODE:     prompt = f"""A candidate applied for {job_title} and scored {match_score}/100. Generate a specific, actionable 30-day plan to help them become competitive for this type of role.
# OLD CODE:
# OLD CODE: Their match analysis:
# OLD CODE: {(match_explanation or '')[:800]}
# OLD CODE:
# OLD CODE: Job requirements:
# OLD CODE: {(requirements or '')[:500]}
# OLD CODE:
# OLD CODE: Create 4–5 specific steps. Each step must be concrete (name a specific skill, course type, or project to build — not just "learn Python"). Focus only on closing the actual gaps identified above.
# OLD CODE:
# OLD CODE: Respond EXACTLY in this format:
# OLD CODE: Step: <short title (3-6 words)>
# OLD CODE: Description: <1-2 sentences — what exactly to do and why it closes a gap>
# OLD CODE: Timeline: <e.g. "Week 1–2" or "Days 1–7">
# OLD CODE:
# OLD CODE: Step: ...
# OLD CODE: Description: ...
# OLD CODE: Timeline: ..."""
# OLD CODE:
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=[{"role": "user", "content": prompt}],
# OLD CODE:         max_tokens=600,
# OLD CODE:         temperature=0.3,
# OLD CODE:     )
# OLD CODE:     content = response.choices[0].message.content.strip()
# OLD CODE:
# OLD CODE:     steps = []
# OLD CODE:     current = {}
# OLD CODE:     for line in content.splitlines():
# OLD CODE:         line = line.strip()
# OLD CODE:         if line.startswith("Step:"):
# OLD CODE:             if current.get("step"):
# OLD CODE:                 steps.append(current)
# OLD CODE:             current = {"step": line[5:].strip(), "description": "", "timeline": ""}
# OLD CODE:         elif line.startswith("Description:"):
# OLD CODE:             current["description"] = line[12:].strip()
# OLD CODE:         elif line.startswith("Timeline:"):
# OLD CODE:             current["timeline"] = line[9:].strip()
# OLD CODE:     if current.get("step"):
# OLD CODE:         steps.append(current)
# OLD CODE:     return steps[:5]
# OLD CODE:
# OLD CODE:
# OLD CODE: VERDICT_CRITERIA = (
# OLD CODE:     "Grade strictly - most candidates should NOT get 'Strong Yes,' and plenty should not get 'Yes' either. "
# OLD CODE:     "A real recruiter screen filters out the majority of applicants; treat this the same way, not as a "
# OLD CODE:     "formality on the way to a job offer.\n"
# OLD CODE:     "- Strong Yes: exceptional, specific, quantified answers across every area probed, with no real "
# OLD CODE:     "weaknesses surfaced. Rare - reserved for candidates a hiring manager would want to fast-track.\n"
# OLD CODE:     "- Yes: solid, mostly specific answers backed by real relevant experience, with only minor gaps. Would "
# OLD CODE:     "genuinely move forward to the next round.\n"
# OLD CODE:     "- No: vague, generic, unconvincing, or off-target answers; real gaps relative to the role; rambling "
# OLD CODE:     "instead of concrete specifics. This is where most candidates who don't clearly stand out belong.\n"
# OLD CODE:     "- Strong No: evasive, contradictory, clearly unqualified, or repeatedly unable to give a concrete answer "
# OLD CODE:     "when pushed.\n"
# OLD CODE:     "Confidence and articulateness alone are NOT enough for a Yes - the content must be specific and "
# OLD CODE:     "substantiated. When genuinely torn between two verdicts, choose the stricter one."
# OLD CODE: )
# OLD CODE:
# OLD CODE: VERDICT_FORMAT = (
# OLD CODE:     "Verdict: <Strong Yes / Yes / No / Strong No>\n\n"
# OLD CODE:     "Why:\n"
# OLD CODE:     "+ <specific strength from the conversation>\n"
# OLD CODE:     "+ <another specific strength, if there genuinely is one>\n"
# OLD CODE:     "- <specific concern or gap from the conversation>\n"
# OLD CODE:     "- <another specific concern or gap, if there genuinely is one>\n"
# OLD CODE:     "(List every substantive strength and every substantive concern you actually observed - don't omit a "
# OLD CODE:     "real one just to fit a fixed count, and don't pad with trivial or repetitive points to hit one either. "
# OLD CODE:     "Typically 2-5 of each is honest for a normal-length interview. Be complete about both sides, not just "
# OLD CODE:     "enough to justify the verdict.)"
# OLD CODE: )
# OLD CODE:
# OLD CODE:
# OLD CODE: INTERVIEW_LENGTH_GUIDANCE = {
# OLD CODE:     "short": (
# OLD CODE:         "Keep this brief — aim for about 3-4 total exchanges. Cover background/motivation in 1 question, "
# OLD CODE:         "one hands-on experience deep-dive, and one weak-spot probe. Skip the behavioral question unless "
# OLD CODE:         "something concerning comes up that needs follow-up."
# OLD CODE:     ),
# OLD CODE:     "standard": (
# OLD CODE:         "A real recruiter screen for a role like this typically runs 5-8 questions across that structure, "
# OLD CODE:         "but use your own judgment of when you have enough to make a confident call, not a fixed count."
# OLD CODE:     ),
# OLD CODE:     "thorough": (
# OLD CODE:         "Go deeper than a typical screen — aim for roughly 8-12 exchanges. Spend more time on hands-on "
# OLD CODE:         "experience (3-4 deep-dives across different projects), ask more than one behavioral/situational "
# OLD CODE:         "question, and probe multiple potential weak spots relative to the role's requirements."
# OLD CODE:     ),
# OLD CODE: }
# OLD CODE:
# OLD CODE:
# OLD CODE: def run_interview_turn(role, job_description, user_message, history, force_conclude=False,
# OLD CODE:                         interview_length="standard", interview_focus=None, interview_questions=None,
# OLD CODE:                         practice_mode=False):
# OLD CODE:     """One turn of the AI recruiter-screen interview. The model alone decides
# OLD CODE:     when it has enough signal to stop asking questions and issue a verdict —
# OLD CODE:     no fixed question cap, just a length steer (short/standard/thorough) the
# OLD CODE:     employer chose for this job. force_conclude is only set by an explicit
# OLD CODE:     candidate "wrap up" action. Returns the assistant's reply text; the caller
# OLD CODE:     detects conclusion by checking whether the reply contains a "Verdict:"
# OLD CODE:     line, not by a precomputed flag.
# OLD CODE:
# OLD CODE:     practice_mode=True is used for the candidate-facing practice interview
# OLD CODE:     (no real employer questions passed in, nothing saved or scored for real).
# OLD CODE:     It steers toward more concrete, role-specific questions grounded in the
# OLD CODE:     actual job description instead of generic templates like "tell me about
# OLD CODE:     a time..." with no connection to the role, since the whole point of
# OLD CODE:     practice is rehearsing for what this specific interview will look like."""
# OLD CODE:     context_block = f"\n=== ROLE ===\n{role}\n"
# OLD CODE:     if job_description:
# OLD CODE:         context_block += f"\n=== JOB DESCRIPTION ===\n{job_description[:2000]}\n"
# OLD CODE:     if interview_focus:
# OLD CODE:         context_block += (
# OLD CODE:             "\n=== EMPLOYER'S GUIDANCE FOR THIS INTERVIEW (topics to make sure get covered, things to "
# OLD CODE:             "listen for, and any conditional instructions — e.g. 'if a candidate mentions X, dig into Y' — "
# OLD CODE:             f"follow these as written) ===\n{interview_focus[:2000]}\n"
# OLD CODE:         )
# OLD CODE:     if interview_questions:
# OLD CODE:         questions_block = "\n".join(f"- {q}" for q in interview_questions[:15])
# OLD CODE:         context_block += (
# OLD CODE:             "\n=== EMPLOYER-WRITTEN QUESTIONS (work these in verbatim or near-verbatim over "
# OLD CODE:             f"the course of the interview) ===\n{questions_block}\n"
# OLD CODE:         )
# OLD CODE:
# OLD CODE:     length_guidance = INTERVIEW_LENGTH_GUIDANCE.get(interview_length, INTERVIEW_LENGTH_GUIDANCE["standard"])
# OLD CODE:
# OLD CODE:     if force_conclude:
# OLD CODE:         decision_rule = (
# OLD CODE:             "- The candidate has asked to wrap up. Do NOT ask another question. "
# OLD CODE:             f"Output a final verdict in EXACTLY this format:\n\n{VERDICT_FORMAT}\n\n"
# OLD CODE:             f"How to decide the verdict itself:\n{VERDICT_CRITERIA}"
# OLD CODE:         )
# OLD CODE:     else:
# OLD CODE:         decision_rule = (
# OLD CODE:             f"- YOU alone decide when you have enough signal to evaluate the candidate. {length_guidance}\n"
# OLD CODE:             f"- Once you have enough signal, end the interview by outputting a final verdict in EXACTLY this format instead of another question:\n\n{VERDICT_FORMAT}\n\n"
# OLD CODE:             f"How to decide the verdict itself:\n{VERDICT_CRITERIA}\n\n"
# OLD CODE:             "- Otherwise, continue with exactly one focused follow-up question, following the structure above."
# OLD CODE:         )
# OLD CODE:
# OLD CODE:     practice_note = (
# OLD CODE:         "\nThis is a PRACTICE run - the candidate is rehearsing before their real interview, nothing here is "
# OLD CODE:         "saved or scored for a real hiring decision. Still run it like a real screen, but make every question "
# OLD CODE:         "concrete and specific to THIS job description (name the actual tools, responsibilities, or requirements "
# OLD CODE:         "it mentions) rather than a generic template question that could apply to any role. A candidate "
# OLD CODE:         "practicing should walk away knowing what this specific interview will actually probe.\n"
# OLD CODE:     ) if practice_mode else ""
# OLD CODE:
# OLD CODE:     system_prompt = (
# OLD CODE:         "You are an experienced recruiter/hiring manager conducting a real screening interview for this "
# OLD CODE:         "specific role — not an interrogation, but a focused professional conversation. You ask ONE question "
# OLD CODE:         "at a time, push for concrete specifics and numbers instead of vague claims, and redirect rambling "
# OLD CODE:         "with a direct follow-up.\n"
# OLD CODE:         f"{practice_note}"
# OLD CODE:         f"{context_block}\n"
# OLD CODE:         "Structure the interview the way a real recruiter screen actually runs:\n"
# OLD CODE:         "1. Open with a quick question on background/motivation for this specific role.\n"
# OLD CODE:         "2. Spend 2-3 questions probing concrete hands-on experience and a specific project/result tied to the role.\n"
# OLD CODE:         "3. Ask one behavioral/situational question (e.g. handling a conflict, a failure, a tight deadline).\n"
# OLD CODE:         "4. Probe one likely weak spot relative to the role's requirements.\n"
# OLD CODE:         "5. If the employer left guidance above, follow it exactly — cover any topics it names, listen for "
# OLD CODE:         "what it says to listen for, and act on any conditional instructions the moment they apply (e.g. if "
# OLD CODE:         "it says to dig deeper when a candidate mentions something specific, do that the instant they do).\n"
# OLD CODE:         "6. If the employer wrote specific questions above, work every one of them into the conversation "
# OLD CODE:         "(verbatim or lightly reworded to fit the flow) in addition to the structure above.\n\n"
# OLD CODE:         "Guidelines:\n"
# OLD CODE:         "- Ask exactly one question per turn. No preamble, no encouragement, no filler.\n"
# OLD CODE:         "- If the candidate's answer is vague, demand a specific number, example, or outcome before moving on.\n"
# OLD CODE:         f"{decision_rule}"
# OLD CODE:     )
# OLD CODE:
# OLD CODE:     messages = [{"role": "system", "content": system_prompt}]
# OLD CODE:     for msg in history[-20:]:
# OLD CODE:         if msg.get("role") in ("user", "assistant") and msg.get("content"):
# OLD CODE:             messages.append({"role": msg["role"], "content": msg["content"]})
# OLD CODE:     if user_message:
# OLD CODE:         messages.append({"role": "user", "content": user_message})
# OLD CODE:     elif not history:
# OLD CODE:         messages.append({"role": "user", "content": "Begin the interview."})
# OLD CODE:
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=messages,
# OLD CODE:         max_tokens=400,
# OLD CODE:         temperature=0.6,
# OLD CODE:     )
# OLD CODE:     return response.choices[0].message.content.strip()
# OLD CODE:
# OLD CODE:
# OLD CODE: QUESTION_BANK_SIZE = {
# OLD CODE:     "short": 8,
# OLD CODE:     "standard": 12,
# OLD CODE:     "thorough": 15,
# OLD CODE: }
# OLD CODE:
# OLD CODE:
# OLD CODE: def generate_interview_question_preview(title, description, interview_length="standard", interview_focus=None):
# OLD CODE:     """Generates a full starting question bank for an employer to review and
# OLD CODE:     edit while setting up a job posting. The employer can edit, remove, or
# OLD CODE:     add to this list — whatever they keep gets worked into the real AI
# OLD CODE:     interview (see run_interview_turn's interview_questions param), so this
# OLD CODE:     is no longer purely illustrative. Returns a list of question strings."""
# OLD CODE:     length_guidance = INTERVIEW_LENGTH_GUIDANCE.get(interview_length, INTERVIEW_LENGTH_GUIDANCE["standard"])
# OLD CODE:     target_count = QUESTION_BANK_SIZE.get(interview_length, QUESTION_BANK_SIZE["standard"])
# OLD CODE:     focus_block = f"\nThe employer's guidance for this interview: {interview_focus[:2000]}\n" if interview_focus else ""
# OLD CODE:
# OLD CODE:     prompt = f"""
# OLD CODE: You are drafting a full bank of recruiter-screen interview questions for this role. The employer will review
# OLD CODE: this list and can edit, remove, or add questions — whatever they keep will actually be asked of every
# OLD CODE: candidate, so make each question concrete and worth asking, not filler.
# OLD CODE:
# OLD CODE: Role: {title}
# OLD CODE: Job Description: {description[:2000]}
# OLD CODE: {focus_block}
# OLD CODE: Length guidance: {length_guidance}
# OLD CODE:
# OLD CODE: List {target_count} questions covering: background/motivation, several hands-on experience questions tied
# OLD CODE: to specifics in the job description, behavioral/situational questions, and weak-spot probes relative to the
# OLD CODE: role's requirements{"" if not interview_focus else ", plus at least one question per employer-requested focus area"}.
# OLD CODE:
# OLD CODE: Respond with ONLY the questions, one per line, no numbering, no extra commentary.
# OLD CODE: """
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=[{"role": "user", "content": prompt}],
# OLD CODE:         max_tokens=800,
# OLD CODE:         temperature=0.7,
# OLD CODE:     )
# OLD CODE:     lines = response.choices[0].message.content.strip().split("\n")
# OLD CODE:     return [line.strip().lstrip("-•0123456789. ").strip() for line in lines if line.strip()]
# OLD CODE:
# OLD CODE:
# OLD CODE: def analyze_ai_likelihood(transcript, job_title):
# OLD CODE:     """Estimate the probability that a candidate's interview answers were
# OLD CODE:     AI-generated (e.g. typed into ChatGPT and read aloud) rather than authentic.
# OLD CODE:     Returns a dict: {score: 0-100, label: str, reasons: [str]}"""
# OLD CODE:     candidate_lines = []
# OLD CODE:     for line in transcript.splitlines():
# OLD CODE:         stripped = line.strip()
# OLD CODE:         if stripped.lower().startswith("user:"):
# OLD CODE:             candidate_lines.append(stripped[5:].strip())
# OLD CODE:
# OLD CODE:     if not candidate_lines:
# OLD CODE:         return {"score": 0, "label": "No data", "reasons": []}
# OLD CODE:
# OLD CODE:     candidate_text = "\n\n".join(candidate_lines)
# OLD CODE:
# OLD CODE:     prompt = f"""You are a hiring expert analyzing job interview answers to detect whether they were AI-generated (e.g. the candidate used ChatGPT to write answers and read or pasted them) rather than authentic spoken responses.
# OLD CODE:
# OLD CODE: Job: {job_title}
# OLD CODE:
# OLD CODE: Candidate's answers only:
# OLD CODE: {candidate_text[:3000]}
# OLD CODE:
# OLD CODE: Analyze for these specific AI signals:
# OLD CODE: 1. Formulaic structure (e.g. "First I would X, then Y, finally Z" repeated across answers)
# OLD CODE: 2. Dense corporate buzzwords used unnaturally ("leverage", "synergize", "holistic approach", "proactive mindset")
# OLD CODE: 3. Suspiciously comprehensive coverage — real humans miss things; AI answers every angle
# OLD CODE: 4. Missing personal specifics — no real names, company names, concrete dates, or actual numbers from memory
# OLD CODE: 5. Zero natural speech disfluencies — no self-corrections, incomplete thoughts, or casual phrasing
# OLD CODE: 6. Answers that parrot the question's exact wording back verbatim
# OLD CODE: 7. Eerily consistent tone, vocabulary level, and answer length across all questions
# OLD CODE: 8. Vague experience claims without supporting detail ("I have extensive experience in X")
# OLD CODE:
# OLD CODE: Score 0-100 where 0 = clearly authentic human speech and 100 = almost certainly AI-generated or heavily AI-edited.
# OLD CODE: Give 3 specific reasons citing actual phrases or patterns from the text above.
# OLD CODE:
# OLD CODE: Respond EXACTLY in this format (no extra text):
# OLD CODE: Score: <number>
# OLD CODE: Reason: <one specific observation — quote or name a phrase from the answers>
# OLD CODE: Reason: <another specific observation>
# OLD CODE: Reason: <another specific observation>"""
# OLD CODE:
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=[{"role": "user", "content": prompt}],
# OLD CODE:         max_tokens=350,
# OLD CODE:         temperature=0.2,
# OLD CODE:     )
# OLD CODE:     content = response.choices[0].message.content.strip()
# OLD CODE:
# OLD CODE:     result = {"score": 0, "label": "Human-like", "reasons": []}
# OLD CODE:     for line in content.splitlines():
# OLD CODE:         line = line.strip()
# OLD CODE:         if line.startswith("Score:"):
# OLD CODE:             try:
# OLD CODE:                 result["score"] = min(100, max(0, int(re.search(r"\d+", line).group())))
# OLD CODE:             except Exception:
# OLD CODE:                 pass
# OLD CODE:         elif line.startswith("Reason:"):
# OLD CODE:             result["reasons"].append(line[7:].strip())
# OLD CODE:
# OLD CODE:     score = result["score"]
# OLD CODE:     if score < 35:
# OLD CODE:         result["label"] = "Human-like"
# OLD CODE:     elif score < 65:
# OLD CODE:         result["label"] = "Uncertain"
# OLD CODE:     else:
# OLD CODE:         result["label"] = "Likely AI-assisted"
# OLD CODE:
# OLD CODE:     return result
# OLD CODE:
# OLD CODE:
# OLD CODE: def analyze_platform_feedback(feedback_rows):
# OLD CODE:     """Summarize a batch of candidate/employer feedback (rating + comment) into
# OLD CODE:     a short overview plus specific, actionable recommendations for admins to
# OLD CODE:     review - this only produces suggestions, it never changes anything itself.
# OLD CODE:     feedback_rows: list of {role, context, rating, comment} dicts.
# OLD CODE:     Returns {summary: str, recommendations: [{title, detail}]}."""
# OLD CODE:     if not feedback_rows:
# OLD CODE:         return {"summary": "No feedback yet.", "recommendations": []}
# OLD CODE:
# OLD CODE:     avg_rating = sum(r["rating"] for r in feedback_rows) / len(feedback_rows)
# OLD CODE:
# OLD CODE:     lines = []
# OLD CODE:     for r in feedback_rows[:200]:
# OLD CODE:         comment = (r.get("comment") or "").strip().replace("\n", " ")
# OLD CODE:         lines.append(f"[{r['role']} | {r['context']} | {r['rating']}/5] {comment or '(no comment)'}")
# OLD CODE:     feedback_text = "\n".join(lines)
# OLD CODE:
# OLD CODE:     prompt = f"""You are analyzing user feedback for an AI-powered hiring platform (candidates apply, get AI-interviewed, \
# OLD CODE: get scored; employers post jobs and review AI-screened applicants). Below is a batch of {len(feedback_rows)} feedback \
# OLD CODE: entries from candidates and employers, average rating {avg_rating:.1f}/5.
# OLD CODE:
# OLD CODE: {feedback_text[:8000]}
# OLD CODE:
# OLD CODE: Identify real, recurring patterns - not one-off complaints. Write a short overall summary, then 2-5 specific, \
# OLD CODE: actionable recommendations. Each recommendation must name a concrete, viable change (not vague advice like "improve \
# OLD CODE: communication") and say which group it's based on (candidates, employers, or both). If the feedback is too sparse or \
# OLD CODE: inconsistent to support a confident recommendation, say so instead of inventing one.
# OLD CODE:
# OLD CODE: Respond EXACTLY in this format:
# OLD CODE: Summary: <2-3 sentences on the overall picture>
# OLD CODE:
# OLD CODE: Recommendation: <short title (4-8 words)>
# OLD CODE: Based on: <candidates / employers / both>
# OLD CODE: Detail: <1-2 sentences - the specific, concrete change and why the feedback supports it>
# OLD CODE:
# OLD CODE: Recommendation: ...
# OLD CODE: Based on: ...
# OLD CODE: Detail: ..."""
# OLD CODE:
# OLD CODE:     response = client.chat.completions.create(
# OLD CODE:         model="gpt-4o",
# OLD CODE:         messages=[{"role": "user", "content": prompt}],
# OLD CODE:         max_tokens=700,
# OLD CODE:         temperature=0.3,
# OLD CODE:     )
# OLD CODE:     content = response.choices[0].message.content.strip()
# OLD CODE:
# OLD CODE:     summary = ""
# OLD CODE:     recommendations = []
# OLD CODE:     current = None
# OLD CODE:     for line in content.splitlines():
# OLD CODE:         line = line.strip()
# OLD CODE:         if line.startswith("Summary:"):
# OLD CODE:             summary = line[8:].strip()
# OLD CODE:         elif line.startswith("Recommendation:"):
# OLD CODE:             if current and current.get("title"):
# OLD CODE:                 recommendations.append(current)
# OLD CODE:             current = {"title": line[16:].strip(), "based_on": "", "detail": ""}
# OLD CODE:         elif line.startswith("Based on:") and current is not None:
# OLD CODE:             current["based_on"] = line[9:].strip()
# OLD CODE:         elif line.startswith("Detail:") and current is not None:
# OLD CODE:             current["detail"] = line[7:].strip()
# OLD CODE:     if current and current.get("title"):
# OLD CODE:         recommendations.append(current)
# OLD CODE:
# OLD CODE:     return {"summary": summary or content[:400], "recommendations": recommendations[:5]}
# OLD CODE:
# OLD CODE:
# OLD CODE: class AudioTooLargeError(Exception):
# OLD CODE:     """Raised when a recorded answer is too long/large for Whisper's 25MB
# OLD CODE:     cap (likely hit with the camera on, since video is far larger per
# OLD CODE:     second than audio-only) - callers should show a specific, actionable
# OLD CODE:     message instead of the generic transcription-failed one."""
# OLD CODE:     pass
# OLD CODE:
# OLD CODE:
# OLD CODE: def extract_audio_for_transcription(input_path):
# OLD CODE:     """Strips an uploaded video down to just its audio track, compressed to
# OLD CODE:     a small mono MP3, before handing it to Whisper - a video file's picture
# OLD CODE:     data is what actually eats into the 25MB cap, not the speech, so this
# OLD CODE:     lets much longer uploads fit under that same fixed limit. Falls back to
# OLD CODE:     returning the original path untouched (not raising) if ffmpeg isn't on
# OLD CODE:     PATH or the conversion fails for any reason - callers always get back a
# OLD CODE:     valid, existing file path, just not necessarily a smaller one."""
# OLD CODE:     import shutil
# OLD CODE:     import subprocess
# OLD CODE:
# OLD CODE:     ffmpeg = shutil.which("ffmpeg")
# OLD CODE:     if not ffmpeg:
# OLD CODE:         return input_path
# OLD CODE:
# OLD CODE:     out_path = f"{input_path}.audio.mp3"
# OLD CODE:     try:
# OLD CODE:         result = subprocess.run(
# OLD CODE:             [ffmpeg, "-y", "-i", input_path, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", out_path],
# OLD CODE:             capture_output=True, timeout=120,
# OLD CODE:         )
# OLD CODE:         if result.returncode == 0 and os.path.getsize(out_path) > 0:
# OLD CODE:             return out_path
# OLD CODE:     except Exception:
# OLD CODE:         logger.exception("ffmpeg audio extraction failed - falling back to the original upload")
# OLD CODE:
# OLD CODE:     if os.path.exists(out_path):
# OLD CODE:         try:
# OLD CODE:             os.unlink(out_path)
# OLD CODE:         except OSError:
# OLD CODE:             pass
# OLD CODE:     return input_path
# OLD CODE:
# OLD CODE:
# OLD CODE: def transcribe_audio(file_path):
# OLD CODE:     """Speech-to-text for a candidate's recorded interview answer."""
# OLD CODE:     with open(file_path, "rb") as f:
# OLD CODE:         try:
# OLD CODE:             transcript = client.audio.transcriptions.create(model="whisper-1", file=f)
# OLD CODE:         except openai.BadRequestError as e:
# OLD CODE:             if "size" in str(e).lower() or "25 mb" in str(e).lower() or "maximum content" in str(e).lower():
# OLD CODE:                 raise AudioTooLargeError(
# OLD CODE:                     "That answer was too long to transcribe - recordings are capped at 25MB, which "
# OLD CODE:                     "video answers can hit in roughly a minute or two depending on quality. Try a "
# OLD CODE:                     "shorter answer, or turn off your camera for longer responses."
# OLD CODE:                 ) from e
# OLD CODE:             raise
# OLD CODE:     return transcript.text.strip()
# OLD CODE:
# OLD CODE:
# OLD CODE: _ALLOWED_AUDIO_EXTENSIONS = {".webm", ".mp4", ".ogg", ".m4a", ".wav", ".mp3"}
# OLD CODE:
# OLD CODE:
# OLD CODE: def audio_file_extension(uploaded_filename):
# OLD CODE:     """Picks the suffix for the temp file a recorded answer gets written to
# OLD CODE:     before transcription, from whatever filename the browser's upload sent.
# OLD CODE:     Matters because Whisper's API decides how to decode the file from this
# OLD CODE:     suffix - Safari (desktop and iOS) doesn't support WebM at all and records
# OLD CODE:     mp4 instead, so hardcoding ".webm" regardless of what was actually
# OLD CODE:     uploaded silently breaks transcription on any non-WebM browser."""
# OLD CODE:     import os as _os
# OLD CODE:     ext = _os.path.splitext(uploaded_filename or "")[1].lower()
# OLD CODE:     return ext if ext in _ALLOWED_AUDIO_EXTENSIONS else ".webm"
# OLD CODE:
# OLD CODE:
# OLD CODE: def synthesize_speech(text, out_path):
# OLD CODE:     """Text-to-speech for an AI interview question — mirrors app.py's /speak route."""
# OLD CODE:     from google.cloud import texttospeech
# OLD CODE:
# OLD CODE:     tts_client = texttospeech.TextToSpeechClient()
# OLD CODE:     input_text = texttospeech.SynthesisInput(text=text)
# OLD CODE:     voice = texttospeech.VoiceSelectionParams(
# OLD CODE:         language_code="en-US",
# OLD CODE:         name="en-US-Wavenet-D",
# OLD CODE:         ssml_gender=texttospeech.SsmlVoiceGender.MALE,
# OLD CODE:     )
# OLD CODE:     audio_config = texttospeech.AudioConfig(
# OLD CODE:         audio_encoding=texttospeech.AudioEncoding.MP3,
# OLD CODE:         speaking_rate=1.0,
# OLD CODE:     )
# OLD CODE:     response = tts_client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)
# OLD CODE:     with open(out_path, "wb") as out:
# OLD CODE:         out.write(response.audio_content)
# ----------------------------------------------------------------
# NEW IMPLEMENTATION - active code starts below
# ----------------------------------------------------------------
"""Public compatibility exports for the split AI service modules."""

from ai_service_documents import (
    extract_pdf_text,
    extract_docx_text,
    extract_text_from_file,
    compare_resume_to_job,
    generate_summary,
    generate_basic_analysis,
    generate_resume_from_profile,
)
from ai_service_matching import (
    suggest_jobs_for_profile,
    suggest_candidates_for_jobs,
    generate_employer_dashboard_answer,
    find_similar_jobs,
    generate_rejection_feedback,
    analyze_job_description,
    generate_job_post_assistant,
)
from ai_service_interview import (
    generate_interview_coaching,
    generate_practice_questions,
    generate_job_fit_verdict,
    generate_skills_roadmap,
    run_interview_turn,
    generate_interview_question_preview,
)
from ai_service_analysis import (
    analyze_ai_likelihood,
    analyze_platform_feedback,
)
from ai_service_audio import (
    AudioTooLargeError,
    extract_audio_for_transcription,
    transcribe_audio,
    audio_file_extension,
    synthesize_speech,
)
from _ai_service_common import (
    INTERVIEW_LENGTH_GUIDANCE,
    JOB_FIT_VERDICTS,
    JOB_FIT_VERDICT_SCORE,
    QUESTION_BANK_SIZE,
    VERDICT_CRITERIA,
    VERDICT_FORMAT,
    _ALLOWED_AUDIO_EXTENSIONS,
)
