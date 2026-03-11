# AI Development Ground Rules

> **CRITICAL CONTEXT FOR AI ASSISTANTS**
> This document contains the absolute architectural and product constraints for the Aikrut HR Assessment OS platform. 
> Whenever an AI agent assists with development, it MUST prioritize these rules over any existing legacy code patterns found in the codebase.

## 1. The Core Pivot (The "Why")
We have pivoted from a standard job board / external CV screener to an **Internal HR Assessment Operating System (Target: BUMN/CorpU)**.
- We do NOT care about "Job Postings" or "External Sourcing" as the core hero features anymore.
- We DO care about tracking a single employee's **Competency Profile** longitudinally over time.

## 2. Unbreakable Architectural Constraints
1. **Multi-Tenancy is Mandatory:** 
   Every single collection that holds tenant data MUST include `company_id`. This is non-negotiable. No data can be leaked across companies.
   - **Enforcement:** All endpoints MUST use `get_company_id(current_user)` to extract `company_id` from the JWT token. NEVER accept `company_id` from query parameters, request body, or path parameters for data access. Cross-tenant access attempts must return `404 Not Found` (not `403 Forbidden`) to avoid revealing other tenants' data existence.
2. **Two Engines, One Profile:** 
   The platform consumes data from two distinct AI engines (Evidence Screener and Roleplay Simulation). Their outputs must NEVER be merged haphazardly. They must pass through a dedicated **Score Normalization Layer** to be standardized against a BUMN Competency Framework (1-5 scale).
3. **Assessment Session as a State Machine:**
   An assessment is not a simple boolean or a single text field. It is a strict State Machine with the following flow:
   `pending` → `in_progress` → `completed` → `pending_review` → (`approved` / `overridden` / `request_more_info`).
   *Audit trails are critical for enterprise users.* Any override must have an explicit `override_reason`.
4. **AI Recommends, Human Decides:**
   The AI never writes the final state of an employment decision. The final decision MUST be triggered by a human reviewer through the Human Review Layer.

## 3. Development Phasing Rules
- **Layer 1 First:** Do not build engine logic until the Foundation Layer (Competency Library CRUD, Position Builder, Rubric Mapping) is complete.
- **Isolate Temporary Hacks:** If a temporary hardcoded mapping is needed (e.g., mapping old categories to new competency IDs in Phase 1 of the Screener Refactor), it MUST be placed in a dedicated `config` or `constants` file. Never embed hardcoded mappings directly inside primary business logic (`server.py` endpoints).

## 4. Reference Documents
Before making major structural changes or generating complex AI prompts, always refer to:
1. `PRODUCT_VISION.md` (The source of truth for features and user paths)
2. `docs/gap_analysis.md` (The historical breakdown of the pivot from As-Is to To-Be)

---
*If you are an AI reading this, acknowledge these constraints automatically before proposing backend schema or logic changes.*
