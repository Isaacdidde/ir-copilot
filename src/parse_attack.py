import json

def parse_attack(filepath="data/raw/cti/enterprise-attack/enterprise-attack.json"):
    with open(filepath, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    records = []
    for obj in bundle["objects"]:
        if obj.get("type") != "attack-pattern" or obj.get("revoked"):
            continue

        technique_id = next(
            (r["external_id"] for r in obj.get("external_references", [])
             if r.get("source_name") == "mitre-attack"),
            None
        )
        if not technique_id:
            continue

        tactics = [p["phase_name"] for p in obj.get("kill_chain_phases", [])]

        records.append({
            "id": f"attack-{technique_id}",
            "source_type": "attack",
            "technique_id": technique_id,
            "text": f"ATT&CK {technique_id} ({', '.join(tactics)}): "
                    f"{obj.get('name')}\n{obj.get('description', '')}",
            "metadata": {
                "technique_id": technique_id,
                "name": obj.get("name"),
                "tactics": ", ".join(tactics),
                "source": "MITRE ATT&CK"
            }
        })
    return records