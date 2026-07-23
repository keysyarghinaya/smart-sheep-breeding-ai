"""
Firestore service untuk manajemen data domba dan matching algorithm.
"""

import firebase_admin
from firebase_admin import credentials, firestore
from pathlib import Path
from typing import Optional, Dict, List, Tuple


# ── Initialize Firebase ────────────────────────────────────────────────────────
def init_firebase():
    """Initialize Firebase Admin SDK dengan serviceAccountKey.json"""
    try:
        cred_path = Path(__file__).parent / "secrets" / "serviceAccountKey.json"
        
        if not cred_path.exists():
            print(f"[WARN] serviceAccountKey.json not found at {cred_path}")
            return None
        
        cred = credentials.Certificate(str(cred_path))
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("[OK] Firebase initialized successfully")
        return db
    except Exception as e:
        print(f"[ERROR] Firebase initialization failed: {e}")
        return None


# Global Firestore client
db = None

def get_db():
    """Get Firestore client (lazy init)"""
    global db
    if db is None:
        db = init_firebase()
    return db


# ── Sheep data queries ─────────────────────────────────────────────────────────
def get_sheep_by_eartag(eartag: str, nama_peternak: str) -> Optional[Dict]:
    """
    Query domba dari collection 'manajemendomba' berdasarkan eartag dan nama_peternak
    """
    db = get_db()
    if db is None:
        return None
    
    try:
        query = db.collection("manajemendomba").where(
            "eartag", "==", eartag
        ).where(
            "nama_peternak", "==", nama_peternak
        ).limit(1)
        
        docs = query.stream()
        for doc in docs:
            data = doc.to_dict()
            data["_id"] = doc.id  # simpan doc ID untuk reference
            return data
        
        return None
    except Exception as e:
        print(f"[ERROR] Query sheep by eartag failed: {e}")
        return None


def get_candidate_sheep(gender: str, nama_peternak: str) -> List[Dict]:
    """
    Query semua domba dengan kelamin tertentu dari peternakan user.
    gender: "Jantan" atau "Betina"
    """
    db = get_db()
    if db is None:
        return []
    
    try:
        query = db.collection("manajemendomba").where(
            "kelamin", "==", gender
        ).where(
            "nama_peternak", "==", nama_peternak
        )
        
        candidates = []
        for doc in query.stream():
            data = doc.to_dict()
            data["_id"] = doc.id
            candidates.append(data)
        
        return candidates
    except Exception as e:
        print(f"[ERROR] Query candidate sheep failed: {e}")
        return []


def get_health_record(eartag: str, nama_peternak: str) -> Optional[Dict]:
    """
    Ambil record kesehatan terbaru dari collection 'catatan_kesehatan'
    """
    db = get_db()
    if db is None:
        return None
    
    try:
        query = db.collection("catatan_kesehatan").where(
            "eartag", "==", eartag
        ).where(
            "nama_peternak", "==", nama_peternak
        ).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(1)
        
        for doc in query.stream():
            return doc.to_dict()
        
        return None
    except Exception as e:
        print(f"[ERROR] Query health record failed: {e}")
        return None


def get_user_by_email(email: str) -> Optional[Dict]:
    """
    Query user document from 'users' collection by email.
    Returns document dict with fields, or None.
    """
    db = get_db()
    if db is None:
        return None

    try:
        query = db.collection("users").where("email", "==", email).limit(1)
        docs = query.stream()
        for doc in docs:
            data = doc.to_dict()
            data["_id"] = doc.id
            return data
        return None
    except Exception as e:
        print(f"[ERROR] Query user by email failed: {e}")
        return None


# ── Matching algorithm ─────────────────────────────────────────────────────────
def calculate_lineage_conflict(sheep1: Dict, sheep2: Dict) -> Tuple[bool, str]:
    """
    Check apakah ada konflik lineage antara dua domba.
    Returns: (has_conflict, reason)
    
    Rules:
    - Tidak boleh dari induk yang sama
    - Tidak boleh dari kakek/buyut yang sama (jika ada data)
    """
    conflicts = []
    
    # Check induk
    induk_betina_1 = sheep1.get("induk_betina", "")
    induk_jantan_1 = sheep1.get("induk_jantan", "")
    induk_betina_2 = sheep2.get("induk_betina", "")
    induk_jantan_2 = sheep2.get("induk_jantan", "")
    
    if induk_betina_1 and induk_betina_1 == induk_betina_2:
        conflicts.append("Induk betina sama")
    if induk_jantan_1 and induk_jantan_1 == induk_jantan_2:
        conflicts.append("Induk jantan sama")
    
    return len(conflicts) > 0, ", ".join(conflicts) if conflicts else "OK"


def score_health(sheep: Dict, health_record: Optional[Dict]) -> float:
    """
    Score kesehatan domba (0-40 points).
    """
    score = 0
    
    # Base health dari manajemendomba
    kesehatan = sheep.get("kesehatan", "").lower()
    if kesehatan == "sehat":
        score += 20
    elif kesehatan == "sakit":
        score += 5
    else:
        score += 10  # neutral
    
    # Health record dari catatan_kesehatan
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
    
    return min(score, 40)  # max 40


def score_physical(sheep: Dict) -> float:
    """
    Score kondisi fisik domba (0-30 points).
    Bisa diexpand dengan field tambahan seperti bobot_badan, warna, dll.
    """
    score = 30  # default baik
    
    # Jika ada field keterangan/kondisi yang spesifik, bisa di-adjust
    keterangan = sheep.get("keterangan", "").lower()
    if "baik" not in keterangan:
        score -= 10
    
    return score


def score_genetic_diversity(sheep1: Dict, sheep2: Dict) -> float:
    """
    Score genetic diversity (0-30 points).
    Semakin berbeda lineage-nya, semakin tinggi score.
    """
    score = 30
    
    # Jika ada kesamaan dalam garis keturunan (tapi tidak conflict), reduce score
    if sheep1.get("induk_betina") == sheep2.get("induk_betina"):
        score -= 5
    if sheep1.get("induk_jantan") == sheep2.get("induk_jantan"):
        score -= 5
    
    return max(score, 0)


def calculate_matching_score(sheep1: Dict, sheep2: Dict, health2: Optional[Dict]) -> float:
    """
    Calculate overall matching score (0-100).
    Kombinasi: health (40) + physical (30) + genetic (30)
    """
    health_score = score_health(sheep2, health2)
    physical_score = score_physical(sheep2)
    genetic_score = score_genetic_diversity(sheep1, sheep2)
    
    total = health_score + physical_score + genetic_score
    return min(total, 100)


def calculate_matching_breakdown(sheep1: Dict, sheep2: Dict, health2: Optional[Dict]) -> Dict[str, float]:
    """
    Return skor per komponen agar bisa divisualisasikan di UI.
    """
    health_score = score_health(sheep2, health2)
    physical_score = score_physical(sheep2)
    genetic_score = score_genetic_diversity(sheep1, sheep2)

    total = min(health_score + physical_score + genetic_score, 100)
    return {
        "health": health_score,
        "physical": physical_score,
        "genetic": genetic_score,
        "total": total,
    }


def get_top_matches(sheep: Dict, candidates: List[Dict], nama_peternak: str, limit: int = 5) -> List[Dict]:
    """
    Return beberapa kandidat terbaik yang sudah diurutkan dari skor tertinggi.
    """
    ranked_matches = []

    for candidate in candidates:
        if candidate.get("eartag") == sheep.get("eartag"):
            continue

        has_conflict, _ = calculate_lineage_conflict(sheep, candidate)
        if has_conflict:
            continue

        health_record = get_health_record(candidate.get("eartag"), nama_peternak)
        breakdown = calculate_matching_breakdown(sheep, candidate, health_record)

        ranked_matches.append({
            "candidate": candidate,
            "score": breakdown["total"],
            "reason": f"Kesehatan {breakdown['health']:.0f}/40, Fisik {breakdown['physical']:.0f}/30, Genetik {breakdown['genetic']:.0f}/30",
            "breakdown": breakdown,
            "health_record": health_record,
        })

    ranked_matches.sort(
        key=lambda item: (
            item["score"],
            str(item["candidate"].get("eartag", "")),
        ),
        reverse=True,
    )
    return ranked_matches[:limit]


def find_best_match(sheep: Dict, candidates: List[Dict], nama_peternak: str) -> Optional[Dict]:
    """
    Find best matching candidate untuk sheep.
    Returns: {candidate_data, score, reason}
    """
    top_matches = get_top_matches(sheep, candidates, nama_peternak, limit=1)
    if not top_matches:
        return None
    
    best_match = top_matches[0]
    return {
        "candidate": best_match["candidate"],
        "score": best_match["score"],
        "reason": best_match["reason"],
        "breakdown": best_match["breakdown"],
        "health_record": best_match["health_record"],
    }

def add_marriage_record(record: Dict, nama_peternak: str) -> Optional[str]:
    """
    Tambah record perkawinan ke collection riwayatrekomendasi.
    Returns document ID, or None.
    """
    db = get_db()
    if db is None:
        return None

    try:
        doc_ref = db.collection("riwayatrekomendasi").document()
        doc_ref.set({
            "nama_peternak": nama_peternak,
            "sheep_eartag": record.get("sheep_eartag"),
            "candidate_eartag": record.get("candidate_eartag"),
            "match_score": record.get("match_score"),
            "timestamp": record.get("timestamp"),
            "filename": record.get("filename"),
            "created_at": firestore.SERVER_TIMESTAMP,
        })
        return doc_ref.id
    except Exception as e:
        print(f"[ERROR] Add marriage record failed: {e}")
        return None


def get_marriage_history(nama_peternak: str) -> List[Dict]:
    """
    Ambil semua record perkawinan untuk peternakan user,
    diurut dari terbaru.
    """
    db = get_db()
    if db is None:
        return []

    try:
        query = db.collection("riwayatrekomendasi").where(
            "nama_peternak", "==", nama_peternak
        ).order_by("created_at", direction=firestore.Query.DESCENDING)

        records = []
        for doc in query.stream():
            data = doc.to_dict()
            data["_id"] = doc.id
            records.append(data)
        return records
    except Exception as e:
        print(f"[ERROR] Get marriage history failed: {e}")
        return []


def delete_marriage_record(record_id: str) -> bool:
    """
    Hapus satu record perkawinan berdasarkan doc ID.
    Returns True jika berhasil, False jika gagal.
    """
    db = get_db()
    if db is None:
        return False

    try:
        db.collection("riwayatrekomendasi").document(record_id).delete()
        return True
    except Exception as e:
        print(f"[ERROR] Delete marriage record failed: {e}")
        return False
