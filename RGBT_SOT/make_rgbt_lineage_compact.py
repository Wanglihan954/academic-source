import csv
import html
import math
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path


BASE = Path(__file__).resolve().parent
XLSX = BASE / "papers_sorted_by_year.xlsx"
OUT_HTML = BASE / "rgbt_paper_lineage_compact.html"
OUT_SVG = BASE / "rgbt_paper_lineage_compact.svg"
OUT_NODES = BASE / "rgbt_paper_lineage_compact_nodes.csv"
OUT_EDGES = BASE / "rgbt_paper_lineage_compact_edges.csv"

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def q(tag):
    return f"{{{NS}}}{tag}"


def colnum(ref):
    letters = "".join(ch for ch in ref if ch.isalpha())
    num = 0
    for ch in letters:
        num = num * 26 + ord(ch.upper()) - 64
    return num


def parse_parents(raw):
    nums = []
    normalized = str(raw or "").replace("\uff0c", ",").replace("\uff1b", ";")
    for part in re.split(r"[,;\s]+", normalized.strip()):
        if not part:
            continue
        match = re.fullmatch(r"(\d+)-(\d+)", part)
        if match:
            start, end = map(int, match.groups())
            if start <= end:
                nums.extend(range(start, end + 1))
            continue
        if re.fullmatch(r"\d+", part):
            nums.append(int(part))
    return nums


def read_xlsx_rows(path):
    with zipfile.ZipFile(path) as archive:
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
            value = cell.find(q("v"))
            if value is None:
                text = ""
            elif cell.attrib.get("t") == "s":
                text = shared[int(value.text)]
            else:
                text = value.text or ""
            values[colnum(cell.attrib["r"])] = text
        rows.append((int(row.attrib["r"]), values))
    return rows


def classify(paper):
    text = f"{paper['title']} {paper['core']} {paper['type']}".lower()
    if paper["datasets"]:
        return "dataset"
    if paper["year"] <= 2012 or any(
        key in text
        for key in [
            "surveillance",
            "particle",
            "spatiogram",
            "belief propagation",
            "contour",
            "mean-shift",
            "mean shift",
            "registration",
            "sensor fusion",
        ]
    ):
        return "early"
    if any(
        key in text
        for key in [
            "unified",
            "rgb-x",
            "any-modality",
            "any modality",
            "foundation",
            "generalist",
            "blind",
            "onetracker",
            "one tracker",
            "sequence-to-sequence",
            "single-model",
            "single model",
            "dreamtrack",
        ]
    ):
        return "unified"
    if any(
        key in text
        for key in ["prompt", "adapter", "lora", "peft", "test-time", "test time"]
    ):
        return "prompt"
    if any(
        key in text
        for key in [
            "transformer",
            "attention",
            "query",
            "token",
            "mamba",
            "ssm",
            "state space",
            "routing",
            "moe",
            "temporal propagation",
        ]
    ):
        return "transformer"
    if any(
        key in text
        for key in [
            "uav",
            "missing",
            "modality validity",
            "low-light",
            "low light",
            "adversarial",
            "attack",
            "robust",
            "quality",
            "reliability",
            "uncertainty",
            "unaligned",
            "alignment",
            "de-biasing",
            "debiasing",
        ]
    ):
        return "robust"
    if any(
        key in text
        for key in [
            "sparse",
            "graph",
            "correlation filter",
            "correlation",
            "low-rank",
            "manifold",
            "ranking",
            "collaborative",
            "laplacian",
            "template learning",
        ]
    ):
        return "traditional"
    return "deep"


def stage(year):
    if year <= 2016:
        return "2004-2016"
    if year <= 2019:
        return "2017-2019"
    if year <= 2022:
        return "2020-2022"
    if year <= 2024:
        return "2023-2024"
    return "2025-2026"


def label_for(paper):
    row_labels = {
        151: "Sparse Data Fusion",
        153: "Thermo-Spatiograms",
        149: "Joint Sparse Fusion",
        145: "Laplacian Sparse",
        142: "Sparse Graph",
        140: "Soft-consistent CF",
        136: "CMR",
        137: "Two-Stream CNN",
        124: "Multi-adapter",
        125: "E2E RGBT",
        119: "Dense Aggreg.",
        123: "Deep Adapt. Fusion",
        129: "SiamFT",
        112: "Pattern Prop.",
        113: "Challenge-aware",
        106: "Multi-Adapter HDL",
        107: "Attribute-driven",
        108: "Quality-aware",
        115: "Modal Attention",
        88: "APFNet",
        91: "ProTrack",
        96: "MFGNet",
        98: "DMCNet",
        73: "Template-Search",
        75: "ViPT",
        77: "Fusion Strategy",
        85: "SiamCAF",
        42: "Bi-dir Adapter",
        44: "Modality Prompt",
        45: "OneTracker",
        46: "SDSTrack",
        47: "Any-Modality",
        49: "Unified Stage",
        50: "ST Contexts",
        20: "SUTrack",
        25: "CSTrack",
        31: "Debiasing",
        35: "MambaVT",
        36: "Adaptive Percep.",
        41: "AFTER",
        2: "CADTrack",
        4: "LoRA RGBT",
        6: "Any-Modality",
        13: "UETrack",
    }
    if paper["row"] in row_labels:
        return row_labels[paper["row"]]
    if paper["datasets"]:
        dataset_labels = {
            "RGBT234-Miss, LasHeR245-Miss, VTUAV176-Miss": "Miss-RGBT Benchmarks",
            "CMOTB (expanded, 1000 sequences)": "CMOTB-expanded",
            "CMOTB (original, 654 sequences)": "CMOTB-original",
        }
        return dataset_labels.get(paper["datasets"], paper["datasets"])
    title = paper["title"]
    patterns = [
        r"^([A-Z][A-Za-z0-9-]{2,12}):",
        r"\b([A-Z][A-Za-z0-9-]{2,12}Net)\b",
        r"\b([A-Z][A-Za-z0-9-]{2,12}Track)\b",
        r"\b([A-Z][A-Za-z0-9-]{2,12}Tracker)\b",
        r"\b([A-Z][A-Za-z0-9-]{2,12}Former)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            return match.group(1)
    short = re.sub(r"\s+", " ", title).strip()
    if len(short) > 34:
        short = short[:33] + "."
    return short


def escape(text):
    return html.escape(str(text), quote=True)


def radius_for(degree, is_dataset):
    # Degree is computed in the full graph. This stronger normalized scaling
    # makes high-connectivity benchmark nodes visibly dominant in the compact
    # figure while keeping low-degree recent nodes readable.
    max_degree = 84
    normalized = min(max(degree, 0), max_degree) / max_degree
    base = 4.6 + (normalized**0.55) * 25.0
    if is_dataset:
        base += 2.4
    return max(6.4, min(base, 33.0))


def load_papers():
    rows = read_xlsx_rows(XLSX)
    columns = {value: key for key, value in rows[0][1].items()}
    papers = []
    for row_num, values in rows[1:]:
        core = values.get(columns["Core Idea"], "") or ""
        dataset_match = re.search(r"Datasets:\s*(.*)$", core)
        papers.append(
            {
                "row": row_num,
                "year": int(float(values.get(columns["Year"], 0))),
                "venue": values.get(columns["Venue"], "") or "",
                "rating": values.get(columns["Rating"], "") or "",
                "title": (values.get(columns["Paper"], "") or "").strip(),
                "type": values.get(columns["Type"], "") or "",
                "core": core,
                "parents_raw": values.get(columns["Parents"], "") or "",
                "parents": parse_parents(values.get(columns["Parents"], "")),
                "datasets": dataset_match.group(1).strip() if dataset_match else "",
            }
        )
    by_row = {paper["row"]: paper for paper in papers}
    incoming = Counter()
    outgoing = Counter()
    for paper in papers:
        for parent in paper["parents"]:
            if parent in by_row:
                outgoing[parent] += 1
                incoming[paper["row"]] += 1
    for paper in papers:
        paper["in_degree"] = incoming[paper["row"]]
        paper["out_degree"] = outgoing[paper["row"]]
        paper["degree"] = paper["in_degree"] + paper["out_degree"]
        paper["lane"] = classify(paper)
        paper["stage"] = stage(paper["year"])
        paper["label"] = label_for(paper)
    return papers


def select_compact_nodes(papers):
    selected = {paper["row"] for paper in papers if paper["datasets"]}

    # Handpicked anchors keep the story coherent even when degree is modest.
    # The compact figure intentionally favors readability over exhaustiveness.
    anchors = {
        151, 153, 149, 144, 145, 142, 140, 136, 137, 121, 124, 125,
        119, 123, 129, 112, 113, 106, 107, 108, 115, 88, 91, 96, 98,
        73, 75, 77, 85, 42, 44, 45, 46, 47, 49, 50,
        20, 25, 31, 35, 36, 41, 2, 4, 6, 7, 13,
    }
    selected.update(anchors)
    return selected


def compact_edges(papers, selected):
    by_row = {paper["row"]: paper for paper in papers}
    edges_by_target = defaultdict(list)
    for paper in papers:
        if paper["row"] not in selected:
            continue
        for parent in paper["parents"]:
            if parent in selected and parent in by_row:
                edges_by_target[paper["row"]].append((parent, paper["row"]))

    edges = []
    for target, target_edges in edges_by_target.items():
        dataset_edges = [
            edge for edge in target_edges if by_row[edge[0]]["datasets"]
        ]
        method_edges = [
            edge for edge in target_edges if not by_row[edge[0]]["datasets"]
        ]
        dataset_edges.sort(key=lambda edge: -by_row[edge[0]]["degree"])
        method_edges.sort(key=lambda edge: -by_row[edge[0]]["degree"])

        chosen = dataset_edges[:3]
        remaining = max(0, 3 - len(chosen))
        chosen.extend(method_edges[:remaining])
        edges.extend(chosen)

    return sorted(set(edges), key=lambda edge: (by_row[edge[1]]["year"], edge[1], edge[0]))


def layout(papers, selected):
    stages = ["2004-2016", "2017-2019", "2020-2022", "2023-2024", "2025-2026"]
    lanes = [
        ("dataset", "Datasets / Benchmarks"),
        ("foundation", "Early + Sparse / Graph / CF"),
        ("deep", "CNN / Siamese / Fusion"),
        ("attention", "Transformer / Prompt / Mamba"),
        ("unified", "Unified RGB-X / Foundation"),
        ("robust", "Robustness / UAV / Missing"),
    ]
    stage_index = {name: index for index, name in enumerate(stages)}
    lane_index = {key: index for index, (key, _) in enumerate(lanes)}

    left = 185
    top = 145
    stage_width = 285
    lane_height = 108
    width = left + stage_width * len(stages) + 52
    height = top + lane_height * len(lanes) + 82

    groups = defaultdict(list)
    selected_papers = [paper for paper in papers if paper["row"] in selected]
    for paper in selected_papers:
        if paper["lane"] in {"early", "traditional"}:
            paper["plot_lane"] = "foundation"
        elif paper["lane"] in {"transformer", "prompt"}:
            paper["plot_lane"] = "attention"
        else:
            paper["plot_lane"] = paper["lane"]
        groups[(paper["stage"], paper["plot_lane"])].append(paper)

    for group in groups.values():
        group.sort(key=lambda item: (-item["degree"], item["year"], item["row"]))

    for (stage_name, lane), group in groups.items():
        stage_i = stage_index[stage_name]
        lane_i = lane_index[lane]
        center_x = left + stage_i * stage_width + stage_width / 2
        center_y = top + lane_i * lane_height + lane_height / 2
        count = len(group)
        if count <= 1:
            positions = [(0, 0)]
        elif count == 2:
            positions = [(-54, 0), (54, 0)]
        elif count == 3:
            positions = [(-66, -8), (0, 12), (66, -8)]
        elif count == 4:
            positions = [(-68, -17), (68, -17), (-68, 21), (68, 21)]
        else:
            columns = 3
            rows = math.ceil(count / columns)
            positions = []
            for index in range(count):
                col = index % columns
                row = index // columns
                positions.append(((col - 1) * 82, (row - (rows - 1) / 2) * 31))
        for paper, (dx, dy) in zip(group, positions):
            paper["x"] = center_x + dx
            paper["y"] = center_y + dy
            paper["radius"] = radius_for(paper["degree"], bool(paper["datasets"]))

    return selected_papers, stages, lanes, width, height, left, top, stage_width, lane_height


def write_outputs(papers):
    selected = select_compact_nodes(papers)
    selected_papers, stages, lanes, width, height, left, top, stage_width, lane_height = layout(
        papers, selected
    )
    by_row = {paper["row"]: paper for paper in papers}
    selected_by_row = {paper["row"]: paper for paper in selected_papers}
    edges = compact_edges(papers, selected)

    colors = {
        "dataset": "#d95f02",
        "traditional": "#8c6d31",
        "deep": "#2f8f4e",
        "transformer": "#386cb0",
        "prompt": "#756bb1",
        "unified": "#1b9e77",
        "robust": "#c51b7d",
        "early": "#666666",
    }

    svg = []
    svg.append(
        f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">Compact RGB-T Single Object Tracking Paper Lineage</title>
<desc id="desc">A compact stage-wise paper lineage graph. Marker size encodes total degree in the full parent graph. Diamond markers indicate dataset and benchmark papers.</desc>
<style>
  .background {{ fill: #fcfbf7; }}
  .stage-band {{ fill: #fffdf8; stroke: #ded8ca; stroke-width: 1; }}
  .stage-band.alt {{ fill: #f5f2eb; }}
  .lane-line {{ stroke: #e0dbcf; stroke-width: 1; }}
  .stage-label {{ font: 700 18px Arial, sans-serif; fill: #242424; }}
  .lane-label {{ font: 700 14px Arial, sans-serif; fill: #363636; }}
  .title {{ font: 700 26px Arial, sans-serif; fill: #181818; }}
  .subtitle {{ font: 14px Arial, sans-serif; fill: #555; }}
  .caption {{ font: 13px Arial, sans-serif; fill: #4b4b4b; }}
  .legend {{ font: 12px Arial, sans-serif; fill: #333; }}
  .edge {{ fill: none; stroke: #777; stroke-width: 1.35; opacity: 0.28; marker-end: url(#arrow); }}
  .edge.dataset-edge {{ stroke: #d95f02; stroke-width: 2.2; stroke-dasharray: 6 5; opacity: 0.54; marker-end: url(#arrowDataset); }}
  .marker {{ stroke: #222; stroke-width: 1.1; }}
  .dataset-marker {{ stroke: #753100; stroke-width: 2.4; }}
  .node-label {{ font: 11.5px Arial, sans-serif; fill: #1e1e1e; paint-order: stroke; stroke: #fcfbf7; stroke-width: 4px; stroke-linejoin: round; }}
  .node-meta {{ font: 9.5px Arial, sans-serif; fill: #555; paint-order: stroke; stroke: #fcfbf7; stroke-width: 3px; stroke-linejoin: round; }}
</style>
<defs>
  <marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto" markerUnits="strokeWidth">
    <path d="M 0 0 L 7 3.5 L 0 7 z" fill="#777" opacity="0.42"/>
  </marker>
  <marker id="arrowDataset" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
    <path d="M 0 0 L 8 4 L 0 8 z" fill="#d95f02" opacity="0.72"/>
  </marker>
</defs>
<rect class="background" x="0" y="0" width="100%" height="100%"/>
<text class="title" x="34" y="44">RGB-T / RGB-X SOT: Compact Paper Lineage</text>
<text class="subtitle" x="34" y="70">Selected representative papers from the full Excel graph. Marker size encodes full-graph degree; diamonds are dataset / benchmark papers.</text>
'''
    )

    legend_y = 104
    svg.append(f'<g transform="translate(34,{legend_y})">')
    svg.append(
        '<circle cx="10" cy="0" r="8" fill="#386cb0" stroke="#222" stroke-width="1.1"/>'
        '<text class="legend" x="26" y="4">method paper</text>'
    )
    svg.append(
        '<path d="M155,-13 L168,0 L155,13 L142,0 Z" fill="#d95f02" stroke="#753100" stroke-width="2.2"/>'
        '<text class="legend" x="184" y="4">dataset / benchmark paper</text>'
    )
    svg.append(
        '<circle cx="385" cy="0" r="6" fill="#999" stroke="#222" stroke-width="1"/>'
        '<circle cx="427" cy="0" r="28" fill="none" stroke="#222" stroke-width="1.2"/>'
        '<text class="legend" x="464" y="4">larger marker = more full-graph edges</text>'
    )
    svg.append(
        '<path d="M690,0 C715,0 715,0 742,0" class="edge"/>'
        '<text class="legend" x="758" y="4">selected lineage edge</text>'
    )
    svg.append(
        '<path d="M930,0 C955,0 955,0 982,0" class="edge dataset-edge"/>'
        '<text class="legend" x="1000" y="4">benchmark influence</text>'
    )
    svg.append("</g>")

    plot_height = lane_height * len(lanes)
    for stage_i, stage_name in enumerate(stages):
        x = left + stage_i * stage_width
        css = "stage-band alt" if stage_i % 2 else "stage-band"
        svg.append(
            f'<rect class="{css}" x="{x}" y="{top}" width="{stage_width}" height="{plot_height}"/>'
        )
        svg.append(
            f'<text class="stage-label" x="{x + stage_width / 2:.1f}" y="{top - 18}" text-anchor="middle">{escape(stage_name)}</text>'
        )

    for lane_i, (_, label) in enumerate(lanes):
        y = top + lane_i * lane_height
        svg.append(
            f'<line class="lane-line" x1="20" y1="{y}" x2="{width - 45}" y2="{y}"/>'
        )
        svg.append(
            f'<text class="lane-label" x="30" y="{y + lane_height / 2 + 5}">{escape(label)}</text>'
        )
    svg.append(
        f'<line class="lane-line" x1="20" y1="{top + plot_height}" x2="{width - 45}" y2="{top + plot_height}"/>'
    )

    for source, target in edges:
        if source not in selected_by_row or target not in selected_by_row:
            continue
        s = selected_by_row[source]
        t = selected_by_row[target]
        sx, sy = s["x"], s["y"]
        tx, ty = t["x"], t["y"]
        midx = (sx + tx) / 2
        cls = "edge dataset-edge" if s["datasets"] else "edge"
        tooltip = f"{s['label']} -> {t['label']}"
        svg.append(
            f'<path class="{cls}" d="M {sx:.1f},{sy:.1f} C {midx:.1f},{sy:.1f} {midx:.1f},{ty:.1f} {tx:.1f},{ty:.1f}"><title>{escape(tooltip)}</title></path>'
        )

    for paper in selected_papers:
        x, y, r = paper["x"], paper["y"], paper["radius"]
        color = colors[paper["lane"]]
        tooltip = (
            f"Row {paper['row']} | {paper['year']} | {paper['venue']} | {paper['rating']}\n"
            f"{paper['title']}\n"
            f"Core: {paper['core']}\n"
            f"Full-graph degree: {paper['degree']} (in {paper['in_degree']}, out {paper['out_degree']})\n"
            f"Parents: {paper['parents_raw'] or 'None'}"
        )
        if paper["datasets"]:
            svg.append(
                f'<path class="marker dataset-marker" d="M {x:.1f},{y-r:.1f} L {x+r:.1f},{y:.1f} L {x:.1f},{y+r:.1f} L {x-r:.1f},{y:.1f} Z" fill="{color}"><title>{escape(tooltip)}</title></path>'
            )
        else:
            svg.append(
                f'<circle class="marker" cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{color}"><title>{escape(tooltip)}</title></circle>'
            )

    # Draw labels after all markers so every label stays readable.
    for paper in selected_papers:
        x, y = paper["x"], paper["y"]
        label = escape(paper["label"])
        meta = escape(f"d={paper['degree']}")
        x_offset = paper["radius"] + 6
        y_offset = -4
        svg.append(
            f'<text class="node-label" x="{x + x_offset:.1f}" y="{y + y_offset:.1f}">{label}</text>'
        )
        svg.append(
            f'<text class="node-meta" x="{x + x_offset:.1f}" y="{y + y_offset + 12:.1f}">{meta}</text>'
        )

    caption_y = top + plot_height + 38
    svg.append(
        f'<text class="caption" x="34" y="{caption_y}">Compact view keeps all dataset/benchmark papers and representative high-connectivity methods. Edges are filtered to the most informative selected parents per paper.</text>'
    )
    svg.append(
        f'<text class="caption" x="34" y="{caption_y + 22}">Full-graph degree is computed before filtering, so marker size reflects each paper&apos;s overall lineage role in the Excel database.</text>'
    )
    svg.append("</svg>")

    svg_text = "\n".join(svg)
    html_text = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Compact RGB-T SOT Paper Lineage</title>
<style>
  body {{ margin: 0; background: #ece7dc; color: #242424; font-family: Arial, sans-serif; }}
  header {{ padding: 18px 24px 12px; background: #fffdf8; border-bottom: 1px solid #d7d0c2; }}
  h1 {{ margin: 0 0 8px; font-size: 21px; }}
  p {{ margin: 4px 0; line-height: 1.45; max-width: 1220px; }}
  code {{ background: #f0ece3; padding: 1px 5px; border-radius: 3px; }}
  .wrap {{ overflow: auto; height: calc(100vh - 132px); }}
  svg {{ display: block; background: #fcfbf7; }}
  @media print {{
    @page {{ size: {width / 96:.2f}in {height / 96:.2f}in; margin: 0; }}
    body {{ background: #fcfbf7; }}
    header {{ display: none; }}
    .wrap {{ overflow: visible; height: auto; }}
  }}
</style>
</head>
<body>
<header>
  <h1>Compact RGB-T / RGB-X SOT Paper Lineage</h1>
  <p>This paper-body version keeps all dataset/benchmark nodes, selected representative methods, and filtered lineage edges from <code>Parents</code>.</p>
  <p>Hover markers and edges for full metadata. Marker size is proportional to the paper's total degree in the full Excel graph.</p>
</header>
<div class="wrap">
{svg_text}
</div>
</body>
</html>
"""

    OUT_SVG.write_text(svg_text, encoding="utf-8")
    OUT_HTML.write_text(html_text, encoding="utf-8")

    with OUT_NODES.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "row",
                "year",
                "stage",
                "lane",
                "label",
                "degree",
                "in_degree",
                "out_degree",
                "datasets",
                "title",
            ],
        )
        writer.writeheader()
        for paper in sorted(selected_papers, key=lambda item: (item["stage"], item["lane"], item["row"])):
            writer.writerow(
                {
                    "row": paper["row"],
                    "year": paper["year"],
                    "stage": paper["stage"],
                    "lane": paper["lane"],
                    "label": paper["label"],
                    "degree": paper["degree"],
                    "in_degree": paper["in_degree"],
                    "out_degree": paper["out_degree"],
                    "datasets": paper["datasets"],
                    "title": paper["title"],
                }
            )

    with OUT_EDGES.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source", "target", "source_label", "target_label", "dataset_edge"])
        writer.writeheader()
        for source, target in edges:
            source_paper = by_row[source]
            target_paper = by_row[target]
            writer.writerow(
                {
                    "source": source,
                    "target": target,
                    "source_label": source_paper["label"],
                    "target_label": target_paper["label"],
                    "dataset_edge": bool(source_paper["datasets"]),
                }
            )

    return selected_papers, edges


def main():
    papers = load_papers()
    selected_papers, edges = write_outputs(papers)
    dataset_count = sum(1 for paper in selected_papers if paper["datasets"])
    print(f"selected_nodes={len(selected_papers)}")
    print(f"selected_edges={len(edges)}")
    print(f"dataset_nodes={dataset_count}")
    print(f"svg={OUT_SVG}")
    print(f"html={OUT_HTML}")
    print(f"nodes_csv={OUT_NODES}")
    print(f"edges_csv={OUT_EDGES}")


if __name__ == "__main__":
    main()
