"""
Matching service — semua logic scoring & ranking pasangan domba.
"""
from typing import Optional, Dict, List, Tuple
from datetime import datetime

from firestore_service import get_health_record, get_sheep_by_eartag


# ── Lineage / pedigree ──────────────────────────────────────────────────────
def calculate_lineage_conflict(sheep1: Dict, sheep2: Dict) -> Tuple[bool, str]:
    conflicts = []
    if sheep1.get("induk_betina") and sheep1.get("induk_betina") == sheep2.get("induk_betina"):
        conflicts.append("Induk betina sama")
    if sheep1.get("induk_jantan") and sheep1.get("induk_jantan") == sheep2.get("induk_jantan"):
        conflicts.append("Induk jantan sama")
    return len(conflicts) > 0, ", ".join(conflicts) if conflicts else "OK"


def get_ancestors(eartag: str, nama_peternak: str, depth: int = 3, _visited=None) -> List[str]:
    """Telusuri leluhur sampai `depth` generasi ke atas."""
    if _visited is None:
        _visited = set()
    if depth == 0 or not eartag or eartag in _visited:
        return []
    _visited.add(eartag)

    sheep = get_sheep_by_eartag(eartag, nama_peternak)
    if not sheep:
        return []

    ancestors = [eartag]
    for parent in (sheep.get("induk_betina"), sheep.get("induk_jantan")):
        if parent:
            ancestors += get_ancestors(parent, nama_peternak, depth - 1, _visited)
    return ancestors


def score_genetic_diversity(sheep1: Dict, sheep2: Dict, nama_peternak: str) -> float:
    anc1 = set(get_ancestors(sheep1.get("induk_betina"), nama_peternak) +
               get_ancestors(sheep1.get("induk_jantan"), nama_peternak))
    anc2 = set(get_ancestors(sheep2.get("induk_betina"), nama_peternak) +
               get_ancestors(sheep2.get("induk_jantan"), nama_peternak))

    total = anc1 | anc2
    if not total:
        return 30.0

    overlap_ratio = len(anc1 & anc2) / len(total)
    return max(30 * (1 - overlap_ratio), 0)


# ── Health & physical ────────────────────────────────────────────────────────
def score_health(sheep: Dict, health_record: Optional[Dict]) -> float:
    score = 0
    kesehatan = sheep.get("kesehatan", "").lower()
    score += 20 if kesehatan == "sehat" else (5 if kesehatan == "sakit" else 10)

    if health_record:
        keterangan = health_record.get("keterangan", "").lower()
        if "baik sekali" in keterangan or "sangat baik" in keterangan:
            score += 20
        elif "baik" in keterangan:
            score += 15
        elif "kurang" in keterangan:
            score += 5
        else:
            score += 10
    return min(score, 40)


def score_physical(sheep: Dict) -> float:
    score = 30
    keterangan = sheep.get("keterangan", "").lower()
    if "baik" not in keterangan:
        score -= 10
    return score


# ── Aggregate scoring ─────────────────────────────────────────────────────────
def calculate_matching_breakdown(sheep1: Dict, sheep2: Dict, health2: Optional[Dict], nama_peternak: str) -> Dict[str, float]:
    health_score = score_health(sheep2, health2)
    physical_score = score_physical(sheep2)
    genetic_score = score_genetic_diversity(sheep1, sheep2, nama_peternak)

    total = min(health_score + physical_score + genetic_score, 100)
    return {"health": health_score, "physical": physical_score, "genetic": genetic_score, "total": total}


def get_top_matches(sheep: Dict, candidates: List[Dict], nama_peternak: str, limit: int = 5) -> List[Dict]:
    ranked_matches = []
    for candidate in candidates:
        if candidate.get("eartag") == sheep.get("eartag"):
            continue

        has_conflict, _ = calculate_lineage_conflict(sheep, candidate)
        if has_conflict:
            continue

        health_record = get_health_record(candidate.get("eartag"), nama_peternak)
        breakdown = calculate_matching_breakdown(sheep, candidate, health_record, nama_peternak)

        ranked_matches.append({
            "candidate": candidate,
            "score": breakdown["total"],
            "reason": f"Kesehatan {breakdown['health']:.0f}/40, Fisik {breakdown['physical']:.0f}/30, Genetik {breakdown['genetic']:.0f}/30",
            "breakdown": breakdown,
            "health_record": health_record,
        })

    ranked_matches.sort(key=lambda item: (item["score"], str(item["candidate"].get("eartag", ""))), reverse=True)
    return ranked_matches[:limit]