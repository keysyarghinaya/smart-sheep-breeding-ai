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
