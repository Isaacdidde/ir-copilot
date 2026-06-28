from langchain_text_splitters import MarkdownHeaderTextSplitter
import glob

def parse_playbooks(playbook_dir="data/raw/playbooks"):
    headers_to_split_on = [("##", "section")]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)

    records = []
    for filepath in glob.glob(f"{playbook_dir}/*.md"):
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        title = text.split("\n")[0].replace("#", "").strip()
        chunks = splitter.split_text(text)

        for i, chunk in enumerate(chunks):
            section = chunk.metadata.get("section", "general")
            records.append({
                "id": f"playbook-{title}-{i}",
                "source_type": "playbook",
                "text": f"Playbook: {title} — {section}\n{chunk.page_content}",
                "metadata": {
                    "playbook": title,
                    "section": section,
                    "source": "Internal runbook"
                }
            })
    return records