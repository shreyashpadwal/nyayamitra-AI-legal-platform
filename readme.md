# ⚖️ NyayaMitra — AI Legal Intelligence Platform

**NyayaMitra** is a professional, AI-powered legal assistance platform built for the Indian legal system. This repository is pre-configured for **Free Production Deployment**.

---

## 🚀 Deployment Guide

### 1. Database (Neon PostgreSQL - Free)
1. Sign up at [Neon.tech](https://neon.tech).
2. Create a new project and copy the **Connection String** (DATABASE_URL).
3. The backend will automatically create tables on first startup.

### 2. Backend (Render - Free)
1. Connect your GitHub repository to [Render](https://render.com).
2. Create a new **Web Service**.
3. **Runtime**: Python 3
4. **Build Command**: `pip install -r backend/requirements.txt`
5. **Start Command**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 10000`
6. **Environment Variables**:
   - `DATABASE_URL`: (From Neon)
   - `GROQ_API_KEY`: (From Groq Cloud)
   - `SECRET_KEY`: (Any random string)
   - `ALGORITHM`: `HS256`
   - `ACCESS_TOKEN_EXPIRE_MINUTES`: `60`

### 3. Frontend (Vercel - Free)
1. Connect your repository to [Vercel](https://vercel.com).
2. Select the `frontend` directory as the root.
3. **Framework Preset**: Vite.
4. **Environment Variables**:
   - Update `frontend/src/utils/auth.js` with your Render backend URL before pushing.

---

## 🛠️ Local Tech Stack
- **Backend**: FastAPI, SQLAlchemy, PostgreSQL, FAISS (Vector DB)
- **Frontend**: React, Vite, TailwindCSS
- **AI**: LangChain, Groq (LLaMA 3.1), sentence-transformers

---

## 📂 Project Structure
```bash
NyayaMitra/
├── backend/            # FastAPI Backend
│   ├── app/            # Source Code
│   ├── data/           # FAISS Index (judgments_index/) & PDFs
│   └── requirements.txt
├── frontend/           # React Frontend (Vite)
├── scripts/            # Admin Utilities (Index builder, DB populator)
└── README.md           # This guide
```

---

## ⚙️ Local Development
1. **Backend**: 
   - `cd backend && python -m venv venv`
   - `source venv/bin/activate` (or `venv\Scripts\activate` on Windows)
   - `pip install -r requirements.txt`
   - `uvicorn app.main:app --reload`
2. **Frontend**:
   - `cd frontend && npm install && npm run dev`

---

⚖️ **NyayaMitra** - *Democratizing Legal Access through AI.*
