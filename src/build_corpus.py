from src.parse_attack import parse_attack
from src.parse_sigma import parse_sigma
from src.parse_playbooks import parse_playbooks
import json

def build_corpus():
    records = parse_attack() + parse_sigma() + parse_playbooks()
    with open("data/processed/corpus.json", "w") as f:
        json.dump(records, f, indent=2)
    print(f"Built corpus with {len(records)} chunks")
    return records

if __name__ == "__main__":
    build_corpus()