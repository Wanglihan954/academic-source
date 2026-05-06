import math
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle
from matplotlib import font_manager
from pathlib import Path

OUT = Path("figures")
OUT.mkdir(exist_ok=True)

plt.rcParams["figure.dpi"] = 160
plt.rcParams["savefig.dpi"] = 320
plt.rcParams["axes.unicode_minus"] = False

candidates = [
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "WenQuanYi Micro Hei",
    "Microsoft YaHei",
    "SimHei",
    "DejaVu Sans",
]
available = {f.name for f in font_manager.fontManager.ttflist}
for name in candidates:
    if name in available:
        plt.rcParams["font.family"] = name
        break

BLUE = "#2454A6"
CYAN = "#35A7C9"
TEAL = "#40B7A2"
GREEN = "#6DBA55"
ORANGE = "#F2A541"
RED = "#D95D5D"
PURPLE = "#7B61B8"
DARK = "#243043"
GRAY = "#6D7788"
LIGHT = "#F4F7FB"


def add_round_box(ax, xy, w, h, text, fc, ec="white", tc="white", fontsize=12, weight="bold"):
    box = FancyBboxPatch(
        xy,
        w,
        h,
        boxstyle="round,pad=0.025,rounding_size=0.05",
        linewidth=1.8,
        facecolor=fc,
        edgecolor=ec,
    )
    ax.add_patch(box)
    ax.text(
        xy[0] + w / 2,
        xy[1] + h / 2,
        text,
        ha="center",
        va="center",
        color=tc,
        fontsize=fontsize,
        fontweight=weight,
        linespacing=1.25,
    )
    return box


def add_arrow(ax, start, end, color=GRAY, lw=2.0, rad=0.0):
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=16,
        linewidth=lw,
        color=color,
        connectionstyle=f"arc3,rad={rad}",
    )
    ax.add_patch(arrow)


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def workflow_figure():
    fig, ax = plt.subplots(figsize=(11.5, 4.8))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.5, 0.93, "频域视觉综述写作工作流", ha="center", va="center", fontsize=20, fontweight="bold", color=DARK)
    ax.text(0.5, 0.865, "从问题定义到论文迭代的闭环流程", ha="center", va="center", fontsize=11, color=GRAY)

    labels = [
        "确定范围\n研究问题",
        "检索文献\n关键词扩展",
        "筛选论文\n建立表格",
        "分类体系\n二维组织",
        "深读证据\n提取消融",
        "写作迭代\n图表完善",
    ]
    colors = [BLUE, CYAN, TEAL, GREEN, ORANGE, PURPLE]
    xs = [0.06 + i * (0.79 - 0.06) / 5 for i in range(6)]
    y = 0.49
    w, h = 0.13, 0.23
    for i, (x, lab, col) in enumerate(zip(xs, labels, colors), start=1):
        ax.add_patch(Circle((x + 0.025, y + h + 0.045), 0.025, facecolor=col, edgecolor="white", linewidth=1.5))
        ax.text(x + 0.025, y + h + 0.045, str(i), ha="center", va="center", color="white", fontsize=11, fontweight="bold")
        add_round_box(ax, (x, y), w, h, lab, col, fontsize=11)
        if i < 6:
            add_arrow(ax, (x + w + 0.008, y + h / 2), (xs[i] - 0.01, y + h / 2), color="#9AA4B2")

    add_arrow(ax, (0.86, 0.49), (0.13, 0.31), color=RED, lw=2.2, rad=-0.28)
    ax.text(0.50, 0.23, "反馈闭环：补充遗漏文献 · 重构分类 · 更新问题意识 · 优化图表叙事", ha="center", fontsize=12, color=DARK)
    ax.add_patch(Rectangle((0.05, 0.12), 0.90, 0.055, facecolor=LIGHT, edgecolor="none"))
    ax.text(0.5, 0.148, "建议输出物：文献矩阵、分类图、代表性方法对比表、开放问题清单", ha="center", va="center", fontsize=10.5, color=GRAY)
    save(fig, "review_workflow")


def taxonomy_figure():
    fig, ax = plt.subplots(figsize=(10.5, 7.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.5, 0.95, "频域方法在计算机视觉中的分类框架", ha="center", fontsize=20, fontweight="bold", color=DARK)
    add_round_box(ax, (0.35, 0.43), 0.30, 0.16, "频域视觉方法\nFrequency-domain Vision", BLUE, fontsize=14)

    nodes = [
        ((0.08, 0.73), "频域表示", "FFT / DCT / Wavelet\n幅度谱 / 相位谱", CYAN),
        ((0.40, 0.73), "架构模块", "频率注意力\n谱卷积 / 全局混合", TEAL),
        ((0.72, 0.73), "训练策略", "频谱损失\n频带增广 / 正则", GREEN),
        ((0.08, 0.17), "鲁棒性分析", "噪声 / 压缩\n对抗扰动 / 域偏移", ORANGE),
        ((0.40, 0.17), "任务应用", "分类 / 检测 / 分割\n复原 / 医学 / 遥感", PURPLE),
        ((0.72, 0.17), "生成建模", "GAN / Diffusion\n伪影检测 / 频域控制", RED),
    ]
    centers = []
    for (x, y), title, desc, color in nodes:
        add_round_box(ax, (x, y), 0.20, 0.16, f"{title}\n{desc}", color, fontsize=11)
        centers.append((x + 0.10, y + 0.08))
    center = (0.50, 0.51)
    for c in centers:
        add_arrow(ax, center, c, color="#AAB3C2", lw=1.8)

    ax.text(0.5, 0.075, "核心组织原则：既按“频域角色”分类，也按“视觉任务”比较，避免逐篇论文堆砌。", ha="center", fontsize=11.5, color=GRAY)
    save(fig, "frequency_taxonomy")


def spectrum_figure():
    fig, ax = plt.subplots(figsize=(11.2, 5.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.5, 0.94, "低频与高频信息的视觉语义示意", ha="center", fontsize=20, fontweight="bold", color=DARK)
    ax.text(0.5, 0.885, "低频偏向全局结构，高频偏向边缘、纹理与噪声", ha="center", fontsize=11, color=GRAY)

    x = [i / 499 for i in range(500)]
    low = [0.45 + 0.12 * math.sin(2 * math.pi * 2 * t) for t in x]
    high = [0.45 + 0.055 * math.sin(2 * math.pi * 26 * t) + 0.035 * math.sin(2 * math.pi * 41 * t) for t in x]
    mixed = [lo + hi - 0.45 for lo, hi in zip(low, high)]

    panels = [
        (0.07, "低频分量", low, BLUE, "轮廓 · 光照 · 全局布局"),
        (0.38, "高频分量", high, RED, "边缘 · 纹理 · 噪声细节"),
        (0.69, "混合视觉信号", mixed, PURPLE, "结构与细节共同形成感知"),
    ]
    for x0, title, yv, color, subtitle in panels:
        ax.add_patch(FancyBboxPatch((x0, 0.22), 0.24, 0.54, boxstyle="round,pad=0.02,rounding_size=0.035", facecolor=LIGHT, edgecolor="#DDE3EE"))
        ax.text(x0 + 0.12, 0.71, title, ha="center", fontsize=14, fontweight="bold", color=DARK)
        ymin, ymax = min(yv), max(yv)
        xp = [x0 + 0.03 + t * 0.18 for t in x]
        yp = [0.29 + (value - ymin) / (ymax - ymin) * 0.32 for value in yv]
        ax.plot(xp, yp, color=color, linewidth=2.6)
        ax.fill_between(xp, 0.29, yp, color=color, alpha=0.12)
        ax.text(x0 + 0.12, 0.25, subtitle, ha="center", fontsize=10.5, color=GRAY)

    ax.add_patch(FancyBboxPatch((0.08, 0.08), 0.84, 0.075, boxstyle="round,pad=0.015,rounding_size=0.025", facecolor="#FFF8EC", edgecolor="#F1D6A5"))
    ax.text(0.5, 0.118, "综述写作提示：分析方法时应说明其关注的频带、作用位置、带来的性能收益及可能损失的信息。", ha="center", va="center", fontsize=11, color="#7A5A20")
    save(fig, "frequency_spectrum_semantics")


if __name__ == "__main__":
    workflow_figure()
    taxonomy_figure()
    spectrum_figure()
    print("Generated figures in", OUT.resolve())
