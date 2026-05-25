import csv
import difflib
import re
import sqlite3
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


BASE = Path(__file__).resolve().parent
EXCEL_PATH = BASE / "papers_sorted_by_year.xlsx"
ZOTERO_COPY = Path(tempfile.gettempdir()) / "zotero_real_query_copy.sqlite"
OUT_PLAN = BASE / "zotero_tracking_tag_plan.tsv"
OUT_UNMATCHED_ZOTERO = BASE / "zotero_tracking_unmatched_to_excel.tsv"
OUT_UNMATCHED_EXCEL = BASE / "excel_unmatched_to_zotero_tracking.tsv"

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
STRUCTURED_PREFIXES = (
    "task:",
    "scope:",
    "arch:",
    "fusion:",
    "role:",
    "dataset:",
    "problem:",
    "tier:",
    "status:",
    "source:",
)


def q(tag):
    return f"{{{NS}}}{tag}"


def colnum(ref):
    letters = "".join(ch for ch in ref if ch.isalpha())
    num = 0
    for ch in letters:
        num = num * 26 + ord(ch.upper()) - 64
    return num


def norm_title(text):
    text = (text or "").lower().replace("&", "and")
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    stop = {"a", "an", "the", "via", "for", "of", "and", "with", "using", "based", "towards", "toward"}
    return " ".join(token for token in text.split() if token not in stop)


def read_excel(path):
    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [
                "".join((text.text or "") for text in item.findall(".//" + q("t")))
                for item in shared_root.findall(q("si"))
            ]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    rows = []
    for row in sheet.findall(".//" + q("sheetData") + "/" + q("row")):
        values = {}
        for cell in row.findall(q("c")):
            column = colnum(cell.attrib["r"])
            if column > 7:
                continue
            cell_type = cell.attrib.get("t")
            if cell_type == "inlineStr":
                value = "".join((text.text or "") for text in cell.findall(".//" + q("t")))
            else:
                raw = cell.find(q("v"))
                if raw is None:
                    value = ""
                elif cell_type == "s":
                    value = shared[int(raw.text)]
                else:
                    value = raw.text or ""
            values[column] = value
        rows.append((int(row.attrib["r"]), values))

    rows.sort(key=lambda item: item[0])
    columns = {value: key for key, value in rows[0][1].items()}
    papers = []
    for row_num, values in rows[1:]:
        papers.append(
            {
                "excel_row": row_num,
                "year": int(float(values.get(columns["Year"], 0))),
                "venue": values.get(columns["Venue"], "") or "",
                "rating": values.get(columns["Rating"], "") or "",
                "title": values.get(columns["Paper"], "") or "",
                "type": values.get(columns["Type"], "") or "",
                "core": values.get(columns["Core Idea"], "") or "",
                "parents": values.get(columns["Parents"], "") or "",
            }
        )
    return papers


def zotero_tracking_items(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    collection = conn.execute("SELECT collectionID FROM collections WHERE collectionName='Tracking'").fetchone()
    if not collection:
        raise RuntimeError("Tracking collection not found in Zotero database copy")
    collection_id = collection["collectionID"]
    query = """
    SELECT i.itemID, i.key, it.typeName,
           MAX(CASE WHEN f.fieldName='title' THEN v.value END) AS title,
           MAX(CASE WHEN f.fieldName='date' THEN v.value END) AS date,
           MAX(CASE WHEN f.fieldName='DOI' THEN v.value END) AS doi,
           MAX(CASE WHEN f.fieldName='publicationTitle' THEN v.value END) AS publicationTitle,
           MAX(CASE WHEN f.fieldName='conferenceName' THEN v.value END) AS conferenceName,
           MAX(CASE WHEN f.fieldName='proceedingsTitle' THEN v.value END) AS proceedingsTitle
    FROM collectionItems ci
    JOIN items i ON ci.itemID=i.itemID
    JOIN itemTypes it ON i.itemTypeID=it.itemTypeID
    LEFT JOIN deletedItems di ON i.itemID=di.itemID
    LEFT JOIN itemData d ON i.itemID=d.itemID
    LEFT JOIN fields f ON d.fieldID=f.fieldID
    LEFT JOIN itemDataValues v ON d.valueID=v.valueID
    WHERE ci.collectionID=? AND di.itemID IS NULL
      AND it.typeName NOT IN ('attachment','note','annotation')
    GROUP BY i.itemID, i.key, it.typeName
    ORDER BY title COLLATE NOCASE
    """
    rows = [dict(row) for row in conn.execute(query, (collection_id,)).fetchall()]
    for row in rows:
        tags = [
            item["name"]
            for item in conn.execute(
                "SELECT tags.name FROM itemTags JOIN tags ON itemTags.tagID=tags.tagID WHERE itemTags.itemID=? ORDER BY tags.name",
                (row["itemID"],),
            )
        ]
        row["existing_tags"] = "; ".join(tags)
    conn.close()
    return rows


def add_once(tags, tag):
    if tag and tag not in tags:
        tags.append(tag)


def derive_tags(paper):
    title = paper["title"]
    paper_type = paper["type"]
    core = paper["core"]
    year = paper["year"]
    text = f"{title} {paper_type} {core}".lower()
    tags = []

    idea_only = "non-rgbt idea-only" in text
    if idea_only:
        add_once(tags, "task:Non-RGBT-Idea")
        add_once(tags, "role:Idea-Only")
    else:
        if any(key in text for key in ["rgb-t", "rgbt", "thermal", "infrared", "visible", "grayscale"]):
            add_once(tags, "task:RGB-T")
        if any(key in text for key in ["rgb-d", "depth", "rgbdt"]):
            add_once(tags, "task:RGB-D")
        if any(key in text for key in ["rgb-e", "event"]):
            add_once(tags, "task:RGB-E")
        if any(
            key in text
            for key in [
                "rgb-x",
                "any-modality",
                "any modality",
                "unified tracking",
                "unified framework",
                "multispectral",
                "multi-modal visual object tracking",
                "unified multimodal",
                "single- and multi-modal",
            ]
        ):
            add_once(tags, "task:RGB-X/Any-Modality")

    if "segment" in text or "vos" in text:
        add_once(tags, "scope:Tracking+Segmentation")
    else:
        add_once(tags, "scope:SOT")

    if any(key in text for key in ["mamba", "ssm", "state space"]):
        add_once(tags, "arch:Mamba/SSM")
    if any(key in text for key in ["transformer", "vit", "token", "query"]):
        add_once(tags, "arch:Transformer/ViT")
    if any(key in text for key in ["cnn", "siamese", "convolutional", "fully convolutional"]):
        add_once(tags, "arch:CNN/Siamese")
    if any(key in text for key in ["sparse", "graph", "correlation filter", "manifold", "ranking", "laplacian"]):
        add_once(tags, "arch:Traditional/Sparse-Graph-CF")
    if any(key in text for key in ["foundation", "generalist", "single-model", "single model"]):
        add_once(tags, "arch:Foundation/Generalist")

    if any(key in text for key in ["prompt", "adapter", "lora", "peft", "test-time", "test time"]):
        add_once(tags, "fusion:Prompt/Adapter/PEFT")
    if any(key in text for key in ["attention", "cross-attention", "cross attention", "query fusion"]):
        add_once(tags, "fusion:Attention/Cross-Attention")
    if any(key in text for key in ["moe", "mixture-of-experts", "mixture of experts", "routing", "router"]):
        add_once(tags, "fusion:MoE/Routing")
    if any(key in text for key in ["align", "alignment", "unaligned", "deformable"]):
        add_once(tags, "fusion:Alignment/Deformable")
    if any(key in text for key in ["decoupl", "disentangl", "de-bias", "debias"]):
        add_once(tags, "fusion:Decoupling/Debiasing")
    if any(key in text for key in ["reliability", "quality", "uncertainty", "modality-missing", "missing modality", "missing"]):
        add_once(tags, "fusion:Reliability/Missing-Modality")
    if any(key in text for key in ["dynamic", "adaptive", "gated", "gate"]):
        add_once(tags, "fusion:Adaptive/Dynamic")

    if "datasets:" in core.lower() or "benchmark" in text or "dataset" in text:
        add_once(tags, "role:Dataset/Benchmark")
        match = re.search(r"Datasets:\s*(.*)$", core)
        if match:
            for name in re.split(r",\s*", match.group(1).strip()):
                clean = name.replace(" (original, 654 sequences)", "").replace(" (expanded, 1000 sequences)", "")
                add_once(tags, "dataset:" + clean)

    if "uav" in text or "drone" in text:
        add_once(tags, "problem:UAV/Drone")
    if any(key in text for key in ["adversarial", "attack", "stealth"]):
        add_once(tags, "problem:Adversarial/Robustness")
    if "low-light" in text or "low light" in text:
        add_once(tags, "problem:Low-Light")

    tier = "tier:T3-Background"
    if (
        "datasets:" in core.lower()
        or any(key in text for key in ["mamba", "unified", "any-modality", "any modality", "foundation", "generalist", "prompt", "adapter", "lora", "moe", "routing"])
    ):
        tier = "tier:T1-Baseline"
    elif year >= 2020 and any(key in text for key in ["transformer", "attention", "quality", "reliability", "adaptive", "dynamic", "cross-modal", "fusion"]):
        tier = "tier:T2-Inspiration"
    elif year >= 2024:
        tier = "tier:T2-Inspiration"
    if paper["excel_row"] in {2, 7, 13, 20, 25, 35, 41, 45, 47, 54, 62, 75, 88, 89, 90, 91, 92, 121, 144}:
        tier = "tier:T1-Baseline"
    if idea_only:
        tier = "tier:T3-Background"

    add_once(tags, tier)
    add_once(tags, "status:Skimmed")
    add_once(tags, "source:Excel-RGBT-SOT")
    return tags


def build_plan():
    excel = read_excel(EXCEL_PATH)
    zotero_items = zotero_tracking_items(ZOTERO_COPY)
    excel_by_norm = {norm_title(item["title"]): item for item in excel}
    excel_norms = list(excel_by_norm)

    matched = []
    unmatched_zotero = []
    used_excel = set()
    for item in zotero_items:
        normalized = norm_title(item["title"])
        best = None
        score = 0.0
        if normalized in excel_by_norm:
            best = excel_by_norm[normalized]
            score = 1.0
        else:
            for candidate in excel_norms:
                candidate_score = difflib.SequenceMatcher(None, normalized, candidate).ratio()
                if candidate_score > score:
                    best = excel_by_norm[candidate]
                    score = candidate_score
        if best and score >= 0.88:
            tags = derive_tags(best)
            matched.append((item, best, score, tags))
            used_excel.add(best["excel_row"])
        else:
            unmatched_zotero.append((item, score, best))

    with OUT_PLAN.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "zotero_itemID",
                "zotero_key",
                "zotero_type",
                "zotero_title",
                "zotero_date",
                "excel_row",
                "excel_year",
                "excel_venue",
                "excel_rating",
                "excel_type",
                "excel_core",
                "match_score",
                "proposed_tags",
                "existing_tags",
            ]
        )
        for item, paper, score, tags in sorted(matched, key=lambda entry: (entry[1]["year"], entry[1]["excel_row"]), reverse=True):
            writer.writerow(
                [
                    item["itemID"],
                    item["key"],
                    item["typeName"],
                    item["title"] or "",
                    item["date"] or "",
                    paper["excel_row"],
                    paper["year"],
                    paper["venue"],
                    paper["rating"],
                    paper["type"],
                    paper["core"],
                    f"{score:.3f}",
                    "; ".join(tags),
                    item.get("existing_tags", ""),
                ]
            )

    with OUT_UNMATCHED_ZOTERO.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["zotero_itemID", "zotero_type", "zotero_date", "zotero_title", "best_score", "best_excel_row", "best_excel_title"])
        for item, score, best in sorted(unmatched_zotero, key=lambda entry: (entry[0]["date"] or "", entry[0]["title"] or ""), reverse=True):
            writer.writerow([item["itemID"], item["typeName"], item["date"] or "", item["title"] or "", f"{score:.3f}", best["excel_row"] if best else "", best["title"] if best else ""])

    with OUT_UNMATCHED_EXCEL.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["excel_row", "year", "venue", "rating", "type", "core", "title"])
        for paper in excel:
            if paper["excel_row"] not in used_excel:
                writer.writerow([paper["excel_row"], paper["year"], paper["venue"], paper["rating"], paper["type"], paper["core"], paper["title"]])

    return matched, unmatched_zotero, len(excel) - len(used_excel)


def main():
    matched, unmatched_zotero, unmatched_excel_count = build_plan()
    print(f"matched_excel_items={len(matched)}")
    print(f"unmatched_zotero_items={len(unmatched_zotero)}")
    print(f"unmatched_excel_items={unmatched_excel_count}")
    print(f"plan={OUT_PLAN}")
    print(f"unmatched_zotero={OUT_UNMATCHED_ZOTERO}")
    print(f"unmatched_excel={OUT_UNMATCHED_EXCEL}")


if __name__ == "__main__":
    main()
