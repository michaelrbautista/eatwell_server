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

            # Word-overlap boost: +0.05 per matching word
            # desc_lower = c["description"].lower()
            # overlap = sum(1 for w in term.lower().split() if w in desc_lower)
            desc_lower = c["description"]  # already normalized
            overlap = sum(1 for w in term.split() if w in desc_lower)
            sim += 0.05 * overlap

            scored.append({
                "fdc_id": c["fdc_id"],
                "data_type": c["data_type"],
                "description": c["description"],
                "similarity": sim
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

# --------------------------------------------------------------------------------
# Fuzzy search
# --------------------------------------------------------------------------------

def fuzzy_search(term, conn, limit=20):
    cursor = conn.cursor()
    # cursor.execute("SELECT fdc_id, description, 'sr_legacy_food' AS data_type FROM sr_legacy_food WHERE description IS NOT NULL")
    cursor.execute("SELECT fdc_id, normalized_description, 'sr_legacy_food' AS data_type FROM sr_legacy_food WHERE normalized_description IS NOT NULL")
    sr_legacy_rows = cursor.fetchall()

    all_rows = sr_legacy_rows
    choices = {row[0]: row[1] for row in all_rows if row[1]}

    results = process.extract(term, choices, scorer=fuzz.token_sort_ratio, limit=limit)

    output = []
    for desc, score, rowid in results:
        cursor.execute("""
            SELECT fdc_id, 'sr_legacy_food' AS data_type, description FROM sr_legacy_food WHERE fdc_id = ?
        """, (rowid,))
        row = cursor.fetchone()
        if row:
            output.append(row)
    return output

# ----------------------------------------
# Full text search
# ----------------------------------------

def fts_search(term, conn, limit=20):
    cursor = conn.cursor()
    # cursor.execute("""
    #     WITH fts_results AS (
    #         SELECT rowid AS fdc_id, bm25(food_search) AS score
    #         FROM food_search
    #         WHERE food_search MATCH ?
    #         ORDER BY bm25(food_search)
    #         LIMIT ?
    #     )
    #     SELECT fts_results.fdc_id, f.data_type, f.description
    #     FROM fts_results
    #     JOIN (
    #         SELECT fdc_id, 'sr_legacy_food' AS data_type, description FROM sr_legacy_food
    #     ) AS f ON f.fdc_id = fts_results.fdc_id
    #     ORDER BY fts_results.score;
    # """, (term, limit))
    cursor.execute("""
        WITH fts_results AS (
            SELECT rowid AS fdc_id, bm25(food_search) AS score
            FROM food_search
            WHERE food_search MATCH ?
            LIMIT ?
        )
        SELECT fts_results.fdc_id, f.data_type, f.description
        FROM fts_results
        JOIN (
            SELECT fdc_id, 'sr_legacy_food' AS data_type, description FROM sr_legacy_food
        ) AS f ON f.fdc_id = fts_results.fdc_id
        ORDER BY fts_results.score;
    """, (term, limit))
    return cursor.fetchall()
