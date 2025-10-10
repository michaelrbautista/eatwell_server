import sqlite3
import json
from openai import OpenAI
from itertools import islice
import os
from dotenv import load_dotenv
import numpy as np
import re
import time
from openai import RateLimitError, APIError

DB_PATH = "../food.db"
BATCH_SIZE = 100
MODEL = "text-embedding-3-small"

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def embed_with_retry(model, input_texts, retries=3, delay=5):
    for i in range(retries):
        try:
            return client.embeddings.create(model=model, input=input_texts)
        except (RateLimitError, APIError) as e:
            print(f"Retrying batch after error: {e}")
            time.sleep(delay * (i + 1))
    raise RuntimeError("Failed to get embeddings after retries")

def normalize_embedding(emb):
    arr = np.array(emb, dtype=np.float32)
    norm = np.linalg.norm(arr)
    return (arr / norm).tolist()

def get_batches(iterable, batch_size):
    """Yield successive batch_size chunks from iterable"""
    it = iter(iterable)
    while True:
        batch = list(islice(it, batch_size))
        if not batch:
            break
        yield batch

def build_embeddings():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Drop old table if exists
    cursor.execute("DROP TABLE IF EXISTS food_embeddings;")

    # Create new embeddings table
    cursor.execute("""
        CREATE TABLE food_embeddings (
            fdc_id INTEGER NOT NULL,
            data_type TEXT NOT NULL,
            description TEXT NOT NULL,
            embedding TEXT NOT NULL,
            PRIMARY KEY (fdc_id, data_type)
        );
    """)

    # cursor.execute("""
    #     SELECT fdc_id, description, 'sr_legacy_food' AS data_type
    #     FROM sr_legacy_food
    #     WHERE description IS NOT NULL;
    # """)
    cursor.execute("""
        SELECT fdc_id, normalized_description, 'sr_legacy_food' AS data_type
        FROM sr_legacy_food
        WHERE normalized_description IS NOT NULL;
    """)
    rows = cursor.fetchall()

    print(f"Found {len(rows)} food descriptions to embed...")

    # Process in batches
    for batch_num, batch in enumerate(get_batches(rows, BATCH_SIZE), start=1):
        fdc_ids = [r[0] for r in batch]
        # descs = [normalize_text(r[1]) for r in batch]
        descs = [r[1] for r in batch]
        data_types = [r[2] for r in batch]

        # Call OpenAI embeddings API with the batch
        response = embed_with_retry(MODEL, descs)

        embeddings = [d.embedding for d in response.data]

        # Insert into DB
        for fdc_id, desc, data_type, emb in zip(fdc_ids, descs, data_types, embeddings):
            emb_list = normalize_embedding(emb)
            cursor.execute(
                "INSERT INTO food_embeddings (fdc_id, data_type, description, embedding) VALUES (?, ?, ?, ?)",
                (fdc_id, data_type, desc, json.dumps(emb_list))
            )

        conn.commit()
        print(f"Processed batch {batch_num}, inserted {len(batch)} rows.")

    cursor.execute("CREATE INDEX idx_food_embeddings_fdc ON food_embeddings(fdc_id);")
    cursor.execute("CREATE INDEX idx_food_embeddings_data_type ON food_embeddings(data_type);")

    conn.close()
    print("✅ Embeddings table built successfully!")

if __name__ == "__main__":
    build_embeddings()
    # conn = sqlite3.connect(DB_PATH)
    # cursor = conn.cursor()
    # cursor.execute("SELECT fdc_id, data_type, description, embedding FROM food_embeddings LIMIT 5;")
    # rows = cursor.fetchall()
    # for row in rows:
    #     fdc_id, data_type, desc, emb_json = row
    #     emb = np.array(json.loads(emb_json))  # convert embedding back to NumPy array if needed
    #     print(f"fdc_id: {fdc_id}, data_type: {data_type}, description: {desc}, embedding_shape: {emb.shape}")

    # conn.close()
