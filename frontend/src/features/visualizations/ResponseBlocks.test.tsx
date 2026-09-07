import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResponseBlocks } from "./ResponseBlocks";

describe("ResponseBlocks", () => {
  it("renders markdown, summaries, and tables from backend blocks", () => {
    render(
      <ResponseBlocks
        blocks={[
          { type: "markdown", payload: { content: "## Brier results" } },
          { type: "summary", payload: { title: "Average wins", label: "Average wins", value: 6.5 } },
          { type: "table", payload: { columns: ["player_name", "wins"], rows: [{ player_name: "Brad Jacobs", wins: 8 }] } },
        ]}
      />,
    );

    expect(screen.getByRole("heading", { name: "Brier results" })).toBeInTheDocument();
    expect(screen.getByText("6.50")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "player name" })).toBeInTheDocument();
    expect(screen.getByText("Brad Jacobs")).toBeInTheDocument();
  });

  it("gives series distinct colors and reserves room for a wrapped title and legend", () => {
    const longTitle = "A long comparison of draw percentages across multiple Curling Canada championship seasons";
    render(
      <ResponseBlocks
        blocks={[{
          type: "chart",
          payload: {
            chart_type: "line",
            title: longTitle,
            x_column: "event_year",
            y_column: "draw_percentage",
            series: [
              { name: "Rachel Homan", points: [{ x: 2023, y: 86 }] },
              { name: "Jennifer Jones", points: [{ x: 2023, y: 84 }] },
            ],
          },
        }]}
      />,
    );

    const plot = screen.getByTestId("plot");
    expect(plot).toHaveAttribute("data-colors", "#c7192d,#087e8b");
    expect(plot.getAttribute("data-layout")).toContain("<br>");
    expect(plot.getAttribute("data-layout")).toContain('"b":120');
  });
});
