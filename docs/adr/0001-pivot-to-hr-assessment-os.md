# ADR 0001: Pivot to HR Assessment OS

**Date:** 2026-03-09
**Status:** Accepted

## Context
Aikrut initially started as a CV screening automation tool targeting external hiring processes. The core entity was the `Candidate` and their match score against a specific `Job` posting.

However, based on market feedback and strategic alignment, the target user base has shifted towards internal HR teams in large enterprises (BUMN, Astra, etc.) focusing on:
- Internal mobility
- Promotion assessments
- Longitudinal employee development tracking

These organizations require standardized competency frameworks (e.g., AKHLAK for BUMN) where employees are assessed on specific behaviors on a 1-5 scale over time. The old "CV vs Job Description" model could not holistically capture this longitudinal, profile-centric data.

## Decision
We have decided to architecturally pivot the platform to an **HR Assessment Operating System (OS)**. 

Key architectural changes include:
1. **Core Entity Shift:** Moving away from ephemeral `Candidate`/`Job` pairings to a persistent `Employee` and `CompetencyProfile`.
2. **Standardized Master Data:** Introducing a central `CompetencyLibrary` defining Hard/Soft skills and distinct 1-5 level descriptions.
3. **Assessment Sessions State Machine:** Implementing an `AssessmentSession` model with a strict 7-state lifecycle (`pending`, `in_progress`, `completed`, `pending_review`, `approved`, `overridden`, `request_more_info`) to separate AI recommendations from the final Human-In-The-Loop decisions.
4. **Data Isolation (Multi-Tenancy):** Mandating `company_id` at the root of all new collections to ensure strict tenant isolation.
5. **Deprecation:** Freezing legacy collections (`candidates`, `jobs`, `analyses`) and completely preventing new writes to them in Phase 1.

## Consequences
- **Positive:** We now have a robust data model capable of supporting enterprise-grade employee profiling and assessment. The architecture separates AI extraction logic from human governance natively.
- **Negative:** We must maintain two parallel codebases/routers temporarily (legacy vs. OS) and eventually retire the old screens. There is no automated migration path for existing legacy beta data; we are starting with a clean slate for the OS.
