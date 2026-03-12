# Aikrut - Product Requirements Document (PRD)

**Version:** 2.0  
**Last Updated:** January 28, 2025  
**Product Owner:** Aikrut Team  
**Status:** Active Development

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Product Vision & Goals](#2-product-vision--goals)
3. [User Personas](#3-user-personas)
4. [Current Features (Implemented)](#4-current-features-implemented)
5. [Future Features - ATS Module](#5-future-features---ats-module)
6. [Functional Requirements](#6-functional-requirements)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [Integration Architecture](#8-integration-architecture)
9. [Data & Analytics Requirements](#9-data--analytics-requirements)
10. [API Specifications](#10-api-specifications)
11. [Success Metrics](#11-success-metrics)
12. [Appendix](#12-appendix)

---

## 1. Executive Summary

### 1.1 Product Overview

**Aikrut** is an AI-powered Smart HR Assistant designed to revolutionize the recruitment process. The platform combines intelligent CV screening with comprehensive applicant tracking capabilities, enabling HR teams to make data-driven hiring decisions while significantly reducing time-to-hire.

### 1.2 Problem Statement

HR teams face several critical challenges in modern recruitment:

| Challenge | Impact |
|-----------|--------|
| High volume of applications | 75% of CVs are unqualified, wasting HR time |
| Subjective screening | Inconsistent evaluation criteria across recruiters |
| Lack of data visibility | No insights into why candidates fail or succeed |
| Poor candidate experience | Candidates rarely receive feedback on rejection reasons |
| Fragmented tools | Multiple systems for different recruitment stages |

### 1.3 Solution

Aikrut addresses these challenges through:

1. **AI-Powered Screening**: Automated, consistent candidate evaluation using customizable playbooks
2. **Explainable AI**: Every score comes with detailed reasoning and evidence
3. **Applicant Tracking System (ATS)**: End-to-end recruitment pipeline management
4. **Analytics Dashboard**: Data-driven insights on recruitment funnel performance
5. **Integration API**: Seamless connection with candidate-facing applications

---

## 2. Product Vision & Goals

### 2.1 Vision Statement

> *"To become the most intelligent and transparent recruitment platform that empowers HR teams with data-driven decisions while providing candidates with meaningful feedback on their applications."*

### 2.2 Strategic Goals

| Goal | Target | Timeline |
|------|--------|----------|
| Reduce CV screening time | 80% reduction | Q1 2025 |
| Improve hire quality | 30% better retention | Q2 2025 |
| Increase candidate satisfaction | NPS > 50 | Q3 2025 |
| Enable data-driven recruitment | 100% analytics coverage | Q2 2025 |

### 2.3 Product Principles

1. **Transparency First**: Every AI decision must be explainable
2. **HR-Centric Design**: Built for recruiters, not against them
3. **Data as a Product**: Analytics should drive continuous improvement
4. **Integration Ready**: API-first architecture for ecosystem connectivity

---

## 3. User Personas

### 3.1 Primary Persona: HR Recruiter (Sarah)

**Demographics:**
- Age: 28-40
- Role: HR Recruiter / Talent Acquisition Specialist
- Company Size: 50-500 employees
- Technical Proficiency: Moderate

**Goals:**
- Screen candidates faster without sacrificing quality
- Maintain consistent evaluation standards
- Track recruitment pipeline efficiently
- Generate reports for hiring managers

**Pain Points:**
- Overwhelmed by application volume
- Difficulty explaining rejection decisions
- Manual tracking in spreadsheets
- No visibility into recruitment bottlenecks

**Aikrut Value Proposition:**
> "Aikrut gives me back 10 hours per week by automating CV screening while ensuring I never miss a qualified candidate."

---

### 3.2 Secondary Persona: Hiring Manager (David)

**Demographics:**
- Age: 35-50
- Role: Department Head / Team Lead
- Technical Proficiency: Low-Moderate

**Goals:**
- Review pre-screened, qualified candidates only
- Understand candidate-job fit quickly
- Make confident hiring decisions
- Track team hiring progress

**Pain Points:**
- Receives too many unqualified resumes
- Lacks context on candidate strengths/weaknesses
- No standardized evaluation framework

**Aikrut Value Proposition:**
> "I only see candidates who match at least 70% of our requirements, with clear scoring breakdowns."

---

### 3.3 Tertiary Persona: Super Admin (Admin)

**Demographics:**
- Role: Platform Administrator / IT Admin
- Technical Proficiency: High

**Goals:**
- Manage user access and permissions
- Configure AI settings and credit allocation
- Monitor system usage and costs
- Ensure data security compliance

**Pain Points:**
- Managing multiple user accounts
- Controlling AI usage costs
- Maintaining system configurations

**Aikrut Value Proposition:**
> "Centralized control over all AI settings, user permissions, and credit management in one dashboard."

---

### 3.4 Future Persona: Job Candidate (Alex)

**Demographics:**
- Age: 22-45
- Role: Active Job Seeker
- Technical Proficiency: Varies

**Goals:**
- Apply for relevant positions easily
- Understand application status
- Receive feedback on rejections
- Improve future applications

**Pain Points:**
- "Black hole" applications with no response
- No understanding of why they were rejected
- Difficulty tracking multiple applications

**Aikrut Value Proposition (via integrated candidate app):**
> "I finally understand why I wasn't selected and can improve my profile for future opportunities."

---

## 4. Current Features (Implemented)

### 4.1 Authentication & Authorization

#### 4.1.1 User Authentication
- **JWT-based authentication** with secure token management
- Email/password registration and login
- Session management with 24-hour token expiry
- Password hashing using bcrypt

#### 4.1.2 User Approval System
- New user registration requires admin approval
- Pending approval page for unapproved users
- Admin can approve/reject user registrations
- Default credit allocation upon approval

#### 4.1.3 Super Admin System
- Separate admin login portal (`/admin-login`)
- Hardcoded super admin credentials
- Full platform management capabilities

**Technical Details:**
```
Endpoint: POST /api/auth/register
Endpoint: POST /api/auth/login
Endpoint: POST /api/admin/login
```

---

### 4.2 Company Management

#### 4.2.1 Company Profile
- Company name, description, industry, website
- One company per user account
- Company-scoped data isolation

#### 4.2.2 Company Values
- Configurable company values with descriptions
- Weight assignment (total = 100%)
- AI-powered value generation from narrative input
- Used for culture fit scoring in analysis

**Data Model:**
```json
{
  "id": "uuid",
  "name": "Company Name",
  "description": "About the company",
  "industry": "Technology",
  "website": "https://example.com",
  "values": [
    {
      "id": "uuid",
      "name": "Innovation",
      "description": "We embrace new ideas",
      "weight": 25
    }
  ]
}
```

---

### 4.3 Job Vacancy Management

#### 4.3.1 Job CRUD Operations
- Create, read, update, delete job postings
- Job status management (open/closed/draft)
- Rich text description and requirements

#### 4.3.2 AI Job Description Generation
- Generate from job title only
- Generate from narrative/context input
- Outputs structured description and requirements

#### 4.3.3 Evaluation Playbook
- AI-generated evaluation criteria per job
- Three categories: Character, Requirement, Skill
- 5 items per category with weights totaling 100%
- Manual editing and customization supported

**Playbook Structure:**
```json
{
  "character": [
    {"id": "uuid", "name": "Leadership", "description": "...", "weight": 20}
  ],
  "requirement": [
    {"id": "uuid", "name": "Experience", "description": "...", "weight": 20}
  ],
  "skill": [
    {"id": "uuid", "name": "Python", "description": "...", "weight": 20}
  ]
}
```

---

### 4.4 Candidate/Talent Pool Management

#### 4.4.1 Candidate Profiles
- Manual candidate creation
- Bulk CV upload (ZIP support)
- Duplicate detection (email, phone, name matching)

#### 4.4.2 Evidence Management
- PDF CV parsing and text extraction
- Multiple evidence types: CV, psychotest, certificates
- Automatic content classification

#### 4.4.3 AI Talent Tagging
- 4-layer tagging taxonomy:
  - **Layer 1**: Domain/Function (e.g., IT, Finance, HR)
  - **Layer 2**: Job Family (e.g., Software Development, Data Analytics)
  - **Layer 3**: Skills/Competencies (free-text, AI-normalized)
  - **Layer 4**: Scope of Work (Operational, Tactical, Strategic)
- Auto-extraction from CV content
- Manual tag addition/removal
- Tag-based candidate filtering

---

### 4.5 Job Fit Analysis

#### 4.5.1 AI-Powered Analysis
- Streaming analysis with real-time progress
- Batch processing multiple candidates
- Analysis against job playbook criteria

#### 4.5.2 Scoring System
- **Final Score**: Weighted average (0-100%)
- **Category Scores**: Character, Requirement, Skill
- **Company Values Alignment**: Culture fit percentage
- **Breakdown**: Per-criterion scores with reasoning

#### 4.5.3 Analysis Output
```json
{
  "final_score": 78.5,
  "category_scores": [
    {
      "category": "character",
      "score": 82,
      "breakdown": [
        {
          "item_name": "Leadership",
          "raw_score": 85,
          "weight": 20,
          "reasoning": "Demonstrated leadership in..."
        }
      ]
    }
  ],
  "company_values_alignment": {
    "score": 75,
    "breakdown": [...]
  },
  "strengths": ["Strong technical background", "..."],
  "gaps": ["Limited management experience", "..."],
  "overall_reasoning": "The candidate shows strong..."
}
```

#### 4.5.4 Results Management
- Filter by minimum score
- Bulk delete analysis results
- Detailed view modal with full breakdown

---

### 4.6 PDF Report Generation

#### 4.6.1 Report Features
- Executive summary with top recommendations
- Job details section
- Individual candidate analysis pages
- Score tables and breakdowns

#### 4.6.2 Report Workflow
- Select job from dropdown
- Select candidates to include
- Generate downloadable PDF

---

### 4.7 Credit System

#### 4.7.1 Credit Management
- Credits deducted for AI operations
- Per-operation credit rates (configurable)
- Credit balance display in navigation
- Usage logging and history

#### 4.7.2 Credit Operations
| Operation | Default Multiplier |
|-----------|-------------------|
| Company Values Generation | 1.5x |
| Job Description Generation | 1.5x |
| Playbook Generation | 1.5x |
| CV Parsing (AI) | 1.3x |
| Candidate Analysis | 2.0x |
| Tag Extraction | 1.5x |

---

### 4.8 Super Admin Dashboard

#### 4.8.1 User Management
- View all registered users (paginated)
- Approve/reject pending users
- Add/subtract user credits
- Activate/deactivate accounts

#### 4.8.2 Global Settings
- OpenRouter API key configuration
- AI model selection
- Default credits for new users
- Credit rate multipliers

#### 4.8.3 Analytics Overview
- Total users, jobs, candidates, analyses
- Credit distribution tracking
- Usage logs with filtering

---

## 5. Future Features - ATS Module

### 5.1 Overview

The Applicant Tracking System (ATS) module extends Aikrut from a screening tool to a complete recruitment management platform. It enables HR teams to track candidates through customizable hiring pipelines while capturing rich data for analytics and candidate feedback.

### 5.2 Core ATS Features

#### 5.2.1 Custom Recruitment Stages

**Description:**
Each job can have its own recruitment pipeline with customizable stages.

**Default Stage Template:**
1. Applied
2. CV Screening (automated by Aikrut)
3. Phone Interview
4. Technical Assessment
5. HR Interview
6. Final Interview
7. Offer
8. Hired / Rejected

**Customization Options:**
- Add/remove stages per job
- Rename stages
- Reorder stages
- Set stage-specific requirements
- Define stage owners/assignees

**Data Model:**
```json
{
  "job_id": "uuid",
  "stages": [
    {
      "id": "uuid",
      "name": "Applied",
      "order": 1,
      "is_automated": false,
      "auto_action": null
    },
    {
      "id": "uuid",
      "name": "AI Screening",
      "order": 2,
      "is_automated": true,
      "auto_action": "run_analysis",
      "auto_threshold": 60
    }
  ]
}
```

---

#### 5.2.2 Candidate Pipeline Tracking

**Application Record:**
```json
{
  "id": "uuid",
  "job_id": "uuid",
  "candidate_id": "uuid",
  "current_stage_id": "uuid",
  "source": "job_portal | manual | referral | linkedin",
  "applied_at": "2025-01-28T10:00:00Z",
  "status": "in_progress | hired | rejected | withdrawn",
  "stage_history": [
    {
      "stage_id": "uuid",
      "stage_name": "Applied",
      "entered_at": "2025-01-28T10:00:00Z",
      "exited_at": "2025-01-28T12:00:00Z",
      "outcome": "passed | rejected | skipped",
      "rejection_data": null
    },
    {
      "stage_id": "uuid",
      "stage_name": "AI Screening",
      "entered_at": "2025-01-28T12:00:00Z",
      "exited_at": "2025-01-28T12:05:00Z",
      "outcome": "rejected",
      "rejection_data": {
        "reason_code": "LOW_SCORE",
        "ai_analysis_id": "uuid",
        "final_score": 45,
        "category_scores": {...},
        "gaps": ["Insufficient experience", "Missing required skills"],
        "auto_rejected": true
      }
    }
  ]
}
```

**Key Tracking Points:**
- Time spent in each stage
- Who moved the candidate
- Outcome at each stage
- Rejection reasons (from AI or manual)

---

#### 5.2.3 Rejection Data Capture

**AI-Based Rejection (Automated):**
When a candidate fails AI screening, the system automatically captures:
- Analysis score and threshold comparison
- Category-level deficiencies
- Specific gaps identified by AI
- Playbook criteria not met

**Rejection Reason Codes:**
| Code | Description | Source |
|------|-------------|--------|
| LOW_SCORE | Below minimum score threshold | AI Analysis |
| SKILL_GAP | Missing critical skills | AI Analysis |
| EXPERIENCE_GAP | Insufficient experience | AI Analysis |
| CULTURE_MISMATCH | Low company values alignment | AI Analysis |
| WITHDRAWN | Candidate withdrew | Manual |
| NO_SHOW | Candidate didn't attend interview | Manual |
| OFFER_DECLINED | Candidate declined offer | Manual |
| POSITION_FILLED | Position was filled | Manual |

**Data Available for Candidate Feedback:**
```json
{
  "application_id": "uuid",
  "job_title": "Senior Developer",
  "final_status": "rejected",
  "rejection_stage": "AI Screening",
  "feedback": {
    "overall_fit": 45,
    "summary": "Your profile shows strong potential but doesn't fully align with current requirements.",
    "strengths": [
      "Strong communication skills",
      "Relevant educational background"
    ],
    "areas_for_improvement": [
      "Additional experience with Python frameworks would strengthen your application",
      "Consider obtaining cloud certification (AWS/GCP)"
    ],
    "category_feedback": {
      "technical_skills": "Meets 60% of requirements",
      "experience": "Below expected level for senior role",
      "soft_skills": "Strong match"
    }
  }
}
```

---

#### 5.2.4 Public Job Portal

**Job Listing Page:**
- Public URL for company job listings
- Filter by location, department, employment type
- Search functionality
- Mobile-responsive design

**Job Detail Page:**
- Full job description
- Requirements list
- Company information
- Apply button

**Application Flow:**
1. Candidate views job listing
2. Clicks "Apply"
3. Fills application form (name, email, phone)
4. Uploads CV (PDF)
5. Receives confirmation email
6. Application enters "Applied" stage

**Candidate Portal (Future):**
- Track application status
- View feedback when rejected
- Update profile information

---

#### 5.2.5 Kanban Board View

**Visual Pipeline Management:**
```
┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│   Applied    │  Screening   │  Interview   │    Offer     │    Hired     │
│     (12)     │     (5)      │     (3)      │     (1)      │     (0)      │
├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ ┌──────────┐ │ ┌──────────┐ │ ┌──────────┐ │ ┌──────────┐ │              │
│ │ John D.  │ │ │ Sarah M. │ │ │ Mike T.  │ │ │ Anna K.  │ │              │
│ │ Score:-- │ │ │ Score:78 │ │ │ Score:85 │ │ │ Score:92 │ │              │
│ │ 2 days   │ │ │ 1 day    │ │ │ 3 days   │ │ │ 5 days   │ │              │
│ └──────────┘ │ └──────────┘ │ └──────────┘ │ └──────────┘ │              │
│ ┌──────────┐ │ ┌──────────┐ │ ┌──────────┐ │              │              │
│ │ Jane S.  │ │ │ Tom B.   │ │ │ Lisa R.  │ │              │              │
│ │ Score:-- │ │ │ Score:65 │ │ │ Score:88 │ │              │              │
│ └──────────┘ │ └──────────┘ │ └──────────┘ │              │              │
└──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

**Drag & Drop Actions:**
- Move candidate between stages
- Automatic timestamp recording
- Validation rules (e.g., must have analysis before interview)

---

### 5.3 Analytics & Reporting

#### 5.3.1 Funnel Conversion Analytics

**Metrics Dashboard:**
```
Job: Senior Developer
Period: Last 30 days

Funnel Conversion:
┌─────────────────────────────────────────────────────────────┐
│ Applied          │████████████████████████████│ 100 (100%)  │
│ Screening        │██████████████              │  50 (50%)   │
│ Phone Interview  │████████                    │  25 (25%)   │
│ Technical Test   │█████                       │  15 (15%)   │
│ Final Interview  │███                         │   8 (8%)    │
│ Offer            │██                          │   3 (3%)    │
│ Hired            │█                           │   2 (2%)    │
└─────────────────────────────────────────────────────────────┘

Drop-off Analysis:
- Highest drop: Screening → Phone (50% lost)
- Reason: 80% had score < 60
```

#### 5.3.2 Time-to-Hire Metrics

**Dashboard Widgets:**
- Average time-to-hire (overall)
- Average time-to-hire by job
- Time spent per stage (average)
- Bottleneck identification

**Data Points:**
```json
{
  "job_id": "uuid",
  "metrics": {
    "avg_time_to_hire_days": 28,
    "median_time_to_hire_days": 25,
    "stage_durations": {
      "applied_to_screening": 1.5,
      "screening_to_interview": 3.2,
      "interview_to_offer": 7.8,
      "offer_to_hired": 5.5
    },
    "bottleneck_stage": "interview_to_offer",
    "trend": "improving"
  }
}
```

#### 5.3.3 Rejection Reasons Breakdown

**Analytics View:**
```
Rejection Analysis - Q1 2025

By Stage:
┌────────────────────┬─────────┬─────────────────────────┐
│ Stage              │ Count   │ Top Reason              │
├────────────────────┼─────────┼─────────────────────────┤
│ AI Screening       │ 450     │ Skill Gap (60%)         │
│ Phone Interview    │ 80      │ Communication (45%)     │
│ Technical Test     │ 35      │ Failed Assessment (70%) │
│ Final Interview    │ 15      │ Culture Fit (50%)       │
│ Offer Stage        │ 8       │ Salary Mismatch (75%)   │
└────────────────────┴─────────┴─────────────────────────┘

AI Screening Detail:
- Skill Gap: 270 (60%)
  - Python: 120
  - Cloud: 85
  - Database: 65
- Experience Gap: 135 (30%)
- Culture Mismatch: 45 (10%)
```

#### 5.3.4 Source Effectiveness

**Tracking Candidate Sources:**
| Source | Applications | Qualified | Hired | Quality Rate | Cost/Hire |
|--------|-------------|-----------|-------|--------------|-----------|
| Job Portal | 500 | 100 | 5 | 20% | $200 |
| LinkedIn | 200 | 80 | 4 | 40% | $500 |
| Referral | 50 | 40 | 3 | 80% | $100 |
| Agency | 30 | 25 | 2 | 83% | $2000 |

---

### 5.4 Integration API

#### 5.4.1 Webhook Events

**Available Events:**
```json
{
  "events": [
    "application.created",
    "application.stage_changed",
    "application.rejected",
    "application.hired",
    "application.withdrawn",
    "analysis.completed",
    "job.created",
    "job.closed"
  ]
}
```

**Webhook Payload Example:**
```json
{
  "event": "application.rejected",
  "timestamp": "2025-01-28T15:30:00Z",
  "data": {
    "application_id": "uuid",
    "job_id": "uuid",
    "candidate_id": "uuid",
    "candidate_email": "candidate@email.com",
    "job_title": "Senior Developer",
    "rejected_at_stage": "AI Screening",
    "rejection_reason": "LOW_SCORE",
    "feedback_available": true,
    "feedback_url": "https://api.aikrut.com/v1/feedback/{token}"
  }
}
```

#### 5.4.2 Public API Endpoints

**Candidate Feedback API:**
```
GET /api/v1/public/feedback/{feedback_token}

Response:
{
  "job_title": "Senior Developer",
  "company_name": "Tech Corp",
  "applied_date": "2025-01-20",
  "decision_date": "2025-01-22",
  "status": "not_selected",
  "feedback": {
    "overall_message": "Thank you for your application...",
    "strengths": [...],
    "improvement_areas": [...],
    "score_summary": {
      "technical": "Meets 60%",
      "experience": "Below requirements",
      "soft_skills": "Strong"
    }
  }
}
```

**Job Listings API:**
```
GET /api/v1/public/jobs?company_id={id}

Response:
{
  "jobs": [
    {
      "id": "uuid",
      "title": "Senior Developer",
      "location": "Remote",
      "employment_type": "Full-time",
      "description_preview": "...",
      "posted_date": "2025-01-15",
      "apply_url": "https://jobs.aikrut.com/apply/{job_id}"
    }
  ]
}
```

---

## 6. Functional Requirements

### 6.1 Current System Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-001 | User registration with email/password | P0 | ✅ Done |
| FR-002 | JWT-based authentication | P0 | ✅ Done |
| FR-003 | User approval workflow | P0 | ✅ Done |
| FR-004 | Company profile management | P0 | ✅ Done |
| FR-005 | Company values configuration | P1 | ✅ Done |
| FR-006 | Job vacancy CRUD | P0 | ✅ Done |
| FR-007 | AI job description generation | P1 | ✅ Done |
| FR-008 | Evaluation playbook generation | P0 | ✅ Done |
| FR-009 | Candidate management | P0 | ✅ Done |
| FR-010 | CV upload and parsing | P0 | ✅ Done |
| FR-011 | AI candidate analysis | P0 | ✅ Done |
| FR-012 | Analysis results display | P0 | ✅ Done |
| FR-013 | PDF report generation | P1 | ✅ Done |
| FR-014 | Credit system | P0 | ✅ Done |
| FR-015 | Super admin dashboard | P0 | ✅ Done |
| FR-016 | AI talent tagging | P1 | ✅ Done |

### 6.2 ATS Module Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-100 | Custom recruitment stages per job | P0 | 📋 Planned |
| FR-101 | Drag-and-drop Kanban board | P0 | 📋 Planned |
| FR-102 | Candidate stage history tracking | P0 | 📋 Planned |
| FR-103 | Automated rejection data capture | P0 | 📋 Planned |
| FR-104 | Public job portal | P1 | 📋 Planned |
| FR-105 | Online job application form | P1 | 📋 Planned |
| FR-106 | Funnel conversion analytics | P0 | 📋 Planned |
| FR-107 | Time-to-hire metrics | P1 | 📋 Planned |
| FR-108 | Rejection reasons analytics | P0 | 📋 Planned |
| FR-109 | Source effectiveness tracking | P1 | 📋 Planned |
| FR-110 | Webhook event system | P0 | 📋 Planned |
| FR-111 | Public feedback API | P0 | 📋 Planned |
| FR-112 | Candidate feedback generation | P1 | 📋 Planned |

---

## 7. Non-Functional Requirements

### 7.1 Performance

| Requirement | Target |
|-------------|--------|
| Page load time | < 2 seconds |
| API response time | < 500ms (95th percentile) |
| AI analysis time | < 30 seconds per candidate |
| Concurrent users | 100+ simultaneous |
| Database queries | < 100ms average |

### 7.2 Security

| Requirement | Implementation |
|-------------|----------------|
| Authentication | JWT with 24hr expiry |
| Password storage | bcrypt hashing |
| API security | Bearer token authentication |
| Data isolation | Company-scoped queries |
| Admin access | Separate authentication flow |

### 7.3 Scalability

| Requirement | Approach |
|-------------|----------|
| Database | MongoDB with indexes |
| File storage | Cloud storage ready |
| API | Stateless design |
| Caching | Redis-ready architecture |

### 7.4 Availability

| Requirement | Target |
|-------------|--------|
| Uptime | 99.5% |
| Backup frequency | Daily |
| Recovery time | < 4 hours |

---

## 8. Integration Architecture

### 8.1 System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AIKRUT ECOSYSTEM                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐      ┌──────────────────┐      ┌──────────────┐  │
│  │   HR User    │◄────►│                  │◄────►│  OpenRouter  │  │
│  │  (Browser)   │      │                  │      │   (AI API)   │  │
│  └──────────────┘      │                  │      └──────────────┘  │
│                        │                  │                        │
│  ┌──────────────┐      │     AIKRUT       │      ┌──────────────┐  │
│  │ Super Admin  │◄────►│     CORE         │◄────►│   MongoDB    │  │
│  │  (Browser)   │      │                  │      │  (Database)  │  │
│  └──────────────┘      │                  │      └──────────────┘  │
│                        │                  │                        │
│  ┌──────────────┐      │                  │      ┌──────────────┐  │
│  │  Candidate   │◄────►│                  │─────►│   Webhooks   │  │
│  │ (Job Portal) │      │                  │      │ (External)   │  │
│  └──────────────┘      └──────────────────┘      └──────────────┘  │
│                                 │                       │          │
│                                 ▼                       ▼          │
│                        ┌──────────────────┐    ┌──────────────┐   │
│                        │  Candidate App   │    │   Email      │   │
│                        │  (External)      │    │   Service    │   │
│                        └──────────────────┘    └──────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 Data Flow Overview

```
Candidate Application Flow:
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Apply   │───►│  Parse   │───►│ Analyze  │───►│  Track   │
│  (Form)  │    │   CV     │    │   AI     │    │  Stage   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                      │
                                      ▼
                               ┌──────────┐
                               │ Generate │
                               │ Feedback │
                               └──────────┘
                                      │
                                      ▼
                               ┌──────────┐
                               │  Notify  │
                               │ External │
                               └──────────┘
```

---

## 9. Data & Analytics Requirements

### 9.1 Data Retention

| Data Type | Retention Period |
|-----------|------------------|
| User accounts | Indefinite (until deleted) |
| Job postings | 2 years after closure |
| Candidate data | 2 years after last activity |
| Analysis results | 2 years |
| Application history | 5 years (compliance) |
| Audit logs | 7 years |

### 9.2 Analytics Data Points

**Required Metrics:**
1. Applications per job per day/week/month
2. Conversion rate per stage
3. Average time in each stage
4. Rejection reasons distribution
5. Source effectiveness scores
6. Recruiter productivity metrics
7. AI accuracy metrics (hire vs. score correlation)

---

## 10. API Specifications

### 10.1 Current API Endpoints

**Authentication:**
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user
- `POST /api/admin/login` - Admin login

**Company:**
- `GET /api/company` - Get company
- `POST /api/company` - Create company
- `PUT /api/company` - Update company
- `POST /api/company/generate-values` - AI generate values

**Jobs:**
- `GET /api/jobs` - List jobs
- `POST /api/jobs` - Create job
- `GET /api/jobs/{id}` - Get job
- `PUT /api/jobs/{id}` - Update job
- `DELETE /api/jobs/{id}` - Delete job
- `POST /api/jobs/generate-description` - AI generate description
- `POST /api/jobs/{id}/generate-playbook` - AI generate playbook

**Candidates:**
- `GET /api/candidates` - List candidates
- `POST /api/candidates` - Create candidate
- `GET /api/candidates/{id}` - Get candidate
- `PUT /api/candidates/{id}` - Update candidate
- `DELETE /api/candidates/{id}` - Delete candidate
- `POST /api/candidates/upload-cv` - Upload CV
- `POST /api/candidates/{id}/extract-tags` - AI extract tags

**Analysis:**
- `POST /api/analysis/run-stream` - Run analysis (streaming)
- `GET /api/analysis/job/{job_id}` - Get analyses for job
- `DELETE /api/analysis/{id}` - Delete analysis
- `POST /api/analysis/bulk-delete` - Bulk delete
- `POST /api/analysis/generate-pdf` - Generate PDF report

**Admin:**
- `GET /api/admin/users` - List users
- `PUT /api/admin/users/{id}` - Update user
- `POST /api/admin/users/{id}/approve` - Approve user
- `GET /api/admin/settings` - Get settings
- `PUT /api/admin/settings` - Update settings

### 10.2 Future ATS API Endpoints

**Pipeline Management:**
- `GET /api/jobs/{id}/stages` - Get pipeline stages
- `PUT /api/jobs/{id}/stages` - Update pipeline stages
- `POST /api/jobs/{id}/stages` - Add stage

**Applications:**
- `GET /api/applications` - List applications
- `POST /api/applications` - Create application
- `GET /api/applications/{id}` - Get application
- `PUT /api/applications/{id}/stage` - Move to stage
- `POST /api/applications/{id}/reject` - Reject application

**Analytics:**
- `GET /api/analytics/funnel/{job_id}` - Funnel metrics
- `GET /api/analytics/time-to-hire` - Time metrics
- `GET /api/analytics/rejections` - Rejection analytics
- `GET /api/analytics/sources` - Source effectiveness

**Public API:**
- `GET /api/v1/public/jobs` - Public job listings
- `POST /api/v1/public/apply` - Submit application
- `GET /api/v1/public/feedback/{token}` - Get feedback

**Webhooks:**
- `POST /api/webhooks` - Register webhook
- `GET /api/webhooks` - List webhooks
- `DELETE /api/webhooks/{id}` - Delete webhook

---

## 11. Success Metrics

### 11.1 Business Metrics

| Metric | Current | Target | Timeline |
|--------|---------|--------|----------|
| Time to screen 100 CVs | 8 hours | 30 minutes | Achieved |
| Screening consistency | 60% | 95% | Achieved |
| Qualified candidate identification | 70% | 90% | Q2 2025 |
| User adoption rate | - | 80% | Q2 2025 |

### 11.2 Product Metrics

| Metric | Target |
|--------|--------|
| Daily active users | 50+ |
| Jobs created per month | 100+ |
| Candidates analyzed per month | 1000+ |
| Average analysis accuracy | 85%+ |
| User satisfaction (NPS) | 50+ |

### 11.3 Technical Metrics

| Metric | Target |
|--------|--------|
| API uptime | 99.5% |
| Average response time | < 500ms |
| Error rate | < 1% |
| Successful deployments | 95%+ |

---

## 12. Appendix

### 12.1 Glossary

| Term | Definition |
|------|------------|
| ATS | Applicant Tracking System |
| Playbook | Evaluation criteria template for job positions |
| Analysis | AI-powered candidate-job fit assessment |
| Evidence | Documents supporting candidate qualifications (CV, certificates) |
| Tags | Classification labels for candidate skills and domains |
| Pipeline | Sequence of recruitment stages for a job |
| Funnel | Visualization of candidate progression through stages |

### 12.2 References

- OpenRouter API Documentation
- MongoDB Best Practices
- GDPR Compliance Guidelines
- HR Technology Standards

### 12.3 Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-21 | Aikrut Team | Initial MVP release |
| 1.5 | 2025-01-25 | Aikrut Team | Added Super Admin, Credits |
| 2.0 | 2025-01-28 | Aikrut Team | Added ATS Module specs |

---

*This document is maintained by the Aikrut product team and should be updated with each major feature release.*
