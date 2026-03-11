# ADR 0002: Admin-Managed Multi-Tenancy

**Date:** 2026-03-11
**Status:** Accepted

## Context
The platform needed a company onboarding mechanism. Two options were evaluated:

- **Option A (Self-Service):** Users create their own company via a public endpoint.
- **Option B (Admin-Managed):** Companies are created exclusively by the Super Admin.

Our target market (BUMN/CorpU) follows a sales-driven motion: demo → deal → vendor setup. Self-service company creation is inappropriate for this segment and introduces security risks (e.g., unrestricted tenant creation, data sprawl).

Additionally, the existing self-service routes at `POST/PUT /api/company` allowed any authenticated user to create/update companies, which contradicts enterprise governance requirements.

## Decision
We adopted **Option B (Admin-Managed Onboarding)** with the following implementation:

1. **Super Admin Company CRUD** via `/api/admin/companies` — only platform admins can create, update, or deactivate companies.
2. **User Approval with Assignment** — the `approve_user` flow now requires `company_id` and `role` to be explicitly set by Admin, ensuring no user exists without a tenant.
3. **JWT-Based Tenant Isolation** — `company_id` is embedded in the user's JWT token at approval time and extracted by `get_company_id()` at every data access point. Query parameters are never trusted for tenant identity.
4. **Self-Service Deprecation** — `POST /api/company` and `PUT /api/company` return HTTP 410 Gone. Endpoints are retained (not deleted) to avoid frontend breakage.
5. **Credits at User Level (MVP)** — `credits_balance` at Company level is display-only. Full credit pooling deferred to Task 8.

## Consequences
- **Positive:** Strict tenant isolation enforced at the data access layer. No user can accidentally or maliciously access another company's data. Enterprise governance requirements are met.
- **Negative:** Frontend components that previously called `POST/PUT /api/company` will receive 410 errors and must be updated. The approval flow now requires an existing company, so the Admin must create the company before approving users.
