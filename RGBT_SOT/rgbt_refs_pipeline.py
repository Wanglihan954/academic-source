#!/usr/bin/env python3
import argparse
import csv
import difflib
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path("/home/lihan/文档/MyArticles/RGBT_SOT")
XLSX = ROOT / "papers_sorted_by_year.xlsx"
ZOTERO_STORAGE = Path("/home/lihan/Zotero/storage")
OUT = ROOT / "refs_pipeline_output"

SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"a": SHEET_NS}

TRACKING_WORDS = {
    "track",
    "tracking",
    "tracker",
    "object",
    "visual",
    "video",
    "sot",
}

MODAL_WORD_PATTERNS = [
    r"\brgb[- ]?t\b",
    r"\brgbt\b",
    r"\brgb[- ]?x\b",
    r"\brgb[- ]?d\b",
    r"\brgb[- ]?e\b",
    r"\brgb[- ]?thermal\b",
    r"\bvisible[- ]?thermal\b",
    r"\bvisible[- ]?infrared\b",
    r"\bthermal[- ]?visible\b",
    r"\bgrayscale[- ]?thermal\b",
    r"\bcolor and infrared\b",
    r"\bthermo[- ]?visual\b",
    r"\bmultispectral\b",
    r"\bmulti[- ]?modal\b",
    r"\bmultimodal\b",
    r"\bany[- ]?modality\b",
    r"\brgb\+d/t/e\b",
    r"\brgb\+x\b",
]

EXCLUDE_CONTEXT = [
    "re-identification",
    "person reid",
    "image registration",
    "image fusion",
    "object detection",
    "semantic segmentation",
    "instance segmentation",
    "multiple object tracking",
    "multi-object tracking",
    "multi target tracking",
    "multi-target tracking",
]

CONFERENCE_RATING = {
    "cvpr": "CCF-A",
    "iccv": "CCF-A",
    "aaai": "CCF-A",
    "acm mm": "CCF-A",
    "acmmm": "CCF-A",
    "neurips": "CCF-A",
    "nips": "CCF-A",
    "icml": "CCF-A",
    "iclr": "CCF-A",
    "ijcai": "CCF-B",
    "eccv": "CCF-B",
    "icme": "CCF-B",
}

JOURNAL_RATING_BY_HINT = {
    "ieee transactions on image processing": "CAS-Q1",
    "ieee trans. image process": "CAS-Q1",
    "tip": "CAS-Q1",
    "ieee transactions on pattern analysis and machine intelligence": "CAS-Q1",
    "tpami": "CAS-Q1",
    "international journal of computer vision": "CAS-Q1",
    "ijcv": "CAS-Q1",
    "pattern recognition": "CAS-Q1",
    "information fusion": "CAS-Q1",
    "ieee transactions on multimedia": "CAS-Q1",
    "tmm": "CAS-Q1",
    "ieee transactions on neural networks and learning systems": "CAS-Q1",
    "tnnls": "CAS-Q1",
    "ieee transactions on intelligent transportation systems": "CAS-Q1",
    "ieee transactions on intelligent vehicles": "CAS-Q1",
    "ieee transactions on circuits and systems for video technology": "CAS-Q2",
    "tcsvt": "CAS-Q2",
    "ieee transactions on instrumentation and measurement": "CAS-Q2",
    "tim": "CAS-Q2",
    "applied intelligence": "CAS-Q2",
    "neurocomputing": "CAS-Q2",
    "ieee transactions on artificial intelligence": "CAS-Q2",
    "tai": "CAS-Q2",
}


@dataclass
class Paper:
    row: int
    values: dict


def norm_title(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"^\[non-rgbt idea-only\]\s*", "", s)
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\b(a|an|the|for|via|with|and|of|to|in|on|by)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def col_to_idx(ref: str) -> int:
    m = re.match(r"([A-Z]+)", ref)
    n = 0
    for ch in m.group(1):
        n = n * 26 + ord(ch) - 64
    return n - 1


def idx_to_col(idx: int) -> str:
    idx += 1
    out = ""
    while idx:
        idx, rem = divmod(idx - 1, 26)
        out = chr(65 + rem) + out
    return out


def read_xlsx_rows(path: Path):
    with ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", NS):
                shared.append("".join(t.text or "" for t in si.findall(".//a:t", NS)))
        root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in root.findall(".//a:sheetData/a:row", NS):
            vals = {}
            for c in row.findall("a:c", NS):
                idx = col_to_idx(c.attrib.get("r", "A1"))
                t = c.attrib.get("t")
                if t == "s":
                    v = c.find("a:v", NS)
                    val = shared[int(v.text)] if v is not None and v.text else ""
                elif t == "inlineStr":
                    val = "".join(tt.text or "" for tt in c.findall(".//a:t", NS))
                else:
                    v = c.find("a:v", NS)
                    val = v.text if v is not None and v.text else ""
                vals[idx] = val
            maxidx = max(vals, default=-1)
            rows.append((int(row.attrib.get("r", "0")), [vals.get(i, "") for i in range(maxidx + 1)]))
    headers = rows[0][1]
    papers = []
    for r, vals in rows[1:]:
        vals = vals + [""] * (len(headers) - len(vals))
        papers.append(Paper(r, dict(zip(headers, vals))))
    return headers, papers


def is_eligible_paper(values: dict) -> bool:
    try:
        year = int(float(values.get("Year", "0") or 0))
    except ValueError:
        year = 0
    if year < 2020:
        return True
    return (values.get("Rating", "") or "").strip() in {"CCF-A", "CCF-B", "CAS-Q1", "CAS-Q2"}


def is_eligible_rating(rating: str) -> bool:
    return (rating or "").strip() in {"CCF-A", "CCF-B", "CAS-Q1", "CAS-Q2"}


def is_relevant_text(text: str) -> bool:
    low = (text or "").lower()
    if any(bad in low for bad in EXCLUDE_CONTEXT):
        return False
    has_modality = any(re.search(p, low) for p in MODAL_WORD_PATTERNS)
    has_tracking = any(w in low for w in TRACKING_WORDS)
    return has_modality and has_tracking


def rating_from_ref(ref: str) -> str:
    low = ref.lower()
    for k, v in CONFERENCE_RATING.items():
        if re.search(r"\b" + re.escape(k).replace(r"\ ", r"[- ]?") + r"\b", low):
            return v
    for k, v in JOURNAL_RATING_BY_HINT.items():
        if k in low:
            return v
    return ""


def list_pdfs() -> list[Path]:
    return sorted(ZOTERO_STORAGE.glob("*/*.pdf")) + sorted((ZOTERO_STORAGE / "download").glob("*.pdf"))


def best_pdf_for_title(title: str, pdfs: list[Path]):
    nt = norm_title(title)
    best = (0.0, None)
    for p in pdfs:
        np = norm_title(p.stem)
        if not np:
            continue
        score = difflib.SequenceMatcher(None, nt, np).ratio()
        # Filename truncation still carries enough title words in Zotero.
        toks_t = set(nt.split())
        toks_p = set(np.split())
        if toks_t:
            score = max(score, len(toks_t & toks_p) / len(toks_t))
        if score > best[0]:
            best = (score, p)
    return best if best[0] >= 0.75 else (best[0], None)


def pdf_to_text(pdf: Path) -> str:
    proc = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=90,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout


def references_section(text: str) -> str:
    markers = list(re.finditer(r"(?im)\b(references|bibliography)\b", text))
    if not markers:
        return ""
    # Use the last marker because arXiv/CVF PDFs sometimes mention
    # "references" in headers/body text before the actual bibliography.
    start = markers[-1].end()
    tail = text[start:]
    # Stop at appendix-like material only if it is far enough from the marker.
    m = re.search(r"(?im)^\s*(appendix|supplementary|acknowledg)", tail)
    if m and m.start() > 1000:
        tail = tail[: m.start()]
    return tail.strip()


def split_references(refs: str) -> list[str]:
    if not refs:
        return []
    lines = [re.sub(r"\s+", " ", ln.strip()) for ln in refs.splitlines()]
    lines = [ln for ln in lines if ln]
    entries = []
    cur = ""
    start_re = re.compile(r"^(\[\d+\]|\d+\.|\d+\)|[A-Z][a-z]+,\s+[A-Z]\.)\s+")
    for ln in lines:
        if start_re.match(ln) and cur:
            entries.append(cur.strip())
            cur = ln
        else:
            cur = (cur + " " + ln).strip()
    if cur:
        entries.append(cur.strip())
    # Fallback for refs extracted as one paragraph with [n] markers.
    if len(entries) <= 3 and re.search(r"\[\d+\]", refs):
        parts = re.split(r"(?=\[\d+\])", re.sub(r"\s+", " ", refs))
        entries = [p.strip() for p in parts if len(p.strip()) > 20]
    return entries


def match_existing_ref(ref: str, papers: list[Paper]):
    nref = norm_title(ref)
    ref_tokens = nref.split()
    best = (0.0, None)
    for paper in papers:
        title = paper.values.get("Paper", "")
        nt = norm_title(title)
        if not nt:
            continue
        title_seq = nt.split()
        title_tokens = set(title_seq)
        if not title_seq:
            continue
        token_hit = len(title_tokens & set(ref_tokens)) / len(title_tokens)
        contiguous = nt in nref
        # PDF two-column extraction can interleave two different references. To
        # avoid matching words scattered across columns, require title words to
        # appear in order and within a compact span unless the full normalized
        # title is a substring.
        pos = []
        search_from = 0
        for tok in title_seq:
            found = -1
            for i in range(search_from, len(ref_tokens)):
                if ref_tokens[i] == tok:
                    found = i
                    break
            if found < 0:
                pos = []
                break
            pos.append(found)
            search_from = found + 1
        compact_order = bool(pos) and (pos[-1] - pos[0] + 1) <= len(title_seq) + 8
        seq = difflib.SequenceMatcher(None, nt, nref).ratio()
        score = max(token_hit, seq) if contiguous else (token_hit if compact_order else min(token_hit, 0.5))
        if score > best[0]:
            best = (score, paper)
    if best[0] >= 0.86:
        return best
    return best[0], None


def compress_rows(rows: list[int]) -> str:
    rows = sorted(set(rows))
    if not rows:
        return ""
    parts = []
    start = prev = rows[0]
    for n in rows[1:]:
        if n == prev + 1:
            prev = n
            continue
        parts.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = n
    parts.append(f"{start}-{prev}" if start != prev else str(start))
    return ", ".join(parts)


def parse_parent_rows(s: str) -> list[int]:
    out = []
    for part in re.split(r"\s*,\s*", s or ""):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            if a.strip().isdigit() and b.strip().isdigit():
                out.extend(range(int(a), int(b) + 1))
        elif part.strip().isdigit():
            out.append(int(part))
    return out


def set_inline(c, text: str):
    for child in list(c):
        c.remove(child)
    c.attrib["t"] = "inlineStr"
    is_el = ET.SubElement(c, f"{{{SHEET_NS}}}is")
    t_el = ET.SubElement(is_el, f"{{{SHEET_NS}}}t")
    t_el.text = text


def update_parents_xlsx(path: Path, new_parents: dict[int, str]):
    ET.register_namespace("", SHEET_NS)
    backup = path.with_name("papers_sorted_by_year.backup_before_refs_pipeline.xlsx")
    shutil.copy2(path, backup)
    with ZipFile(path, "r") as zin:
        root = ET.fromstring(zin.read("xl/worksheets/sheet1.xml"))
        for row in root.findall(".//a:sheetData/a:row", NS):
            rnum = int(row.attrib.get("r", "0"))
            if rnum not in new_parents:
                continue
            cells = {col_to_idx(c.attrib.get("r", "A1")): c for c in row.findall("a:c", NS)}
            idx = 6
            if idx in cells:
                c = cells[idx]
            else:
                c = ET.Element(f"{{{SHEET_NS}}}c", {"r": f"{idx_to_col(idx)}{rnum}"})
                inserted = False
                for pos, old in enumerate(list(row)):
                    if old.tag.endswith("c") and col_to_idx(old.attrib.get("r", "A1")) > idx:
                        row.insert(pos, c)
                        inserted = True
                        break
                if not inserted:
                    row.append(c)
            set_inline(c, new_parents[rnum])
        sheet_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        fd, tmpname = tempfile.mkstemp(suffix=".xlsx", dir=str(path.parent))
        os.close(fd)
        tmp = Path(tmpname)
        with ZipFile(tmp, "w", ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = sheet_bytes if item.filename == "xl/worksheets/sheet1.xml" else zin.read(item.filename)
                zout.writestr(item, data)
    os.replace(tmp, path)
    return backup


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-parents", action="store_true")
    ap.add_argument("--min-year", type=int, default=0)
    ap.add_argument("--max-year", type=int, default=9999)
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    headers, papers = read_xlsx_rows(XLSX)
    pdfs = list_pdfs()
    by_row = {p.row: p for p in papers}

    pdf_matches = []
    parent_updates = {}
    matched_refs_rows = []
    missing_candidates = []
    extraction_failures = []

    target_papers = []
    for paper in papers:
        try:
            year = int(float(paper.values.get("Year", "0") or 0))
        except ValueError:
            year = 0
        if args.min_year <= year <= args.max_year:
            target_papers.append(paper)

    for paper in target_papers:
        title = paper.values.get("Paper", "")
        if "NON-RGBT IDEA-ONLY" in title:
            continue
        score, pdf = best_pdf_for_title(title, pdfs)
        pdf_matches.append([paper.row, paper.values.get("Year", ""), title, f"{score:.3f}", str(pdf or "")])
        if not pdf:
            extraction_failures.append([paper.row, title, "no_pdf_match"])
            continue
        text = pdf_to_text(pdf)
        refs_text = references_section(text)
        refs = split_references(refs_text)
        if len(refs) < 3:
            extraction_failures.append([paper.row, title, f"refs_extracted={len(refs)}", str(pdf)])
            continue
        matched_parent_rows = []
        for ref in refs:
            score2, matched = match_existing_ref(ref, papers)
            if matched:
                if matched.row == paper.row:
                    continue
                if not is_eligible_paper(matched.values):
                    continue
                if "Idea-only / Not RGB-T" in matched.values.get("Type", ""):
                    continue
                matched_parent_rows.append(matched.row)
                matched_refs_rows.append([
                    paper.row,
                    paper.values.get("Paper", ""),
                    matched.row,
                    matched.values.get("Paper", ""),
                    f"{score2:.3f}",
                    ref[:500],
                ])
            elif is_relevant_text(ref):
                rating = rating_from_ref(ref)
                if is_eligible_rating(rating):
                    missing_candidates.append([
                        paper.row,
                        paper.values.get("Paper", ""),
                        rating,
                        ref[:800],
                    ])
        existing = [
            r
            for r in parse_parent_rows(paper.values.get("Parents", ""))
            if r in by_row
            and r != paper.row
            and is_eligible_paper(by_row[r].values)
            and "Idea-only / Not RGB-T" not in by_row[r].values.get("Type", "")
        ]
        combined = sorted(set(existing) | set(matched_parent_rows))
        parent_updates[paper.row] = compress_rows(combined)

    def write_tsv(name, rows, header):
        with (OUT / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(header)
            w.writerows(rows)

    write_tsv("pdf_matches.tsv", pdf_matches, ["row", "year", "paper", "score", "pdf"])
    write_tsv("matched_existing_refs.tsv", matched_refs_rows, ["paper_row", "paper", "parent_row", "parent", "score", "reference"])
    write_tsv("missing_eligible_candidates.tsv", missing_candidates, ["citing_row", "citing_paper", "inferred_rating", "reference"])
    write_tsv("extraction_failures.tsv", extraction_failures, ["row", "paper", "reason", "pdf"])
    write_tsv(
        "parent_updates.tsv",
        [[r, by_row[r].values.get("Paper", ""), by_row[r].values.get("Parents", ""), v] for r, v in sorted(parent_updates.items())],
        ["row", "paper", "old_parents", "new_parents"],
    )

    if args.write_parents:
        backup = update_parents_xlsx(XLSX, parent_updates)
        print(f"wrote parents; backup={backup}")
    print(f"target_papers={len(target_papers)}")
    print(f"pdf_matches={sum(1 for r in pdf_matches if r[4])}/{len(pdf_matches)}")
    print(f"matched_existing_refs={len(matched_refs_rows)}")
    print(f"missing_eligible_candidates={len(missing_candidates)}")
    print(f"extraction_failures={len(extraction_failures)}")
    print(f"out={OUT}")


if __name__ == "__main__":
    main()
