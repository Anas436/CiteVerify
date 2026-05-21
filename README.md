# CiteVerify 🔍

**Multi-Agent AI Citation Hallucination Detector**

CiteVerify is a Django web application that uses a **5-agent AI pipeline** powered by **Groq's LLaMA 3.3 70B** to automatically detect hallucinated (fabricated/non-existent) citations in research papers. Upload a PDF, DOCX, or paste text, and the system analyzes each citation for credibility, providing a detailed forensic report with severity ratings.

---

## Features

- **Multi-Agent Pipeline** — 5 specialized AI agents work sequentially: Citation Extractor → Context Analyzer → Source Verifier → Hallucination Detector → Report Generator
- **File Support** — Upload PDF (via PyPDF2) or DOCX (via python-docx), or paste text directly
- **Real-Time Progress** — Live polling updates as each agent processes the paper
- **Severity Classification** — Each citation gets a **Green** (Verified), **Yellow** (Questionable), or **Red** (Hallucinated) rating with confidence scores
- **Forensic Reports** — Comprehensive report with credibility score, citation distribution, and actionable recommendations
- **User Authentication** — Sign up / log in to track analysis history and manage papers
- **Tailwind CSS + Alpine.js** — Modern, responsive UI with glass-morphism design

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User (Browser)                             │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Django Web Server                            │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                  URL Router (config/urls.py)                  │  │
│  │ /* admin /*    /* accounts/*    /* detector/*                 │  │
│  └─────┼───────────────┼───────────────┼─────────────────────────┘  │
│        │               │               │                            │
│        ▼               ▼               ▼                            │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐                  │
│  │ Landing  │  │ Accounts App │  │ Detector App  │                  │
│  │  Page    │  │ - signup     │  │ - upload      │                  │
│  │          │  │ - login      │  │ - progress    │                  │
│  │          │  │ - logout     │  │ - results     │                  │
│  │          │  │              │  │ - report      │                  │
│  │          │  │              │  │ - history     │                  │
│  └──────────┘  └──────────────┘  └───────┬───────┘                  │
│                                          │                          │
│                                          ▼                          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                   Multi-Agent Pipeline                        │  │
│  │                                                               │  │
│  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │  │
│  │  │  Agent 1     │──▶│  Agent 2     │──▶│  Agent 3    │       │  │
│  │  │  Citation    │   │  Context     │   │  Source      │       │  │
│  │  │  Extractor   │   │  Analyzer    │   │  Verifier    │       │  │
│  │  └──────────────┘   └──────────────┘   └───────┬──────┘       │  │
│  │                                                │              │  │
│  │  ┌──────────────┐   ┌──────────────┐           │              │  │
│  │  │  Agent 5     │◀──│  Agent 4     │ ◀───────┘               │  │
│  │  │  Report      │   │  Hallucination│                         │  │
│  │  │  Generator   │   │  Detector     │                         │  │
│  │  └──────┬───────┘   └──────────────┘                          │  │
│  │         │                                                     │  │
│  │         ▼                                                     │  │
│  │  ┌────────────────────────────────────┐                       │  │
│  │  │      Groq API (LLaMA-3.3-70B)      │                       │  │
│  │  └────────────────────────────────────┘                       │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                     Database (SQLite)                         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌────────────┐   │  │
│  │  │ Analysis │  │ Citation │  │AnalysisRepo│  │ AgentLog   │   │  │
│  │  │          │  │          │  │rt          │  │            │   │  │
│  │  └──────────┘  └──────────┘  └────────────┘  └────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Agent Pipeline Detail

```
┌─────────────────────────────────────────────────────────────────┐
│                   Agent 1: Citation Extractor                   │
│  Regex patterns (author-year, numeric brackets, IEEE, ACM)      │
│  + LLM analysis for missed citations                            │
│  Output: list of citations with context                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Agent 2: Context Analyzer                     │
│  Analyzes surrounding text for each citation                    │
│  Determines claim type (factual, numerical, methodological...)  │
│  Output: claim summaries per citation                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Agent 3: Source Verifier                      │
│  Evaluates plausibility of each cited source                    │
│  Flags red flags (suspicious authors, impossible years, etc.)   │
│  Output: confidence scores + severity per citation              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Agent 4: Hallucination Detector               │
│  Cross-references all evidence from previous agents             │
│  Makes final hallucination determination                        │
│  Output: is_hallucinated bool + reason per citation             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Agent 5: Report Generator                     │
│  Aggregates all results into a comprehensive report             │
│  Calculates overall credibility score                           │
│  Output: summary, recommendations, key findings                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
citeverify/
├── .env                          # Environment variables (API keys, secrets)
├── .gitignore
├── db.sqlite3                    # SQLite database
├── manage.py                     # Django management entry point
├── package.json                  # Node/npm config (Tailwind CSS)
├── requirements.txt              # Python dependencies
├── tailwind.config.js            # Tailwind CSS configuration
│
├── accounts/                     # Django app: User Accounts
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py                  # SignUpForm, LoginForm
│   ├── models.py                 # Profile model (OneToOneField with User)
│   ├── urls.py                   # signup, login, logout routes
│   ├── views.py                  # SignUpView, CustomLoginView, logout_view
│   ├── migrations/
│   │   └── 0001_initial.py
│   └── templates/accounts/
│       ├── login.html
│       └── signup.html
│
├── config/                       # Django project configuration
│   ├── __init__.py
│   ├── settings.py               # Main settings
│   ├── urls.py                   # Root URL configuration
│   └── wsgi.py                   # WSGI application
│
├── detector/                     # ★ Core Django app
│   ├── admin.py
│   ├── agents.py                 # ★ 5-agent AI pipeline (517 lines)
│   ├── apps.py
│   ├── models.py                 # Analysis, Citation, AnalysisReport, AgentLog
│   ├── urls.py                   # 8 URL routes
│   ├── utils.py                  # File extraction helpers (PDF, DOCX)
│   ├── views.py                  # All views + background analysis thread
│   ├── migrations/
│   │   └── 0001_initial.py
│   ├── templatetags/
│   │   ├── __init__.py
│   │   └── detector_extras.py    # Custom template filter
│   └── templates/detector/
│       ├── dashboard.html        # User dashboard with stats
│       ├── history.html          # Analysis history table
│       ├── progress.html         # Live progress (polling via JS)
│       ├── report_detail.html    # Full forensic report
│       ├── results.html          # Citation-by-citation results
│       └── upload.html           # Upload/paste text form
│
├── static/                       # Static assets
│   ├── css/input.css             # Tailwind CSS entry point
│   └── js/main.js                # Custom JavaScript
│
├── staticfiles/                  # Django collectstatic output (build)
│
└── templates/                    # Root-level templates
    ├── base.html                 # Base template (nav, Alpine.js, Tailwind CDN)
    └── index.html                # Landing / hero page
```

---

## Tech Stack

| Layer        | Technology                                      |
|-------------|-------------------------------------------------|
| **Backend** | Django 5.0, Python 3.11+                        |
| **AI/LLM**  | Groq API (LPU inference), LLaMA 3.3 70B         |
| **Database**| SQLite (Django ORM)                              |
| **Frontend**| Tailwind CSS 3, Alpine.js                        |
| **PDF**     | PyPDF2                                           |
| **DOCX**    | python-docx                                      |
| **Static**  | WhiteNoise                                       |
| **Forms**   | django-crispy-forms + crispy-tailwind             |

---

## Prerequisites

- Python 3.11+
- Node.js 18+ (for Tailwind CSS)
- A [Groq API key](https://console.groq.com/) (free tier available)

---

## Setup

### 1. Clone and enter the project

```bash
git clone https://github.com/Anas436/CiteVerify.git
cd CiteVerify
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

Create a `.env` file in the `citeverify/` directory:

```env
DJANGO_SECRET_KEY=your-django-secret-key
DJANGO_DEBUG=True
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### 5. Install Node dependencies and build Tailwind CSS

```bash
npm install
npm run build
```

### 6. Run database migrations

```bash
python manage.py migrate
```

### 7. Create a superuser (optional, for admin panel)

```bash
python manage.py createsuperuser
```

### 8. Start the development server

```bash
python manage.py runserver
```

Visit **http://127.0.0.1:8000** to use the app.

---

## Usage

1. **Sign up** for an account or log in
2. **Upload** a research paper (PDF/DOCX) or paste text on the upload page
3. **Wait** while the 5-agent pipeline processes each citation (progress updates in real-time)
4. **Review** citation-by-citation results with severity ratings (Green / Yellow / Red)
5. **Read** the forensic report with overall credibility score and recommendations

### Limits

- Maximum **60 citations** analyzed per batch
- Text truncated to **8,000 characters** for LLM extraction (citations beyond this are extracted via regex only)

---

## Configuration

All configuration is via environment variables in `.env`:

| Variable              | Default                        | Description                                |
|-----------------------|--------------------------------|--------------------------------------------|
| `DJANGO_SECRET_KEY`   | (dev key)                      | Django secret key                          |
| `DJANGO_DEBUG`        | `True`                         | Debug mode (`True` / `False`)              |
| `GROQ_API_KEY`        | Your API Key                   | Groq API key                               |
| `GROQ_MODEL`          | `llama-3.3-70b-versatile`      | Groq LLM model name                        |

---

## Models

| Model           | Description                                    | Key Fields                                                                 |
|-----------------|------------------------------------------------|----------------------------------------------------------------------------|
| **Analysis**    | A single citation analysis session             | `id` (UUID), `user`, `title`, `input_text`, `input_file`, `status`, `progress` |
| **Citation**    | An individual citation found in the text       | `analysis` (FK), `citation_text`, `context_before/after`, `claimed_source/year`, `confidence_score`, `severity`, `is_hallucinated` |
| **AnalysisReport** | Comprehensive report for an analysis        | `analysis` (OneToOne), `summary`, `total_citations`, `verified/questionable/hallucinated_citations`, `overall_credibility_score`, `agent_logs`, `recommendations` |
| **AgentLog**    | Log entry for each agent's activity            | `analysis` (FK), `agent_name`, `action`, `status`, `details`              |

---

## How It Works

1. **User uploads** a paper → `new_analysis` view extracts text (PDF/DOCX/pasted) and creates an `Analysis` record
2. **Background thread** starts → `_run_analysis_in_background()` runs the 5-agent pipeline sequentially
3. **Agent 1 (Citation Extractor)** uses regex patterns AND Groq LLM to find all citation markers
4. **Agent 2 (Context Analyzer)** examines surrounding text to determine what claim each citation supports
5. **Agent 3 (Source Verifier)** evaluates whether each source plausibly exists (red flags, confidence scores)
6. **Agent 4 (Hallucination Detector)** cross-references all evidence for the final hallucination verdict
7. **Agent 5 (Report Generator)** creates a summary with credibility score and recommendations
8. **Results saved** → Citation, AnalysisReport, and AgentLog records are persisted
9. **Frontend polls** `/detector/<id>/status/` every 2 seconds for live progress updates
10. **User views** results page (traffic-light severity) and detailed forensic report

---

