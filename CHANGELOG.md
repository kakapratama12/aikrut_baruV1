# Changelog

All notable changes to the Aikrut platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (currently in `v0.x` pre-release phase).

## [v0.1.1-alpha] - 2026-02-21

### Added
- **Job Deletion**: Added a delete button (trash icon) on each job card in the Job Vacancies list, with a confirmation dialog to prevent accidental deletions.

### Changed
- **Credit Indicator**: Replaced the misleading `$` (DollarSign) icon in the TopBar with a neutral `Coins` token icon to clarify that credits are not real currency.

### Fixed
- **Job List Crash**: Fixed a Pydantic validation error that caused the `/jobs` API to return 500 when legacy jobs with string-based descriptions existed in the database. The schema now accepts both `dict` and `str` formats for backwards compatibility.

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
