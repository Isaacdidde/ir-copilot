import yaml, glob

def parse_sigma(rules_dir="data/raw/sigma/rules"):
    records = []
    for filepath in glob.glob(f"{rules_dir}/**/*.yml", recursive=True):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                rule = yaml.safe_load(f)
        except yaml.YAMLError:
            continue
        if not rule or "title" not in rule:
            continue

        tags = rule.get("tags", [])
        attack_ids = [t.replace("attack.", "").upper() for t in tags if t.startswith("attack.t")]

        records.append({
            "id": f"sigma-{rule.get('id', filepath)}",
            "source_type": "sigma",
            "text": f"Detection rule: {rule.get('title')}\n"
                    f"{rule.get('description', '')}\n"
                    f"Log source: {rule.get('logsource', {})}\n"
                    f"Maps to: {', '.join(attack_ids) if attack_ids else 'unmapped'}",
            "metadata": {
                "title": rule.get("title"),
                "level": rule.get("level", "unknown"),
                "attack_ids": ", ".join(attack_ids),
                "source": "Sigma"
            }
        })
    return records