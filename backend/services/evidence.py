import io
import logging
import pdfplumber
from typing import List, Dict, Any
from fastapi import HTTPException
from bson import ObjectId
from backend.services.ai_service import call_openrouter

logger = logging.getLogger(__name__)

def parse_pdf(file_content: bytes) -> str:
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        logger.error(f"PDF parsing error: {e}")
        raise HTTPException(status_code=400, detail="Failed to parse PDF file")
    return text.strip()

# Keywords for classifying evidence types
EVIDENCE_KEYWORDS = {
    "cv": [
        "experience", "education", "skills", "work history", "summary", "objective",
        "employment", "career", "professional", "responsibilities", "achievements",
        "qualification", "proficient", "expertise", "background", "profile",
        "pengalaman", "pendidikan", "keahlian", "riwayat", "karir"  # Indonesian
    ],
    "certificate": [
        "certificate", "certified", "certification", "awarded", "completion",
        "achievement", "successfully completed", "has completed", "is hereby",
        "certify", "recognize", "accomplished", "training", "course completion",
        "sertifikat", "sertifikasi", "penghargaan", "telah menyelesaikan"  # Indonesian
    ],
    "diploma": [
        "degree", "diploma", "bachelor", "master", "doctor", "phd", "university",
        "graduate", "conferred", "awarded the degree", "faculty", "school of",
        "cum laude", "magna cum laude", "summa cum laude", "honors", "honour",
        "ijazah", "gelar", "sarjana", "magister", "doktor", "universitas"  # Indonesian
    ],
    "reference": [
        "reference", "recommendation", "to whom it may concern", "i am pleased",
        "i am writing to recommend", "has worked with", "i highly recommend",
        "strong recommendation", "letter of recommendation", "referee",
        "surat rekomendasi", "referensi"  # Indonesian
    ],
    "transcript": [
        "transcript", "academic record", "grade", "gpa", "credits", "semester",
        "course", "cumulative", "academic standing", "course code",
        "transkrip", "nilai", "ipk", "mata kuliah"  # Indonesian
    ]
}

def classify_page_by_keywords(page_text: str) -> tuple:
    """
    Classify a page based on keyword detection.
    Returns (evidence_type, confidence_score)
    """
    if not page_text:
        return ("unknown", 0)
    
    text_lower = page_text.lower()
    scores = {}
    
    for evidence_type, keywords in EVIDENCE_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword in text_lower:
                # Weight longer/more specific keywords higher
                score += len(keyword.split())
        scores[evidence_type] = score
    
    if not scores or max(scores.values()) == 0:
        return ("unknown", 0)
    
    best_type = max(scores, key=scores.get)
    confidence = scores[best_type]
    
    # Require minimum confidence threshold
    if confidence < 2:
        return ("unknown", confidence)
    
    return (best_type, confidence)

def parse_pdf_by_pages(file_content: bytes) -> List[Dict]:
    """
    Parse PDF and return list of pages with their text content.
    Returns: [{"page_num": 1, "text": "...", "has_content": True}, ...]
    """
    pages = []
    try:
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                pages.append({
                    "page_num": i + 1,
                    "text": page_text.strip() if page_text else "",
                    "has_content": bool(page_text and page_text.strip())
                })
    except Exception as e:
        logger.error(f"PDF page parsing error: {e}")
        raise HTTPException(status_code=400, detail="Failed to parse PDF file")
    return pages

async def classify_page_with_ai(page_text: str, api_key: str, model: str) -> str:
    """
    Use AI to classify a page when keyword detection is uncertain.
    """
    if not api_key or not page_text:
        return "cv"  # Default to CV
    
    prompt = f"""Classify this document page into ONE of these categories:
- cv (resume, work experience, skills, education background)
- certificate (certification, course completion, awards)
- diploma (academic degree, graduation document)
- reference (recommendation letter, reference letter)
- transcript (academic transcript, grades)
- other (none of the above)

Document text (first 1500 chars):
{page_text[:1500]}

Return ONLY the category name, nothing else."""

    try:
        messages = [{"role": "user", "content": prompt}]
        response = await call_openrouter(api_key, model, messages, temperature=0.1)
        result = response.strip().lower()
        
        # Validate response
        valid_types = ["cv", "certificate", "diploma", "reference", "transcript", "other"]
        for vt in valid_types:
            if vt in result:
                return vt
        return "cv"  # Default
    except Exception as e:
        logger.warning(f"AI classification failed: {e}")
        return "cv"  # Default to CV on error

async def split_pdf_into_evidence(
    file_content: bytes, 
    file_name: str,
    api_key: str = None, 
    model: str = None
) -> List[Dict]:
    """
    Split a PDF into multiple evidence entries based on content classification.
    Groups consecutive pages of the same type together.
    
    Returns: [{"type": "cv", "content": "...", "pages": [1,2], "file_name": "..."}, ...]
    """
    pages = parse_pdf_by_pages(file_content)
    
    if not pages:
        return []
    
    # Single page - just return as CV (most common case)
    if len(pages) == 1:
        return [{
            "type": "cv",
            "content": pages[0]["text"],
            "pages": [1],
            "file_name": file_name
        }]
    
    # Classify each page
    classified_pages = []
    for page in pages:
        if not page["has_content"]:
            classified_pages.append({"page": page, "type": "empty", "confidence": 0})
            continue
            
        evidence_type, confidence = classify_page_by_keywords(page["text"])
        
        # If low confidence and AI available, try AI classification
        if confidence < 3 and api_key and evidence_type == "unknown":
            evidence_type = await classify_page_with_ai(page["text"], api_key, model)
            confidence = 5  # AI classification gets medium confidence
        
        # Default unknown to CV (most common document type)
        if evidence_type == "unknown":
            evidence_type = "cv"
        
        classified_pages.append({
            "page": page,
            "type": evidence_type,
            "confidence": confidence
        })
    
    # Group consecutive pages of the same type
    evidence_groups = []
    current_group = None
    
    for cp in classified_pages:
        if cp["type"] == "empty":
            continue
            
        if current_group is None:
            current_group = {
                "type": cp["type"],
                "pages": [cp["page"]["page_num"]],
                "texts": [cp["page"]["text"]]
            }
        elif cp["type"] == current_group["type"]:
            # Same type - add to current group
            current_group["pages"].append(cp["page"]["page_num"])
            current_group["texts"].append(cp["page"]["text"])
        else:
            # Different type - save current and start new
            evidence_groups.append(current_group)
            current_group = {
                "type": cp["type"],
                "pages": [cp["page"]["page_num"]],
                "texts": [cp["page"]["text"]]
            }
    
    # Don't forget the last group
    if current_group:
        evidence_groups.append(current_group)
    
    # Build final evidence list
    evidence_list = []
    base_name = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
    
    # Count evidence types for naming
    type_counts = {}
    
    for group in evidence_groups:
        ev_type = group["type"]
        type_counts[ev_type] = type_counts.get(ev_type, 0) + 1
        
        # Create descriptive filename
        if len(evidence_groups) == 1:
            ev_file_name = file_name
        else:
            page_range = f"p{group['pages'][0]}" if len(group['pages']) == 1 else f"p{group['pages'][0]}-{group['pages'][-1]}"
            suffix = f"_{type_counts[ev_type]}" if type_counts[ev_type] > 1 else ""
            ev_file_name = f"{base_name}_{ev_type}{suffix}_{page_range}.pdf"
        
        evidence_list.append({
            "type": ev_type,
            "content": "\n\n".join(group["texts"]),
            "pages": group["pages"],
            "file_name": ev_file_name
        })
    
    return evidence_list

def serialize_doc(doc):
    """Recursively convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            if key == '_id':
                continue  # Skip _id field
            elif isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = serialize_doc(value)
            elif isinstance(value, list):
                result[key] = serialize_doc(value)
            else:
                result[key] = value
        return result
