# Paper Existence Check

Date: 2026-05-22

Checked file: `papers_sorted_by_year.xlsx`

Method:
- Batch checked 116 paper titles against OpenAlex, DBLP, and Crossref.
- Manually rechecked low-confidence titles with exact web search and official/arXiv pages.

Summary:
- 105 / 116 were matched directly by academic indexes.
- 5 / 11 initially unmatched were verified manually.
- 6 entries remain high-risk and should be removed or corrected.

High-risk entries:

| Row | Year | Venue | Paper | Reason |
|---:|---:|---|---|---|
| 14 | 2025 | AAAI | Robust RGB-T Tracking via Modality-aware Feature Decoupling | No exact match found in OpenAlex/DBLP/Crossref/web search; not found in AAAI/OJS search. |
| 15 | 2025 | AAAI | Efficient Adapter-based RGBT Tracking | No exact match found; likely confused with `Bi-directional adapter for multimodal tracking` or other adapter/prompt RGBT papers. |
| 18 | 2025 | CVPR | MambaVT: Vision Mamba based RGB-T Tracking | No exact match for this title/venue. Real related paper appears to be `MambaVT: Spatio-temporal contextual modeling for robust RGB-T tracking`, already present as row 29. |
| 22 | 2025 | ICCV | Unified Multi-modal Tracking via Shared Latent Representation | No exact match found; not found in ICCV 2025 paper list. |
| 23 | 2025 | ICCV | Cross-modal Uncertainty-aware RGBT Tracking | No exact match found; not found in ICCV 2025 paper list. |
| 24 | 2025 | ICCV | Temporal-aware Mamba Tracker for RGB-T Tracking | No exact match found; not found in ICCV 2025 paper list. |

Initially unmatched but verified:

| Row | Paper | Evidence |
|---:|---|---|
| 7 | Progressive Multi-cue Alignment for Unaligned RGBT Tracking | Found in CVPR 2026 official program PDF/search results. |
| 8 | Spatio-Temporal Conditional Denoising Transformer for Modality-Missing RGBT Tracking | Found in CVPR 2026 official program PDF/search results. |
| 11 | Unified Multimodal Visual Tracking with Dual Mixture-of-Experts | arXiv:2605.03716; marked accepted by ICML 2026. |
| 25 | CSTrack: Enhancing RGB-X Tracking via Compact Spatiotemporal Features | arXiv:2505.19434; marked accepted by ICML 2025. |
| 78 | RGB-T tracking via multimodal mutual prompt learning | arXiv:2308.16386. |

Generated data:
- `paper_existence_check.tsv`: raw batch matching results.
