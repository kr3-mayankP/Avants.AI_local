"""AI service functions split out of ai_services.py."""

from _ai_service_common import *

# Moved from ai_services.py: extract_pdf_text
def extract_pdf_text(file_stream):
    reader = PdfReader(file_stream)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

# Moved from ai_services.py: extract_docx_text
def extract_docx_text(file_stream):
    try:
        file_stream.seek(0)
        document = Document(file_stream)
        text = "\n".join(para.text for para in document.paragraphs if para.text.strip())
        return text if text.strip() else "No text found in DOCX file."
    except Exception as e:
        logger.error(f"Error reading DOCX: {e}", exc_info=True)
        return f"Error reading DOCX: {str(e)}"

# Moved from ai_services.py: extract_text_from_file
def extract_text_from_file(filename: str, resume_bytes: bytes):
    file_stream = io.BytesIO(resume_bytes)
    if filename.endswith('.pdf'):
        return extract_pdf_text(file_stream)
    elif filename.endswith('.docx'):
        return extract_docx_text(file_stream)
    elif filename.endswith('.txt'):
        return file_stream.getvalue().decode('utf-8')
    return ""

# Moved from ai_services.py: compare_resume_to_job
def compare_resume_to_job(job_description, resume):
    prompt = f"""
Given the following job description and resume, rate how well the resume matches the job description.

Job Description:
{job_description}

Resume:
{resume}

Respond EXACTLY in this format (no asterisks, no markdown bold):

Score: <number 0-100> (<Poor / Fair / Good / Excellent>)

Explanation:

What the resume MATCHES (prefix each bullet with +):
+ <specific match>
+ <specific match>

What the resume is MISSING or does not match (prefix each bullet with -):
- <specific gap>
- <specific gap>

Education:
+ or - <education match/gap>

Skills / Technical:
+ or - <skill match or gap>

Experience / Internships:
+ or - <experience match or gap>

Project Links (list ALL links found in the resume, no duplicates):
<link>

Rules:
- Use + at the start of every line that is a STRENGTH or MATCH
- Use - at the start of every line that is a GAP or MISSING requirement
- Remove all asterisks
- Be specific — mention exact skills, tools, and requirements from the job description
"""
    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# Moved from ai_services.py: generate_summary
def generate_summary(text):
    """Generate AI resume summary with retry logic."""
    try:
        #response = client.chat.completions.create(
        response = openrouter_client.chat.completions.create(
            #model="gpt-3.5-turbo",
            model=Config.OPENROUTER_CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You're a professional resume analyst. Create a 9-11 sentence summary "
                        "focusing on skills, experience, education, and other notable mentions. "
                        "Highlight KEY details and technical experience specifically. Be concise."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Summarize this resume:\n\n{text[:Config.MAX_TEXT_LENGTH]}",
                },
            ],
            max_tokens=600,
            timeout=Config.OPENAI_TIMEOUT,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise

# Moved from ai_services.py: generate_basic_analysis
def generate_basic_analysis(text):
    """Fallback analysis when AI is unavailable."""
    try:
        words = [w for w in text.split() if len(w) > 3]
        word_counts = Counter(words)
        top_terms = [w[0] for w in word_counts.most_common(5)]
        return {
            "analysis": "Basic Text Analysis",
            "word_count": len(words),
            "top_terms": top_terms,
            "estimated_experience": "Junior" if len(words) < 300 else "Senior",
        }
    except Exception as e:
        logger.error(f"Basic analysis failed: {str(e)}")
        return {"error": "Could not generate basic analysis"}

# Moved from ai_services.py: generate_resume_from_profile
def generate_resume_from_profile(linkedin_url, profile_text):
    """Turn pasted LinkedIn profile content into a structured resume — for
    candidates who have a LinkedIn presence but no resume on hand."""
    prompt = f"""
A candidate has no resume but has pasted their LinkedIn profile content below.
Turn this into a clean, professional resume.

LinkedIn URL: {linkedin_url or "Not provided"}

Pasted profile content (About / Experience / Education / Skills, in whatever
order the candidate pasted it):
{profile_text[:Config.MAX_TEXT_LENGTH]}

Respond EXACTLY in this format (no asterisks, no markdown bold):

[Name / Title]
<best-guess professional title based on experience>

[Professional Summary]
<3-4 sentence summary>

[Experience]
<Company — Role — Dates>
<2-3 bullet points per role, prefixed with ->

[Education]
<Degree, Institution, Dates>

[Skills]
<comma-separated list>

Rules:
- Only use information present in the pasted content — never invent companies, dates, or credentials.
- If a section has no information, write "Not provided" under that heading instead of guessing.
"""
    #response = client.chat.completions.create(
    response = openrouter_client.chat.completions.create(
        #model="gpt-4o",
        model=Config.OPENROUTER_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=900,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()

