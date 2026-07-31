# Expanding IR-Copilot to the Full Knowledge Base

By default IR-Copilot ships with a small **sample** knowledge base (8 MITRE
techniques, 3 Sigma rules, a short NIST summary, 2 playbooks) so the pipeline
works out of the box with no downloads. This guide walks through swapping
each sample source for the **real, full source** — the entire MITRE ATT&CK
Enterprise matrix, the entire SigmaHQ rule repository, and the full NIST
SP 800-61 PDF.

**You do not need to touch any code.** Three new loader modules
(`backend/mitre_stix_loader.py`, `backend/sigma_bulk_loader.py`,
`backend/nist_pdf_loader.py`) are already wired into `backend/ingestion.py`.
It auto-detects whether the full source files are present and uses them
automatically — falling back to the samples only if they're missing.

---

## Quick Reference

| Source | Where to download | Where to place it |
|---|---|---|
| MITRE ATT&CK | [github.com/mitre/cti](https://github.com/mitre/cti) — **one JSON file inside the repo**, not the whole repo | `knowledge/mitre/enterprise-attack.json` |
| Sigma rules | [github.com/SigmaHQ/sigma](https://github.com/SigmaHQ/sigma) — the whole repo, cloned | `knowledge/sigma/sigma-repo/` (the cloned repo) |
| NIST SP 800-61 | [nvlpubs.nist.gov](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r2.pdf) — a single PDF | `knowledge/nist/NIST.SP.800-61r2.pdf` |

The MITRE file specifically — download it directly with one command, no
`git clone` needed:

```powershell
curl.exe -o knowledge\mitre\enterprise-attack.json https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json
```

(Full walkthroughs for all three, including a git-clone alternative for
MITRE if you prefer it, are in the sections below.)

After placing files, reindex:

> **Prerequisite:** the FastAPI backend must already be running
> (`python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000` in its
> own terminal) before the command below will work. If you get
> `curl: (7) Failed to connect to localhost port 8000`, that's not a curl
> problem — the backend simply isn't up yet on that port. Verify it's
> reachable first:
> ```powershell
> curl.exe http://localhost:8000/health
> ```
> This should return `{"status":"ok"}`. If it doesn't, start (or check the
> terminal running) the backend before retrying reindex.

```powershell
curl.exe -X POST http://localhost:8000/kb/reindex
```

> **Windows note:** all commands in this guide use `curl.exe` explicitly,
> not plain `curl`. In PowerShell, `curl` is an alias for
> `Invoke-WebRequest`, which does **not** support curl's flags like `-X` or
> `-o` and will error out (`A parameter cannot be found that matches
> parameter name 'X'`). `curl.exe` is the real curl binary, bundled with
> Windows 10/11 in `System32`, and bypasses the alias. If you're on an
> older Windows without `curl.exe` available, use the PowerShell-native
> equivalent instead:
> ```powershell
> Invoke-WebRequest -Method POST -Uri http://localhost:8000/kb/reindex
> ```

or just restart the backend — it reindexes automatically on startup, and
only embeds new/changed content thanks to the content-hash cache.

---

## 1. Full MITRE ATT&CK Enterprise Matrix

### What you're downloading

MITRE publishes the entire ATT&CK knowledge base as a STIX 2.x JSON bundle
in their official `cti` GitHub repository. This contains every technique,
sub-technique, tactic, mitigation, and the relationships between them —
hundreds of techniques instead of the 8 in the sample set.

### Steps

**Option A — download just the file you need (fastest):**

```powershell
curl.exe -o knowledge\mitre\enterprise-attack.json https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json
```

**Option B — clone the full repo** (also gives you Mobile and ICS matrices
if you want to extend further later):

```powershell
git clone https://github.com/mitre/cti.git knowledge\mitre\cti-repo
copy knowledge\mitre\cti-repo\enterprise-attack\enterprise-attack.json knowledge\mitre\enterprise-attack.json
```

### What happens next

`backend/ingestion.py` checks for `knowledge/mitre/enterprise-attack.json`
on every load. If it exists, `mitre_stix_loader.py` takes over. If a file
by that exact name isn't found, it also checks any other `.json` file in
`knowledge/mitre/` by content (looking for the STIX `"type": "bundle"`
signature) — so if your browser saved the download as something like
`enterprise-attack (1).json`, it's still detected correctly instead of
being mistaken for the sample format. (Naming it exactly
`enterprise-attack.json` is still recommended for clarity, but no longer
required for it to work.)

- Parses every `attack-pattern` object (technique) in the bundle
- **Filters out revoked and deprecated techniques** — MITRE marks
  superseded techniques this way rather than deleting them, so without this
  filter you'd get stale technique IDs mixed in with current ones
- Follows `mitigates` relationship objects to attach the correct mitigation
  guidance to each technique, pulled from the corresponding
  `course-of-action` object
- Produces one chunk per technique, tagged with `technique_id`, `tactic`,
  and `platforms` metadata for filtering

Expect roughly **600+ technique chunks** from the full bundle (exact count
changes as MITRE updates ATT&CK).

### Verifying it worked

Restart the backend and check the logs for:

```
Loaded 6XX MITRE ATT&CK techniques from full STIX bundle (enterprise-attack.json)
```

(instead of `Loaded 8 MITRE technique chunks`, which means it's still using
the sample file). Also check:

```powershell
curl.exe http://localhost:8000/kb/status
```

`mitre_count` should jump from `8` to several hundred.

---

## 2. Full SigmaHQ Rule Repository

### What you're downloading

The [SigmaHQ/sigma](https://github.com/SigmaHQ/sigma) repository is the
canonical, community-maintained Sigma rule set — thousands of detection
rules organized by platform and log source (`rules/windows/`,
`rules/linux/`, `rules/network/`, `rules/cloud/`, etc.), plus a
`rules-emerging-threats/` folder for recent high-value detections and a
`rules-deprecated/` folder for superseded rules.

### Steps

```powershell
git clone https://github.com/SigmaHQ/sigma.git knowledge\sigma\sigma-repo
```

That's it — no file copying needed. The loader walks the whole tree.

### What happens next

`backend/ingestion.py` checks whether `knowledge/sigma/sigma-repo/rules/`
exists. If so, `sigma_bulk_loader.py` takes over and:

- Recursively walks every subfolder under the repo (handles the real
  nested layout, e.g. `rules/windows/process_creation/...`,
  `rules/windows/builtin/security/...`)
- **Skips the entire `rules-deprecated/` folder**
- **Skips individual rules with `status: deprecated` or `status:
  unsupported`**, wherever they live, since these don't represent current
  detections
- Includes `rules-emerging-threats/` by default
- Extracts the MITRE technique ID directly from each rule's `tags` field
  (e.g. `attack.t1059.001` → `T1059.001`) so Sigma rules and MITRE
  techniques stay cross-referenced automatically
- Skips non-rule files (READMEs, images, config files) automatically since
  it only looks at `.yml`/`.yaml` files and validates each one has a
  `title` field before treating it as a rule

Expect roughly **3,000+ rule chunks** from the full repo.

### Verifying it worked

```
Loaded 3XXX Sigma rules from knowledge/sigma/sigma-repo (skipped XXX deprecated/unsupported, 0 malformed)
```

```powershell
curl.exe http://localhost:8000/kb/status
```

`sigma_count` should jump from `3` to several thousand.

### Optional: exclude emerging-threats rules

If you only want stable, long-established rules, you can disable the
emerging-threats folder by editing the call in `backend/ingestion.py`:

```python
all_chunks.extend(load_sigma_bulk_chunks(sigma_repo_path, include_emerging_threats=False))
```

---

## 3. Full NIST SP 800-61 (Computer Security Incident Handling Guide)

### What you're downloading

The actual NIST Special Publication PDF — the real, current revision
(Revision 2), rather than the short hand-written summary shipped as a
sample.

### Steps

```powershell
curl.exe -o knowledge\nist\NIST.SP.800-61r2.pdf https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r2.pdf
```

### What happens next

`backend/ingestion.py` checks for any `.pdf` file in `knowledge/nist/`. If
one is found, `nist_pdf_loader.py` takes over instead of the markdown
summary loader and:

- Extracts text page-by-page using `pdfplumber`
- Detects section headings (e.g. `3.2 Detection and Analysis`) as it scans
  each page
- Tags every chunk with the section heading that was actually active at
  that point in the document — including correctly **carrying a heading
  across page boundaries** when a section continues onto a page with no
  heading of its own
- Splits each page's text using the same token-aware chunking as the rest
  of the knowledge base (400–600 token chunks, 50–80 token overlap)
- Skips near-empty fragments (stray headers/footers/page numbers)

Each chunk's `source_name` becomes something like
`NIST SP 800-61 — 3.3 Containment, Eradication, and Recovery`, so citations
in the UI point to the actual section, not just "NIST."

### Verifying it worked

```
Loaded XX chunks from NIST SP 800-61 PDF (NIST.SP.800-61r2.pdf, 79 pages)
```

```powershell
curl.exe http://localhost:8000/kb/status
```

`nist_count` should jump from `2` to several dozen.

> **Note:** if you have multiple NIST-related PDFs you want indexed (e.g.
> an older revision for comparison, or a related publication), just drop
> them all into `knowledge/nist/` — every `.pdf` found there gets loaded.

---

## 4. Reindex After Adding Sources

Whichever sources you added, trigger a reindex:

```powershell
curl.exe -X POST http://localhost:8000/kb/reindex
```

(or `Invoke-WebRequest -Method POST -Uri http://localhost:8000/kb/reindex`
— see the note in the Quick Reference section above if `curl.exe` isn't
available on your system)

or restart the backend (`Ctrl+C` then re-run `uvicorn`/`python -m uvicorn`
as before) — indexing happens automatically on startup.

Only **new or changed** content is embedded. If you already indexed the
sample set and then add the full sources, the sample chunks that no longer
exist on disk will simply not be re-loaded (they get replaced by the full
source's chunks on the next fresh index build), and nothing already
embedded gets needlessly recomputed.

---

## 5. Things to Expect After Expanding

- **First reindex will take longer.** Going from 17 sample chunks to
  ~4,000+ real chunks means the embedding model has thousands of new texts
  to encode. This is a one-time cost — the embedding cache means it won't
  repeat unless the source files change.
- **Retrieval quality should improve noticeably** on real-world incident
  descriptions, since the sample set only covered PowerShell, LSASS
  access, and ransomware scenarios.
- **You may want to retune `IRCOPILOT_FINAL_TOP_K` and
  `IRCOPILOT_MIN_CONFIDENCE_THRESHOLD`** in `.env` once the full sources are
  in — with thousands of chunks instead of 17, retrieval scores and
  confidence distributions shift. Watch a few real queries and adjust if
  everything suddenly reads as "insufficient evidence" or, conversely, if
  confidence looks inflated.
- **Disk/memory usage increases.** ChromaDB's on-disk store and the
  in-memory BM25 index both scale with chunk count. A few thousand chunks
  is still lightweight (tens of MB), so this is unlikely to be a problem
  on a normal laptop, but it's worth knowing if you plan to add Mobile and
  ICS ATT&CK matrices too.

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Backend log still says `Loaded 8 MITRE technique chunks` | File not at the exact expected path | Confirm the file is at `knowledge/mitre/enterprise-attack.json` exactly (not inside a subfolder) |
| Backend log still says `Loaded 3 Sigma rule chunks` | Repo cloned to wrong path, or `rules/` folder missing | Confirm `knowledge/sigma/sigma-repo/rules/` exists — the loader checks for that exact subfolder as its trigger |
| `nist_count` still shows `2` | PDF not in `knowledge/nist/`, or wrong extension | Confirm the file ends in `.pdf` and sits directly inside `knowledge/nist/` |
| `curl: (7) Failed to connect to localhost port 8000` on reindex | Backend isn't running yet | Start it: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`, wait for "Application startup complete", then retry |
| Reindex is very slow | Expected on first run after expanding | Let it finish once; subsequent restarts skip unchanged chunks via the embedding cache |
| `git clone` fails / not recognized | Git not installed | Install Git for Windows from [git-scm.com](https://git-scm.com/download/win), or use the `curl` single-file download option for MITRE instead of cloning |
| `string indices must be integers, not 'str'` on reindex | The downloaded STIX bundle landed in `knowledge/mitre/` under a filename the loader didn't recognize, so it was parsed as sample-format JSON instead | Fixed as of this update — the loader now detects a STIX bundle by content, not just the exact filename `enterprise-attack.json`, and never crashes on a mismatched file. If you still hit this on an older copy of the project, rename the file to exactly `enterprise-attack.json` |
| PDF loader returns 0 chunks | PDF is a scanned image, not real text | `pdfplumber` extracts text layers only; a scanned/image-only PDF needs OCR first (not currently built into this loader) |
