# HR Assessment Platform — Product Roadmap
> **Version:** 2.2  
> **Last Updated:** March 2026  
> **Status:** Active — Phase 1 COMPLETE (including Task 9 Refactor)  
> **Owner:** Solo Founder (AI-assisted: Cursor/Windsurf, Claude, NotebookLM)

---

## TL;DR

Platform all-in-one HR Assessment yang menggabungkan **Evidence Screening** (CV, knowledge test) dan **Roleplay Simulation** (AI persona) ke dalam satu **Competency Profile** per individu — dari hiring hingga promotion.

**Primary Target:** BUMN, Instansi Pemerintah, Corporate University (Corpu)  
**Primary Use Case:** Internal assessment & promotion (bukan hiring eksternal)  
**Business Model:** Credits per assessment session + masa aktif akun per company

---

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [Architecture Overview](#2-architecture-overview)
3. [Decisions Log](#3-decisions-log)
4. [Database Schema](#4-database-schema)
5. [Build Roadmap](#5-build-roadmap)
6. [Risks & Mitigations](#6-risks--mitigations)
7. [Open Items](#7-open-items)

---

## 1. Product Vision

### Problem Statement

| Segment | Pain Point | Status |
|---|---|---|
| BUMN / Instansi | Pegawai banyak, interview bottleneck, decision lama | ✅ Validated |
| BUMN / Instansi | "Gamau ribet — bayar, urusan beres" | ✅ Validated |
| Corpu (Telkom, PLN, BRI, dll) | Assess gap kompetensi secara scalable | ✅ Validated |
| Corpu | Buktikan ROI training ke manajemen | 🔲 To validate |
| Swasta / Startup | Sourcing + hiring (volume tinggi) | ⚠️ Deferred — sourcing belum tersolve |

### Positioning

```
Bukan: "Tools assessment"
Tapi:  "HR Assessment Operating System"
       — satu profil kompetensi per individu
       — dari hari pertama masuk hingga jadi senior
```

### Core Value Proposition

- **Scalable assessment** — ratusan karyawan bisa diassess paralel tanpa bottleneck interviewer
- **Two engines, one language** — Evidence + Roleplay berbicara dalam bahasa kompetensi yang sama
- **AI recommend, human decide** — AI tidak menggantikan HR, AI membantu HR memutuskan lebih cepat dan objektif
- **Longitudinal competency tracking** — progress kompetensi dari waktu ke waktu (differentiator utama)
- **Minimal setup** — template ready-to-use, "gamau ribet" sebagai design principle

### As-Is vs To-Be

```
SEKARANG
CV + Knowledge Test → AI relevance check → Rekomendasi hire

TARGET
Evidence (CV, test, dll)  ─┐
                            ├→ Competency Profile → Gap Analysis → Decision Support
Roleplay Simulation       ─┘   (per individu)       (vs standar)    (AI + Human layer)
```

---

## 2. Architecture Overview

### 3-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1 — FOUNDATION                                       │
│  Competency Library · Position Builder · Rubrik Template    │
│  → Standar kompetensi per posisi, dikustomisasi oleh HR     │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  LAYER 2 — ENGINES                                          │
│  Evidence Screener (existing) · Roleplay Engine (API)       │
│  → Raw scores per attribute / dimensi rubrik                │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  LAYER 3 — INTELLIGENCE                                     │
│  Competency Aggregator · Gap Analysis · Decision Support    │
│  Dashboard HR · Dashboard C-Level                           │
│  → Profil kompetensi individu + rekomendasi actionable      │
└─────────────────────────────────────────────────────────────┘
```

### User Roles & Access

| Role | Access Level | Fungsi Utama |
|---|---|---|
| HR Admin | Full access | Setup posisi, rubrik, trigger assessment, review hasil |
| Manager / Atasan | Review + approve | Lihat hasil, tambah notes, final approval |
| Owner / C-Level | View-only dashboard | Company-wide competency overview |
| Kandidat / Karyawan | Assessment only | Akses sesi assessment mereka sendiri |

### Billing Model

```
CREDITS       →  Dikonsumsi per assessment session:
                   - 1 Evidence Analysis    = 10 credits
                   - 1 Roleplay Session     = 25 credits
                   - 1 Competency Scoring   = 5 credits
                   - Dashboard & report     = gratis

MASA AKTIF    →  Di-set oleh Super Admin saat onboarding company
                   - Credits habis  → assessment locked, report tetap bisa akses
                   - Expired        → seluruh akses locked

PRICING       →  Ditentukan per deal (bukan self-serve)
                   Top up via Super Admin panel
                   Angka credits baseline editable via admin settings
```

---

## 3. Decisions Log

> Semua keputusan product yang sudah final. Jangan diubah tanpa diskusi eksplisit.

### D1 — MVP Focus ✅
**Keputusan:** Promotion / Internal Assessment dulu  
**Target Utama:** BUMN, Instansi, Corporate University  
**Rationale:**
- Rekrutmen BUMN sudah centralized — pain point bukan di sourcing
- Corpu butuh assessment & competency tracking untuk karyawan yang sudah ada
- Budget lebih besar di segment ini
- Hiring eksternal tetap di-support (untuk tenaga ahli), tapi bukan hero feature

---

### D2 — Competency Framework ✅
**Keputusan:** Adapt — framework PLN/Astra sebagai template default, skala 1-5  
**Detail:**
- Skala ditampilkan sebagai **1-5** (de facto standard di market Indonesia)
- Di backend dinormalisasi ke **0-100** untuk keperluan agregasi
- Setiap klien bisa customize deskripsi behavioral per level per kompetensi
- Framework PLN/Astra (Hard Skill + Soft Skill, Golongan 1-6) jadi template bawaan
- Corpu yang sudah punya framework sendiri bisa import/customize

---

### D3 — Score Unification ✅
**Keputusan:** Context-based default weight, HR bisa override  
**Detail:**
- Evidence relevance % → dinormalisasi ke skor kompetensi
- Roleplay dimensi 1-5 → dinormalisasi ke skor kompetensi
- System punya default weight yang sensible (roleplay lebih berat untuk behavioral)
- HR bisa override bobot per posisi sesuai kebutuhan
- Output: angka (competency score) + narasi (AI-generated)

---

### D4 — Roleplay API Coupling ✅
**Keputusan:** Abstraction layer — interface defined by appmu, partner adalah implementasi pertama  
**Detail:**
- Partner (Elwyn/Skillana) adalah implementasi pertama di balik abstraction layer
- White-label: tidak ada nama partner yang muncul di appmu
- Bisa mock data selama API partner belum ready
- Kalau partner berubah, hanya mapping layer yang perlu di-update

---

### D5 — Human Layer in Decision Making ✅
**Keputusan:** AI recommend, human decide — selalu, tanpa exception  
**Prinsip:**
- AI tidak pernah "memutuskan" — AI "merekomendasikan dengan reasoning"
- Override harus disertai alasan (untuk audit trail)
- Framing di seluruh UI: *"Rekomendasi AI"* bukan *"Keputusan sistem"*

---

### D6 — Billing Model ✅
**Keputusan:** Credits only — tidak ada subscription tier  
**Detail:**
- Credits dikonsumsi per assessment action (bukan per fitur/bulan)
- Masa aktif akun di-set saat Super Admin onboard company
- Credits habis → assessment locked, dashboard/report tetap bisa akses
- Masa aktif expired → seluruh akses locked
- Credits per-user untuk MVP, company pool di post-MVP
- Top up dan onboarding via Super Admin panel — tidak ada self-serve
- Harga per credit ditentukan per deal

**Rationale:** BUMN budgeting tahunan, butuh angka pasti untuk PO. Model "X karyawan × Y credits = total budget" lebih mudah dijual daripada variable token cost.

---

### D7 — Database Architecture ✅
**Keputusan:** Clean slate — collections baru, collections lama di-deprecate  
**Deprecation mapping:**
- `jobs` → diganti `positions`
- `candidates` → diganti `employees`
- `analyses` → diganti `assessment_sessions` + `competency_profiles`

**Separation of concerns (intentional):**
- `competency_profiles` → murni data objektif AI
- `assessment_sessions` → metadata operasional + keputusan subjektif HR

---

### D8 — Company Onboarding ✅
**Keputusan:** Admin-managed — tidak ada self-service onboarding  
**Detail:**
- Super Admin create company via `/api/admin/companies`
- Self-service routes (`POST/PUT /api/company`) di-disable, return 410 Gone
- `GET /api/company` tetap aktif untuk display purposes
- `company_id` selalu diambil dari JWT token, bukan dari request params

**Rationale:** BUMN/Corpu tidak self-serve onboard. Sales motion adalah demo → deal → vendor setup. Self-service juga membuka security gap.

---

## 4. Database Schema

> Approved — Phase 1 implementation reference  
> Semua collections wajib punya `company_id` (multi-tenancy constraint)

### Master Data Collections

#### `competency_library`
```
_id / competency_id
company_id          (string) — mandatory
name                (string)
description         (string)
type                (enum: 'hard_skill' | 'soft_skill')
levels              (array[5] of CompetencyLevel) — {score: 1-5, description: str}
created_at / updated_at
```

#### `positions`
```
_id / position_id
company_id          (string) — mandatory
title               (string)
department / divisi (string)
level / golongan    (int: 1-6)
required_competencies (array):
  - competency_id   (ref → competency_library)
  - rubric_id       (ref → evaluation_rubrics) — nullable, reusable
  - standard_minimum (int: 1-5)
  - weight_evidence  (int: %) — default 50
  - weight_roleplay  (int: %) — default 50
created_at / updated_at
```

> ⚠️ `rubric_id` dan bobot 50/50 adalah placeholder. Direvisit di Phase 2 Task 5.

#### `evaluation_rubrics`
```
_id / rubric_id
company_id          (string) — mandatory
name                (string)
evidence_mapping    (array) — mapping category_scores → competency_id
roleplay_mapping    (array) — mapping dimensi Elwyn → competency_id
created_at / updated_at
```

### Transactional & User Collections

#### `employees`
```
_id / person_id
company_id          (string) — mandatory
name, email         (string)
current_position    (string)
employment_type     (enum: 'internal' | 'external')
status              (string: 'aktif' | 'non-aktif')
```

#### `assessment_sessions`
State machine heart — status transitions:
```
pending → in_progress → completed → pending_review
                                  → approved
                                  → overridden       (override_reason WAJIB)
                                  → request_more_info → kembali ke pending_review
```

Fields:
```
_id / session_id, company_id, person_id, target_position_id
purpose             (enum: 'promotion' | 'hiring')
status              (enum: 7 states di atas)
reviewer_id, reviewer_notes
ai_recommendation   (enum: 'promote' | 'hire' | 'not_yet' | 'no')
override_reason     (string) — WAJIB jika final_outcome ≠ ai_recommendation
final_outcome       (enum: 'promoted' | 'hired' | 'not_yet' | 'no')
credits_consumed    (int)
created_at / decided_at
```

#### `competency_profiles`
```
_id / profile_id
session_id, person_id, company_id
competency_scores   (array) — normalized per competency_id (1-5 + %)
raw_evidence        (object) — JSON mentah dari Evidence Screener
raw_roleplay        (object) — JSON mentah dari Roleplay API
narrative           (object) — AI output: strengths, gaps, summary
```

### Credit System

```
Credit rates (editable via admin_settings, default):
  evidence_analysis   = 2.0x multiplier  (= 10 credits baseline)
  roleplay_session    = 5.0x multiplier  (= 25 credits baseline)
  competency_scoring  = 1.5x multiplier  (= 5 credits baseline)

Enforcement:
  check_user_credits() → cek expiry dulu (403), lalu cek balance (402)
  deduct_credits()     → log ke credit_usage_logs dengan token detail
```

---

## 5. Build Roadmap

> ⚠️ **Rule:** Setiap phase harus selesai sebelum phase berikutnya dimulai.

---

### Phase 0 — Decision & Validation ✅ COMPLETED

| # | Task | Status |
|---|---|---|
| 1 | Jawab Open Decisions D1-D8 | ✅ Done |
| 2 | Audit Evidence Screener output | ✅ Done |
| 3 | Define database schema Phase 1 | ✅ Done |
| 4 | Gap analysis: As-Is vs To-Be | ✅ Done |
| 5 | Validasi framework ke paying user | 🔄 Ongoing |
| 6 | Review Roleplay API (Elwyn) | 🔄 Partial — API belum ready |

---

### Phase 1 — Foundation Layer ✅ COMPLETED
*Commit: `b9458df` — pushed ke GitHub*

| # | Task | Status |
|---|---|---|
| 1 | Setup database schema | ✅ Done |
| 2 | Competency Library CRUD | ✅ Done |
| 3 | Template posisi bawaan (PLN/Astra seed) | ✅ Done |
| 4 | Position Builder CRUD | ✅ Done |
| 5 | Evaluation Rubrics Builder | ✅ Done |
| 6 | User roles & permissions (RBAC) | ✅ Done |
| 7 | Multi-tenant setup & company isolation | ✅ Done |
| 8 | Subscription + Credits infrastructure | ✅ Done |

---

### Task 9 — Codebase Refactor 🟡 NEXT
*Dikerjakan sebelum Phase 2 dimulai*

**Problem:** `server.py` sudah 5,400+ baris (God File anti-pattern). Kalau Phase 2 ditambahkan ke struktur yang sama, file akan mencapai 7,000-8,000+ baris dan menjadi sangat sulit di-maintain, bahkan untuk AI engineer.

**Target struktur:**
```
backend/
├── server.py          # App factory + startup only (~100 lines)
├── models/
│   ├── user.py
│   ├── company.py
│   ├── competency.py
│   ├── position.py
│   ├── rubric.py
│   └── legacy.py      # deprecated models
├── routes/
│   ├── auth.py
│   ├── admin.py
│   ├── competency.py
│   ├── position.py
│   ├── rubric.py
│   └── legacy.py      # deprecated routes
├── services/
│   ├── ai_service.py
│   ├── credit.py
│   └── evidence.py
├── auth/
│   ├── dependencies.py  # get_current_user, RequireRole, get_company_id
│   └── admin.py
└── config.py
```

**Verification wajib setelah refactor:**
- Semua existing tests pass
- Server mount tanpa error
- Semua Phase 1 endpoints masih berjalan normal
- Tidak ada perubahan behavior — pure structural refactor

---

### Phase 2 — Engine Integration
*Dimulai setelah Task 9 selesai*

| # | Task | Subtasks | Dependencies |
|---|---|---|---|
| 1 | **Refactor Evidence Screener — Tahap 1** | Map category_scores → competency_id via config layer | Phase 1, D3 |
| 2 | **Roleplay abstraction layer** | Define interface · Mock data · Connect Elwyn API ketika ready | D4 |
| 3 | **Assessment session management** | HR trigger sesi · State machine transitions · Notifikasi | Phase 1 |
| 4 | **Evidence input expansion** | CV · Psikotes report · Interview notes · Knowledge test | Task 1 |
| 5 | **Score normalization layer** | Evidence % → normalized · Roleplay 1-5 → normalized · Blended score | D3, Task 1, 2 |
| 6 | **Promotion flow end-to-end** | HR pilih karyawan → assign → complete → output rekomendasi | Semua task Phase 2 |
| 7 | **Hiring flow end-to-end** | Job posting → submit → assessment → output | Task 6 |
| 8 | **Refactor Evidence Screener — Tahap 2** | Upgrade prompt dengan competency_library context | Setelah master data stabil |

---

### Phase 3 — Intelligence Layer

| # | Task | Subtasks | Dependencies |
|---|---|---|---|
| 1 | **Competency Aggregator** | Score per individu · Gap vs standar · Gap magnitude | Phase 2 |
| 2 | **AI Narrative Generator** | Summary · Strengths · Development areas · Recommendations | Task 1 |
| 3 | **Human Review Layer UI** | Approve / override · Override wajib isi alasan · Audit trail | D5 |
| 4 | **Decision Support output** | Rekomendasi + confidence · Framing: AI recommend, human decide | Task 2, 3 |
| 5 | **Individual Competency Profile page** | Radar chart · Perbandingan vs standar · History sessions | Task 1-4 |
| 6 | **HR Dashboard** | Pipeline aktif · Status per individu · Export PDF/Excel | Task 5 |
| 7 | **C-Level Dashboard** | Company-wide overview · Gap per divisi · View-only | Task 6 |
| 8 | **Notification & workflow** | Email/in-app per stage · Approval reminder | Task 3 |

---

### Phase 4 — Post-MVP Enhancements
*Dikerjakan setelah paying user pakai dan feedback masuk.*

| # | Enhancement | Trigger |
|---|---|---|
| 1 | Longitudinal progress visualization | User request |
| 2 | Training/development recommendation engine | Feedback dari Corpu |
| 3 | Bulk import karyawan | Enterprise onboarding need |
| 4 | Company-pooled credits (migrasi dari per-user) | Scale need |
| 5 | Roleplay engine alternatif / in-house | Jika partner risk terealisasi |
| 6 | Hiring flow polish (untuk swasta) | Jika segment swasta convert |
| 7 | Analytics & ROI reporting untuk Corpu | Corpu butuh buktikan value |

---

## 6. Risks & Mitigations

| Level | Risiko | Mitigasi |
|---|---|---|
| 🔴 Critical | Build fitur yang tidak dibutuhkan paying user | Validate sebelum Phase 2 dimulai |
| 🟡 Medium | Partner API (Elwyn) belum ready saat Phase 2 | Abstraction layer + mock data |
| 🟡 Medium | Enterprise client Elwyn build sendiri | Same ecosystem mitigates. Abstraction layer protects |
| 🟡 Medium | Competency framework terlalu complex | "Gamau ribet" sebagai design principle |
| 🟡 Medium | server.py God File makin besar | Task 9 refactor sebelum Phase 2 — tidak boleh di-skip |
| 🟡 Medium | Credits per-user confusing (HR Admin 3 punya 0 credits) | Document sebagai best practice onboarding: distribute credits ke semua HR Admin saat setup |
| 🟢 Low | Solo founder bottleneck | AI tools aggressively. Ship MVP dulu, iterate. |

---

## 7. Open Items

| # | Item | Priority | Notes |
|---|---|---|---|
| 1 | Elwyn API documentation — kapan ready? | 🔴 High | Blocking untuk Phase 2 Task 2 |
| 2 | Validasi skala 1-5 dengan paying user | 🔴 High | Desk research bisa substitute sementara |
| 3 | Default weight evidence vs roleplay (D3) — angka pastinya? | 🟡 Medium | Perlu sebelum Phase 2 Task 5 |
| 4 | Volume hiring eksternal vs promotion di target BUMN | 🟡 Medium | Affects Phase 2 prioritization |
| 5 | docs/ERD.md — update ke schema Phase 1 | 🟡 Medium | Dikerjakan saat Task 9 refactor |

---

*Living document — update setiap ada keputusan baru.*  
*Setiap perubahan Decisions Log harus disertai tanggal dan rationale.*