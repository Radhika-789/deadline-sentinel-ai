# 🚀 Deadline Sentinel AI

An AI-powered deadline management platform that automatically extracts important opportunity details from unstructured content such as PDFs, images, screenshots, and plain text. Instead of manually tracking placement drives, internships, hackathons, or scholarships, students can upload the announcement and let AI organize everything into a searchable dashboard.

The system uses Google Gemini for intelligent information extraction and provides a centralized dashboard to monitor deadlines, application status, and upcoming opportunities.

---

## ✨ Features

### 🤖 AI-Powered Extraction
- Extracts structured information from raw text using Google Gemini
- Supports placement drives, internships, hackathons, scholarships, competitions, and more
- Automatically identifies:
  - Company / Organization
  - Role
  - Category
  - Deadline
  - Eligibility
  - Application Link
  - Additional Notes

### 📂 Multi-format Upload
Upload announcements directly from:
- PDF
- DOCX
- TXT
- PNG
- JPG / JPEG

Images are processed using Gemini OCR before information extraction.

### 📊 Interactive Dashboard
Built with Streamlit.

Includes:
- Dashboard overview
- Deadline statistics
- Upcoming vs Expired opportunities
- Search & filtering
- Sorting
- Pagination
- Upload interface
- Responsive data table

### ⚙️ Backend API
REST APIs built with FastAPI.

Implemented endpoints include:
- Extract opportunity from text
- Upload files
- View all deadlines
- View individual deadline
- Update deadline
- Soft delete deadline
- Filtering, sorting and pagination

### 💾 Database
- SQLAlchemy ORM
- SQLite (development)
- PostgreSQL ready

---

# 🏗️ Tech Stack

| Layer | Technology |
|--------|------------|
| Backend | FastAPI |
| AI | Google Gemini API |
| Database | SQLite + SQLAlchemy |
| Frontend | Streamlit |
| OCR | Gemini Vision |
| Scheduling | APScheduler |
| Language | Python 3.11+ |

---

# 📁 Project Structure

```text
deadline-sentinel-ai/
│
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── main.py
│
├── streamlit_app/
│
├── requirements.txt
├── README.md
└── .env.example
```

---

# ⚡ Getting Started

## 1. Clone the repository

```bash
git clone https://github.com/Radhika-789/deadline-sentinel-ai.git

cd deadline-sentinel-ai
```

## 2. Create a virtual environment

```bash
python -m venv venv
```

Windows

```bash
venv\Scripts\activate
```

Linux / macOS

```bash
source venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure environment variables

Create a `.env` file.

```env
GEMINI_API_KEY=your_api_key_here
```

## 5. Start FastAPI

```bash
uvicorn app.main:app --reload
```

Backend:

```
http://127.0.0.1:8000
```

Swagger:

```
http://127.0.0.1:8000/docs
```

## 6. Start Streamlit

```bash
streamlit run streamlit_app/app.py
```

---


# 🚧 Roadmap

- [x] AI deadline extraction
- [x] CRUD APIs
- [x] File upload support
- [x] OCR for images
- [x] Interactive dashboard
- [x] Filtering & pagination
- [ ] Email reminders
- [ ] Authentication
- [ ] Calendar integration
- [ ] Docker deployment

---

# 💡 Motivation

Students often receive opportunity announcements through WhatsApp groups, emails, LinkedIn posts, or PDF notices. Important deadlines can easily get buried or forgotten.

Deadline Sentinel AI was built to reduce that manual effort by automatically extracting and organizing opportunity details into a single dashboard, helping students focus on applying rather than managing deadlines.

---

# 📄 License

This project is licensed under the MIT License.