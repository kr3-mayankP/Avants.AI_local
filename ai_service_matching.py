# ----------------------------------------------------------------
# CHANGE BLOCK: 2026-11-22
# NEW FILE - active implementation
# ----------------------------------------------------------------
"""AI service functions split out of ai_services.py."""

from _ai_service_common import *
import json

# Moved from ai_services.py: suggest_jobs_for_profile
def suggest_jobs_for_profile(profile_text, target_roles, jobs):
    """Rank a candidate's profile/resume against the platform's open job
    postings and return the best-fitting ones. `jobs` is a list of dicts with
    id/title/company/category/description. Returns a list of dicts (id, score,
    reason), best match first, capped to the jobs the model considers a real fit."""
    if not jobs:
        return []

    listings_block = "\n\n".join(
        f"[Job ID: {job['id']}] {job['title']} — {job['company']} ({job['category']})\n"
        f"{job['description'][:500]}"
        for job in jobs
    )
    target_roles_block = f"\nThe candidate also says they're interested in: {target_roles[:300]}\n" if target_roles else ""

    prompt = f"""
A candidate is looking for their next role. Here is their profile/resume:
{profile_text[:Config.MAX_TEXT_LENGTH]}
{target_roles_block}
Here are the open job postings on the platform:
{listings_block}

Identify which of these jobs are a genuinely good fit for this candidate. Only include jobs that are a
reasonable match — do not pad the list with poor fits just to fill space.

Respond with one block per recommended job, ranked best fit first, EXACTLY in this format (no asterisks,
no markdown bold, no extra commentary):

Job ID: <id>
Score: <number 0-100>
Reason: <1-2 sentences, specific to this candidate's actual background and this job's requirements>
"""
    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=900,
        temperature=0.3,
    )
    content = response.choices[0].message.content.strip()

    results = []
    for block in re.split(r"\n(?=Job ID:)", content):
        id_match = re.search(r"Job ID:\s*(\d+)", block)
        score_match = re.search(r"Score:\s*(\d{1,3})", block)
        reason_match = re.search(r"Reason:\s*(.+)", block, re.DOTALL)
        if not id_match:
            continue
        results.append({
            "job_id": int(id_match.group(1)),
            "score": int(score_match.group(1)) if score_match else 0,
            "reason": reason_match.group(1).strip() if reason_match else "",
        })
    return results

# Moved from ai_services.py: suggest_candidates_for_jobs
def suggest_candidates_for_jobs(jobs, candidates):
    """Reverse of suggest_jobs_for_profile: rank a company's open-to-work talent
    pool against its own open job postings and return the best-fitting
    candidates. `jobs` is a list of dicts with id/title/category/description.
    `candidates` is a list of dicts with id/headline/skills/target_roles/
    years_experience. Returns a list of dicts (candidate_id, score, reason),
    best match first, capped to candidates the model considers a real fit."""
    if not jobs or not candidates:
        return []

    jobs_block = "\n\n".join(
        f"- {job['title']} ({job['category']}): {job['description'][:400]}"
        for job in jobs
    )
    candidates_block = "\n\n".join(
        f"[Candidate ID: {c['id']}] {c.get('headline') or 'No headline given'}\n"
        f"Skills: {c.get('skills') or 'none listed'}\n"
        f"Target roles: {c.get('target_roles') or 'none listed'}\n"
        f"Experience: {c.get('years_experience') or 'unspecified'}"
        for c in candidates
    )

    prompt = f"""
A company has these open job postings:
{jobs_block}

Here is a pool of candidates who are currently open to work:
{candidates_block}

Identify which candidates are a genuinely good fit for at least one of these open roles. Only include
candidates who are a reasonable match - do not pad the list with poor fits just to fill space.

Respond with one block per recommended candidate, ranked best fit first, EXACTLY in this format (no
asterisks, no markdown bold, no extra commentary):

Candidate ID: <id>
Score: <number 0-100>
Reason: <1-2 sentences, specific to this candidate's actual background and which role they fit>
"""
    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=900,
        temperature=0.3,
    )
    content = response.choices[0].message.content.strip()

    results = []
    for block in re.split(r"\n(?=Candidate ID:)", content):
        id_match = re.search(r"Candidate ID:\s*(\d+)", block)
        score_match = re.search(r"Score:\s*(\d{1,3})", block)
        reason_match = re.search(r"Reason:\s*(.+)", block, re.DOTALL)
        if not id_match:
            continue
        results.append({
            "candidate_id": int(id_match.group(1)),
            "score": int(score_match.group(1)) if score_match else 0,
            "reason": reason_match.group(1).strip() if reason_match else "",
        })
    return results


# --------------------------------------------------------------------------------
# Recruiter dashboard assistant
# --------------------------------------------------------------------------------

def generate_employer_dashboard_answer(question, hiring_context):
    """Answer one recruiter question using the company's aggregate hiring data."""
    context = json.dumps(hiring_context, ensure_ascii=False)
    response = openrouter_client.chat.completions.create(
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a practical recruiting assistant inside Avants AI. Answer clearly and briefly. "
                    "Use dashboard context only for company-specific facts. If context does not contain an "
                    "answer, say so and suggest where the recruiter can find it. Never invent metrics or "
                    "candidate details. Do not make hiring decisions or infer protected characteristics."
                ),
            },
            {
                "role": "user",
                "content": f"Dashboard context:\n{context}\n\nRecruiter's question:\n{question[:1000]}",
            },
        ],
        max_tokens=500,
        temperature=0.3,
    )
    answer = response.choices[0].message.content
    if not answer or not answer.strip():
        raise RuntimeError("The dashboard assistant returned an empty response.")
    return answer.strip()


def generate_job_post_assistant(action, prompt="", current_job=None):
    """Generate or improve recruiter-entered job content.

    Returns a JSON object containing editable fields. The recruiter must
    review and explicitly submit it; this function never publishes a job.
    """
    action = (action or "").strip().lower()
    if action not in ("generate", "improve", "suggest_skills"):
        raise ValueError("Unsupported job assistant action.")

    job = current_job or {}
    context = json.dumps(job, ensure_ascii=False)
    action_instruction = {
        "generate": "Create a complete, inclusive, realistic job post from the recruiter prompt.",
        "improve": "Improve the supplied job-post fields. Preserve accurate facts, remove vague or discriminatory language, and make responsibilities and requirements specific.",
        "suggest_skills": "Suggest a concise set of required and preferred skills for the supplied role.",
    }[action]

    response = openrouter_client.chat.completions.create(
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert recruiting content assistant. Return only valid JSON, no markdown. "
                    "Do not invent employer benefits, compensation, locations, credentials, or hard requirements "
                    "that are not supported by the prompt or existing fields. Keep language inclusive and concise."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{action_instruction}\n\n"
                    f"Recruiter prompt: {prompt[:1500]}\n\n"
                    f"Existing editable job fields:\n{context[:12000]}\n\n"
                    "Return this exact JSON shape:\n"
                    "{"
                    "\"title\":\"...\",\"work_type\":\"Remote (Worldwide)|Remote (US Only)|Hybrid|On-site\","
                    "\"employment_type\":\"Full-time|Part-time|Contract|Internship\","
                    "\"category\":\"...\",\"experience_level\":\"...\","
                    "\"about\":\"...\",\"responsibilities\":\"...\",\"requirements\":\"...\","
                    "\"preferred\":\"...\",\"contract_terms\":\"...\","
                    "\"required_skills\":[\"...\"],\"preferred_skills\":[\"...\"],"
                    "\"benefits\":[\"...\"],\"interview_focus\":\"...\","
                    "\"salary_min\":0,\"salary_max\":0,"
                    "\"quality_score\":92"
                    "}"
                ),
            },
        ],
        max_tokens=1500,
        temperature=0.35,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content.strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise RuntimeError("The AI returned invalid job-post JSON.")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise RuntimeError("The AI returned an invalid job-post response.")
    data.setdefault("required_skills", [])
    data.setdefault("preferred_skills", [])
    data.setdefault("benefits", [])
    return data

# Moved from ai_services.py: find_similar_jobs
def find_similar_jobs(current_job, other_jobs):
    """Given a job dict (id, title, description) and a list of other open jobs,
    return the 3 most semantically similar ones. Similarity is based on role
    responsibilities and required skills, not category labels.

    Returns list of dicts: {job_id, similarity, reason}"""
    if not other_jobs:
        return []

    current_block = (
        f"Title: {current_job['title']}\n"
        f"Description: {current_job['description'][:800]}"
    )
    candidates_block = "\n\n".join(
        f"[Job ID: {j['id']}] {j['title']} — {j['company']}\n{j['description'][:500]}"
        for j in other_jobs
    )

    prompt = f"""You are a job similarity engine. Given a reference job and a list of other open roles, identify the 3 most similar jobs based on the actual role responsibilities, required skills, and seniority level — NOT by job category label.

Reference job:
{current_block}

Other open jobs:
{candidates_block}

Pick the 3 most similar jobs and respond EXACTLY in this format (no extra text, no markdown):

Job ID: <id>
Similarity: <number 0-100>
Reason: <one short sentence explaining the similarity>

Job ID: <id>
Similarity: <number 0-100>
Reason: <one short sentence>

Job ID: <id>
Similarity: <number 0-100>
Reason: <one short sentence>"""

    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.2,
    )
    content = response.choices[0].message.content.strip()

    results = []
    for block in re.split(r"\n(?=Job ID:)", content):
        id_match = re.search(r"Job ID:\s*(\d+)", block)
        sim_match = re.search(r"Similarity:\s*(\d{1,3})", block)
        reason_match = re.search(r"Reason:\s*(.+)", block, re.DOTALL)
        if not id_match:
            continue
        results.append({
            "job_id": int(id_match.group(1)),
            "similarity": int(sim_match.group(1)) if sim_match else 0,
            "reason": reason_match.group(1).strip() if reason_match else "",
        })
    return results[:3]

# Moved from ai_services.py: generate_rejection_feedback
def generate_rejection_feedback(job_title, company_name, match_score, match_explanation, interview_verdict, interview_transcript):
    """Draft a short, honest, encouraging rejection feedback note from employer to candidate.
    The employer will review and optionally edit before sending."""
    score_context = f"Their match score was {match_score}/100." if match_score is not None else ""
    verdict_context = f"The AI interview verdict was: {interview_verdict}." if interview_verdict else "They did not complete an AI interview."
    explanation_context = match_explanation[:600] if match_explanation else ""
    transcript_snippet = (interview_transcript or "")[:800]

    prompt = f"""You are writing a brief, honest rejection feedback note on behalf of a hiring company to a job candidate. The note should:
- Be 3-5 sentences maximum
- Be warm and encouraging in tone
- Give specific, actionable feedback (what gaps existed, what would strengthen future applications)
- NOT be generic (avoid "we had many strong candidates")
- NOT mention the AI interview or match scoring system by name
- Be written as if from the employer directly to the candidate

Context:
- Role: {job_title} at {company_name}
- {score_context}
- {verdict_context}
- Match analysis: {explanation_context}
- Interview highlights: {transcript_snippet}

Write only the feedback message text. No subject line, no greeting, no sign-off."""

    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=250,
        temperature=0.5,
    )
    return response.choices[0].message.content.strip()

# Moved from ai_services.py: analyze_job_description
def analyze_job_description(title, about, requirements, preferred, what_you_do, contract_terms, salary_provided, category):
    """Analyze a job description and return a quality score + specific improvement suggestions.
    Returns {score: int, issues: [{level: 'error'|'warning'|'tip', text: str}]}"""

    salary_note = "Salary range: NOT provided." if not salary_provided else "Salary range: provided."
    desc_block = "\n".join(filter(None, [
        f"Title: {title}",
        f"Category: {category}",
        salary_note,
        f"About the role:\n{about[:600]}" if about else "",
        f"Requirements:\n{requirements[:600]}" if requirements else "",
        f"Preferred:\n{preferred[:400]}" if preferred else "",
        f"What you'll do:\n{what_you_do[:400]}" if what_you_do else "",
        f"Contract terms:\n{contract_terms[:300]}" if contract_terms else "",
    ]))

    prompt = f"""You are an expert recruiter reviewing a job posting for quality and candidate appeal. Analyze the posting below and return:
1. An overall quality score from 0-100
2. A list of specific, actionable issues (errors, warnings, or tips)

Scoring guide:
- 85-100: Excellent — clear, complete, specific, competitive
- 70-84: Good — minor gaps
- 50-69: Fair — missing important elements
- Below 50: Needs work — major issues

Issue levels:
- error: Missing or critically wrong (e.g., no description at all, discriminatory language)
- warning: Important gap that reduces applications (e.g., no salary, vague requirements)
- tip: Improvement opportunity (e.g., requirements list too long, could be more specific)

Job posting to analyze:
{desc_block}

Respond EXACTLY in this format (no extra text):
Score: <number>
Issue: <level> | <specific actionable feedback, 1 sentence>
Issue: <level> | <specific actionable feedback, 1 sentence>
...

Include 3-7 issues total. Be specific to this actual posting — do not give generic advice."""

    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.2,
    )
    content = response.choices[0].message.content.strip()

    score = 70
    issues = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("Score:"):
            try:
                score = int(re.search(r"\d+", line).group())
            except Exception:
                pass
        elif line.startswith("Issue:"):
            rest = line[6:].strip()
            if "|" in rest:
                level, text = rest.split("|", 1)
                level = level.strip().lower()
                if level not in ("error", "warning", "tip"):
                    level = "tip"
                issues.append({"level": level, "text": text.strip()})

    return {"score": min(100, max(0, score)), "issues": issues}

