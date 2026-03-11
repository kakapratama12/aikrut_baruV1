# Gap Analysis: CV Screener to HR Assessment OS

Berdasarkan *update* pada `PRODUCT_VISION.md`, kita sedang melakukan pivot besar dari sekadar **alat bantu screening CV (hiring eksternal)** menjadi **Operating System untuk HR Assessment (fokus internal/promotion)**.

Berikut adalah hasil analisis *gap* antara kondisi sistem saat ini (As-Is) dengan target visi baru (To-Be), beserta dampaknya secara teknis.

---

## 1. Perbedaan Mendasar (Gap Analysis)

| Aspek | Kondisi Saat Ini (As-Is) | Visi Baru (To-Be) | Gap (Apa yang kurang?) |
|---|---|---|---|
| **Target Pengguna & Use Case** | Perusahaan swasta/startup, untuk rekrutmen/hiring eksternal. | **BUMN, Instansi, Corpu**, utamanya untuk **Internal Assessment & Promosi**. | *Mindset* sistem dari "mencari orang baru" menjadi "mengukur dan memetakan orang lama". |
| **Pusat Data (Core Entity)** | **Job Board / Lowongan Pekerjaan.** Sistem berputar pada *Job Posting* dan pelamar (Candidate). | **Competency Profile per Individu.** Sistem berpusat pada karyawan/kandidat secara longitudinal (dari waktu ke waktu). | Kita belum punya struktur `Competency Profile` yang persisten dan terhubung dengan riwayat karyawan. |
| **Sumber Penilaian (Engine)** | Hanya 1 mesin: **Evidence Screener** (parsing CV & Portofolio). | 2 mesin: **Evidence Screener** + **Roleplay Simulation API** (terintegrasi). | Perlu ada layer abstraksi baru untuk Roleplay API dan layer penggabungan (Normalization) dari 2 sumber skor yang berbeda. |
| **Kerangka Penilaian (Framework)** | Menggunakan *Prompt-based AI Playbook* (dinamis, bebas). | **Competency Library Baku** skala 1-5 (contoh: standar PLN/Astra). | Backend saat ini langsung *generate score* bebas dari AI. Kita butuh database Master Kompetensi (Hard/Soft skill) skala 1-5. |
| **Peran Manusia (Decision)** | HR melihat skor akhir dari AI sebagai hasil penentu (semi-final). | **AI Recommend, Human Decide**. AI hanya memberi rekomendasi (*promote/not yet*), atasan/HR memberi *final approval* / *override*. | Perlu ada fitur *Human Review Layer* tersendiri di dalam *workflow* (approval/override dengan alasan). |

---

## 2. Technical Impact (Dampak pada Codebase Saat Ini)

Pivot ini akan mengubah arsitektur aplikasi secara signifikan, dari *monolithic scoring* menjadi *multi-layer architecture*.

### 🔴 Arsitektur & Database Saat Ini (Perbedaan Kritis)
Pada investigasi `backend/server.py` sebelumnya, endpoint `/analysis/run` langsung membuang teks CV ke OpenRouter dan meminta JSON balasan berupa `category_scores` (berdasarkan Playbook: *Character, Requirements, Skills*). 

**Dampak:**
1. **Schema Database Harus Berubah:** 
   Saat ini *collection* `analyses` berisi skor mentah. Ke depannya, ini harus bertransformasi menjadi struktur `CompetencyProfile` yang menyimpan riwayat sesi (*assessment session*), data identitas karyawan (*internal vs eksternal*), serta menyimpan *raw data* dari Evidence dan Roleplay secara terpisah.
   **Keputusan Engineer:** Kita akan membuat *collection* baru (`competency_profiles`, `assessment_sessions`, dll) dan men-*deprecate* collection lama. Migrasi data lama tidak diperlukan karena *evidence screener* saat ini belum memiliki *paying user* dengan data historis yang kritis. Pendekatan ini lebih bersih (*clean slate*) dan *zero risk*.
2. **Score Normalization Layer (Baru):**
   Skor dari CV (% atau 0-100) dan skor dari Roleplay (1-5) tidak bisa digabung begitu saja. Harus ada layer normalisasi yang menerjemahkan keduanya ke dalam persentase standar sesuai bobot (Decision D3).
3. **Master Data Baru (Layer 1):**
   Aplikasi membutuhkan *module* CRUD baru untuk **Competency Library** dan **Position/Rubric Builder** karena penilaian tidak lagi sekadar mendeskripsikan *Playbook*, melainkan mengacu ke standar BUMN/Instansi.
4. **Multi-Tenancy (Gap A):**
   Ini adalah *architectural constraint*, bukan sekadar fitur. *Codebase* harus memastikan `company_id` menjadi *mandatory field* di semua *collections* baru (termasuk *master data* dan *transactional data*) sejak hari pertama schema dibuat. Isolasi data antar *tenant* (BUMN/Instansi) adalah harga mati.
5. **State Machine untuk Assessment Session (Gap B):**
   *Workflow review* tidak boleh hanya sekadar *field* status teks biasa. Harus didesain sebagai *State Machine* yang eksplisit:
   `pending` → `in_progress` → `completed` → `pending_review` → (`approved` / `overridden` / `request_more_info`).
   Setiap transisi (terutama *override*) memerlukan validasi ketat (wajib ada alasan) untuk memenuhi kebutuhan *audit trail* BUMN. Logika *state machine* ini harus mulai di-*lay out* pada **Phase 1 (Foundation)** di level database schema, meskipun *UI review*-nya baru akan dibangun di Phase 3.

---

## 3. Rekomendasi Langkah Implementasi (Sesuai Roadmap)

Sesuai *Build Roadmap* (Phase 1), berikut adalah prioritas langkah teknis untuk developer:

**Langkah 1: Setup Schema Database (Competency Profile & State Machine)**
Implementasikan schema `CompetencyProfile` v2 dan `AssessmentSession` (termasuk *state machine logic* dan mandatory `company_id`). Pastikan *backend* siap menerima entitas "Karyawan" (`internal`), bukan hanya "Kandidat" (`eksternal`). Buat *collections* baru, biarkan yang lama *deprecated*.

**Langkah 2: Bangun Foundation Layer (Master Data)**
Buat *endpoints* CRUD untuk **Competency Library**, **Position Builder**, dan **Playbook/Rubric Mapping**. Ini adalah urat nadi platform baru.

**Langkah 3: Refactor Evidence Screener (Pendekatan 2 Tahap yang Lebih Aman)**
Jangan langsung memaksa AI untuk *output* `competency_id` demi mencegah sistem yang rapuh (*brittle prompt*).
- **Tahap 1 (Minimal Refactor - Segera):** AI tetap *output* format `category_scores` (*Character/Requirement/Skill*) seperti sekarang. Buat **Mapping Layer di Backend** (*hardcoded sementara*) yang menerjemahkan `category` tersebut menjadi agregasi `competency_id`. *Catatan Engineer:* Konfigurasi *hardcode* ini akan diletakkan di dalam *config/constants module* terpisah, bukan di-embed langsung ke *business logic function*, agar nanti sangat mudah diganti oleh data dinamis dari DB.
- **Tahap 2 (Post-Foundation):** Setelah *Master Data Competency Library* siap dan stabil, kita *upgrade prompt* AI dengan menyertakan referensi kompetensi sebagai konteks, sehingga AI bisa mengeluarkan *output JSON* yang lebih terstruktur.

**Langkah 4: Bangun Abstraction Layer untuk Roleplay**
Buat *interface* statis (mocking) untuk API Roleplay (sebagai antisipasi API Elwyn/Skillana) agar tim *frontend* bisa mulai membuat UI penggabungan skor *(Intelligence Layer)*.
