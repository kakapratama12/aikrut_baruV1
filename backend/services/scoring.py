import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from backend.config import db

async def normalize_evidence_score(raw_score: float) -> float:
    """Normalize evidence score ke 0-100."""
    if raw_score is None:
        return None
    return max(0.0, min(100.0, raw_score))

async def normalize_roleplay_score(raw_score: float) -> float:
    """Normalize roleplay score ke 0-100."""
    if raw_score is None:
        return None
    return max(0.0, min(100.0, raw_score))

def score_to_display(score_normalized: float) -> int:
    """Convert 0-100 ke skala 1-5 untuk display."""
    if score_normalized <= 20: return 1
    elif score_normalized <= 40: return 2
    elif score_normalized <= 60: return 3
    elif score_normalized <= 80: return 4
    else: return 5

async def compute_blended_score(
    competency_id: str,
    evidence_score: Optional[float],
    roleplay_score: Optional[float],
    weight_evidence: int,
    weight_roleplay: int,
) -> dict:
    """
    Hitung blended competency score dari evidence + roleplay.
    """
    if evidence_score is None and roleplay_score is None:
        return {
            "score_normalized": 0.0,
            "score_display": 1,
            "is_complete": False,
            "source": "none"
        }

    if evidence_score is None:
        blended = roleplay_score
        source = "roleplay_only"
    elif roleplay_score is None:
        blended = evidence_score
        source = "evidence_only"
    else:
        # Normalize weights kalau tidak total 100
        total_weight = weight_evidence + weight_roleplay
        if total_weight == 0:
            w_ev = 0.5
            w_rp = 0.5
        else:
            w_ev = weight_evidence / total_weight
            w_rp = weight_roleplay / total_weight
            
        blended = (evidence_score * w_ev) + (roleplay_score * w_rp)
        source = "blended"

    return {
        "score_normalized": round(blended, 2),
        "score_display": score_to_display(blended),
        "is_complete": True,
        "source": source
    }

def _find_evidence_score(competency_id: str, session: dict) -> Optional[float]:
    """Helper to extract competency score from evidence_result if exists."""
    evidence_result = session.get("evidence_result", {})
    category_scores = evidence_result.get("category_scores", [])
    
    # In Task 1 we mapped item_name -> competency_id, but for now
    # Evidence Screener still outputs broad categories. Let's do a basic lookup
    # assuming we have target_competency_id or mapped_competency_id 
    # (Simplified for Task 5 implementation)
    
    for score_item in category_scores:
        # If the screener output matches the competency exactly
        if score_item.get("competency_id") == competency_id:
            return float(score_item.get("score", 0))
        # Or if it's stored in a breakdown
        for b in score_item.get("breakdown", []):
            if b.get("mapped_competency_id") == competency_id or b.get("item_name", "").lower() == competency_id.lower():
                return float(score_item.get("score", 0)) # Using category score for the item for now
                
    return None

def _find_roleplay_score(competency_id: str, session: dict) -> Optional[float]:
    """Helper to extract competency score from roleplay_result if exists."""
    roleplay_result = session.get("roleplay_result", {})
    metrics = roleplay_result.get("competency_metrics", [])
    
    for metric in metrics:
        if metric.get("competency_name", "").lower() == competency_id.lower() or metric.get("competency_id") == competency_id:
            return float(metric.get("score_percent", 0))
            
    return None

async def compute_competency_profile(
    session_id: str,
    company_id: str,
) -> list:
    """
    Main function — compute semua competency scores untuk satu session.
    Dipanggil setelah semua evidence dan roleplay selesai.
    """
    # 1. Ambil session + position
    session = await db.assessment_sessions.find_one({
        "id": session_id, "company_id": company_id
    })
    
    if not session:
        return []
        
    position = await db.positions.find_one({
        "id": session.get("target_position_id")
    })
    
    if not position:
        return []

    results = []
    
    # 4. Untuk setiap required_competency di position
    for req_comp in position.get("required_competencies", []):
        competency_id = req_comp.get("competency_id")
        if not competency_id:
            continue
            
        weight_ev = req_comp.get("weight_evidence", 50)
        weight_rp = req_comp.get("weight_roleplay", 50)
        standard_min = req_comp.get("standard_minimum", 3)

        # Match scores dari masing-masing engine
        ev_score_raw = _find_evidence_score(competency_id, session)
        rp_score_raw = _find_roleplay_score(competency_id, session)
        
        ev_score = await normalize_evidence_score(ev_score_raw) if ev_score_raw is not None else None
        rp_score = await normalize_roleplay_score(rp_score_raw) if rp_score_raw is not None else None

        blended = await compute_blended_score(
            competency_id, ev_score, rp_score,
            weight_ev, weight_rp
        )

        results.append({
            "competency_id": competency_id,
            "score_normalized": blended["score_normalized"],
            "score_display": blended["score_display"],
            "source": blended["source"],
            "is_complete": blended["is_complete"],
            "weight_evidence": weight_ev,
            "weight_roleplay": weight_rp,
            "standard_minimum": standard_min,
            "meets_standard": blended["score_display"] >= standard_min,
            "gap_magnitude": round(blended["score_display"] - standard_min, 1)
        })

    return results


def compute_overall_recommendation(competency_scores: list) -> dict:
    if not competency_scores:
        return {"recommendation": "no", "confidence": "low"}

    meets = sum(1 for c in competency_scores if c.get("meets_standard"))
    total = len(competency_scores)
    pct = meets / total

    if pct >= 0.8:
        return {"recommendation": "promote", "confidence": "high"}
    elif pct >= 0.6:
        return {"recommendation": "promote", "confidence": "medium"}
    elif pct >= 0.4:
        return {"recommendation": "not_yet", "confidence": "medium"}
    else:
        return {"recommendation": "no", "confidence": "high"}
