import "@testing-library/jest-dom/vitest";
import { createElement } from "react";
import { vi } from "vitest";

type PlotProps = {
  data: Array<{ marker?: { color?: string } }>;
  layout: object;
};

vi.mock("react-plotly.js", () => ({
  default: ({ data, layout }: PlotProps) => createElement("div", {
    "data-colors": data.map((trace) => trace.marker?.color).join(","),
    "data-layout": JSON.stringify(layout),
    "data-testid": "plot",
  }),
}));
