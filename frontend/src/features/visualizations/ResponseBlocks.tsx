import { lazy, Suspense } from "react";
import ReactMarkdown from "react-markdown";

import type {
  ChartBlock as ChartResponseBlock,
  SummaryBlock as SummaryResponseBlock,
  TableBlock as TableResponseBlock,
  ResponseBlock,
} from "../../types/api";
import { loadPlotly } from "./plotly";

const seriesColors = ["#c7192d", "#087e8b", "#315e9e", "#d97b29", "#7552a1"];
const Plot = lazy(loadPlotly);

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

const decimalString = /^-?\d+\.\d+$/;

const displayNumber = (value: number) =>
  Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2).replace(/\.00$/, "");

const displayValue = (value: unknown) => {
  if (typeof value === "number") return displayNumber(value);
  if (typeof value === "string" && decimalString.test(value)) {
    const numericValue = Number(value);
    if (Number.isFinite(numericValue)) return displayNumber(numericValue);
  }
  return value == null ? "—" : String(value);
};

function TableBlock({ payload }: TableResponseBlock) {
  const { columns, column_labels: columnLabels, rows, title } = payload;

  return (
    <section className="artifact artifact-table">
      {title && <h3>{title}</h3>}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{columnLabels[column]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td key={column}>{displayValue(row[column])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SummaryBlock({ payload }: SummaryResponseBlock) {
  const { title, label, value } = payload;
  return (
    <section className="artifact summary-card">
      <span>{title ?? label}</span>
      <strong>{displayValue(value)}</strong>
      {title && <small>{label}</small>}
    </section>
  );
}

function ChartBlock({ payload }: ChartResponseBlock) {
  const chartType =
    payload.chart_type === "line" ? "scatter" : payload.chart_type === "dot" ? "scatter" : "bar";
  const mode = payload.chart_type === "line" ? "lines+markers" : "markers";
  const title = payload.title ?? undefined;
  const titleLines = title ? wrapChartTitle(title).split("<br>").length : 0;
  const points = payload.points ?? [];
  const series = payload.series ?? [];
  const hasLegend = series.length > 0;
  const datasets = series.length
    ? series.map((item) => ({
        name: item.name,
        x: item.points.map((point) => point.x),
        y: item.points.map((point) => point.y),
      }))
    : [{ x: points.map((point) => point.x), y: points.map((point) => point.y) }];

  return (
    <section className="artifact chart-card">
      <Suspense fallback={<div className="chart-loading">Loading chart…</div>}>
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
              title: { text: payload.x_label, standoff: 18 },
              gridcolor: "rgba(7,31,79,.08)",
            },
            yaxis: {
              title: payload.y_label,
              gridcolor: "rgba(7,31,79,.1)",
              zerolinecolor: "rgba(7,31,79,.2)",
            },
            barmode: payload.bar_mode === "group" ? "group" : undefined,
            showlegend: hasLegend,
            legend: { orientation: "h", x: 0, xanchor: "left", y: -0.46, yanchor: "top" },
          }}
          config={{ displayModeBar: false, responsive: true }}
          className="plot"
          useResizeHandler
        />
      </Suspense>
    </section>
  );
}

export function ResponseBlocks({ blocks }: { blocks: ResponseBlock[] }) {
  return (
    <>
      {blocks.map((block, index) => {
        const key = `${block.type}-${index}`;
        if (block.type === "markdown")
          return (
            <div className="markdown-block" key={key}>
              <ReactMarkdown>{String(block.payload.content ?? "")}</ReactMarkdown>
            </div>
          );
        if (block.type === "table") return <TableBlock key={key} {...block} />;
        if (block.type === "summary") return <SummaryBlock key={key} {...block} />;
        if (block.type === "chart") return <ChartBlock key={key} {...block} />;
        return null;
      })}
    </>
  );
}
