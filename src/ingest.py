# src/ingest.py
import json
import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

def ingest():
    with open("data/processed/corpus.json") as f:
        records = json.load(f)

    model = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection(name="ir_knowledge")

    batch_size = 64
    for i in tqdm(range(0, len(records), batch_size)):
        batch = records[i:i + batch_size]
        texts = [r["text"] for r in batch]
        embeddings = model.encode(texts).tolist()

        collection.add(
            ids=[r["id"] for r in batch],
            embeddings=embeddings,
            documents=texts,
            metadatas=[r["metadata"] for r in batch]
        )

    print(f"Ingested {len(records)} chunks into ChromaDB")

if __name__ == "__main__":
    ingest()