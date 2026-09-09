export const loadPlotly = () => import("react-plotly.js");

export function preloadPlotly() {
  void loadPlotly();
}
