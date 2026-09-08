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
          {
            type: "table",
            payload: {
              columns: ["player_name", "wins"],
              column_labels: { player_name: "Player Name", wins: "Wins" },
              rows: [{ player_name: "Brad Jacobs", wins: 8 }],
            },
          },
        ]}
      />,
    );

    expect(screen.getByRole("heading", { name: "Brier results" })).toBeInTheDocument();
    expect(screen.getByText("6.50")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Player Name" })).toBeInTheDocument();
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
            x_label: "Event Year",
            y_label: "Draw Percentage",
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
    expect(plot.getAttribute("data-layout")).toContain('"text":"Event Year"');
    expect(plot.getAttribute("data-layout")).toContain('"title":"Draw Percentage"');
  });

  it("formats decimal strings from table artifacts as readable numbers", () => {
    render(
      <ResponseBlocks
        blocks={[{
          type: "table",
          payload: {
            columns: ["display_name", "inturn_percentage", "difference"],
            column_labels: {
              display_name: "Display Name",
              inturn_percentage: "Inturn Percentage",
              difference: "Difference",
            },
            rows: [{
              display_name: "Stephen Trickett",
              inturn_percentage: "71.0000000000000000",
              difference: "38.1250000000000000",
            }],
          },
        }]}
      />,
    );

    expect(screen.getByText("Stephen Trickett")).toBeInTheDocument();
    expect(screen.getByText("71")).toBeInTheDocument();
    expect(screen.getByText("38.13")).toBeInTheDocument();
    expect(screen.queryByText("71.0000000000000000")).not.toBeInTheDocument();
  });

  it("uses display labels supplied by new visualization artifacts", () => {
    render(
      <ResponseBlocks
        blocks={[
          {
            type: "table",
            payload: {
              columns: ["draw_percentage"],
              column_labels: { draw_percentage: "Draw Percentage" },
              rows: [{ draw_percentage: 86 }],
            },
          },
          {
            type: "chart",
            payload: {
              chart_type: "line",
              x_column: "event_year",
              y_column: "draw_percentage",
              x_label: "Season",
              y_label: "Draw Percentage",
              points: [{ x: 2024, y: 86 }],
            },
          },
        ]}
      />,
    );

    expect(screen.getByRole("columnheader", { name: "Draw Percentage" })).toBeInTheDocument();
    const latestPlot = screen.getAllByTestId("plot").at(-1);
    expect(latestPlot?.getAttribute("data-layout")).toContain('"text":"Season"');
    expect(latestPlot?.getAttribute("data-layout")).toContain('"title":"Draw Percentage"');
  });
});
