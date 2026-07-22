# 🚀 Deadline Sentinel AI

An AI-powered opportunity tracking platform that automatically extracts important deadlines and application details from unstructured documents such as PDFs, images, screenshots, DOCX files, and plain text. Instead of manually tracking internships, placements, hackathons, scholarships, and competitions, users can upload an announcement and let AI organize everything into a searchable dashboard with automated reminders.

Deadline Sentinel AI combines **Google Gemini**, **FastAPI**, and **Streamlit** to provide intelligent extraction, secure user management, and proactive deadline tracking.

---

# ✨ Features

## 🤖 AI-Powered Information Extraction

- Extracts structured information using Google Gemini
- Supports:
  - Internships
  - Placement drives
  - Hackathons
  - Scholarships
  - Competitions
  - Fellowships
- Automatically extracts:
  - Company / Organization
  - Role / Opportunity
  - Category
  - Deadline
  - Eligibility
  - Application Link
  - Additional Notes

---

## 📂 Multi-format Upload

Upload announcements from:

- PDF
- DOCX
- TXT
- PNG
- JPG / JPEG

Images are processed using Gemini Vision before structured extraction.

---

## 🔐 Authentication & Multi-Tenancy

- JWT Authentication
- Secure password hashing
- User registration & login
- Protected APIs
- User-specific deadline management
- Multi-tenant architecture ensuring data isolation

---

## 📧 Automated Email Reminder Engine

Never miss an important deadline.

Features include:

- APScheduler-based background scheduler
- Configurable reminder intervals
- SMTP email integration
- UUID-based claim locking
- Lease-based crash recovery
- Duplicate reminder prevention
- Automatic retry after failed email delivery

---

## 📊 Interactive Dashboard

Built with Streamlit.

Includes:

- Dashboard overview
- Upload interface
- Opportunity statistics
- Upcoming vs Expired opportunities
- Search
- Filtering
- Sorting
- Pagination
- Recent uploads
- User-specific dashboards

---

## ⚙️ REST API

FastAPI-powered REST APIs.

Includes:

- User Authentication
- Upload files
- AI extraction
- Create deadlines
- Retrieve deadlines
- Update deadlines
- Soft delete
- Filtering
- Sorting
- Pagination
- Health endpoint

---

## 💾 Database

- SQLAlchemy ORM
- Alembic migrations
- SQLite (Development)
- PostgreSQL-ready

---

# 🏗️ Tech Stack

| Layer | Technology |
|--------|------------|
| Backend | FastAPI |
| Frontend | Streamlit |
| AI | Google Gemini API |
| Database | SQLite + SQLAlchemy |
| ORM | SQLAlchemy |
| Authentication | JWT |
| Scheduler | APScheduler |
| Migrations | Alembic |
| OCR | Gemini Vision |
| Email | SMTP |
| Language | Python 3.11+ |

---

# 📁 Project Structure

```text
deadline-sentinel-ai/
│
├── alembic/
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── auth/
│   └── main.py
│
├── streamlit_app/
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

---

# ⚡ Getting Started

## 1. Clone Repository

```bash
git clone https://github.com/Radhika-789/deadline-sentinel-ai.git
cd deadline-sentinel-ai
```

---

## 2. Create Virtual Environment

```bash
python -m venv venv
```

Windows

```bash
venv\Scripts\activate
```

Linux/macOS

```bash
source venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

Create a `.env` file.

```env
GEMINI_API_KEY=your_api_key
JWT_SECRET_KEY=your_secret_key

DATABASE_URL=sqlite:///./deadline_sentinel.db

SMTP_HOST=localhost
SMTP_PORT=1025

REMINDER_INTERVAL_MINUTES=60
REMINDER_THRESHOLD_HOURS=24
```

---

## 5. Run Backend

```bash
uvicorn app.main:app --reload
```

Swagger UI:

```
http://127.0.0.1:8000/docs
```

---

## 6. Run Streamlit

```bash
streamlit run streamlit_app/app.py
```

---

# 🚧 Roadmap

- ✅ AI-powered deadline extraction
- ✅ Multi-format document upload
- ✅ Gemini Vision OCR
- ✅ Authentication & JWT authorization
- ✅ Multi-tenant architecture
- ✅ CRUD APIs
- ✅ Interactive dashboard
- ✅ Filtering, sorting & pagination
- ✅ Automated email reminder engine
- ✅ APScheduler background jobs
- ✅ Alembic database migrations
- ⏳ Google Calendar integration
- ⏳ Manual deadline entry
- ⏳ Docker deployment
- ⏳ CI/CD pipeline

---

# 💡 Motivation

Students receive opportunities through WhatsApp groups, emails, LinkedIn posts, college portals, and PDFs. Important deadlines often get buried across multiple platforms.

Deadline Sentinel AI automatically extracts, organizes, and tracks these opportunities while proactively reminding users before deadlines—helping them focus on applying instead of manually managing dates.

---

# 📄 License

This project is licensed under the MIT License.