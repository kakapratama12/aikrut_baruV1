# Aikrut - AI CV Screening Platform

## Product Overview
AI-powered CV screening platform helping HR teams reduce time spent on candidate evaluation using explainable, weighted, and configurable AI scoring.

## User Personas
- **Primary**: HR Recruiters - Need to screen large volumes of CVs efficiently
- **Secondary**: Hiring Managers - Need to review shortlisted candidates with clear reasoning
- **Super Admin**: Platform administrator - Manages users, credits, and AI settings

## Core Requirements
1. **Authentication**: JWT-based email/password authentication with user approval system
2. **Company Settings**: Company profile and configurable company values with weights
3. **Job Vacancies**: Job descriptions with AI-generated evaluation playbooks
4. **Talent Pool**: CV upload, parsing, and candidate evidence management with AI tagging
5. **Job Fit Analysis**: AI-powered batch scoring with explainable reasoning
6. **Super Admin System**: User management, credit allocation, global AI settings
7. **PDF Reports**: Downloadable analysis reports with job-specific candidate selection

## Tech Stack
- **Frontend**: React + Tailwind CSS + shadcn/ui
- **Backend**: FastAPI + Python
- **Database**: MongoDB
- **AI**: OpenRouter API (configurable by super admin)
- **PDF Generation**: ReportLab

## Implementation Status

### ✅ Completed Features

#### Core MVP (Phase 1)
- User registration and login with JWT auth
- Dashboard with KPI cards and activity feed
- Company settings with General Info and Company Values tabs
- AI-powered company values generation
- Job vacancy CRUD with AI-generated descriptions
- Evaluation playbook generation (Character/Requirement/Skill categories)
- Talent Pool with PDF CV upload and parsing
- Candidate evidence management
- Job Fit Analysis with batch AI scoring
- Explainable scoring with category breakdowns
- Shortlist filtering by minimum score
- Settings page (model, language)
- Responsive sidebar navigation
- Modern pastel SaaS UI design

#### Super Admin System (Phase 2-4)
- Separate admin login (`/admin-login`) with hardcoded credentials
- Super Admin dashboard (`/super-admin`) for user management
- User approval system - new users require admin approval
- Credit system - AI features deduct credits from user balance
- Global AI settings - OpenRouter API key managed centrally by admin
- Credit balance visible in navigation bar
- "Pending Approval" page for unapproved users
- Add/subtract credit management interface

#### Performance Optimizations
- Database indexes for all major collections
- Optimized admin user list endpoint (fixed N+1 queries)
- Frontend pagination and code splitting

#### Bug Fixes
- ObjectId serialization with recursive `serialize_doc` helper
- Deleted candidate handling in analysis results
- Duplicate candidate detection
- Analysis modal scrollability
- Bulk delete analysis results
- Route ordering for candidate search
- Credit deduction across all AI features

### ✅ Completed Today (January 28, 2025)
- **PDF Download Dialog UX**: Complete redesign with 2-step flow
  - Standalone "Download Report" button always visible
  - Step 1: Select job from dropdown
  - Step 2: Select candidates from that job's analysis results
  - Proper loading states and empty state handling
- **Branding Rename**: TalentAI → Aikrut throughout the app
  - Login, Register, Admin Login, Super Admin pages
  - Sidebar navigation
  - Page title and HTTP headers
  - PendingApproval email reference

### 🔄 P1 Features (Next Priority)
- **PDF Branding**: Add company logo and brand colors to PDF reports
  - Backend: Add branding fields to global settings
  - Frontend: Admin UI for configuring branding
- **Dashboard Report Export**: Summary report (CSV/PDF) from main dashboard

### 📋 P2 Features (Future/Backlog)
- Account Expiry system
- OpenRouter Cost Tracking & Margins
- Advanced Super Admin Analytics Dashboard
- Backend code refactoring (`server.py` modularization)
- Email notifications for completed analyses

## Architecture

```
/app/
├── backend/
│   ├── .env              # MONGO_URL, DB_NAME
│   ├── requirements.txt
│   └── server.py         # Monolithic FastAPI app
├── frontend/
│   ├── .env              # REACT_APP_BACKEND_URL
│   ├── package.json
│   └── src/
│       ├── App.js
│       ├── components/
│       ├── context/AuthContext.js
│       ├── lib/api.js
│       └── pages/
└── memory/
    └── PRD.md
```

## Key API Endpoints
- `/api/auth/*` - User authentication
- `/api/admin/login` - Super admin authentication
- `/api/admin/users` - User management (approval, credits)
- `/api/admin/settings` - Global AI settings
- `/api/company` - Company management
- `/api/jobs/*` - Job vacancy management
- `/api/candidates/*` - Candidate management with tagging
- `/api/analysis/*` - Job fit analysis
- `/api/analysis/generate-pdf` - PDF report generation
- `/api/settings` - User settings
- `/api/dashboard/*` - Dashboard statistics

## Credentials
- **Super Admin**:
  - URL: `/admin-login`
  - Username: `admin`
  - Password: `MakanBaksoSapi99`
- **Regular Users**: Register via `/register`, require admin approval

## Database Schema
- `users`: credentials, `is_approved`, `is_active`, `credits`
- `companies`: company profile and values
- `jobs`: job descriptions and playbooks
- `candidates`: CV data, evidence, tags
- `analyses`: analysis results per candidate-job pair
- `admin_settings`: global AI settings (type: "global")
- `credit_usage_logs`: credit deduction history
