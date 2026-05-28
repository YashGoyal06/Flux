import re
import os
import requests
import pdfplumber
import docx
import logging

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        logger.error(f"Error reading PDF {pdf_path}: {e}")
    return text

def extract_text_from_docx(docx_path):
    text = ""
    try:
        doc = docx.Document(docx_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        logger.error(f"Error reading DOCX {docx_path}: {e}")
    return text

def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif ext in ('.docx', '.doc'):
        return extract_text_from_docx(file_path)
    elif ext in ('.txt', '.rtf'):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading text file {file_path}: {e}")
    return ""

def parse_resume_heuristics(text):
    """
    Regex and heuristic fallback parser to run locally without external APIs.
    """
    parsed = {
        "name": "Unknown",
        "email": "",
        "phone": "",
        "skills": [],
        "experience_years": 0,
        "education": [],
        "work_history": []
    }

    if not text:
        return parsed

    lines = [l.strip() for l in text.split('\n')]
    non_empty_lines = [l for l in lines if l]

    # 1. Parse Email
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    if email_match:
        parsed["email"] = email_match.group(0)

    # 2. Parse Phone
    phone_match = re.search(r'(?:\+?\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}', text)
    if phone_match:
        parsed["phone"] = phone_match.group(0)

    # 3. Parse Name (usually on the first line or first few lines)
    if non_empty_lines:
        for line in non_empty_lines[:4]:
            # Avoid lines with contact info or headers
            if (
                '@' not in line 
                and 'resume' not in line.lower() 
                and 'curriculum' not in line.lower()
                and 'cv' not in line.lower()
                and not re.search(r'\d{3,}', line) # no phone numbers/dates
                and len(line.split()) <= 4
                and not line.endswith(':')
            ):
                parsed["name"] = line
                break

    # 4. Parse Skills (keyword check against a rich predefined list)
    skills_taxonomy = {
        "python": "Python", "django": "Django", "flask": "Flask", "fastapi": "FastAPI",
        "javascript": "JavaScript", "typescript": "TypeScript", "react": "React", 
        "vue": "Vue", "angular": "Angular", "node": "Node.js", "express": "Express",
        "html": "HTML", "css": "CSS", "tailwind": "Tailwind CSS", "bootstrap": "Bootstrap",
        "postgres": "PostgreSQL", "postgresql": "PostgreSQL", "sql": "SQL", "mysql": "MySQL", 
        "mongodb": "MongoDB", "redis": "Redis", "sqlite": "SQLite", "supabase": "Supabase",
        "aws": "AWS", "docker": "Docker", "kubernetes": "Kubernetes", "git": "Git", 
        "github": "GitHub", "java": "Java", "c++": "C++", "c#": "C#", "rust": "Rust", 
        "go": "Go", "golang": "Go", "ruby": "Ruby", "php": "PHP", "figma": "Figma", 
        "ui/ux": "UI/UX", "machine learning": "Machine Learning", "deep learning": "Deep Learning",
        "nlp": "NLP", "pytorch": "PyTorch", "tensorflow": "TensorFlow", "pandas": "Pandas", 
        "numpy": "NumPy", "scikit-learn": "Scikit-Learn", "graphql": "GraphQL", "rest api": "REST API"
    }
    
    text_lower = text.lower()
    found_skills = []
    for skill_key, skill_name in skills_taxonomy.items():
        pattern = r'\b' + re.escape(skill_key) + r'\b'
        if re.search(pattern, text_lower):
            if skill_name not in found_skills:
                found_skills.append(skill_name)
    parsed["skills"] = found_skills

    # 5. Experience estimate
    # Look for "X years of experience" or similar
    exp_patterns = [
        r'(\d+)\+?\s*(?:years?|yrs?)(?:\s+(?:of\s+)?experience)?\b',
        r'experience[:\s]+(\d+)\+?\s*(?:years?|yrs?)'
    ]
    exp_years = 0
    for pattern in exp_patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            exp_years = max(exp_years, max([int(x) for x in matches]))
    
    parsed["experience_years"] = exp_years

    # 6. Parse Education
    degree_keywords = ["b.s.", "m.s.", "b.tech", "m.tech", "bachelor", "master", "ph.d", "phd", "b.sc", "m.sc", "degree", "diploma", "high school"]
    inst_keywords = ["university", "college", "institute", "school", "academy", "polytechnic"]
    
    for line in non_empty_lines:
        line_lower = line.lower()
        has_degree = any(dk in line_lower for dk in degree_keywords)
        has_inst = any(ik in line_lower for ik in inst_keywords)
        
        if has_degree or has_inst:
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', line)
            year = int(year_match.group(0)) if year_match else None
            
            degree = "Degree"
            for dk in degree_keywords:
                if dk in line_lower:
                    idx = line_lower.find(dk)
                    degree_part = line[idx:idx+len(dk)]
                    if dk == "b.s.": degree = "B.S. Computer Science" if "computer" in line_lower else "B.S."
                    elif dk == "b.tech": degree = "B.Tech Computer Science" if "computer" in line_lower else "B.Tech"
                    elif dk == "m.s.": degree = "M.S. Computer Science" if "computer" in line_lower else "M.S."
                    elif dk == "bachelor": degree = "Bachelor's Degree"
                    elif dk == "master": degree = "Master's Degree"
                    else: degree = degree_part.upper()
                    break
            
            inst = "University"
            for ik in inst_keywords:
                if ik in line_lower:
                    parts = re.split(r'[,–\-—]', line)
                    for p in parts:
                        if ik in p.lower():
                            inst = p.strip()
                            break
                    break
            
            parsed["education"].append({
                "degree": degree,
                "institution": inst,
                "year": year or 2020
            })
            
    unique_edu = []
    edu_keys = set()
    for edu in parsed["education"]:
        key = (edu["degree"].lower(), edu["institution"].lower())
        if key not in edu_keys:
            edu_keys.add(key)
            unique_edu.append(edu)
    parsed["education"] = unique_edu

    # 7. Parse Work History
    role_keywords = ["engineer", "developer", "designer", "manager", "analyst", "consultant", "architect", "lead", "specialist", "intern", "programmer"]
    
    work_history = []
    
    for i, line in enumerate(non_empty_lines):
        line_lower = line.lower()
        has_role = any(rk in line_lower for rk in role_keywords)
        if not has_role:
            continue
            
        if any(k in line_lower for k in ["summary", "objective", "profile", "skills:", "education", "university", "college", "school"]):
            continue
            
        if any(k in line_lower for k in ["i am", "passionate", "seeking", "experienced", "with building", "specializing in"]):
            continue
            
        if len(line) > 90:
            continue

        cleaned_line = line.lstrip('-*• \t')
        
        date_match = re.search(r'\(?\b(19\d{2}|20\d{2})\s*[-–—]\s*(present|\b19\d{2}\b|\b20\d{2}\b)\)?\b', cleaned_line, re.IGNORECASE)
        duration = "2 years"
        if date_match:
            duration = date_match.group(0).strip('() ')
            cleaned_line = cleaned_line.replace(date_match.group(0), "").strip()
        
        cleaned_line = re.sub(r'\(\s*\)', '', cleaned_line).strip("() ")
        
        role = "Software Engineer"
        company = "Company"
        
        if " at " in cleaned_line:
            parts = cleaned_line.split(" at ")
            role = parts[0].strip()
            company = parts[1].strip()
        elif " @ " in cleaned_line:
            parts = cleaned_line.split(" @ ")
            role = parts[0].strip()
            company = parts[1].strip()
        elif "@" in cleaned_line:
            parts = cleaned_line.split("@")
            role = parts[0].strip()
            company = parts[1].strip()
        elif " - " in cleaned_line:
            parts = cleaned_line.split(" - ")
            role = parts[0].strip()
            company = parts[1].strip()
        elif " – " in cleaned_line:
            parts = cleaned_line.split(" – ")
            role = parts[0].strip()
            company = parts[1].strip()
        elif "," in cleaned_line:
            parts = cleaned_line.split(",")
            role = parts[0].strip()
            company = parts[1].strip()
        else:
            for rk in role_keywords:
                if rk in line_lower:
                    role = line.strip()
                    break
        
        description_lines = []
        for j in range(i+1, min(i+6, len(non_empty_lines))):
            next_line = non_empty_lines[j]
            next_line_lower = next_line.lower()
            if any(rk in next_line_lower for rk in role_keywords) and re.search(r'\b(19\d{2}|20\d{2})\b', next_line_lower):
                break
            if any(h in next_line_lower for h in ["education", "skills:", "summary", "objective"]):
                break
            if next_line.startswith('-') or next_line.startswith('*') or next_line.startswith('•') or len(next_line) > 20:
                description_lines.append(next_line.lstrip('-*• ').strip())
        
        description = " ".join(description_lines) if description_lines else "Responsible for software development and collaboration."
        
        work_history.append({
            "company": company,
            "role": role,
            "duration": duration,
            "description": description
        })
        
    parsed["work_history"] = work_history
    
    if parsed["experience_years"] == 0 and work_history:
        total_yrs = 0
        for job in work_history:
            dur = job["duration"].lower()
            years_match = re.findall(r'\b(20\d{2}|19\d{2})\b', dur)
            if len(years_match) == 2:
                total_yrs += abs(int(years_match[1]) - int(years_match[0]))
            elif len(years_match) == 1 and "present" in dur:
                from datetime import datetime
                total_yrs += abs(datetime.now().year - int(years_match[0]))
        if total_yrs > 0:
            parsed["experience_years"] = total_yrs

    return parsed

def parse_resume_llm(text):
    """
    If a Gemini API or Claude API is available, use it for structured JSON parsing.
    Otherwise returns None.
    """
    # Check if Gemini/Claude API keys are present in environment
    # Let's write a standard fallback call or template.
    # In this plan, we provide a placeholder call to show how it's done.
    # If the user has a Gemini API key configured:
    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        return None

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
        prompt = (
            "You are an expert resume parsing engine. Parse the following resume text into a single JSON object. "
            "Return EXACTLY this JSON format and nothing else. Do not wrap in markdown tags:\n"
            "{\n"
            '  "name": "Candidate Name",\n'
            '  "email": "email@example.com",\n'
            '  "phone": "+1234567890",\n'
            '  "skills": ["JavaScript", "Python", ...],\n'
            '  "experience_years": 5,\n'
            '  "education": [{"degree": "B.S. Computer Science", "institution": "University Name", "year": 2020}],\n'
            '  "work_history": [{"company": "Google", "role": "Software Engineer", "duration": "2 years", "description": "built systems"}]\n'
            "}\n\n"
            f"Resume Text:\n{text}"
        )
        
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            content = res_json['candidates'][0]['content']['parts'][0]['text']
            # Clean JSON markdown fences
            content = content.replace("```json", "").replace("```", "").strip()
            import json
            return json.loads(content)
    except Exception as e:
        logger.error(f"Error parsing resume via Gemini: {e}")
    return None

def parse_resume_hf(text):
    """
    Use the Hugging Face Inference API to parse the resume text into structured JSON.
    """
    api_key = os.environ.get('HUGGINGFACE_API_KEY') or os.environ.get('HF_API_KEY')
    if not api_key:
        return None

    # Default to Llama-3-8B-Instruct if no model is specified
    model_id = os.environ.get('HF_MODEL_ID', 'meta-llama/Meta-Llama-3-8B-Instruct')
    
    endpoints = [
        {
            "url": f"https://api-inference.huggingface.co/models/{model_id}",
            "type": "standard"
        },
        {
            "url": f"https://router.huggingface.co/models/{model_id}",
            "type": "standard"
        },
        {
            "url": "https://router.huggingface.co/v1/chat/completions",
            "type": "chat"
        },
        {
            "url": "https://api-inference.huggingface.co/v1/chat/completions",
            "type": "chat"
        }
    ]
    
    headers = {"Authorization": f"Bearer {api_key}"}
    
    prompt_system = "You are an expert resume parsing engine. Parse the provided resume text into a single JSON object. Return ONLY valid JSON. Do not include markdown formatting, markdown code blocks, or any explanation text."
    prompt_user = (
        "Format the parsed data exactly as follows:\n"
        "{\n"
        '  "name": "Candidate Name",\n'
        '  "email": "email@example.com",\n'
        '  "phone": "+1234567890",\n'
        '  "skills": ["Skill1", "Skill2"],\n'
        '  "experience_years": 5,\n'
        '  "education": [{"degree": "Degree Name", "institution": "Institution Name", "year": 2020}],\n'
        '  "work_history": [{"company": "Company Name", "role": "Role Name", "duration": "Duration", "description": "Description"}]\n'
        "}\n\n"
        f"Resume Text:\n{text}"
    )

    prompt_legacy = (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        f"{prompt_system}<|eot_id|>"
        "<|start_header_id|>user<|end_header_id|>\n\n"
        f"{prompt_user}<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n\n"
    )
    
    for endpoint in endpoints:
        url = endpoint["url"]
        etype = endpoint["type"]
        
        try:
            logger.info(f"Attempting resume parsing via Hugging Face endpoint: {url} ({etype})")
            if etype == "standard":
                response = requests.post(url, json={
                    "inputs": prompt_legacy,
                    "parameters": {
                        "max_new_tokens": 1000,
                        "return_full_text": False
                    }
                }, headers=headers, timeout=8)
            else:
                response = requests.post(url, json={
                    "model": model_id,
                    "messages": [
                        {"role": "system", "content": prompt_system},
                        {"role": "user", "content": prompt_user}
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.1
                }, headers=headers, timeout=8)
                
            if response.status_code == 200:
                res_json = response.json()
                if etype == "standard":
                    if isinstance(res_json, list) and len(res_json) > 0:
                        content = res_json[0].get('generated_text', '').strip()
                    elif isinstance(res_json, dict):
                        content = res_json.get('generated_text', '').strip()
                    else:
                        continue
                else:
                    content = res_json['choices'][0]['message']['content'].strip()
                
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
                    
                import json
                parsed_res = json.loads(content)
                logger.info(f"Successfully parsed resume via HF endpoint: {url}")
                return parsed_res
            else:
                logger.warning(f"Hugging Face endpoint {url} returned status {response.status_code}: {response.text}")
        except Exception as e:
            logger.warning(f"Failed to parse via Hugging Face endpoint {url}: {e}")
            
    logger.error("All Hugging Face API endpoints failed to parse the resume.")
    return None

def parse_resume(file_path):
    raw_text = extract_text(file_path)
    if not raw_text:
        return {
            "name": "Unknown",
            "email": "",
            "phone": "",
            "skills": [],
            "experience_years": 0,
            "education": [],
            "work_history": [],
            "raw_text": ""
        }, 0.2

    # 1. Try Gemini LLM first
    parsed_json = parse_resume_llm(raw_text)
    if parsed_json:
        parsed_json["raw_text"] = raw_text
        return parsed_json, 0.95

    # 2. Try Hugging Face Inference API next
    parsed_json = parse_resume_hf(raw_text)
    if parsed_json:
        parsed_json["raw_text"] = raw_text
        return parsed_json, 0.95

    # 3. Fallback to local regex/heuristics
    parsed_json = parse_resume_heuristics(raw_text)
    parsed_json["raw_text"] = raw_text
    return parsed_json, 0.6

def calculate_ats_score(parsed_resume, job):
    """
    Calculate an ATS match score (between 0.0 and 1.0) based on:
    1. Skill overlap (parsed skills vs job requirements/description).
    2. Experience match (parsed experience vs experience requested in job description).
    3. Keyword overlap between job description/title and resume raw text.
    """
    if not parsed_resume:
        return 0.5

    # 1. Skill overlap
    parsed_skills = [s.lower().strip() for s in parsed_resume.get('skills', [])]
    job_reqs_text = " ".join(job.requirements).lower()
    job_desc_text = job.description.lower()
    job_title_text = job.title.lower()
    
    # Identify skills mentioned in requirements or description
    known_skills = [
        "python", "django", "javascript", "typescript", "react", "vue", "angular", "node", "express",
        "html", "css", "tailwind", "bootstrap", "postgres", "sql", "mysql", "mongodb", "redis",
        "aws", "docker", "kubernetes", "git", "java", "c++", "c", "rust", "go", "ruby", "php",
        "figma", "sketch", "photoshop", "illustrator", "wireframing", "prototyping", "ui", "ux",
        "tableau", "powerbi", "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "machine learning",
        "statistics", "spark", "hadoop", "excel"
    ]
    
    job_skills = []
    for skill in known_skills:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, job_reqs_text) or re.search(pattern, job_desc_text) or re.search(pattern, job_title_text):
            job_skills.append(skill)
            
    skill_score = 1.0
    if job_skills:
        matched_skills = [s for s in parsed_skills if s in job_skills]
        skill_score = len(matched_skills) / len(job_skills)
        skill_score = min(max(skill_score, 0.2), 1.0)

    # 2. Experience match
    candidate_exp = parsed_resume.get('experience_years', 0)
    required_years = 0
    all_text = f"{job_reqs_text} {job_desc_text}"
    exp_matches = re.findall(r'(\d+)\+?\s*(?:years?|yrs?)\b', all_text)
    if exp_matches:
        required_years = max([int(x) for x in exp_matches])
        
    exp_score = 1.0
    if required_years > 0:
        if candidate_exp >= required_years:
            exp_score = 1.0
        else:
            exp_score = candidate_exp / required_years
            exp_score = min(max(exp_score, 0.3), 1.0)

    # 3. Keyword / semantic overlap
    raw_text = parsed_resume.get('raw_text', '').lower()
    keyword_score = 0.5
    if raw_text:
        job_words = set(re.findall(r'\b[a-z]{3,15}\b', f"{job_title_text} {job_desc_text} {job_reqs_text}"))
        resume_words = set(re.findall(r'\b[a-z]{3,15}\b', raw_text))
        
        stopwords = {
            'and', 'the', 'for', 'with', 'you', 'will', 'our', 'are', 'that', 'this', 'from', 'have', 'has', 'been', 'their', 'they', 
            'our', 'your', 'about', 'some', 'any', 'but', 'not', 'can', 'should', 'would', 'could', 'their', 'them', 'these', 'those'
        }
        job_words -= stopwords
        resume_words -= stopwords
        
        if job_words:
            overlap = len(job_words.intersection(resume_words)) / len(job_words)
            keyword_score = min(max(overlap, 0.1), 1.0)

    # Weighted score: 50% Skills, 25% Experience, 25% Keyword overlap
    final_score = (skill_score * 0.50) + (exp_score * 0.25) + (keyword_score * 0.25)
    
    # Scale to typical ATS range (e.g. 50% to 98%)
    scaled_score = 0.5 + (final_score * 0.48)
    return round(min(max(scaled_score, 0.1), 0.99), 2)
