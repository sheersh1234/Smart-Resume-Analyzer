# Smart Resume Analyzer

A production-quality ATS (Applicant Tracking System) Resume Analyzer web application built with Flask, Python, and Bootstrap 5. This application helps students and job seekers evaluate and improve their resumes through comprehensive analysis, skill extraction, and job description matching.

## Features

### Core Functionality
- **User Authentication**: Secure sign up, login, and logout with password hashing
- **Resume Upload**: Upload PDF resumes with automatic text extraction
- **ATS Score Analysis**: Generate ATS scores out of 100 based on structure, keywords, format, and content
- **Skill Extraction**: Automatic detection and categorization of technical skills
- **Job Description Matching**: Calculate resume match percentage against job descriptions
- **Resume Feedback Engine**: Detailed strengths, weaknesses, and improvement recommendations
- **Analytics Dashboard**: Comprehensive overview of resume statistics and analysis history
- **PDF Report Generation**: Download professional PDF reports with detailed analysis
- **Dark Mode**: Toggle between light and dark themes
- **Search History**: Search and filter analysis history

### Skill Categories
- Programming Languages
- Web Development
- Databases
- AI/ML
- Tools & Technologies

## Tech Stack

- **Backend**: Python 3.x, Flask
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Database**: SQLite
- **PDF Processing**: PyPDF2
- **Report Generation**: ReportLab
- **Authentication**: Werkzeug security

## Project Structure

```
smart-resume-analyzer-pro/
├── app.py                 # Main Flask application
├── resume_utils.py        # Utility functions for analysis
├── requirements.txt       # Python dependencies
├── README.md             # Project documentation
├── database/             # SQLite database directory
│   └── smart_resume_analyzer.db
├── templates/            # HTML templates
│   ├── base.html        # Base template with navigation
│   ├── login.html       # Login page
│   ├── signup.html      # Sign up page
│   ├── dashboard.html   # User dashboard
│   ├── upload.html      # Resume upload page
│   ├── history.html     # Analysis history
│   └── analysis.html    # Detailed analysis view
├── static/              # Static assets (CSS, JS, images)
├── uploads/             # Uploaded resume files
└── reports/             # Generated PDF reports
```

## Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package manager)

### Step-by-Step Installation

1. **Clone or download the project**
   ```bash
   cd "c:/Users/sheer/Desktop/python project"
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the application**
   Open your web browser and navigate to: `http://127.0.0.1:5000`

## Usage

### First Time Setup
1. Click "Sign Up" to create a new account
2. Enter your name, email, and password
3. Log in with your credentials

### Uploading and Analyzing Resumes
1. Navigate to the "Upload" page
2. Select a PDF resume file (max 12MB)
3. Optionally paste a job description for match analysis
4. Click "Upload & Analyze"
5. View your analysis results on the dashboard

### Viewing Analysis History
1. Go to the "History" page
2. View all previous resume analyses
3. Search by filename
4. Download PDF reports for any analysis

### Downloading Reports
1. From the dashboard or history page
2. Click the download button for any analysis
3. A professional PDF report will be generated

## ATS Score Breakdown

The ATS score is calculated based on four components:

1. **Structure Score (30 points)**: Presence of essential sections (Experience, Education, Skills, Summary, etc.)
2. **Keyword Score (30 points)**: Use of strong action verbs and relevant keywords
3. **Format Score (20 points)**: Inclusion of quantifiable metrics and achievements
4. **Content Score (20 points)**: Overall content depth and word count

**Score Interpretation:**
- **70-100**: Excellent - Well-optimized for ATS systems
- **50-69**: Good - Some improvements needed
- **Below 50**: Needs improvement - Focus on structure and keywords

## Security Features

- Password hashing using Werkzeug's secure password functions
- Secure file upload handling with filename sanitization
- Session-based authentication
- File size limits (12MB max)
- SQL injection prevention through parameterized queries
- CSRF protection through Flask's session management

## Development

### Adding New Skills
To add new skills to the detection system, edit the `SKILL_CATEGORIES` dictionary in `resume_utils.py`:

```python
SKILL_CATEGORIES = {
    "Category Name": [
        "skill1", "skill2", "skill3"
    ]
}
```

### Customizing Analysis
Modify the analysis algorithms in `resume_utils.py`:
- `analyze_resume_text()`: ATS scoring algorithm
- `extract_skills()`: Skill extraction logic
- `match_job_description()`: Job matching algorithm

### Database Schema
The application uses three main tables:
- **users**: User account information
- **resumes**: Uploaded resume metadata
- **analyses**: Analysis results and job descriptions

## Troubleshooting

### Common Issues

**Issue**: PDF text extraction fails
- **Solution**: Ensure the PDF is text-based (not a scanned image)

**Issue**: Database errors
- **Solution**: Ensure the `database/` directory exists and has write permissions

**Issue**: File upload fails
- **Solution**: Check file size (max 12MB) and format (PDF only)

**Issue**: Report generation fails
- **Solution**: Ensure the `reports/` directory exists and has write permissions

## Dependencies

See `requirements.txt` for the complete list:
- Flask==3.0.0
- Werkzeug==3.0.1
- PyPDF2==3.0.1
- reportlab==4.0.7

## License

This project is provided as-is for educational and personal use.

## Support

For issues, questions, or contributions, please refer to the project documentation or contact the development team.

## Future Enhancements

Potential features for future versions:
- Resume version comparison
- Advanced analytics and trends
- Multiple file format support (DOCX, TXT)
- Export to other formats (Word, Excel)
- Integration with job boards
- AI-powered resume suggestions
- Collaborative features for teams

## Credits

Built with modern web technologies and best practices for resume analysis and ATS optimization.
