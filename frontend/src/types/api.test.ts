import { describe, expect, it } from "vitest";

import { parseChatResponse, parseChatStreamEvent } from "./api";

describe("API contract parsers", () => {
  it("parses typed table artifacts from a chat response", () => {
    const response = parseChatResponse({
      conversation_id: "conversation-id",
      message: "Brad Jacobs had eight wins.",
      blocks: [
        { type: "markdown", payload: { content: "Brad Jacobs had eight wins." } },
        {
          type: "table",
          payload: {
            columns: ["display_name", "wins"],
            column_labels: { display_name: "Player", wins: "Wins" },
            rows: [{ display_name: "Brad Jacobs", wins: 8 }],
            title: "Results",
          },
        },
      ],
    });

    expect(response.blocks[1]).toEqual({
      type: "table",
      payload: {
        columns: ["display_name", "wins"],
        column_labels: { display_name: "Player", wins: "Wins" },
        rows: [{ display_name: "Brad Jacobs", wins: 8 }],
        title: "Results",
      },
    });
  });

  it("rejects artifacts that omit required display labels", () => {
    expect(() =>
      parseChatResponse({
        conversation_id: "conversation-id",
        message: "Results",
        blocks: [
          {
            type: "table",
            payload: { columns: ["wins"], rows: [{ wins: 8 }], title: null },
          },
        ],
      }),
    ).toThrow("table column_labels");
  });

  it("parses chart artifacts from the stream and rejects Markdown artifacts", () => {
    const event = parseChatStreamEvent("artifact", {
      type: "chart",
      payload: {
        chart_type: "line",
        x_column: "event_year",
        y_column: "wins",
        x_label: "Event Year",
        y_label: "Wins",
        title: null,
        points: [{ x: 2024, y: 8 }],
      },
    });

    expect(event).toMatchObject({ type: "artifact", payload: { type: "chart" } });
    expect(() =>
      parseChatStreamEvent("artifact", {
        type: "markdown",
        payload: { content: "Not an artifact." },
      }),
    ).toThrow("cannot be Markdown");
  });
});
