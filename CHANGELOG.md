# Changelog

All notable changes to the Aikrut platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (currently in `v0.x` pre-release phase).

## [v0.3.0-alpha] - 2026-03-11

### Added
- **Multi-tenant Setup (Admin-Managed Onboarding)**: Implemented strict tenant isolation across the platform. Companies are now created and managed exclusively by the Super Admin via new `/api/admin/companies` endpoints (CRUD + soft-delete).
- **`get_company_id()` Helper**: Introduced a centralized function that extracts `company_id` from the authenticated user's JWT token. All Phase 1 endpoints (Competencies, Positions, Rubrics — 18 endpoints total) now derive `company_id` exclusively from this helper, never from query parameters or request body.
- **Super Admin Company CRUD**: Five new admin-only endpoints for company lifecycle management: `POST`, `GET` (list), `GET` (single), `PUT`, `DELETE` (soft-deactivate) under `/api/admin/companies`.
- **Enhanced User Approval Flow**: `POST /api/admin/users/{user_id}/approve` now accepts a JSON body with `company_id`, `role`, and `credits`. The endpoint validates the target company exists and is active before assignment.
- **Company Model Enhancement**: Added `subscription_tier`, `credits_balance`, `expiry_date`, and `is_active` fields to the Company model for admin-managed companies.

### Changed
- **Tenant Isolation (Breaking)**: All Phase 1 endpoints (`/competencies`, `/positions`, `/rubrics` — including CRUD and seed endpoints) no longer accept `company_id` as a query parameter. The company context is now automatically derived from the user's JWT token. Frontend clients must update API calls accordingly.

### Deprecated
- **Self-service Company Routes**: `POST /api/company` and `PUT /api/company` now return **HTTP 410 Gone**. Company creation and updates are exclusively handled via `/api/admin/companies`. `GET /api/company` remains active for users to read their own company data.

### Security
- **Cross-tenant Data Leak Prevention**: Previously, any authenticated user could pass an arbitrary `company_id` query parameter to access another company's competencies, positions, or rubrics. This is now blocked — `company_id` is always extracted from the JWT token, making cross-tenant queries impossible.
- **Cross-tenant 404 (not 403)**: Attempting to access a resource belonging to another company returns `404 Not Found` instead of `403 Forbidden`, preventing information leakage about other tenants' data existence.

## [v0.2.0-alpha] - 2026-03-09

### Added
- **Architectural Pivot (HR Assessment OS)**: Transitioned the platform's core vision from an external CV Screening tool to an internal BUMN-focused HR Assessment Operating System.
- **Competency Library**: Implemented Phase 1 database schemas and CRUD API endpoints for managing the core `CompetencyLibrary`, complete with a seeder for the default PLN/Astra competency framework (scores 1-5).
- **Position Builder**: Added CRUD APIs for Position management (`company_id` enforced), featuring dynamic `required_competencies` via full array replacement pattern, and Golongan 1-6 template seeding.
- **Evaluation Rubrics**: Introduced dynamic, configurable `evidence_mapping` and `roleplay_mapping` structures that connect output weights to a `competency_id` directly within the JSON array (without hardcoding functions) via `/rubrics` CRUD endpoints.
- **Role-Based Access Control (RBAC)**: Implemented `UserRole` enum (`hr_admin`, `manager`, `viewer`, `employee`) natively within the `User` model along with a `RequireRole` FastAPI dependency to protect Phase 1 endpoints. Fastapi HTTPBearer automatically returns 403 on missing credentials and bad scopes now effectively block unauthorized actions.
- **Assessment Sessions**: Added robust State Machine logic (7 states including `request_more_info`) to handle the assessment review lifecycle, bridging AI recommendations with final Human-in-the-Loop outcomes.
- **Architectural Guardrails**: Introduced `docs/AI_DEVELOPMENT_RULES.md` and `.cursorrules` to strictly enforce multi-tenancy (`company_id`), object-based competency levels, and the separation of objective profile data from subjective review sessions.


### Changed
- **Core Entities**: Shifted focus from `jobs` and `candidates` to `positions`, `employees`, `evaluation_rubrics`, and `competency_profiles`.

### Deprecated
- **Legacy Collections**: Marked the legacy `jobs`, `candidates`, and `analyses` collections as deprecated inside the backend models to prevent further writes during the transition phase.

## [v0.1.1-alpha] - 2026-02-21

### Added
- **Job Deletion**: Added a delete button (trash icon) on each job card in the Job Vacancies list, with a confirmation dialog to prevent accidental deletions.
- **Product Vision**: Promoted a high-level `PRODUCT_VISION.md` to establish Aikrut's core goals, capabilities, and design principles.

### Changed
- **Job Edit Layout**: Refactored the "Role Structure" and "Job Information" columns to a fluid flexbox architecture. Panels now intelligently bound themselves to the viewport (`calc(100vh - 270px)`), and textareas divide the remaining space without triggering internal scrollbars.
- **Credit Indicator**: Replaced the misleading `$` (DollarSign) icon in the TopBar with a neutral `Coins` token icon to clarify that credits are not real currency.

### Fixed
- **Job List Crash**: Fixed a Pydantic validation error that caused the `/jobs` API to return 500 when legacy jobs with string-based descriptions existed in the database. The schema now accepts both `dict` and `str` formats for backwards compatibility.
- **Sticky TopBar**: The page header (title + credit balance) now stays pinned at the top when scrolling, instead of scrolling away with the content.
- **Job Card Alignment**: The "Playbook ready" footer row and trash icon on job cards are now always anchored to the bottom of each card, regardless of varying content heights.

## [v0.1.0-alpha] - 2026-02-21

### Added
- **Job Edit UI**: Implemented the "Rumah Sendiri" (Structured Fields) UI for Job Descriptions and Requirements, replacing the standard textareas.
- **AI Job Generation**: Upgraded the AI prompt to use an executive HR tone, enforcing strict JSON structures with specific sections (*About the Role*, *Key Responsibilities*, *What You'll Do*, *Required Experience*, *Required Skills*, *Qualifications*, *Nice-to-Haves*).
- **PDF Reporting**: Enhancements to `/analysis/generate-pdf` to dynamically read and elegantly format the new structured JSON job descriptions using ReportLab logic and proper sub-headers.
- **Changelog**: Introduced `CHANGELOG.md` to track version history and feature updates during the MVP development phase.

### Security
- **Hardcoded Secrets**: Removed hardcoded secrets and JWT keys from the codebase.
- **Environment Variables**: Enforced strict environment variable dependencies `SUPER_ADMIN_PASSWORD`, `JWT_SECRET`, `ADMIN_JWT_SECRET`, and `CORS_ORIGINS`.
- **CORS**: Updated CORS middleware in the backend to utilize environment-defined origins instead of wildcards where applicable.
- **Prompt Injection**: Refactored OpenRouter API logic to rigidly separate System instructions from raw User Input (like CV parsed texts) to mitigate prompt-injection vulnerabilities.
- **Rate Limiting**: Integrated `slowapi` to protect critical Auth and AI-generation endpoints from abuse and brute-force attacks.
- **Nginx Headers**: Added essential `Content-Security-Policy` configurations to production Nginx.
