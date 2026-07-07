import os
import sqlite3
import json
import secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from resume_utils import (
    init_db,
    get_db_connection,
    extract_text_from_pdf,
    analyze_resume_text,
    extract_skills,
    match_job_description,
    generate_report_pdf,
)
import openai

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = "/tmp/uploads"
REPORTS_FOLDER = "/tmp/reports"
DATABASE_PATH = "/tmp/smart_resume_analyzer.db"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(24))
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["REPORTS_FOLDER"] = REPORTS_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024

# OpenAI Configuration
app.config["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "")

init_db(DATABASE_PATH)

# Ensure necessary directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(view_func):
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(**kwargs)
    wrapped_view.__name__ = view_func.__name__
    return wrapped_view


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not name or not email or not password or not confirm:
            flash("Please fill in all fields.", "warning")
            return render_template("signup.html")
        if password != confirm:
            flash("Passwords do not match.", "warning")
            return render_template("signup.html")

        conn = get_db_connection(DATABASE_PATH)
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            flash("An account with that email already exists.", "danger")
            return render_template("signup.html")

        password_hash = generate_password_hash(password)
        conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name, email, password_hash, datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()

        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection(DATABASE_PATH)
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            flash("Welcome back, {}!".format(user[1]), "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    conn = get_db_connection(DATABASE_PATH)
    resume_count = conn.execute("SELECT COUNT(*) FROM resumes WHERE user_id = ?", (user_id,)).fetchone()[0]
    analysis_count = conn.execute("SELECT COUNT(*) FROM analyses WHERE user_id = ?", (user_id,)).fetchone()[0]
    latest_analysis = conn.execute(
        "SELECT id, resume_id, created_at, ats_score, match_percent, skills_found FROM analyses WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()

    last_summary = None
    if latest_analysis:
        last_summary = {
            "analysis_id": latest_analysis[0],
            "resume_id": latest_analysis[1],
            "created_at": latest_analysis[2],
            "ats_score": latest_analysis[3],
            "match_percent": latest_analysis[4],
            "skills_found": latest_analysis[5],
        }

    return render_template(
        "dashboard.html",
        resume_count=resume_count,
        analysis_count=analysis_count,
        last_summary=last_summary,
    )


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        if "resume" not in request.files:
            flash("Select a PDF resume to upload.", "warning")
            return render_template("upload.html")

        file = request.files["resume"]
        job_description = request.form.get("job_description", "").strip()

        if file.filename == "":
            flash("No file selected.", "warning")
            return render_template("upload.html")
        
        if not allowed_file(file.filename):
            flash("Only PDF files are allowed.", "danger")
            return render_template("upload.html")
        
        try:
            filename = secure_filename(file.filename)
            unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(8)}_{filename}"
            saved_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
            file.save(saved_path)

            raw_text = extract_text_from_pdf(saved_path)
            
            if not raw_text.strip():
                flash("Uploaded PDF contains no readable text. Please upload a text-based resume.", "danger")
                return render_template("upload.html")

            analysis = analyze_resume_text(raw_text)
            skills = extract_skills(raw_text)
            analysis.update(skills)

            if job_description:
                match_result = match_job_description(raw_text, job_description)
                analysis.update(match_result)

            conn = get_db_connection(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO resumes (user_id, filename, filepath, uploaded_at) VALUES (?, ?, ?, ?)",
                (session["user_id"], filename, unique_name, datetime.utcnow().isoformat()),
            )
            resume_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO analyses (user_id, resume_id, analysis_data, job_description, ats_score, match_percent, skills_found, missing_keywords, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session["user_id"],
                    resume_id,
                    json.dumps(analysis),
                    job_description,
                    analysis["ats_score"],
                    analysis.get("match_percent", 0),
                    ", ".join(analysis["skills_found"]),
                    ", ".join(analysis.get("missing_keywords", [])),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
            conn.close()

            flash("Resume uploaded and analyzed successfully.", "success")
            return redirect(url_for("history"))
        except Exception as e:
            flash(f"Error processing resume: {str(e)}. Please try again.", "danger")
            return render_template("upload.html")

    return render_template("upload.html")


@app.route("/history")
@login_required
def history():
    conn = get_db_connection(DATABASE_PATH)
    rows = conn.execute(
        "SELECT r.id, r.filename, r.uploaded_at, a.id, a.ats_score, a.match_percent, a.skills_found FROM resumes r LEFT JOIN analyses a ON r.id = a.resume_id WHERE r.user_id = ? ORDER BY r.uploaded_at DESC",
        (session["user_id"],),
    ).fetchall()
    conn.close()

    records = []
    for row in rows:
        records.append({
            "resume_id": row[0],
            "filename": row[1],
            "uploaded_at": row[2],
            "analysis_id": row[3],
            "ats_score": row[4],
            "match_percent": row[5],
            "skills_found": row[6],
        })
    return render_template("history.html", records=records)


@app.route("/delete/<int:resume_id>", methods=["POST"])
@login_required
def delete_resume(resume_id):
    conn = get_db_connection(DATABASE_PATH)
    
    # Verify the resume belongs to the current user
    resume = conn.execute("SELECT filepath FROM resumes WHERE id = ? AND user_id = ?", (resume_id, session["user_id"])).fetchone()
    
    if resume:
        # Delete the analysis first (foreign key dependency)
        conn.execute("DELETE FROM analyses WHERE resume_id = ?", (resume_id,))
        
        # Delete the resume record
        conn.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
        
        # Delete the physical file
        filepath = resume[0]
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filepath)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        conn.commit()
        flash("Resume deleted successfully.", "success")
    else:
        flash("Resume not found or you don't have permission to delete it.", "danger")
    
    conn.close()
    return redirect(url_for("history"))


@app.route("/analysis/<int:analysis_id>")
@login_required
def analysis_detail(analysis_id):
    conn = get_db_connection(DATABASE_PATH)
    row = conn.execute(
        "SELECT a.analysis_data FROM analyses a WHERE a.id = ? AND a.user_id = ?",
        (analysis_id, session["user_id"]),
    ).fetchone()
    conn.close()

    if not row:
        flash("Analysis not found.", "danger")
        return redirect(url_for("history"))

    analysis = json.loads(row[0])
    return render_template("analysis.html", analysis=analysis, analysis_id=analysis_id)


@app.route("/ai-resume", methods=["GET", "POST"])
@login_required
def ai_resume():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        location = request.form.get("location", "").strip()
        summary = request.form.get("summary", "").strip()
        experience = request.form.get("experience", "").strip()
        education = request.form.get("education", "").strip()
        skills = request.form.get("skills", "").strip()
        template = request.form.get("template", "modern")

        if not full_name or not email:
            flash("Name and email are required.", "warning")
            return render_template("ai_resume.html")

        # Handle photo upload
        photo_path = None
        if "photo" in request.files and request.files["photo"].filename:
            photo = request.files["photo"]
            if photo and allowed_file(photo.filename) or photo.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                photo_filename = secure_filename(photo.filename)
                unique_photo_name = f"photo_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(8)}_{photo_filename}"
                photo_saved_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_photo_name)
                photo.save(photo_saved_path)
                photo_path = unique_photo_name

        # AI-enhanced content (simulated for demo)
        enhanced_summary = enhance_with_ai(summary, "summary")
        enhanced_experience = enhance_with_ai(experience, "experience")
        enhanced_skills = enhance_with_ai(skills, "skills")

        # Generate resume based on template
        resume_content = generate_resume_template(
            full_name, email, phone, location,
            enhanced_summary, enhanced_experience, education, enhanced_skills,
            template, photo_path
        )

        # Save generated resume
        filename = f"{full_name.replace(' ', '_')}_resume_{template}.html"
        saved_path = os.path.join(app.config["UPLOAD_FOLDER"], f"generated_{filename}")
        
        with open(saved_path, 'w', encoding='utf-8') as f:
            f.write(resume_content)

        # Store in database
        conn = get_db_connection(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO resumes (user_id, filename, filepath, uploaded_at) VALUES (?, ?, ?, ?)",
            (session["user_id"], filename, f"generated_{filename}", datetime.utcnow().isoformat()),
        )
        resume_id = cursor.lastrowid
        conn.commit()
        conn.close()

        flash("AI-generated resume created successfully!", "success")
        
        # Return the content for download
        return send_file(saved_path, mimetype="text/html", download_name=filename, as_attachment=True)

    return render_template("ai_resume.html")


def enhance_with_ai(text, section_type):
    """Simulate AI enhancement (in production, use OpenAI API)"""
    if not text:
        return text
    
    # Simple enhancement rules
    enhancements = {
        "summary": [
            "Results-driven professional",
            "Proven track record",
            "Dedicated and motivated",
            "Strong analytical skills"
        ],
        "experience": [
            "Successfully managed",
            "Led cross-functional teams",
            "Implemented strategic initiatives",
            "Achieved key performance indicators"
        ],
        "skills": [
            "Proficient in",
            "Advanced knowledge of",
            "Expert-level",
            "Strong command of"
        ]
    }
    
    words = text.split()
    if len(words) > 10:
        # Add some professional enhancements
        enhancements_list = enhancements.get(section_type, [])
        if enhancements_list:
            import random
            enhancement = random.choice(enhancements_list)
            return f"{enhancement}. {text}"
    
    return text


def generate_resume_template(name, email, phone, location, summary, experience, education, skills, template, photo_path=None):
    """Generate resume based on selected template"""
    
    photo_html = ""
    if photo_path:
        photo_html = f'<img src="{photo_path}" alt="Profile Photo" style="width: 140px; height: 140px; border-radius: 50%; object-fit: cover; border: 4px solid #1a365d; box-shadow: 0 4px 8px rgba(0,0,0,0.15);">'
    
    templates = {
        "modern": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{name} - Resume</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #e8eef2;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 850px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .header {{
            background: #1a365d;
            color: white;
            padding: 45px 60px;
        }}
        .header h1 {{
            font-size: 38px;
            font-weight: 600;
            letter-spacing: 1px;
            margin-bottom: 15px;
        }}
        .contact-bar {{
            display: flex;
            gap: 25px;
            font-size: 14px;
            flex-wrap: wrap;
            opacity: 0.95;
        }}
        .contact-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .content {{
            padding: 40px 60px;
        }}
        .section {{
            margin-bottom: 35px;
        }}
        .section-title {{
            font-size: 18px;
            color: #1a365d;
            font-weight: 600;
            margin-bottom: 18px;
            padding-bottom: 8px;
            border-bottom: 2px solid #4a6fa5;
            display: inline-block;
        }}
        .section-content {{
            color: #333;
            line-height: 1.7;
            white-space: pre-wrap;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{name}</h1>
            <div class="contact-bar">
                <div class="contact-item">📍 {location}</div>
                <div class="contact-item">📧 {email}</div>
                <div class="contact-item">📱 {phone}</div>
            </div>
        </div>
        
        <div class="content">
            <div class="section">
                <div class="section-title">Professional Summary</div>
                <div class="section-content">{summary}</div>
            </div>
            
            <div class="section">
                <div class="section-title">Work Experience</div>
                <div class="section-content">{experience}</div>
            </div>
            
            <div class="section">
                <div class="section-title">Education</div>
                <div class="section-content">{education}</div>
            </div>
            
            <div class="section">
                <div class="section-title">Skills & Expertise</div>
                <div class="section-content">{skills}</div>
            </div>
        </div>
    </div>
</body>
</html>
""",
        "professional": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{name} - Resume</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Georgia', serif;
            background-color: #f0f0f0;
            padding: 50px 30px;
        }}
        .container {{
            max-width: 950px;
            margin: 0 auto;
            background: white;
            display: flex;
            box-shadow: 0 2px 12px rgba(0,0,0,0.1);
        }}
        .sidebar {{
            width: 280px;
            background: #2c3e50;
            color: white;
            padding: 40px 25px;
            text-align: center;
        }}
        .sidebar-photo {{
            margin-bottom: 25px;
        }}
        .sidebar h1 {{
            font-size: 26px;
            margin-bottom: 10px;
            line-height: 1.3;
        }}
        .contact-section {{
            margin-top: 35px;
            text-align: left;
        }}
        .contact-section h3 {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 18px;
            border-bottom: 1px solid rgba(255,255,255,0.2);
            padding-bottom: 8px;
        }}
        .contact-item {{
            margin-bottom: 12px;
            font-size: 13px;
            line-height: 1.5;
        }}
        .main-content {{
            flex: 1;
            padding: 50px 40px;
        }}
        .section {{
            margin-bottom: 35px;
        }}
        .section-title {{
            font-size: 20px;
            color: #2c3e50;
            margin-bottom: 18px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3498db;
            font-weight: 600;
        }}
        .section-content {{
            color: #444;
            line-height: 1.7;
            white-space: pre-wrap;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <div class="sidebar-photo">
                {photo_html}
            </div>
            <h1>{name}</h1>
            
            <div class="contact-section">
                <h3>Contact</h3>
                <div class="contact-item">📧 {email}</div>
                <div class="contact-item">📱 {phone}</div>
                <div class="contact-item">📍 {location}</div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="section">
                <div class="section-title">Professional Profile</div>
                <div class="section-content">{summary}</div>
            </div>
            
            <div class="section">
                <div class="section-title">Work Experience</div>
                <div class="section-content">{experience}</div>
            </div>
            
            <div class="section">
                <div class="section-title">Education</div>
                <div class="section-content">{education}</div>
            </div>
            
            <div class="section">
                <div class="section-title">Core Competencies</div>
                <div class="section-content">{skills}</div>
            </div>
        </div>
    </div>
</body>
</html>
""",
        "creative": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{name} - Resume</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Helvetica Neue', Arial, sans-serif;
            background: #d4d9e2;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            position: relative;
            overflow: hidden;
        }}
        .accent-bar {{
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 6px;
            background: #5a7d9a;
        }}
        .header {{
            background: #5a7d9a;
            color: white;
            padding: 50px 50px 50px 65px;
        }}
        .header h1 {{
            font-size: 40px;
            font-weight: 600;
            letter-spacing: 1px;
            margin-bottom: 18px;
        }}
        .contact-info {{
            display: flex;
            gap: 20px;
            font-size: 14px;
            font-weight: 400;
        }}
        .content {{
            padding: 40px 65px;
        }}
        .section {{
            margin-bottom: 40px;
            position: relative;
        }}
        .section-title {{
            font-size: 22px;
            color: #5a7d9a;
            font-weight: 600;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .section-title::before {{
            content: '';
            width: 40px;
            height: 3px;
            background: #5a7d9a;
        }}
        .section-content {{
            color: #333;
            line-height: 1.8;
            white-space: pre-wrap;
            font-size: 14px;
            padding-left: 52px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="accent-bar"></div>
        <div class="header">
            <h1>{name}</h1>
            <div class="contact-info">
                <span>📍 {location}</span>
                <span>📧 {email}</span>
                <span>📱 {phone}</span>
            </div>
        </div>
        
        <div class="content">
            <div class="section">
                <div class="section-title">About Me</div>
                <div class="section-content">{summary}</div>
            </div>
            
            <div class="section">
                <div class="section-title">Experience</div>
                <div class="section-content">{experience}</div>
            </div>
            
            <div class="section">
                <div class="section-title">Education</div>
                <div class="section-content">{education}</div>
            </div>
            
            <div class="section">
                <div class="section-title">Skills</div>
                <div class="section-content">{skills}</div>
            </div>
        </div>
    </div>
</body>
</html>
""",
        "minimal": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{name} - Resume</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #f5f5f5;
            padding: 60px 40px;
        }}
        .container {{
            max-width: 750px;
            margin: 0 auto;
            background: white;
            padding: 70px 80px;
            border: 1px solid #d0d0d0;
        }}
        .header {{
            margin-bottom: 50px;
            padding-bottom: 30px;
            border-bottom: 2px solid #333;
        }}
        .header h1 {{
            font-size: 32px;
            font-weight: 400;
            color: #1a1a1a;
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-bottom: 20px;
        }}
        .contact-info {{
            font-size: 13px;
            color: #555;
            line-height: 1.8;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section-title {{
            font-size: 12px;
            font-weight: 600;
            color: #333;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 18px;
        }}
        .section-content {{
            color: #333;
            line-height: 1.7;
            white-space: pre-wrap;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{name}</h1>
            <div class="contact-info">
                {email}<br>
                {phone}<br>
                {location}
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">Experience</div>
            <div class="section-content">{experience}</div>
        </div>
        
        <div class="section">
            <div class="section-title">Education</div>
            <div class="section-content">{education}</div>
        </div>
        
        <div class="section">
            <div class="section-title">Skills</div>
            <div class="section-content">{skills}</div>
        </div>
    </div>
</body>
</html>
""",
        "executive": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{name} - Executive Resume</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Playfair Display', Georgia, serif;
            background: #e8e8e8;
            padding: 50px 30px;
        }}
        .container {{
            max-width: 950px;
            margin: 0 auto;
            background: white;
            border: 2px solid #1a365d;
            position: relative;
        }}
        .container::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: #1a365d;
        }}
        .header {{
            background: #1a365d;
            color: white;
            padding: 50px 60px;
            text-align: center;
        }}
        .header h2 {{
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-bottom: 12px;
            opacity: 0.9;
        }}
        .header h1 {{
            font-size: 38px;
            font-weight: 600;
            margin-bottom: 18px;
        }}
        .contact-info {{
            font-size: 14px;
            font-weight: 400;
            opacity: 0.9;
        }}
        .content {{
            padding: 50px 60px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section-title {{
            font-size: 17px;
            color: #1a365d;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 1px solid #d0d0d0;
            font-weight: 600;
        }}
        .section-content {{
            color: #333;
            line-height: 1.8;
            white-space: pre-wrap;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Executive Profile</h2>
            <h1>{name}</h1>
            <div class="contact-info">
                {email} | {phone} | {location}
            </div>
        </div>
        
        <div class="content">
            <div class="section">
                <div class="section-title">Executive Summary</div>
                <div class="section-content">{summary}</div>
            </div>
            
            <div class="section">
                <div class="section-title">Leadership Experience</div>
                <div class="section-content">{experience}</div>
            </div>
            
            <div class="section">
                <div class="section-title">Education & Credentials</div>
                <div class="section-content">{education}</div>
            </div>
            
            <div class="section">
                <div class="section-title">Strategic Competencies</div>
                <div class="section-content">{skills}</div>
            </div>
        </div>
    </div>
</body>
</html>
"""
    }
    
    return templates.get(template, templates["modern"])


@app.route("/report/<int:analysis_id>")
@login_required
def report(analysis_id):
    conn = get_db_connection(DATABASE_PATH)
    row = conn.execute(
        "SELECT r.filename, r.filepath, a.analysis_data, a.job_description, a.created_at FROM analyses a JOIN resumes r ON a.resume_id = r.id WHERE a.id = ? AND a.user_id = ?",
        (analysis_id, session["user_id"]),
    ).fetchone()
    conn.close()

    if not row:
        flash("Report not found.", "danger")
        return redirect(url_for("history"))

    filename, filepath, analysis_data, job_description, created_at = row
    analysis = json.loads(analysis_data)
    report_name = f"resume-report-{analysis_id}.pdf"
    report_path = os.path.join(app.config["REPORTS_FOLDER"], report_name)

    generate_report_pdf(
        report_path,
        session["user_name"],
        filename,
        created_at,
        analysis,
        job_description,
    )

    return send_file(report_path, mimetype="application/pdf", download_name=report_name, as_attachment=True)


@app.errorhandler(413)
def request_entity_too_large(error):
    flash("Uploaded file is too large. Maximum file size is 12MB.", "danger")
    return redirect(request.url)


if __name__ == "__main__":
    app.run(debug=True)
