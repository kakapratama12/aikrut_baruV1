# HR Assessment Platform — Product Roadmap
> **Version:** 2.1  
> **Last Updated:** March 2026  
> **Status:** Active — Phase 1 IN PROGRESS  
> **Owner:** Solo Founder (AI-assisted: Cursor/Windsurf, Claude, NotebookLM)

---

## TL;DR

Platform all-in-one HR Assessment yang menggabungkan **Evidence Screening** (CV, knowledge test) dan **Roleplay Simulation** (AI persona) ke dalam satu **Competency Profile** per individu — dari hiring hingga promotion.

**Primary Target:** BUMN, Instansi Pemerintah, Corporate University (Corpu)  
**Primary Use Case:** Internal assessment & promotion (bukan hiring eksternal)  
**Business Model:** Subscription (feature access) + Credits (per API consumption)

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
SUBSCRIPTION  →  Unlock fitur platform (freemium tiers)
CREDITS       →  Dikonsumsi per API call:
                   - 1 Evidence Analysis  = X credits
                   - 1 Roleplay Session   = Y credits
                   - Report generation    = gratis (sudah subscribe)
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

**Rationale:** Skala 1-5 adalah standar yang sudah familiar di BUMN/enterprise. Flexibility customize adalah keharusan karena tiap Corpu punya standar sendiri.

---

### D3 — Score Unification ✅
**Keputusan:** Context-based default weight, HR bisa override  
**Detail:**
- Evidence relevance % → dinormalisasi ke skor kompetensi
- Roleplay dimensi 1-5 → dinormalisasi ke skor kompetensi
- System punya default weight yang sensible (roleplay lebih berat dari evidence untuk assessment behavioral)
- HR bisa override bobot per posisi sesuai kebutuhan
- Output ke user: **angka** (competency score) + **narasi** (AI-generated analysis)

---

### D4 — Roleplay API Coupling ✅
**Keputusan:** Abstraction layer — interface defined by appmu, partner adalah implementasi pertama  
**Detail:**
- Partner (Elwyn/Skillana) adalah implementasi pertama di balik abstraction layer
- White-label: tidak ada nama partner yang muncul di appmu
- Interface input/output didefinisikan dari perspektif appmu
- Bisa mock data selama API partner belum ready
- Kalau partner berubah/pivot, hanya mapping layer yang perlu di-update

**Input ke partner (abstracted):**
```json
{
  "persona_config": {},
  "scenario_config": {},
  "rubric_config": {},
  "candidate_id": "",
  "session_metadata": {}
}
```

**Output dari partner (abstracted):**
```json
{
  "overall_score_percent": 0,
  "rubric_total": 0,
  "per_dimension_scores": [],
  "per_dimension_analysis": [],
  "improvements": [],
  "transcript": [],
  "quest_progress": {},
  "knowledge_areas": []
}
```

**Risk:** Partner (Elwyn) built for enterprise clients (HSBC level). Ada signal mereka kehilangan klien besar karena klien build sendiri. Monitor tapi tidak blocking — same ecosystem, same owner.

---

### D5 — Human Layer in Decision Making ✅
**Keputusan:** AI recommend, human decide — selalu, tanpa exception  
**Prinsip:**
- AI tidak pernah "memutuskan" — AI "merekomendasikan dengan reasoning"
- HR / Manager selalu punya final say
- Override harus disertai alasan (untuk audit trail)
- Framing di seluruh UI: *"Rekomendasi AI"* bukan *"Keputusan sistem"*

**Rationale:** BUMN sensitif terhadap akuntabilitas dan compliance. Audit trail harus menunjukkan keputusan dibuat oleh manusia.

---

### D6 — Billing Model ✅
**Keputusan:** Subscription + Credits  
**Detail:**
- Subscription: unlock fitur platform, freemium tiers
- Credits: dikonsumsi per API consumption (evidence analysis + roleplay session)
- Dashboard, report viewing, setup: covered oleh subscription
- Data isolated per company (multi-tenant)

---

### D7 — Database Architecture ✅
**Keputusan:** Clean slate — collections baru, collections lama di-deprecate  
**Rationale:** Evidence screener belum ada paying user dengan data historis kritis. Clean slate lebih aman dan tidak ada risiko merusak data curated user existing.

**Deprecation mapping:**
- `jobs` → diganti `positions`
- `candidates` → diganti `employees`
- `analyses` → diganti `assessment_sessions` + `competency_profiles`

**Separation of concerns (intentional):**
- `competency_profiles` → murni data objektif AI (scores, raw data, narrative)
- `assessment_sessions` → metadata operasional + keputusan subjektif HR

---

## 4. Database Schema

> Approved — Phase 1 implementation reference  
> Semua collections wajib punya `company_id` (multi-tenancy constraint, bukan fitur)

### Master Data Collections

#### `competency_library`
Kamus/pustaka kompetensi standar. Template bawaan dari framework PLN/Astra.

```
_id / competency_id
company_id          (string) — mandatory
name                (string) e.g. "Analytical Thinking"
description         (string)
type                (enum: 'hard_skill' | 'soft_skill')
levels              (array[5]) — deskripsi behavioral per skor 1-5
created_at / updated_at
```

#### `positions`
Menggantikan `jobs`. Standar peran di perusahaan, bukan lowongan.

```
_id / position_id
company_id          (string) — mandatory
title               (string)
department / divisi (string)
level / golongan    (int: 1-6)
required_competencies (array):
  - competency_id   (ref → competency_library)
  - rubric_id       (ref → evaluation_rubrics) — reusable
  - standard_minimum (int: 1-5)
  - weight_evidence  (int: %)
  - weight_roleplay  (int: %)
created_at / updated_at
```

#### `evaluation_rubrics`
Aturan mapping dari Assessment Engine → Competency Library.  
**Reusable lintas posisi** — satu rubrik CARE bisa dipakai di banyak posisi.

```
_id / rubric_id
company_id          (string) — mandatory
name                (string) e.g. "Standard Frontliner Roleplay Rubric"
evidence_mapping    (array) — mapping category_scores → competency_id
                             (hardcoded Phase 1, akan jadi dinamis Phase 2)
roleplay_mapping    (array) — mapping dimensi Elwyn → competency_id
created_at / updated_at
```

> ⚠️ **Note untuk engineer:** `evidence_mapping` yang di-hardcode di Phase 1 harus disimpan sebagai config terpisah (bukan embedded dalam function) agar mudah di-replace di Phase 2 tanpa refactor besar.

### Transactional & User Collections

#### `employees`
Menggantikan `candidates`. Entitas orang yang persisten lintas sesi.

```
_id / person_id
company_id          (string) — mandatory
name                (string)
email               (string)
current_position    (string)
employment_type     (enum: 'internal' | 'external') — default: internal
status              (string: 'aktif' | 'non-aktif')
```

#### `assessment_sessions`
Jantung dari state machine + human review layer.

```
_id / session_id
company_id          (string) — mandatory
person_id           (ref → employees)
target_position_id  (ref → positions)
purpose             (enum: 'promotion' | 'hiring')
status              (enum — state machine):
                      pending → in_progress → completed
                      → pending_review
                      → approved | overridden | request_more_info
                      (request_more_info → kembali ke pending_review)
reviewer_id         (ref → users)
reviewer_notes      (string)
ai_recommendation   (enum: 'promote' | 'hire' | 'not_yet' | 'no')
override_reason     (string) — WAJIB jika final_outcome ≠ ai_recommendation
final_outcome       (enum: 'promoted' | 'hired' | 'not_yet' | 'no')
credits_consumed    (int)
created_at / decided_at
```

> ⚠️ **State machine lay out di Phase 1 (schema level). UI review baru di Phase 3.**

#### `competency_profiles`
Menggantikan `analyses`. Murni hasil objektif AI — terpisah dari keputusan HR.

```
_id / profile_id
session_id          (ref → assessment_sessions)
person_id           (ref → employees)
company_id          (string) — mandatory
competency_scores   (array) — skor normalisasi per competency_id (1-5 + %)
raw_evidence        (object) — JSON mentah dari Evidence Screener
raw_roleplay        (object) — JSON mentah dari Roleplay API
narrative           (object) — AI output: strengths, gaps, summary
```

---

## 5. Build Roadmap

> ⚠️ **Rule:** Setiap phase harus selesai sebelum phase berikutnya dimulai.

---

### Phase 0 — Decision & Validation ✅ COMPLETED

| # | Task | Status |
|---|---|---|
| 1 | Jawab Open Decisions D1-D6 | ✅ Done |
| 2 | Audit Evidence Screener output | ✅ Done — output JSON terdokumentasi |
| 3 | Define database schema Phase 1 | ✅ Done — approved, lihat Section 4 |
| 4 | Gap analysis: As-Is vs To-Be | ✅ Done — engineer reviewed & approved |
| 5 | Validasi framework ke paying user | 🔄 Ongoing — desk research |
| 6 | Review Roleplay API (Elwyn) | 🔄 Partial — API belum ready, analisa dari web-app |

---

### Phase 1 — Foundation Layer 🟡 IN PROGRESS

*Setup system — dikerjakan HR sekali, jadi backbone semua engine*

| # | Task | Subtasks | Dependencies |
|---|---|---|---|
| 1 | **Setup database schema** | Buat collections baru · Deprecate collections lama · Pastikan company_id mandatory di semua collections | D7 |
| 2 | **Competency Library (CRUD)** | Buat/edit/hapus kompetensi · Seed template PLN/Astra · Field levels[1-5] per kompetensi | Task 1 |
| 3 | **Template posisi bawaan** | Digitalisasi posisi dari framework PLN/Astra · List kompetensi default + golongan 1-6 | D2, Task 2 |
| 4 | **Position Builder** | HR create/edit posisi · Assign kompetensi + rubrik · Set standard_minimum + bobot per kompetensi | Task 2, 3 |
| 5 | **Evaluation Rubrics Builder** | HR buat/edit rubrik (CARE, dll) · Deskripsi 1-5 per dimensi · evidence_mapping hardcoded sebagai config · roleplay_mapping | Task 2 |
| 6 | **User roles & permissions** | HR Admin · Manager · Owner/C-Level · Karyawan/Kandidat | Task 1 |
| 7 | **Multi-tenant setup** | Data isolation per company · Company onboarding flow | Task 1, 6 |
| 8 | **Subscription + Credits infra** | Tier management · Credit balance · Consumption tracking per API call | D6 — define freemium tiers dulu |

---

### Phase 2 — Engine Integration

*Evidence + Roleplay berjalan di dalam platform*

| # | Task | Subtasks | Dependencies |
|---|---|---|---|
| 1 | **Refactor Evidence Screener — Tahap 1** | AI tetap output category_scores · Tambah mapping layer di backend (config, bukan hardcode dalam function) · Map ke competency_id | Phase 1, D3 |
| 2 | **Roleplay abstraction layer** | Define interface (input/output) · Mock data untuk development · Connect ke Elwyn API ketika ready | D4 — API Elwyn belum ready |
| 3 | **Assessment session management** | HR trigger sesi · Karyawan/kandidat terima notif + link · State machine transitions | Phase 1, Task 1 schema |
| 4 | **Evidence input expansion** | CV (existing) · Psikotes report · Interview notes · Knowledge test builder | Task 1 |
| 5 | **Score normalization layer** | Evidence % → normalized competency score · Roleplay 1-5 → normalized · Blended dengan bobot D3 | D3, Task 1, 2 |
| 6 | **Promotion flow end-to-end** | HR pilih karyawan → assign assessment → complete → output rekomendasi | Semua task Phase 2 |
| 7 | **Hiring flow end-to-end** | Job posting → kandidat submit → assessment → output | Task 6 |
| 8 | **Refactor Evidence Screener — Tahap 2** | Upgrade prompt AI dengan referensi competency_library · Output lebih structured | Task 1, setelah master data stabil |

---

### Phase 3 — Intelligence Layer

*Platform "berpikir" — gap analysis, decision support, dashboard*

| # | Task | Subtasks | Dependencies |
|---|---|---|---|
| 1 | **Competency Aggregator** | Hitung competency score per individu · Gap vs standar posisi · Gap magnitude | Phase 2 |
| 2 | **AI Narrative Generator** | Overall summary · Key strengths · Development areas · Recommendations | Task 1 |
| 3 | **Human Review Layer UI** | Reviewer notes · Approve / override flow · Override wajib isi alasan · Audit trail display | D5, state machine dari Phase 1 |
| 4 | **Decision Support output** | "Layak promote/hire?" + confidence · Framing: rekomendasi bukan keputusan · Final outcome oleh manusia | Task 2, 3 |
| 5 | **Individual Competency Profile page** | Visual/radar chart per kompetensi · Perbandingan vs standar · History sessions (list) | Task 1-4 |
| 6 | **HR Dashboard** | Pipeline assessment aktif · Status per individu · Export PDF/Excel | Task 5 |
| 7 | **C-Level Dashboard** | Company-wide competency overview · Gap per divisi · View-only | Task 6 |
| 8 | **Notification & workflow** | Email/in-app per stage · Manager approval reminder | Task 3 |

---

### Phase 4 — Post-MVP Enhancements

*Dikerjakan setelah paying user pakai dan feedback masuk. Jangan di-build sebelum ada signal dari user.*

| # | Enhancement | Trigger |
|---|---|---|
| 1 | Longitudinal progress visualization | User request setelah pakai |
| 2 | Training/development recommendation engine | Feedback dari Corpu |
| 3 | Bulk import karyawan | Enterprise onboarding need |
| 4 | Roleplay engine alternatif / in-house | Jika partner risk terealisasi |
| 5 | Hiring flow polish (untuk swasta) | Jika segment swasta mulai convert |
| 6 | Analytics & ROI reporting untuk Corpu | Corpu butuh buktikan value ke manajemen |

---

## 6. Risks & Mitigations

| Level | Risiko | Mitigasi |
|---|---|---|
| 🔴 Critical | Build fitur yang tidak dibutuhkan paying user | Validate dulu sebelum Phase 1 selesai |
| 🟡 Medium | Partner API (Elwyn) belum ready saat Phase 2 | Abstraction layer + mock data — tidak perlu nunggu |
| 🟡 Medium | Enterprise client Elwyn build sendiri (HSBC case) | Same ecosystem mitigates. Abstraction layer protects jangka panjang |
| 🟡 Medium | Competency framework terlalu complex untuk user | "Gamau ribet" sebagai design principle — defaults sensible |
| 🟡 Medium | evidence_mapping hardcode jadi sulit di-replace | Simpan sebagai config file terpisah, bukan embedded dalam function |
| 🟢 Low | Solo founder bottleneck | AI tools aggressively. Ship MVP dulu, iterate. |

---

## 7. Open Items

| # | Item | Priority | Notes |
|---|---|---|---|
| 1 | Elwyn API documentation — kapan ready? | 🔴 High | Blocking untuk Phase 2 Task 2 |
| 2 | Validasi skala 1-5 secara eksplisit dengan paying user | 🔴 High | Desk research bisa substitute sementara |
| 3 | Default weight evidence vs roleplay (D3) — berapa angkanya? | 🟡 Medium | Perlu definisi sebelum Phase 2 Task 5 |
| 4 | Freemium tier — fitur apa yang free vs paid? | 🟡 Medium | Perlu definisi sebelum Phase 1 Task 8 |
| 5 | Volume hiring eksternal vs promotion di target BUMN | 🟡 Medium | Affects feature prioritization Phase 2 |

---

*Living document — update setiap ada keputusan baru.*  
*Setiap perubahan Decisions Log harus disertai tanggal dan rationale.*