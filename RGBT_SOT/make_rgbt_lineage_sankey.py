import csv
import html
import math
from collections import Counter, defaultdict
from pathlib import Path

from make_rgbt_lineage_compact import classify, load_papers, stage


BASE = Path(__file__).resolve().parent
OUT_HTML = BASE / "rgbt_paper_lineage_sankey.html"
OUT_SVG = BASE / "rgbt_paper_lineage_sankey.svg"
OUT_NODES = BASE / "rgbt_paper_lineage_sankey_nodes.csv"
OUT_LINKS = BASE / "rgbt_paper_lineage_sankey_links.csv"
DISPLAY_WEIGHT_THRESHOLD = 5


STAGES = ["2004-2016", "2017-2019", "2020-2022", "2023-2024", "2025-2026"]
LANES = [
    ("dataset", "Datasets / Benchmarks"),
    ("foundation", "Early + Sparse / Graph / CF"),
    ("deep", "CNN / Siamese / Fusion"),
    ("attention", "Transformer / Prompt / Mamba"),
    ("unified", "Unified RGB-X / Foundation"),
    ("robust", "Robustness / UAV / Missing"),
]

COLORS = {
    "dataset": "#d95f02",
    "foundation": "#8c6d31",
    "deep": "#2f8f4e",
    "attention": "#386cb0",
    "unified": "#1b9e77",
    "robust": "#c51b7d",
}


def escape(text):
    return html.escape(str(text), quote=True)


def plot_lane(paper):
    lane = classify(paper)
    if lane in {"early", "traditional"}:
        return "foundation"
    if lane in {"prompt", "transformer"}:
        return "attention"
    return lane


def compact_dataset_names(names):
    short = []
    for name in names:
        if name == "RGBT234-Miss, LasHeR245-Miss, VTUAV176-Miss":
            short.append("Miss-RGBT")
        elif name == "CMOTB (expanded, 1000 sequences)":
            short.append("CMOTB-exp.")
        elif name == "CMOTB (original, 654 sequences)":
            short.append("CMOTB-orig.")
        else:
            short.append(name)
    return ", ".join(short)


def build_sankey():
    papers = load_papers()
    by_row = {paper["row"]: paper for paper in papers}
    stage_index = {name: index for index, name in enumerate(STAGES)}

    for paper in papers:
        paper["stage"] = stage(paper["year"])
        paper["plot_lane"] = plot_lane(paper)

    node_counts = Counter()
    dataset_names = defaultdict(list)
    for paper in papers:
        key = (paper["stage"], paper["plot_lane"])
        node_counts[key] += 1
        if paper["datasets"]:
            dataset_names[key].append(paper["datasets"])

    links = Counter()
    skipped_same_stage = 0
    skipped_reverse = 0
    total_parent_edges = 0
    for child in papers:
        child_key = (child["stage"], child["plot_lane"])
        for parent_row in child["parents"]:
            if parent_row not in by_row:
                continue
            total_parent_edges += 1
            parent = by_row[parent_row]
            parent_key = (parent["stage"], parent["plot_lane"])
            source_stage = stage_index[parent_key[0]]
            target_stage = stage_index[child_key[0]]
            if source_stage == target_stage:
                skipped_same_stage += 1
                continue
            if source_stage > target_stage:
                skipped_reverse += 1
                continue
            links[(parent_key, child_key)] += 1

    incoming = Counter()
    outgoing = Counter()
    for (source, target), weight in links.items():
        outgoing[source] += weight
        incoming[target] += weight

    nodes = []
    for stage_name in STAGES:
        for lane_key, lane_label in LANES:
            key = (stage_name, lane_key)
            paper_count = node_counts[key]
            if paper_count == 0 and incoming[key] == 0 and outgoing[key] == 0:
                continue
            datasets = compact_dataset_names(dataset_names[key])
            label = lane_label
            if lane_key == "dataset" and datasets:
                label = datasets
            value = max(incoming[key], outgoing[key], paper_count * 2)
            nodes.append(
                {
                    "key": key,
                    "stage": stage_name,
                    "lane": lane_key,
                    "label": label,
                    "paper_count": paper_count,
                    "incoming": incoming[key],
                    "outgoing": outgoing[key],
                    "value": value,
                    "datasets": datasets,
                }
            )

    node_by_key = {node["key"]: node for node in nodes}
    link_rows = []
    for (source, target), weight in links.items():
        if source in node_by_key and target in node_by_key:
            link_rows.append(
                {
                    "source": source,
                    "target": target,
                    "weight": weight,
                    "source_lane": source[1],
                    "target_lane": target[1],
                }
            )

    return {
        "papers": papers,
        "nodes": nodes,
        "links": link_rows,
        "total_parent_edges": total_parent_edges,
        "skipped_same_stage": skipped_same_stage,
        "skipped_reverse": skipped_reverse,
    }


def layout(data):
    stage_index = {name: index for index, name in enumerate(STAGES)}
    lane_index = {key: index for index, (key, _) in enumerate(LANES)}

    left = 205
    top = 132
    stage_width = 270
    lane_height = 88
    node_width = 22
    width = left + stage_width * len(STAGES) + 72
    height = top + lane_height * len(LANES) + 86

    max_value = max(node["value"] for node in data["nodes"])
    for node in data["nodes"]:
        x = left + stage_index[node["stage"]] * stage_width + 72
        y = top + lane_index[node["lane"]] * lane_height + lane_height / 2
        node["x"] = x
        node["y"] = y
        node["height"] = 18 + 56 * ((node["value"] / max_value) ** 0.62)
        node["width"] = node_width

    node_by_key = {node["key"]: node for node in data["nodes"]}
    display_links = [
        link for link in data["links"] if link["weight"] >= DISPLAY_WEIGHT_THRESHOLD
    ]
    data["display_links"] = display_links
    max_weight = max(link["weight"] for link in display_links) if display_links else 1
    outgoing_links = defaultdict(list)
    incoming_links = defaultdict(list)
    for link in display_links:
        source_node = node_by_key[link["source"]]
        target_node = node_by_key[link["target"]]
        outgoing_links[link["source"]].append(link)
        incoming_links[link["target"]].append(link)
        link["stroke"] = 1.2 + 17.0 * ((link["weight"] / max_weight) ** 0.62)
        link["source_color"] = COLORS[source_node["lane"]]
        link["target_color"] = COLORS[target_node["lane"]]

    for key, links in outgoing_links.items():
        node = node_by_key[key]
        links.sort(key=lambda item: (node_by_key[item["target"]]["y"], node_by_key[item["target"]]["x"]))
        total = sum(link["weight"] for link in links)
        cursor = -node["height"] / 2
        for link in links:
            segment = node["height"] * link["weight"] / total if total else 0
            link["source_y"] = node["y"] + cursor + segment / 2
            cursor += segment

    for key, links in incoming_links.items():
        node = node_by_key[key]
        links.sort(key=lambda item: (node_by_key[item["source"]]["y"], node_by_key[item["source"]]["x"]))
        total = sum(link["weight"] for link in links)
        cursor = -node["height"] / 2
        for link in links:
            segment = node["height"] * link["weight"] / total if total else 0
            link["target_y"] = node["y"] + cursor + segment / 2
            cursor += segment

    return width, height, left, top, stage_width, lane_height


def draw_svg(data):
    width, height, left, top, stage_width, lane_height = layout(data)
    node_by_key = {node["key"]: node for node in data["nodes"]}

    svg = []
    svg.append(
        f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">RGB-T SOT Lineage Sankey</title>
<desc id="desc">A stage-wise Sankey diagram generated from the Parents field. Link width encodes the number of cross-stage lineage edges.</desc>
<style>
  .background {{ fill: #fcfbf7; }}
  .stage-band {{ fill: #fffdf8; stroke: #ded8ca; stroke-width: 1; }}
  .stage-band.alt {{ fill: #f5f2eb; }}
  .lane-line {{ stroke: #e1dccf; stroke-width: 1; }}
  .title {{ font: 700 25px Arial, sans-serif; fill: #181818; }}
  .subtitle {{ font: 14px Arial, sans-serif; fill: #555; }}
  .stage-label {{ font: 700 17px Arial, sans-serif; fill: #242424; }}
  .lane-label {{ font: 700 13px Arial, sans-serif; fill: #333; }}
  .node-label {{ font: 11.2px Arial, sans-serif; fill: #191919; paint-order: stroke; stroke: #fcfbf7; stroke-width: 4px; stroke-linejoin: round; }}
  .node-meta {{ font: 9.4px Arial, sans-serif; fill: #555; paint-order: stroke; stroke: #fcfbf7; stroke-width: 3px; stroke-linejoin: round; }}
  .node {{ stroke: #222; stroke-width: 1.05; }}
  .node.dataset {{ stroke: #753100; stroke-width: 2.2; }}
  .flow {{ fill: none; stroke-linecap: round; opacity: 0.30; mix-blend-mode: multiply; }}
  .flow.dataset {{ opacity: 0.56; stroke-dasharray: 7 5; }}
  .caption {{ font: 12.5px Arial, sans-serif; fill: #4b4b4b; }}
  .legend {{ font: 12px Arial, sans-serif; fill: #333; }}
</style>
<rect class="background" x="0" y="0" width="100%" height="100%"/>
<text class="title" x="30" y="40">RGB-T / RGB-X SOT Lineage Sankey</text>
<text class="subtitle" x="30" y="65">Aggregated from Excel Parents: node height and flow width encode cross-stage lineage counts. Orange nodes/flows are datasets or benchmark influence.</text>
'''
    )

    legend_y = 96
    svg.append(f'<g transform="translate(30,{legend_y})">')
    svg.append(
        '<rect class="node" x="0" y="-10" width="20" height="20" rx="2" fill="#386cb0"/>'
        '<text class="legend" x="30" y="4">method category node</text>'
    )
    svg.append(
        '<rect class="node dataset" x="190" y="-10" width="20" height="20" rx="2" fill="#d95f02"/>'
        '<text class="legend" x="220" y="4">dataset / benchmark node</text>'
    )
    svg.append(
        '<path class="flow" d="M 435,0 C 462,0 472,0 500,0" stroke="#777" stroke-width="5"/>'
        '<text class="legend" x="514" y="4">aggregated parent flow</text>'
    )
    svg.append(
        '<path class="flow dataset" d="M 700,0 C 727,0 737,0 765,0" stroke="#d95f02" stroke-width="7"/>'
        '<text class="legend" x="780" y="4">benchmark influence flow</text>'
    )
    svg.append("</g>")

    plot_height = lane_height * len(LANES)
    for stage_i, stage_name in enumerate(STAGES):
        x = left + stage_i * stage_width
        css = "stage-band alt" if stage_i % 2 else "stage-band"
        svg.append(
            f'<rect class="{css}" x="{x}" y="{top}" width="{stage_width}" height="{plot_height}"/>'
        )
        svg.append(
            f'<text class="stage-label" x="{x + stage_width / 2:.1f}" y="{top - 16}" text-anchor="middle">{escape(stage_name)}</text>'
        )

    for lane_i, (lane_key, label) in enumerate(LANES):
        y = top + lane_i * lane_height
        svg.append(f'<line class="lane-line" x1="18" y1="{y}" x2="{width - 30}" y2="{y}"/>')
        svg.append(f'<text class="lane-label" x="30" y="{y + lane_height / 2 + 4}">{escape(label)}</text>')
    svg.append(f'<line class="lane-line" x1="18" y1="{top + plot_height}" x2="{width - 30}" y2="{top + plot_height}"/>')

    # Draw low-weight flows first so important flows remain visible.
    for link in sorted(data["display_links"], key=lambda item: item["weight"]):
        source = node_by_key[link["source"]]
        target = node_by_key[link["target"]]
        sx = source["x"] + source["width"]
        tx = target["x"]
        sy = link["source_y"]
        ty = link["target_y"]
        dx = max(80, (tx - sx) * 0.52)
        cls = "flow dataset" if source["lane"] == "dataset" else "flow"
        color = COLORS[source["lane"]]
        tooltip = (
            f"{source['stage']} {source['label']} -> {target['stage']} {target['label']}: "
            f"{link['weight']} parent edges"
        )
        svg.append(
            f'<path class="{cls}" d="M {sx:.1f},{sy:.1f} C {sx + dx:.1f},{sy:.1f} {tx - dx:.1f},{ty:.1f} {tx:.1f},{ty:.1f}" stroke="{color}" stroke-width="{link["stroke"]:.1f}"><title>{escape(tooltip)}</title></path>'
        )

    for node in data["nodes"]:
        x = node["x"]
        y = node["y"] - node["height"] / 2
        color = COLORS[node["lane"]]
        cls = "node dataset" if node["lane"] == "dataset" else "node"
        tooltip = (
            f"{node['stage']} | {node['label']}\n"
            f"Papers: {node['paper_count']}\n"
            f"Incoming cross-stage edges: {node['incoming']}\n"
            f"Outgoing cross-stage edges: {node['outgoing']}"
        )
        svg.append(
            f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{node["width"]:.1f}" height="{node["height"]:.1f}" rx="3" fill="{color}"><title>{escape(tooltip)}</title></rect>'
        )

    for node in data["nodes"]:
        x = node["x"] + node["width"] + 8
        y = node["y"] - 3
        label = escape(node["label"])
        meta = escape(f"n={node['paper_count']}, in={node['incoming']}, out={node['outgoing']}")
        svg.append(f'<text class="node-label" x="{x:.1f}" y="{y:.1f}">{label}</text>')
        svg.append(f'<text class="node-meta" x="{x:.1f}" y="{y + 12:.1f}">{meta}</text>')

    caption_y = top + plot_height + 34
    shown_edges = sum(link["weight"] for link in data["display_links"])
    full_cross_stage = sum(link["weight"] for link in data["links"])
    svg.append(
        f'<text class="caption" x="30" y="{caption_y}">Shown flow = {shown_edges} / {full_cross_stage} cross-stage parent edges (threshold >= {DISPLAY_WEIGHT_THRESHOLD}). Same-stage edges ({data["skipped_same_stage"]}) are omitted.</text>'
    )
    svg.append(
        f'<text class="caption" x="30" y="{caption_y + 21}">Dataset/benchmark nodes are separated from method categories; dashed orange flows indicate benchmark papers used as parents by later categories.</text>'
    )
    svg.append("</svg>")

    return "\n".join(svg), width, height


def write_outputs():
    data = build_sankey()
    svg_text, width, height = draw_svg(data)
    html_text = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RGB-T SOT Lineage Sankey</title>
<style>
  body {{ margin: 0; background: #ece7dc; color: #242424; font-family: Arial, sans-serif; }}
  header {{ padding: 16px 24px 10px; background: #fffdf8; border-bottom: 1px solid #d7d0c2; }}
  h1 {{ margin: 0 0 6px; font-size: 21px; }}
  p {{ margin: 4px 0; line-height: 1.45; max-width: 1200px; }}
  .wrap {{ overflow: auto; height: calc(100vh - 114px); }}
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
  <h1>RGB-T / RGB-X SOT Lineage Sankey</h1>
  <p>Aggregated from the Excel Parents field. Flow width means number of cross-stage parent edges; dataset/benchmark influence is highlighted in orange.</p>
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
                "stage",
                "lane",
                "label",
                "paper_count",
                "incoming",
                "outgoing",
                "value",
                "datasets",
            ],
        )
        writer.writeheader()
        for node in data["nodes"]:
            writer.writerow(
                {
                    "stage": node["stage"],
                    "lane": node["lane"],
                    "label": node["label"],
                    "paper_count": node["paper_count"],
                    "incoming": node["incoming"],
                    "outgoing": node["outgoing"],
                    "value": node["value"],
                    "datasets": node["datasets"],
                }
            )

    with OUT_LINKS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_stage",
                "source_lane",
                "target_stage",
                "target_lane",
                "weight",
            ],
        )
        writer.writeheader()
        for link in data["links"]:
            writer.writerow(
                {
                    "source_stage": link["source"][0],
                    "source_lane": link["source"][1],
                    "target_stage": link["target"][0],
                    "target_lane": link["target"][1],
                    "weight": link["weight"],
                }
            )

    return data, width, height


def main():
    data, width, height = write_outputs()
    print(f"nodes={len(data['nodes'])}")
    print(f"links={len(data['links'])}")
    print(f"display_links={len(data.get('display_links', []))}")
    print(f"cross_stage_edge_weight={sum(link['weight'] for link in data['links'])}")
    print(f"display_edge_weight={sum(link['weight'] for link in data.get('display_links', []))}")
    print(f"skipped_same_stage={data['skipped_same_stage']}")
    print(f"skipped_reverse={data['skipped_reverse']}")
    print(f"svg_size={width}x{height}")
    print(f"svg={OUT_SVG}")
    print(f"html={OUT_HTML}")
    print(f"nodes_csv={OUT_NODES}")
    print(f"links_csv={OUT_LINKS}")


if __name__ == "__main__":
    main()
