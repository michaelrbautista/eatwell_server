import sqlite3
from query_service import get_candidates
from helper import get_nutrients, map_nutrients, get_portions
from models.meal_analysis import AnalysisIngredient
import os
import re
from rapidfuzz import fuzz, process

# source venv/bin/activate

DB_PATH = os.getenv("DB_PATH", "food.db")

def normalize_text(text):
    text = text.lower()
    text = text.replace("-", " ")  # 🔹 convert hyphens to spaces
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def _normalize_search_text(value: str) -> str:
    cleaned = value.lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _build_nonempty_choices(candidates):
    return {
        rowid: combined
        for rowid, combined in candidates
        if combined and combined.strip()
    }

def reorder_modifiers(term: str) -> str:
    # Cooking methods that should be preserved and reordered
    cooking_modifiers = {
        "grilled", "fried", "baked", "roasted", "boiled", "steamed", 
        "smoked", "poached", "seared", "broiled", "scrambled", "green",
        "red", "orange", "yellow"
    }

    # Form descriptors to remove completely
    form_descriptors = {
        "cooked", "sliced", "slices", "diced", "chopped", "cubed", "minced",
        "pieces", "chunks", "wedges", "halves", "quarters", "shredded",
        "whole", "peeled", "fresh", "cherry"
    }

    words = term.lower().replace(",", "").split()

    # Separate cooking modifiers, form descriptors, and base words
    cooking_mods = [w for w in words if w in cooking_modifiers]
    base_words = [w for w in words if w not in cooking_modifiers and w not in form_descriptors]

    if not base_words:
        return term.lower().strip()

    # Format to match USDA naming: "food, modifier"
    reordered = " ".join(base_words)
    if cooking_mods:
        reordered += ", " + " ".join(cooking_mods)

    return reordered.strip()

def try_exact_match(term: str, conn):
    cursor = conn.cursor()
    term_norm = term.lower().strip()
    
    # Try exact match
    cursor.execute("""
        SELECT fdc_id, 'sr_legacy_food' AS data_type, description
        FROM sr_legacy_food
        WHERE LOWER(description) = ?
        LIMIT 1
    """, (term_norm,))
    
    row = cursor.fetchone()
    if row:
        return {
            "fdc_id": row[0],
            "data_type": row[1],
            "description": row[2],
            "similarity": 1.0  # Perfect match
        }
    
    # Try exact match with common variations (comma-separated)
    # e.g., "chicken grilled" should match "chicken, grilled"
    words = term_norm.split()
    if len(words) >= 2:
        # Try last word as modifier: "chicken grilled" → "chicken, grilled"
        variant1 = f"{' '.join(words[:-1])}, {words[-1]}"
        cursor.execute("""
            SELECT fdc_id, 'sr_legacy_food' AS data_type, description
            FROM sr_legacy_food
            WHERE LOWER(description) = ?
            LIMIT 1
        """, (variant1,))
        
        row = cursor.fetchone()
        if row:
            return {
                "fdc_id": row[0],
                "data_type": row[1],
                "description": row[2],
                "similarity": 0.98  # Very close match
            }
        
        # Try first word as modifier: "grilled chicken" → "chicken, grilled"
        variant2 = f"{' '.join(words[1:])}, {words[0]}"
        cursor.execute("""
            SELECT fdc_id, 'sr_legacy_food' AS data_type, description
            FROM sr_legacy_food
            WHERE LOWER(description) = ?
            LIMIT 1
        """, (variant2,))
        
        row = cursor.fetchone()
        if row:
            return {
                "fdc_id": row[0],
                "data_type": row[1],
                "description": row[2],
                "similarity": 0.98
            }
    
    # Try prefix match (only if term is reasonably specific, 5+ chars)
    if len(term_norm) >= 5:
        cursor.execute("""
            SELECT fdc_id, 'sr_legacy_food' AS data_type, description
            FROM sr_legacy_food
            WHERE LOWER(description) LIKE ? || '%'
            LIMIT 1
        """, (term_norm,))
        
        row = cursor.fetchone()
        if row:
            return {
                "fdc_id": row[0],
                "data_type": row[1],
                "description": row[2],
                "similarity": 0.95  # Good prefix match
            }
    
    return None


def _fetch_candidates(conn: sqlite3.Connection, candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []

    fdc_ids = [c["fdc_id"] for c in candidates]
    placeholders = ",".join("?" * len(fdc_ids))
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT
            fdc_id,
            data_type,
            description,
            fermented_food_serving_size,
            CAST(collagen AS REAL) AS collagen,
            CAST(processing_score AS REAL) AS processing_score
        FROM sr_legacy_food
        WHERE fdc_id IN ({placeholders})
    """, fdc_ids)

    rows = {row[0]: dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()}

    # Preserve candidate ordering from ranking
    return [rows[c["fdc_id"]] for c in candidates if c["fdc_id"] in rows]


def build_ingredient(food_data: dict, quantity: float, conn):
    nutrients = get_nutrients(conn, food_data["fdc_id"])
    mapped_nutrients = map_nutrients(nutrients, food_data)
    portions = get_portions(conn, food_data["fdc_id"])

    return AnalysisIngredient(
        fdc_id=food_data["fdc_id"],
        description=food_data["description"],
        amount=round(quantity / 1.0, 2),
        selected_portion_id=0,
        portions=portions,
        nutrients=mapped_nutrients,
        processing_score=food_data.get("processing_score"),
        quality_score=food_data.get("processing_score")
    )


def search_food(term: str, quantity: float):
    conn = sqlite3.connect(DB_PATH)

    normalized_term = normalize_text(term)
    reordered_term = reorder_modifiers(normalized_term)

    # Fast path: exact match
    exact_match = try_exact_match(reordered_term, conn)
    if exact_match and exact_match["similarity"] >= 0.95:
        food_data = _fetch_candidates(conn, [exact_match])
        if food_data:
            result = build_ingredient(food_data[0], quantity, conn)
            conn.close()
            return result

    # Slow path: rank then fetch in one batch
    candidates = get_candidates(reordered_term, conn)
    if not candidates:
        conn.close()
        return None

    ranked = _rank_candidates(reordered_term, candidates, limit=10)
    fetched = _fetch_candidates(conn, ranked)

    if not fetched:
        conn.close()
        return None

    best = fetched[0]
    result = build_ingredient(best, quantity, conn)
    conn.close()
    return result

def _rank_candidates(term: str, candidates: list[dict], limit: int) -> list[dict]:
    normalized_term = _normalize_search_text(term)
    term_tokens = set(normalized_term.split()) if normalized_term else set()

    scored = []
    for candidate in candidates:
        desc_norm = _normalize_search_text(candidate["description"])
        desc_tokens = set(desc_norm.split())
        score = 0.0

        if normalized_term and desc_norm == normalized_term:
            score += 50
        if normalized_term and desc_norm.startswith(normalized_term):
            score += 30
        if term_tokens and term_tokens.issubset(desc_tokens):
            score += 20

        # Penalize extra tokens — "salmon" should rank above "salmon oil" and "salmon oil, canned"
        if term_tokens:
            extra_tokens = len(desc_tokens - term_tokens)
            score -= extra_tokens * 2

        ratio = fuzz.token_sort_ratio(normalized_term, desc_norm) / 100 if normalized_term else 0
        score += ratio * 10

        scored.append({**candidate, "rank_score": score})

    scored.sort(key=lambda c: c["rank_score"], reverse=True)
    return scored[:limit]

if __name__ == "__main__":
    ingredients = [
        "Steak",
        "Yogurt",
        "Blueberries",
        "Raspberries",
        "Turkey bacon",
        "Kiwi",
        "Boiled eggs"
    ]

    valid_results = []
    for ingredient in ingredients:
        result = search_food(ingredient, 100.0)
        if isinstance(result, AnalysisIngredient):
            valid_results.append(result)
            
    print()
    for result in valid_results:
        print(result.description)
        print(result.fdc_id)
    print()

    # print(json.dumps(valid_results, indent=4))
    # print(food.model_dump_json(indent=4))
