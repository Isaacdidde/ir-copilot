import json
from src.retrieve import retrieve

def recall_at_k(golden_path="eval/golden_set.json", k=5):
    with open(golden_path) as f:
        golden_set = json.load(f)

    total_expected = 0
    total_hit = 0
    for item in golden_set:
        retrieved = retrieve(item["query"], k=k)
        retrieved_ids = {c["metadata"].get("technique_id") for c in retrieved if c["metadata"].get("technique_id")}
        expected = set(item["expected_techniques"])

        total_hit += len(retrieved_ids & expected)
        total_expected += len(expected)

    score = total_hit / total_expected if total_expected else 0
    print(f"Recall@{k}: {score:.2%}")
    return score

if __name__ == "__main__":
    recall_at_k()