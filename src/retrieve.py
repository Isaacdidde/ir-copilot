import chromadb
from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("all-MiniLM-L6-v2")
_client = chromadb.PersistentClient(path="./chroma_db")
_collection = _client.get_collection("ir_knowledge")

def retrieve(query, k=5):
    query_embedding = _model.encode(query).tolist()
    results = _collection.query(query_embeddings=[query_embedding], n_results=k)

    chunks = []
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        chunks.append({"text": doc, "metadata": meta, "score": 1 - dist})
    return chunks