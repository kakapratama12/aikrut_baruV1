# Aikrut - Entity Relationship Diagram (ERD)

**Version:** 2.0  
**Last Updated:** January 28, 2025

---

## 1. Current System ERD

### 1.1 Visual Diagram (Text Representation)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              AIKRUT DATABASE SCHEMA                             │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐          ┌──────────────────┐          ┌──────────────────┐
│      USERS       │          │    COMPANIES     │          │   ADMIN_SETTINGS │
├──────────────────┤          ├──────────────────┤          ├──────────────────┤
│ PK id: UUID      │          │ PK id: UUID      │          │ PK type: String  │
│    email: String │    ┌────►│    name: String  │          │    rates: Object │
│    password: Hash│    │     │    description   │          │    openrouter_   │
│    name: String  │    │     │    industry      │          │      api_key     │
│ FK company_id ───┼────┘     │    website       │          │    model_name    │
│    credits: Float│          │    values: Array │          │    default_      │
│    is_approved   │          │    created_at    │          │      credits     │
│    is_active     │          │    updated_at    │          └──────────────────┘
│    created_at    │          └──────────────────┘
└──────────────────┘                   │
        │                              │
        │                              │ 1:N
        │                              ▼
        │                    ┌──────────────────┐
        │                    │       JOBS       │
        │                    ├──────────────────┤
        │                    │ PK id: UUID      │
        │               ┌───►│ FK company_id    │
        │               │    │    title: String │
        │               │    │    description   │
        │               │    │    requirements  │
        │               │    │    location      │
        │               │    │    employment_   │
        │               │    │      type        │
        │               │    │    salary_range  │
        │               │    │    playbook:     │
        │               │    │      Object      │
        │               │    │    status        │
        │               │    │    created_at    │
        │               │    │    updated_at    │
        │               │    └──────────────────┘
        │               │              │
        │               │              │ 1:N
        │               │              ▼
        │               │    ┌──────────────────┐
        │               │    │    ANALYSES      │
        │               │    ├──────────────────┤
        │               │    │ PK id: UUID      │
        │               │    │ FK job_id ───────┼──────┐
        │               │    │ FK candidate_id ─┼────┐ │
        │               │    │    candidate_    │    │ │
        │               │    │      name        │    │ │
        │               │    │    final_score   │    │ │
        │               │    │    category_     │    │ │
        │               │    │      scores      │    │ │
        │               │    │    overall_      │    │ │
        │               │    │      reasoning   │    │ │
        │               │    │    company_      │    │ │
        │               │    │      values_     │    │ │
        │               │    │      alignment   │    │ │
        │               │    │    strengths     │    │ │
        │               │    │    gaps          │    │ │
        │               │    │    created_at    │    │ │
        │               │    └──────────────────┘    │ │
        │               │                            │ │
        │               │                            │ │
        │               │    ┌──────────────────┐    │ │
        │               │    │   CANDIDATES     │◄───┘ │
        │               │    ├──────────────────┤      │
        │               └────┤ PK id: UUID      │      │
        │                    │ FK company_id    │      │
        │                    │    name: String  │      │
        │                    │    email: String │      │
        │                    │    phone: String │      │
        │                    │    evidence:     │      │
        │                    │      Array       │      │
        │                    │    tags: Array   │      │
        │                    │    deleted_tags  │      │
        │                    │    created_at    │      │
        │                    │    updated_at    │      │
        │                    └──────────────────┘      │
        │                                              │
        │                                              │
        │         ┌──────────────────┐                 │
        │         │ CREDIT_USAGE_LOGS│                 │
        │         ├──────────────────┤                 │
        └────────►│ PK id: UUID      │                 │
                  │ FK user_id       │                 │
                  │    operation_    │                 │
                  │      type        │                 │
                  │    tokens_used   │                 │
                  │    openrouter_   │                 │
                  │      cost        │                 │
                  │    credits_      │                 │
                  │      charged     │                 │
                  │    model_used    │                 │
                  │    created_at    │                 │
                  └──────────────────┘                 │
                                                       │
        ┌──────────────────┐                           │
        │    SETTINGS      │                           │
        ├──────────────────┤                           │
        │ FK user_id       │◄──────────────────────────┘
        │    openrouter_   │
        │      api_key     │
        │    model_name    │
        │    language      │
        └──────────────────┘
```

---

### 1.2 Entity Definitions

#### 1.2.1 Users

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique user identifier |
| email | String | UNIQUE, NOT NULL | User email address |
| password | String | NOT NULL | Bcrypt hashed password |
| name | String | NOT NULL | User display name |
| company_id | UUID | FK → Companies | Associated company |
| credits | Float | DEFAULT 0.0 | Available AI credits |
| is_approved | Boolean | DEFAULT false | Admin approval status |
| is_active | Boolean | DEFAULT false | Account active status |
| created_at | DateTime | NOT NULL | Registration timestamp |

**Indexes:**
- `email` (unique)
- `id` (unique)
- `company_id`
- `is_approved`
- `is_active`
- `created_at`

---

#### 1.2.2 Companies

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique company identifier |
| name | String | NOT NULL | Company name |
| description | String | | Company description |
| industry | String | | Industry sector |
| website | String | | Company website URL |
| values | Array[Object] | | Company values with weights |
| created_at | DateTime | NOT NULL | Creation timestamp |
| updated_at | DateTime | NOT NULL | Last update timestamp |

**Values Array Structure:**
```json
[
  {
    "id": "uuid",
    "name": "string",
    "description": "string",
    "weight": "number (0-100)"
  }
]
```

**Indexes:**
- `id` (unique)

---

#### 1.2.3 Jobs

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique job identifier |
| company_id | UUID | FK → Companies, NOT NULL | Parent company |
| title | String | NOT NULL | Job title |
| description | String | NOT NULL | Job description |
| requirements | String | NOT NULL | Job requirements |
| location | String | | Work location |
| employment_type | String | DEFAULT 'full-time' | Employment type |
| salary_range | String | | Salary range |
| playbook | Object | | Evaluation playbook |
| status | String | DEFAULT 'open' | Job status |
| created_at | DateTime | NOT NULL | Creation timestamp |
| updated_at | DateTime | NOT NULL | Last update timestamp |

**Playbook Structure:**
```json
{
  "character": [
    {"id": "uuid", "name": "string", "description": "string", "weight": "number"}
  ],
  "requirement": [
    {"id": "uuid", "name": "string", "description": "string", "weight": "number"}
  ],
  "skill": [
    {"id": "uuid", "name": "string", "description": "string", "weight": "number"}
  ]
}
```

**Indexes:**
- `id` (unique)
- `company_id`
- `created_at`

---

#### 1.2.4 Candidates

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique candidate identifier |
| company_id | UUID | FK → Companies, NOT NULL | Parent company |
| name | String | NOT NULL | Candidate name |
| email | String | NOT NULL | Candidate email |
| phone | String | | Candidate phone |
| evidence | Array[Object] | | Documents/evidence |
| tags | Array[Object] | | Classification tags |
| deleted_tags | Array[String] | | Blacklisted tag values |
| created_at | DateTime | NOT NULL | Creation timestamp |
| updated_at | DateTime | NOT NULL | Last update timestamp |

**Evidence Structure:**
```json
[
  {
    "type": "cv | psychotest | certificate | other",
    "file_name": "string",
    "content": "string (parsed text)",
    "uploaded_at": "datetime",
    "source": "string"
  }
]
```

**Tags Structure:**
```json
[
  {
    "tag_value": "string",
    "layer": "1 | 2 | 3 | 4",
    "layer_name": "string",
    "source": "AUTO | MANUAL",
    "confidence_score": "number (0-1)",
    "created_at": "datetime"
  }
]
```

**Indexes:**
- `id` (unique)
- `company_id`
- `email`
- `created_at`

---

#### 1.2.5 Analyses

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique analysis identifier |
| job_id | UUID | FK → Jobs, NOT NULL | Associated job |
| candidate_id | UUID | FK → Candidates, NOT NULL | Associated candidate |
| candidate_name | String | | Cached candidate name |
| final_score | Float | NOT NULL | Overall fit score (0-100) |
| category_scores | Array[Object] | | Per-category scores |
| overall_reasoning | String | | AI reasoning summary |
| company_values_alignment | Object | | Culture fit assessment |
| strengths | Array[String] | | Identified strengths |
| gaps | Array[String] | | Identified gaps |
| created_at | DateTime | NOT NULL | Analysis timestamp |

**Category Scores Structure:**
```json
[
  {
    "category": "character | requirement | skill",
    "score": "number (0-100)",
    "breakdown": [
      {
        "item_id": "uuid",
        "item_name": "string",
        "raw_score": "number (0-100)",
        "weight": "number",
        "weighted_score": "number",
        "reasoning": "string"
      }
    ]
  }
]
```

**Indexes:**
- `id` (unique)
- `job_id`
- `candidate_id`
- `created_at`

---

#### 1.2.6 Settings

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| user_id | UUID | FK → Users, UNIQUE | Associated user |
| openrouter_api_key | String | | User's API key (legacy) |
| model_name | String | DEFAULT 'openai/gpt-4o-mini' | Preferred AI model |
| language | String | DEFAULT 'en' | Preferred language |

---

#### 1.2.7 Admin_Settings

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| type | String | PK | Setting type identifier |
| rates | Object | | Credit rate multipliers |
| openrouter_api_key | String | | Global API key |
| model_name | String | | Global model setting |
| default_credits_new_user | Float | | Default credits on approval |

---

#### 1.2.8 Credit_Usage_Logs

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique log identifier |
| user_id | UUID | FK → Users, NOT NULL | Associated user |
| operation_type | String | NOT NULL | Type of AI operation |
| tokens_used | Integer | NOT NULL | Tokens consumed |
| openrouter_cost | Float | NOT NULL | Actual API cost |
| credits_charged | Float | NOT NULL | Credits deducted |
| model_used | String | NOT NULL | AI model used |
| created_at | DateTime | NOT NULL | Log timestamp |

**Indexes:**
- `id` (unique)
- `user_id`
- `created_at`

---

## 2. Future ATS Module ERD

### 2.1 Visual Diagram (Text Representation)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ATS MODULE DATABASE SCHEMA                            │
└─────────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────┐
    │       JOBS       │
    │   (existing)     │
    └────────┬─────────┘
             │
             │ 1:1
             ▼
    ┌──────────────────┐         ┌──────────────────┐
    │  JOB_PIPELINES   │         │ PIPELINE_STAGES  │
    ├──────────────────┤         ├──────────────────┤
    │ PK id: UUID      │    1:N  │ PK id: UUID      │
    │ FK job_id ───────┼────────►│ FK pipeline_id   │
    │    created_at    │         │    name: String  │
    │    updated_at    │         │    order: Int    │
    └──────────────────┘         │    is_automated  │
                                 │    auto_action   │
                                 │    auto_threshold│
                                 │    created_at    │
                                 └────────┬─────────┘
                                          │
                                          │ 1:N
                                          ▼
    ┌──────────────────┐         ┌──────────────────┐
    │   CANDIDATES     │         │  APPLICATIONS    │
    │   (existing)     │         ├──────────────────┤
    └────────┬─────────┘         │ PK id: UUID      │
             │                   │ FK job_id        │
             │ 1:N               │ FK candidate_id ─┼────┘
             └──────────────────►│ FK current_      │
                                 │   stage_id       │
                                 │    source        │
                                 │    status        │
                                 │    applied_at    │
                                 │    hired_at      │
                                 │    rejected_at   │
                                 │    created_at    │
                                 │    updated_at    │
                                 └────────┬─────────┘
                                          │
                                          │ 1:N
                                          ▼
                                 ┌──────────────────┐
                                 │ STAGE_HISTORY    │
                                 ├──────────────────┤
                                 │ PK id: UUID      │
                                 │ FK application_id│
                                 │ FK stage_id      │
                                 │    entered_at    │
                                 │    exited_at     │
                                 │    outcome       │
                                 │    moved_by      │
                                 │    notes         │
                                 └────────┬─────────┘
                                          │
                                          │ 1:1 (optional)
                                          ▼
                                 ┌──────────────────┐
                                 │ REJECTION_DATA   │
                                 ├──────────────────┤
                                 │ PK id: UUID      │
                                 │ FK stage_history │
                                 │   _id            │
                                 │ FK analysis_id   │
                                 │    reason_code   │
                                 │    auto_rejected │
                                 │    score         │
                                 │    gaps: Array   │
                                 │    feedback_     │
                                 │      generated   │
                                 │    feedback_token│
                                 │    created_at    │
                                 └──────────────────┘


    ┌──────────────────┐         ┌──────────────────┐
    │    WEBHOOKS      │         │  WEBHOOK_LOGS    │
    ├──────────────────┤         ├──────────────────┤
    │ PK id: UUID      │    1:N  │ PK id: UUID      │
    │ FK company_id    │────────►│ FK webhook_id    │
    │    url: String   │         │    event_type    │
    │    events: Array │         │    payload       │
    │    secret: String│         │    status_code   │
    │    is_active     │         │    response      │
    │    created_at    │         │    created_at    │
    └──────────────────┘         └──────────────────┘


    ┌──────────────────┐
    │ CANDIDATE_       │
    │ FEEDBACK         │
    ├──────────────────┤
    │ PK id: UUID      │
    │ FK application_id│
    │    token: String │
    │    job_title     │
    │    status        │
    │    summary       │
    │    strengths     │
    │    improvements  │
    │    category_     │
    │      feedback    │
    │    viewed_at     │
    │    created_at    │
    │    expires_at    │
    └──────────────────┘
```

---

### 2.2 New Entity Definitions

#### 2.2.1 Job_Pipelines

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique pipeline identifier |
| job_id | UUID | FK → Jobs, UNIQUE | Associated job |
| created_at | DateTime | NOT NULL | Creation timestamp |
| updated_at | DateTime | NOT NULL | Last update timestamp |

---

#### 2.2.2 Pipeline_Stages

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique stage identifier |
| pipeline_id | UUID | FK → Job_Pipelines | Parent pipeline |
| name | String | NOT NULL | Stage name |
| order | Integer | NOT NULL | Stage order (1-based) |
| is_automated | Boolean | DEFAULT false | Auto-process enabled |
| auto_action | String | | Action type (run_analysis, etc.) |
| auto_threshold | Integer | | Score threshold for pass |
| created_at | DateTime | NOT NULL | Creation timestamp |

---

#### 2.2.3 Applications

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique application identifier |
| job_id | UUID | FK → Jobs, NOT NULL | Target job |
| candidate_id | UUID | FK → Candidates, NOT NULL | Applicant |
| current_stage_id | UUID | FK → Pipeline_Stages | Current stage |
| source | String | NOT NULL | Application source |
| status | String | DEFAULT 'in_progress' | Application status |
| applied_at | DateTime | NOT NULL | Application timestamp |
| hired_at | DateTime | | Hire timestamp |
| rejected_at | DateTime | | Rejection timestamp |
| created_at | DateTime | NOT NULL | Creation timestamp |
| updated_at | DateTime | NOT NULL | Last update timestamp |

**Source Values:** `job_portal`, `manual`, `referral`, `linkedin`, `agency`, `other`

**Status Values:** `in_progress`, `hired`, `rejected`, `withdrawn`, `on_hold`

---

#### 2.2.4 Stage_History

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique history identifier |
| application_id | UUID | FK → Applications | Parent application |
| stage_id | UUID | FK → Pipeline_Stages | Stage reference |
| entered_at | DateTime | NOT NULL | Entry timestamp |
| exited_at | DateTime | | Exit timestamp |
| outcome | String | | Stage outcome |
| moved_by | UUID | FK → Users | User who moved candidate |
| notes | String | | Optional notes |

**Outcome Values:** `passed`, `rejected`, `skipped`, `withdrawn`

---

#### 2.2.5 Rejection_Data

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique rejection identifier |
| stage_history_id | UUID | FK → Stage_History | Associated history |
| analysis_id | UUID | FK → Analyses | AI analysis reference |
| reason_code | String | NOT NULL | Rejection reason code |
| auto_rejected | Boolean | DEFAULT false | System-generated rejection |
| score | Float | | Analysis score at rejection |
| gaps | Array[String] | | Identified gaps |
| feedback_generated | Boolean | DEFAULT false | Feedback created |
| feedback_token | String | UNIQUE | Secure feedback access token |
| created_at | DateTime | NOT NULL | Creation timestamp |

**Reason Codes:** `LOW_SCORE`, `SKILL_GAP`, `EXPERIENCE_GAP`, `CULTURE_MISMATCH`, `WITHDRAWN`, `NO_SHOW`, `OFFER_DECLINED`, `POSITION_FILLED`, `OTHER`

---

#### 2.2.6 Candidate_Feedback

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique feedback identifier |
| application_id | UUID | FK → Applications | Associated application |
| token | String | UNIQUE, NOT NULL | Public access token |
| job_title | String | NOT NULL | Job title (cached) |
| status | String | NOT NULL | Final status |
| summary | String | | General feedback message |
| strengths | Array[String] | | Positive points |
| improvements | Array[String] | | Areas to improve |
| category_feedback | Object | | Per-category feedback |
| viewed_at | DateTime | | First view timestamp |
| created_at | DateTime | NOT NULL | Creation timestamp |
| expires_at | DateTime | NOT NULL | Token expiry |

---

#### 2.2.7 Webhooks

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique webhook identifier |
| company_id | UUID | FK → Companies | Owner company |
| url | String | NOT NULL | Webhook endpoint URL |
| events | Array[String] | NOT NULL | Subscribed events |
| secret | String | NOT NULL | Signing secret |
| is_active | Boolean | DEFAULT true | Webhook enabled |
| created_at | DateTime | NOT NULL | Creation timestamp |

---

#### 2.2.8 Webhook_Logs

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique log identifier |
| webhook_id | UUID | FK → Webhooks | Parent webhook |
| event_type | String | NOT NULL | Event that triggered |
| payload | Object | NOT NULL | Sent payload |
| status_code | Integer | | Response status code |
| response | String | | Response body |
| created_at | DateTime | NOT NULL | Log timestamp |

---

## 3. Relationship Summary

### 3.1 Current System Relationships

| From | To | Type | Description |
|------|-----|------|-------------|
| Users | Companies | N:1 | Multiple users per company |
| Companies | Jobs | 1:N | Company has many jobs |
| Companies | Candidates | 1:N | Company has many candidates |
| Jobs | Analyses | 1:N | Job has many analyses |
| Candidates | Analyses | 1:N | Candidate has many analyses |
| Users | Credit_Usage_Logs | 1:N | User has many usage logs |
| Users | Settings | 1:1 | User has one settings record |

### 3.2 ATS Module Relationships

| From | To | Type | Description |
|------|-----|------|-------------|
| Jobs | Job_Pipelines | 1:1 | Each job has one pipeline |
| Job_Pipelines | Pipeline_Stages | 1:N | Pipeline has many stages |
| Jobs | Applications | 1:N | Job has many applications |
| Candidates | Applications | 1:N | Candidate has many applications |
| Applications | Stage_History | 1:N | Application has stage history |
| Stage_History | Rejection_Data | 1:1 | Optional rejection details |
| Applications | Candidate_Feedback | 1:1 | Optional feedback |
| Companies | Webhooks | 1:N | Company has many webhooks |
| Webhooks | Webhook_Logs | 1:N | Webhook has many logs |

---

## 4. Database Indexes

### 4.1 Current Indexes

```javascript
// Users
db.users.createIndex({ "email": 1 }, { unique: true })
db.users.createIndex({ "id": 1 }, { unique: true })
db.users.createIndex({ "company_id": 1 })
db.users.createIndex({ "is_approved": 1 })
db.users.createIndex({ "created_at": 1 })

// Companies
db.companies.createIndex({ "id": 1 }, { unique: true })

// Jobs
db.jobs.createIndex({ "id": 1 }, { unique: true })
db.jobs.createIndex({ "company_id": 1 })
db.jobs.createIndex({ "created_at": 1 })

// Candidates
db.candidates.createIndex({ "id": 1 }, { unique: true })
db.candidates.createIndex({ "company_id": 1 })
db.candidates.createIndex({ "email": 1 })
db.candidates.createIndex({ "created_at": 1 })

// Analyses
db.analyses.createIndex({ "id": 1 }, { unique: true })
db.analyses.createIndex({ "job_id": 1 })
db.analyses.createIndex({ "candidate_id": 1 })
db.analyses.createIndex({ "created_at": 1 })

// Credit Usage Logs
db.credit_usage_logs.createIndex({ "id": 1 }, { unique: true })
db.credit_usage_logs.createIndex({ "user_id": 1 })
db.credit_usage_logs.createIndex({ "created_at": 1 })
```

### 4.2 ATS Module Indexes (Planned)

```javascript
// Applications
db.applications.createIndex({ "id": 1 }, { unique: true })
db.applications.createIndex({ "job_id": 1 })
db.applications.createIndex({ "candidate_id": 1 })
db.applications.createIndex({ "current_stage_id": 1 })
db.applications.createIndex({ "status": 1 })
db.applications.createIndex({ "applied_at": 1 })
db.applications.createIndex({ "job_id": 1, "status": 1 })  // Compound

// Stage History
db.stage_history.createIndex({ "id": 1 }, { unique: true })
db.stage_history.createIndex({ "application_id": 1 })
db.stage_history.createIndex({ "stage_id": 1 })
db.stage_history.createIndex({ "entered_at": 1 })

// Candidate Feedback
db.candidate_feedback.createIndex({ "token": 1 }, { unique: true })
db.candidate_feedback.createIndex({ "application_id": 1 })
db.candidate_feedback.createIndex({ "expires_at": 1 })

// Webhooks
db.webhooks.createIndex({ "id": 1 }, { unique: true })
db.webhooks.createIndex({ "company_id": 1 })
db.webhooks.createIndex({ "is_active": 1 })
```

---

*Document maintained by Aikrut Engineering Team*
