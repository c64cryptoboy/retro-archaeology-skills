# Compact views of the exact graph

- `rnd-histograms.svg`: canonical weighted histograms and survival view.
- `rnd-component-depth.svg`: canonical component/depth atlas.
- `small-mu5-lambda7.{bas,json,dot,svg,txt}`: complete small orbit from
  `RND(-.311306466)`, with five ramp states and a seven-state cycle.

Open SVG directly in a browser; no renderer dependency is needed. Regenerate
views with `render_histograms.py`, `render_component_depth.py` and
`render_small_graph.py` from the parent analysis directory. Exact data and
population qualifications are in `../FINAL_REPORT.md`. The package's compact
result manifest pins the retained views; no billion-node drawing is implied.
