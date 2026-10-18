import "@testing-library/jest-dom/vitest";
import { createElement } from "react";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(cleanup);

type PlotProps = {
  data: Array<{ marker?: { color?: string } }>;
  layout: object;
};

vi.mock("react-plotly.js", () => ({
  default: ({ data, layout }: PlotProps) =>
    createElement("div", {
      "data-colors": data.map((trace) => trace.marker?.color).join(","),
      "data-layout": JSON.stringify(layout),
      "data-testid": "plot",
    }),
}));
