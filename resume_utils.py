"""
Resume Utilities Module
Contains all core functions for resume analysis, skill extraction, and report generation.
"""

import os
import sqlite3
import re
from datetime import datetime
from typing import Dict, List, Tuple
import PyPDF2
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch


# Skill categories with comprehensive keyword lists
SKILL_CATEGORIES = {
    "Programming Languages": [
        "python", "java", "javascript", "c++", "c#", "ruby", "go", "rust", "swift",
        "kotlin", "scala", "php", "typescript", "r", "matlab", "perl", "shell",
        "bash", "powershell", "sql", "html", "css", "assembly", "haskell", "elixir"
    ],
    "Web Development": [
        "react", "angular", "vue", "node.js", "express", "django", "flask", "spring",
        "rails", "laravel", "asp.net", "next.js", "nuxt.js", "gatsby", "webpack",
        "rest", "graphql", "api", "json", "xml", "ajax", "websocket", "http",
        "https", "nginx", "apache", "docker", "kubernetes", "aws", "azure", "gcp"
    ],
    "Databases": [
        "mysql", "postgresql", "mongodb", "sqlite", "oracle", "sql server", "redis",
        "elasticsearch", "cassandra", "dynamodb", "firebase", "supabase", "prisma",
        "sequelize", "typeorm", "hibernate", "jdbc", "odbc", "nosql", "rdbms"
    ],
    "AI/ML": [
        "machine learning", "deep learning", "tensorflow", "pytorch", "keras", "scikit-learn",
        "pandas", "numpy", "matplotlib", "nlp", "natural language processing", "computer vision",
        "opencv", "data science", "data analysis", "statistics", "ai", "artificial intelligence",
        "neural networks", "transformers", "bert", "gpt", "llm", "reinforcement learning",
        "jupyter", "spark", "hadoop", "tableau", "power bi"
    ],
    "Tools & Technologies": [
        "git", "github", "gitlab", "bitbucket", "jenkins", "ci/cd", "devops", "linux",
        "ubuntu", "debian", "centos", "windows", "macos", "agile", "scrum", "jira",
        "confluence", "slack", "trello", "vscode", "intellij", "eclipse", "vim", "emacs",
        "postman", "swagger", "figma", "sketch", "jira", "selenium", "cypress", "jest",
        "mocha", "pytest", "unittest", "maven", "gradle", "npm", "yarn", "pip", "conda"
    ]
}

# Essential resume sections for ATS scoring
ESSENTIAL_SECTIONS = [
    "experience", "education", "skills", "summary", "objective", "projects",
    "certifications", "achievements", "contact", "about"
]

# Keywords that indicate strong resume content
STRONG_KEYWORDS = [
    "developed", "implemented", "designed", "created", "managed", "led", "achieved",
    "improved", "optimized", "increased", "decreased", "reduced", "built", "launched",
    "deployed", "maintained", "coordinated", "collaborated", "analyzed", "developing",
    "implementing", "designing", "creating", "managing", "leading", "achieving",
    "improving", "optimizing", "increasing", "decreasing", "reducing", "building",
    "launching", "deploying", "maintaining", "coordinating", "collaborating", "analyzing"
]

# Metrics and quantifiers that strengthen resumes
METRIC_KEYWORDS = [
    "%", "percent", "dollar", "$", "million", "billion", "thousand", "increased by",
    "decreased by", "reduced by", "improved by", "growth", "revenue", "cost", "savings",
    "time", "hours", "days", "months", "years", "users", "customers", "clients"
]


def init_db(database_path: str) -> None:
    """
    Initialize the SQLite database with required tables.
    Creates users, resumes, and analyses tables if they don't exist.
    """
    # os.makedirs(os.path.dirname(database_path), exist_ok=True)
    
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    # Resumes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    # Analyses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            resume_id INTEGER NOT NULL,
            analysis_data TEXT NOT NULL,
            job_description TEXT,
            ats_score INTEGER NOT NULL,
            match_percent INTEGER DEFAULT 0,
            skills_found TEXT,
            missing_keywords TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (resume_id) REFERENCES resumes (id)
        )
    """)
    
    conn.commit()
    conn.close()


def get_db_connection(database_path: str) -> sqlite3.Connection:
    """
    Get a database connection with row factory enabled for dict-like access.
    """
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    return conn


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF file using PyPDF2.
    Returns the extracted text as a string.
    """
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""
    return text


def analyze_resume_text(resume_text: str) -> Dict:
    """
    Analyze resume text and generate ATS score with detailed feedback.
    Returns a dictionary with analysis results.
    """
    text_lower = resume_text.lower()
    words = text_lower.split()
    word_count = len(words)
    
    # Initialize analysis components
    structure_score = 0
    keyword_score = 0
    format_score = 0
    content_score = 0
    
    feedback = {
        "strengths": [],
        "weaknesses": [],
        "recommendations": []
    }
    
    # 1. Structure Analysis - Check for essential sections
    sections_found = []
    for section in ESSENTIAL_SECTIONS:
        if section in text_lower:
            sections_found.append(section)
    
    section_coverage = len(sections_found) / len(ESSENTIAL_SECTIONS)
    structure_score = int(section_coverage * 30)
    
    if len(sections_found) >= 6:
        feedback["strengths"].append("Excellent resume structure with comprehensive sections")
    elif len(sections_found) >= 4:
        feedback["strengths"].append("Good resume structure with key sections present")
    else:
        feedback["weaknesses"].append("Resume lacks essential sections")
        feedback["recommendations"].append("Add missing sections: Education, Experience, Skills")
    
    # 2. Keyword Analysis - Check for strong action verbs
    strong_keyword_count = sum(1 for keyword in STRONG_KEYWORDS if keyword in text_lower)
    keyword_density = strong_keyword_count / max(len(words), 1) * 100
    keyword_score = min(int(keyword_density * 50), 30)
    
    if strong_keyword_count >= 10:
        feedback["strengths"].append(f"Strong use of action verbs ({strong_keyword_count} found)")
    elif strong_keyword_count >= 5:
        feedback["strengths"].append("Good use of action verbs")
    else:
        feedback["weaknesses"].append("Limited use of strong action verbs")
        feedback["recommendations"].append("Incorporate more action verbs: developed, implemented, achieved")
    
    # 3. Format Analysis - Check for metrics and quantifiers
    metric_count = sum(1 for metric in METRIC_KEYWORDS if metric in text_lower)
    format_score = min(int(metric_count * 5), 20)
    
    if metric_count >= 3:
        feedback["strengths"].append("Good use of quantifiable metrics")
    else:
        feedback["weaknesses"].append("Resume lacks quantifiable achievements")
        feedback["recommendations"].append("Add metrics to quantify achievements (e.g., 'increased revenue by 25%')")
    
    # 4. Content Analysis - Word count and depth
    if word_count >= 400:
        content_score = 20
        feedback["strengths"].append("Comprehensive resume with good content depth")
    elif word_count >= 250:
        content_score = 15
        feedback["strengths"].append("Adequate content length")
    else:
        content_score = 10
        feedback["weaknesses"].append("Resume content is too brief")
        feedback["recommendations"].append("Expand content to provide more detail about experience")
    
    # Calculate total ATS score
    ats_score = structure_score + keyword_score + format_score + content_score
    ats_score = min(ats_score, 100)
    
    return {
        "ats_score": ats_score,
        "structure_score": structure_score,
        "keyword_score": keyword_score,
        "format_score": format_score,
        "content_score": content_score,
        "sections_found": sections_found,
        "word_count": word_count,
        "strong_keywords_count": strong_keyword_count,
        "metrics_count": metric_count,
        "feedback": feedback
    }


def extract_skills(resume_text: str) -> Dict:
    """
    Extract and categorize skills from resume text.
    Returns a dictionary with categorized skills and total count.
    """
    text_lower = resume_text.lower()
    skills_found = {category: [] for category in SKILL_CATEGORIES}
    
    for category, keywords in SKILL_CATEGORIES.items():
        for keyword in keywords:
            if keyword in text_lower:
                skills_found[category].append(keyword)
    
    # Flatten all skills into a single list
    all_skills = []
    for category_skills in skills_found.values():
        all_skills.extend(category_skills)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_skills = []
    for skill in all_skills:
        if skill not in seen:
            seen.add(skill)
            unique_skills.append(skill)
    
    return {
        "skills_found": unique_skills,
        "skills_by_category": {k: v for k, v in skills_found.items() if v},
        "total_skills": len(unique_skills)
    }


def match_job_description(resume_text: str, job_description: str) -> Dict:
    """
    Match resume against job description and calculate compatibility.
    Returns match percentage and missing keywords.
    """
    resume_lower = resume_text.lower()
    job_lower = job_description.lower()
    
    # Extract keywords from job description (simple approach)
    job_words = re.findall(r'\b[a-zA-Z]{3,}\b', job_lower)
    job_keywords = list(set([word for word in job_words if len(word) > 3]))
    
    # Filter out common words
    common_words = {
        'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had',
        'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'will', 'with',
        'this', 'that', 'from', 'they', 'would', 'there', 'their', 'what', 'about',
        'which', 'when', 'make', 'like', 'into', 'year', 'your', 'just', 'over',
        'also', 'such', 'because', 'these', 'first', 'being', 'through', 'work',
        'team', 'looking', 'seeking', 'ability', 'experience', 'skills', 'knowledge'
    }
    
    job_keywords = [kw for kw in job_keywords if kw not in common_words]
    
    # Find matching keywords
    matched_keywords = []
    missing_keywords = []
    
    for keyword in job_keywords:
        if keyword in resume_lower:
            matched_keywords.append(keyword)
        else:
            missing_keywords.append(keyword)
    
    # Calculate match percentage
    if len(job_keywords) > 0:
        match_percent = int((len(matched_keywords) / len(job_keywords)) * 100)
    else:
        match_percent = 0
    
    # Generate feedback
    feedback = {
        "matched_keywords": matched_keywords[:20],  # Limit to top 20
        "missing_keywords": missing_keywords[:20],  # Limit to top 20
        "match_percent": match_percent,
        "total_keywords": len(job_keywords),
        "matched_count": len(matched_keywords)
    }
    
    if match_percent >= 70:
        feedback["recommendation"] = "Excellent match! Your resume aligns well with this job description."
    elif match_percent >= 50:
        feedback["recommendation"] = "Good match. Consider adding some missing keywords to improve alignment."
    elif match_percent >= 30:
        feedback["recommendation"] = "Moderate match. Focus on incorporating missing keywords from the job description."
    else:
        feedback["recommendation"] = "Low match. Tailor your resume to include more keywords from the job description."
    
    return feedback


def generate_report_pdf(
    report_path: str,
    user_name: str,
    resume_filename: str,
    created_at: str,
    analysis: Dict,
    job_description: str
) -> None:
    """
    Generate a professional PDF report with analysis results.
    """
    doc = SimpleDocTemplate(report_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=30
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#34495E'),
        spaceAfter=12
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#555555'),
        spaceAfter=10
    )
    
    # Title
    story.append(Paragraph("Smart Resume Analyzer - Analysis Report", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Report metadata
    metadata_data = [
        ["User Name:", user_name],
        ["Resume File:", resume_filename],
        ["Analysis Date:", created_at[:19] if created_at else "N/A"]
    ]
    metadata_table = Table(metadata_data, colWidths=[1.5*inch, 4*inch])
    metadata_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ECF0F1')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    story.append(metadata_table)
    story.append(Spacer(1, 0.3*inch))
    
    # ATS Score Section
    story.append(Paragraph("ATS Score Analysis", heading_style))
    ats_score = analysis.get('ats_score', 0)
    score_color = colors.green if ats_score >= 70 else colors.orange if ats_score >= 50 else colors.red
    
    score_data = [
        ["Overall ATS Score:", f"{ats_score}/100"],
        ["Structure Score:", f"{analysis.get('structure_score', 0)}/30"],
        ["Keyword Score:", f"{analysis.get('keyword_score', 0)}/30"],
        ["Format Score:", f"{analysis.get('format_score', 0)}/20"],
        ["Content Score:", f"{analysis.get('content_score', 0)}/20"],
        ["Word Count:", str(analysis.get('word_count', 0))],
        ["Sections Found:", ", ".join(analysis.get('sections_found', []))]
    ]
    score_table = Table(score_data, colWidths=[1.5*inch, 4*inch])
    score_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ECF0F1')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    story.append(score_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Skills Section
    story.append(Paragraph("Skills Analysis", heading_style))
    skills_found = analysis.get('skills_found', [])
    skills_by_category = analysis.get('skills_by_category', {})
    
    if skills_found:
        skills_text = f"<b>Total Skills Found:</b> {len(skills_found)}<br/>"
        for category, skills in skills_by_category.items():
            skills_text += f"<b>{category}:</b> {', '.join(skills)}<br/>"
        story.append(Paragraph(skills_text, normal_style))
    else:
        story.append(Paragraph("No skills detected in resume.", normal_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Job Description Match Section
    if job_description:
        story.append(Paragraph("Job Description Match", heading_style))
        match_percent = analysis.get('match_percent', 0)
        story.append(Paragraph(f"<b>Match Percentage:</b> {match_percent}%", normal_style))
        
        matched = analysis.get('matched_keywords', [])
        missing = analysis.get('missing_keywords', [])
        
        if matched:
            story.append(Paragraph(f"<b>Matched Keywords:</b> {', '.join(matched)}", normal_style))
        if missing:
            story.append(Paragraph(f"<b>Missing Keywords:</b> {', '.join(missing)}", normal_style))
        
        recommendation = analysis.get('recommendation', '')
        if recommendation:
            story.append(Paragraph(f"<b>Recommendation:</b> {recommendation}", normal_style))
        story.append(Spacer(1, 0.3*inch))
    
    # Feedback Section
    story.append(Paragraph("Resume Feedback", heading_style))
    feedback = analysis.get('feedback', {})
    
    strengths = feedback.get('strengths', [])
    weaknesses = feedback.get('weaknesses', [])
    recommendations = feedback.get('recommendations', [])
    
    if strengths:
        story.append(Paragraph("<b>Strengths:</b>", normal_style))
        for strength in strengths:
            story.append(Paragraph(f"• {strength}", normal_style))
    
    if weaknesses:
        story.append(Paragraph("<b>Areas for Improvement:</b>", normal_style))
        for weakness in weaknesses:
            story.append(Paragraph(f"• {weakness}", normal_style))
    
    if recommendations:
        story.append(Paragraph("<b>Recommendations:</b>", normal_style))
        for rec in recommendations:
            story.append(Paragraph(f"• {rec}", normal_style))
    
    story.append(Spacer(1, 0.5*inch))
    
    # Footer
    story.append(Paragraph("Generated by Smart Resume Analyzer", normal_style))
    
    # Build PDF
    doc.build(story)
