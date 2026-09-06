import Plot from "react-plotly.js";
import ReactMarkdown from "react-markdown";

import type { ResponseBlock } from "../../types/api";

const seriesColors = ["#c7192d", "#087e8b", "#315e9e", "#d97b29", "#7552a1"];

function wrapChartTitle(title: string, maxCharacters = 72) {
  const lines: string[] = [];
  let line = "";
  for (const word of title.split(/\s+/)) {
    if (line && `${line} ${word}`.length > maxCharacters) {
      lines.push(line);
      line = word;
    } else {
      line = line ? `${line} ${word}` : word;
    }
  }
  if (line) lines.push(line);
  return lines.join("<br>");
}

const displayValue = (value: unknown) => {
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2).replace(/\.00$/, "");
  }
  return value == null ? "—" : String(value);
};

function TableBlock({ payload }: { payload: Record<string, unknown> }) {
  const columns = Array.isArray(payload.columns) ? payload.columns.map(String) : [];
  const rows = Array.isArray(payload.rows) ? payload.rows : [];
  const title = typeof payload.title === "string" ? payload.title : null;

  return (
    <section className="artifact artifact-table">
      {title && <h3>{title}</h3>}
      <div className="table-scroll">
        <table>
          <thead><tr>{columns.map((column) => <th key={column}>{column.replaceAll("_", " ")}</th>)}</tr></thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>
                {columns.map((column) => <td key={column}>{displayValue((row as Record<string, unknown>)[column])}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SummaryBlock({ payload }: { payload: Record<string, unknown> }) {
  const title = typeof payload.title === "string" ? payload.title : null;
  const label = typeof payload.label === "string" ? payload.label.replaceAll("_", " ") : "Summary";
  return (
    <section className="artifact summary-card">
      <span>{title ?? label}</span>
      <strong>{displayValue(payload.value)}</strong>
      {title && <small>{label}</small>}
    </section>
  );
}

function ChartBlock({ payload }: { payload: Record<string, unknown> }) {
  const chartType = payload.chart_type === "line" ? "scatter" : payload.chart_type === "dot" ? "scatter" : "bar";
  const mode = payload.chart_type === "line" ? "lines+markers" : "markers";
  const title = typeof payload.title === "string" ? payload.title : undefined;
  const titleLines = title ? wrapChartTitle(title).split("<br>").length : 0;
  const points = Array.isArray(payload.points) ? payload.points as Array<{ x: unknown; y: unknown }> : [];
  const series = Array.isArray(payload.series)
    ? payload.series as Array<{ name: string; points: Array<{ x: unknown; y: unknown }> }>
    : [];
  const hasLegend = series.length > 0;
  const datasets = series.length
    ? series.map((item) => ({ name: item.name, x: item.points.map((point) => point.x), y: item.points.map((point) => point.y) }))
    : [{ x: points.map((point) => point.x), y: points.map((point) => point.y) }];

  return (
    <section className="artifact chart-card">
      <Plot
        data={datasets.map((dataset, index) => {
          const color = seriesColors[index % seriesColors.length];
          return {
          ...dataset,
          type: chartType,
          mode: chartType === "scatter" ? mode : undefined,
          marker: { color },
          line: { color, width: 3 },
          hovertemplate: "%{x}<br><b>%{y}</b><extra></extra>",
          };
        })}
        layout={{
          title: title ? { text: wrapChartTitle(title), x: 0.5, xanchor: "center" } : undefined,
          autosize: true,
          height: 330,
          margin: {
            l: 48,
            r: 24,
            t: title ? 35 + titleLines * 20 : 24,
            b: hasLegend ? 120 : 64,
          },
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(234,244,251,0.6)",
          font: { family: "Inter, system-ui, sans-serif", color: "#19325d" },
          xaxis: {
            title: { text: String(payload.x_column ?? ""), standoff: 18 },
            gridcolor: "rgba(7,31,79,.08)",
          },
          yaxis: { title: String(payload.y_column ?? ""), gridcolor: "rgba(7,31,79,.1)", zerolinecolor: "rgba(7,31,79,.2)" },
          barmode: payload.bar_mode === "group" ? "group" : undefined,
          showlegend: hasLegend,
          legend: { orientation: "h", x: 0, xanchor: "left", y: -0.46, yanchor: "top" },
        }}
        config={{ displayModeBar: false, responsive: true }}
        className="plot"
        useResizeHandler
      />
    </section>
  );
}

export function ResponseBlocks({ blocks }: { blocks: ResponseBlock[] }) {
  return <>{blocks.map((block, index) => {
    const key = `${block.type}-${index}`;
    if (block.type === "markdown") return <div className="markdown-block" key={key}><ReactMarkdown>{String(block.payload.content ?? "")}</ReactMarkdown></div>;
    if (block.type === "table") return <TableBlock key={key} payload={block.payload} />;
    if (block.type === "summary") return <SummaryBlock key={key} payload={block.payload} />;
    if (block.type === "chart") return <ChartBlock key={key} payload={block.payload} />;
    return null;
  })}</>;
}
