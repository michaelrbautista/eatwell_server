import sqlite3
import json
from openai import OpenAI
from itertools import islice
import os
from dotenv import load_dotenv

DB_PATH = "../food.db"
BATCH_SIZE = 100
MODEL = "text-embedding-3-small"

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

    # Get all rows with descriptions
    # cursor.execute("""
    #     SELECT fdc_id, description, 'foundation_food' AS data_type
    #     FROM foundation_food
    #     WHERE description IS NOT NULL
    #     UNION ALL
    #     SELECT fdc_id, description, 'sr_legacy_food' AS data_type
    #     FROM sr_legacy_food
    #     WHERE description IS NOT NULL;
    # """)
    cursor.execute("""
        SELECT fdc_id, description, 'sr_legacy_food' AS data_type
        FROM sr_legacy_food
        WHERE description IS NOT NULL;
    """)
    rows = cursor.fetchall()

    print(f"Found {len(rows)} food descriptions to embed...")

    # Process in batches
    for batch_num, batch in enumerate(get_batches(rows, BATCH_SIZE), start=1):
        fdc_ids = [r[0] for r in batch]
        descs = [r[1] for r in batch]
        data_types = [r[2] for r in batch]

        # Call OpenAI embeddings API with the batch
        response = client.embeddings.create(
            model=MODEL,
            input=descs
        )

        embeddings = [d.embedding for d in response.data]

        # Insert into DB
        for fdc_id, desc, data_type, emb in zip(fdc_ids, descs, data_types, embeddings):
            # Convert all embedding values to native Python float for JSON serialization
            emb_list = [float(x) for x in emb]
            cursor.execute(
                "INSERT INTO food_embeddings (fdc_id, data_type, description, embedding) VALUES (?, ?, ?, ?)",
                (fdc_id, data_type, desc, json.dumps(emb_list))
            )

        conn.commit()
        print(f"Processed batch {batch_num}, inserted {len(batch)} rows.")

    conn.close()
    print("✅ Embeddings table built successfully!")

if __name__ == "__main__":
    build_embeddings()
