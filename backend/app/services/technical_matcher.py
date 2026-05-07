import re
import asyncio
from typing import Dict, List
from app.models import BidderDocument
from app.ai.embeddings import index_document, search_similar
from app.ai.ollama_client import OLLAMA_HOST
import httpx

SIMILAR_PROJECT_KEYWORDS = [
    "similar project", "comparable work", "relevant experience",
    "past project", "previous contract", "executed work",
    "completed project", "project experience", "work done",
    "executed contract", "performance certificate",
    "work order", "completion certificate",
    "site photograph", "as-built drawing"
]

TENDER_CATEGORY_KEYWORDS = {
    "construction": ["building", "civil", "structural", "road", "bridge", "dam", "tunnel"],
    "it": ["software", "hardware", "network", "cloud", "data center", "server"],
    "electrical": ["power", "transformer", "substation", "wiring", "electrification"],
    "medical": ["hospital", "clinic", "equipment", "patient", "surgical"],
    "defense": ["army", "military", "crpf", "barrack", "border", "security"]
}


def extract_project_blocks(document_text: str) -> List[str]:
    """Split document into candidate project description blocks."""
    if not document_text:
        return []
    paragraphs = re.split(r'\n\s*\n|\n{2,}', document_text)
    candidates = []
    for para in paragraphs:
        para_lower = para.lower()
        has_project_kw = any(kw in para_lower for kw in SIMILAR_PROJECT_KEYWORDS)
        if has_project_kw and len(para) > 60:
            candidates.append(para.strip())
    return candidates


async def llm_judge_similarity(officer_definition: str, project_description: str) -> Dict:
    """Use DeepSeek R1 to judge if a project is similar to officer's definition."""
    from app.ai.prompts import get_similarity_prompt
    import os

    prompt = get_similarity_prompt(
        officer_definition=officer_definition[:500],
        project_description=project_description[:500]
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": os.getenv("OLLAMA_MODEL", "deepseek-r1"),
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1, "num_predict": 256}
                }
            )
        if response.status_code != 200:
            return {"similar": False, "reason": "LLM unavailable", "confidence": 0.3}

        result = response.json()
        raw = result.get("response", "{}").strip()
        # Clean markdown code fences
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        import json
        parsed = json.loads(raw)
        return {
            "similar": bool(parsed.get("similar", False)),
            "reason": parsed.get("reason", "No explanation"),
            "confidence": float(parsed.get("confidence", 0.5))
        }
    except Exception as e:
        print(f"LLM judge similarity failed: {e}")
        return {"similar": False, "reason": "LLM error", "confidence": 0.3}


async def extract_similar_projects_semantic(document_text: str, officer_definition: str, tender_category: str = "construction") -> dict:
    """Extract similar projects using Qdrant semantic search + DeepSeek R1 verification."""
    if not document_text:
        return {
            "verdict": "NEEDS_REVIEW",
            "reason": "No document text available",
            "projects": [],
            "confidence": 0.3
        }

    # Step 1: Extract candidate project blocks with keyword pre-filter
    candidates = extract_project_blocks(document_text)
    if not candidates:
        return {
            "projects": [],
            "count": 0,
            "confidence": 0.3,
            "reason": "No project experience blocks found in document"
        }

    # Step 2: Index officer's definition into Qdrant (temporary)
    import uuid
    query_id = f"query_{uuid.uuid4().hex[:8]}"
    officer_text = f"{tender_category} project: {officer_definition}"
    indexed = await index_document(query_id, officer_text, {"type": "officer_definition"})

    # Step 3: Index candidate projects and search
    found_projects = []
    for idx, candidate in enumerate(candidates[:20]):  # limit to 20 candidates
        doc_id = f"proj_{uuid.uuid4().hex[:8]}"
        await index_document(doc_id, candidate, {"type": "bidder_project", "index": idx})

    # Step 4: Semantic search — find projects most similar to officer definition
    similar_results = await search_similar(officer_text, limit=min(len(candidates), 10))

    # Step 5: DeepSeek R1 final judgment on top matches
    for result in similar_results:
        if result["score"] < 0.55:
            continue  # Too dissimilar semantically

        payload = result.get("payload", {})
        proj_text = payload.get("text", "")
        if not proj_text:
            continue

        # LLM double-check for high-confidence semantic matches
        llm_result = await llm_judge_similarity(officer_definition, proj_text)

        # Extract structured fields from text
        para_lower = proj_text.lower()
        category_keywords = TENDER_CATEGORY_KEYWORDS.get(tender_category.lower(), TENDER_CATEGORY_KEYWORDS["construction"])
        has_category_match = sum(1 for kw in category_keywords if kw in para_lower)

        project = {
            "text_snippet": proj_text[:300],
            "semantic_score": round(result["score"], 3),
            "llm_similar": llm_result["similar"],
            "llm_reason": llm_result["reason"],
            "llm_confidence": round(llm_result["confidence"], 2),
            "category_matches": has_category_match,
            "combined_confidence": round(min(1.0, result["score"] * llm_result["confidence"] * 1.2), 2)
        }

        # Only count as valid if LLM agrees OR semantic score is very high
        if llm_result["similar"] or result["score"] > 0.80:
            found_projects.append(project)

    # Clean up temporary query vector
    from app.ai.embeddings import delete_document
    delete_document(query_id)

    confidence = min(0.95, 0.5 + len(found_projects) * 0.15) if found_projects else 0.3

    return {
        "projects": found_projects,
        "count": len(found_projects),
        "confidence": confidence,
        "reason": f"Semantic search found {len(similar_results)} candidates, LLM verified {len(found_projects)} similar projects"
    }

async def evaluate_technical(bidder_doc: BidderDocument, criterion: dict) -> dict:
    """Evaluate technical criterion using Qdrant semantic search + DeepSeek R1."""
    tender_category = criterion.get("category", "construction")
    min_projects = criterion.get("min_projects", 3)
    officer_definition = criterion.get("description", f"Similar {tender_category} project experience")

    extracted = await extract_similar_projects_semantic(
        bidder_doc.extracted_text or "",
        officer_definition,
        tender_category
    )

    if extracted.get("verdict") == "NEEDS_REVIEW":
        return {
            "verdict": "NEEDS_REVIEW",
            "reason": extracted["reason"],
            "confidence": 0.3,
            "source_page": 1,
            "verbatim_quote": None
        }

    project_count = extracted["count"]
    confidence = extracted["confidence"]

    if project_count >= min_projects:
        verdict = "ELIGIBLE"
        reason = f"Found {project_count} similar projects (minimum {min_projects} required)"
    elif project_count >= min_projects // 2:
        verdict = "NEEDS_REVIEW"
        reason = f"Found only {project_count} similar projects, minimum is {min_projects} — manual review recommended"
    else:
        verdict = "NOT_ELIGIBLE"
        reason = f"Found {project_count} similar projects, minimum {min_projects} required"

    # Get best project as evidence
    best_project = extracted["projects"][0] if extracted["projects"] else None
    verbatim = best_project["text_snippet"] if best_project else None

    # Flag for confidence gating
    if confidence < 0.70:
        if verdict != "NOT_ELIGIBLE":
            verdict = "NEEDS_REVIEW"
            reason += " — Low confidence in semantic project extraction"

    return {
        "verdict": verdict,
        "reason": reason,
        "confidence": confidence,
        "source_page": 1,
        "verbatim_quote": verbatim,
        "computed_value": project_count,
        "project_details": extracted["projects"][:3]
    }
