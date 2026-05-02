from rapidfuzz import process, fuzz
import os
from dotenv import load_dotenv
from openai import OpenAI
import numpy as np
import json
import re

DB_PATH = os.getenv("DB_PATH", "../food.db")

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def normalize_text(text):
    text = text.lower()
    text = text.replace("-", " ")  # 🔹 convert hyphens to spaces
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

# --------------------------------------------------------------------------------
# Rank based on embeddings
# --------------------------------------------------------------------------------

def get_embedding(text):
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return np.array(resp.data[0].embedding)

def load_embedding(emb_json):
    """Convert JSON string to NumPy array."""
    return np.array(json.loads(emb_json), dtype=np.float32)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def rerank_with_embeddings(term, candidates, conn, top_k=5):
    model = "text-embedding-3-small"

    # Embed the search term
    query_emb = np.array(client.embeddings.create(model=model, input=term).data[0].embedding, dtype=np.float32)

    cursor = conn.cursor()
    scored = []

    for c in candidates:
        cursor.execute("""
            SELECT embedding FROM food_embeddings
            WHERE fdc_id = ? AND data_type = ?
        """, (c["fdc_id"], c["data_type"]))
        row = cursor.fetchone()
        if row:
            emb = load_embedding(row[0])
            sim = cosine_similarity(query_emb, emb)

            desc = c["description"].lower()

            # 🔻 Penalize "raw" foods if user didn't ask for "raw"
            raw_penalty = -0.15 if "raw" in desc and "raw" not in term else 0.0

            scored.append({
                "fdc_id": c["fdc_id"],
                "data_type": c["data_type"],
                "description": c["description"],
                "similarity": sim + raw_penalty
            })
        else:
            # fallback if no embedding stored
            c["similarity"] = 0.0

    # Sort by similarity descending
    ranked = sorted(scored, key=lambda x: x["similarity"], reverse=True)
    return ranked[:top_k]

# --------------------------------------------------------------------------------
# Combine results from full textsearach and fuzzy search
# --------------------------------------------------------------------------------

def get_candidates(term, conn):
    cursor = conn.cursor()
    term_norm = term.lower().strip()

    # Step 1: exact or prefix matches (highest priority)
    exact_prefix_matches = cursor.execute("""
        SELECT fdc_id, 'sr_legacy_food' AS data_type, description
        FROM sr_legacy_food
        WHERE LOWER(description) = ?
           OR LOWER(description) LIKE ? || '%'
        LIMIT 20
    """, (term_norm, term_norm)).fetchall()

    if exact_prefix_matches:
        return [{"fdc_id": r[0], "data_type": r[1], "description": r[2]} for r in exact_prefix_matches]

    # Step 2: fallback to FTS + fuzzy
    fts_results = fts_search(term, conn, limit=20)
    fuzzy_results = fuzzy_search(term, conn, limit=20)

    seen = set()
    candidates = []
    for fdc_id, data_type, description in fts_results + fuzzy_results:
        key = (fdc_id, data_type)
        if key not in seen:
            candidates.append({"fdc_id": fdc_id, "data_type": data_type, "description": description})
            seen.add(key)

    return candidates

# ----------------------------------------
# Full text search
# ----------------------------------------

def fts_search(term: str, conn, limit: int = 20) -> list[tuple]:
    fts_term = re.sub(r'[^\w\s]', ' ', term)
    fts_term = re.sub(r'\s+', ' ', fts_term).strip()
    if not fts_term:
        return []

    # Try prefix match first ("chicken b" → "chicken breast"), fall back to plain match
    prefix_term = " ".join(f'"{word}"*' for word in fts_term.split())

    cursor = conn.cursor()
    for query_term in [prefix_term, fts_term]:
        try:
            cursor.execute("""
                SELECT f.fdc_id, 'sr_legacy_food' AS data_type, f.description
                FROM food_search
                JOIN sr_legacy_food f ON f.fdc_id = food_search.rowid
                WHERE food_search MATCH ?
                ORDER BY bm25(food_search)
                LIMIT ?
            """, (query_term, limit))
            rows = cursor.fetchall()
            if rows:
                return rows
        except Exception:
            continue

    return []

# --------------------------------------------------------------------------------
# Fuzzy search
# --------------------------------------------------------------------------------

def fuzzy_search(term: str, conn, limit: int = 20) -> list[tuple]:
    """
    Full table scan — only called when FTS undershoots.
    Consider caching `choices` at startup if DB is static.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT fdc_id, normalized_description, description FROM sr_legacy_food WHERE normalized_description IS NOT NULL"
    )
    rows = cursor.fetchall()

    choices = {row[0]: row[1] for row in rows}
    matches = process.extract(term, choices, scorer=fuzz.token_sort_ratio, limit=limit)

    fdc_id_to_desc = {row[0]: row[2] for row in rows}
    return [
        (fdc_id, "sr_legacy_food", fdc_id_to_desc[fdc_id])
        for _, score, fdc_id in matches
        if score >= 60  # drop low-confidence fuzzy matches
    ]
