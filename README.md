# Deadline Sentinel AI

An AI-powered web app that extracts structured deadline information
(placements, internships, scholarships, hackathons) from unstructured
sources like PDFs, screenshots, and text — then tracks and reminds
students before they miss out.

## Tech Stack
- **Backend:** FastAPI (Python)
- **AI:** Google Gemini API
- **Database:** SQLite (dev) → PostgreSQL (prod-ready)
- **Frontend:** Streamlit
- **Scheduling:** APScheduler

## Setup
1. `python -m venv venv && source venv/bin/activate` (or `venv\Scripts\activate` on Windows)
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in your Gemini API key
4. Run instructions will be added as we build each service.

## Status
🚧 Under active development — built step by step as a learning + portfolio project.