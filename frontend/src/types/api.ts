export type ChartType = "bar" | "line" | "dot";
export type SummaryAggregation = "average" | "maximum" | "minimum" | "sum";
export type ChartAxisValue = string | number;

export interface MarkdownBlock {
  type: "markdown";
  payload: { content: string };
}

export interface TableBlock {
  type: "table";
  payload: {
    columns: string[];
    column_labels: Record<string, string>;
    rows: Array<Record<string, unknown>>;
    title: string | null;
  };
}

export interface SummaryBlock {
  type: "summary";
  payload: {
    label: string;
    value: number;
    source_column: string;
    aggregation: SummaryAggregation;
    title: string | null;
  };
}

export interface ChartPoint {
  x: ChartAxisValue;
  y: number;
}

export interface ChartSeries {
  name: string;
  points: ChartPoint[];
}

export interface ChartBlock {
  type: "chart";
  payload: {
    chart_type: ChartType;
    x_column: string;
    y_column: string;
    x_label: string;
    y_label: string;
    title: string | null;
    points?: ChartPoint[];
    series_column?: string;
    series?: ChartSeries[];
    bar_mode?: "group";
    value_columns?: string[];
  };
}

export type ResponseBlock = MarkdownBlock | TableBlock | SummaryBlock | ChartBlock;
export type ArtifactBlock = Exclude<ResponseBlock, MarkdownBlock>;
export type BlockType = ResponseBlock["type"];

export interface ChatResponse {
  conversation_id: string;
  message: string;
  blocks: ResponseBlock[];
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
  blocks: ResponseBlock[];
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

export type ChatStreamEvent =
  | { type: "message_start"; payload: { conversation_id: string } }
  | { type: "status"; payload: { label: string } }
  | { type: "markdown_delta"; payload: { delta: string } }
  | { type: "artifact"; payload: ArtifactBlock }
  | { type: "complete"; payload: Record<string, never> };

export function parseChatResponse(value: unknown): ChatResponse {
  const record = expectRecord(value, "chat response");
  return {
    conversation_id: expectString(record.conversation_id, "chat response conversation_id"),
    message: expectString(record.message, "chat response message"),
    blocks: expectArray(record.blocks, "chat response blocks").map(parseResponseBlock),
  };
}

export function parseConversations(value: unknown): Conversation[] {
  return expectArray(value, "conversations").map((item) => {
    const record = expectRecord(item, "conversation");
    return {
      id: expectString(record.id, "conversation id"),
      title: expectString(record.title, "conversation title"),
      created_at: expectString(record.created_at, "conversation created_at"),
      updated_at: expectString(record.updated_at, "conversation updated_at"),
    };
  });
}

export function parseConversationMessages(value: unknown): ConversationMessage[] {
  return expectArray(value, "conversation messages").map((item) => {
    const record = expectRecord(item, "conversation message");
    const role = expectString(record.role, "conversation message role");
    if (role !== "user" && role !== "assistant") {
      throw new TypeError("Invalid conversation message role.");
    }
    return {
      role,
      content: expectString(record.content, "conversation message content"),
      blocks: expectArray(record.blocks, "conversation message blocks").map(parseResponseBlock),
    };
  });
}

export function parseChatStreamEvent(type: string, payload: unknown): ChatStreamEvent {
  const record = expectRecord(payload, `${type} event payload`);
  switch (type) {
    case "message_start":
      return {
        type,
        payload: { conversation_id: expectString(record.conversation_id, "conversation_id") },
      };
    case "status":
      return { type, payload: { label: expectString(record.label, "status label") } };
    case "markdown_delta":
      return { type, payload: { delta: expectString(record.delta, "markdown delta") } };
    case "artifact": {
      const artifact = parseResponseBlock(record);
      if (artifact.type === "markdown") {
        throw new TypeError("Streamed artifacts cannot be Markdown blocks.");
      }
      return { type, payload: artifact };
    }
    case "complete":
      return { type, payload: {} };
    default:
      throw new TypeError(`Unsupported chat stream event: ${type}.`);
  }
}

function parseResponseBlock(value: unknown): ResponseBlock {
  const record = expectRecord(value, "response block");
  const payload = expectRecord(record.payload, "response block payload");
  switch (record.type) {
    case "markdown":
      return {
        type: "markdown",
        payload: { content: expectString(payload.content, "Markdown content") },
      };
    case "table": {
      const columns = expectStringArray(payload.columns, "table columns");
      const columnLabels = expectStringRecord(payload.column_labels, "table column_labels");
      if (columns.some((column) => columnLabels[column] === undefined)) {
        throw new TypeError("Table column_labels must include every column.");
      }
      return {
        type: "table",
        payload: {
          columns,
          column_labels: columnLabels,
          rows: expectRecordArray(payload.rows, "table rows"),
          title: expectOptionalString(payload.title, "table title"),
        },
      };
    }
    case "summary":
      return {
        type: "summary",
        payload: {
          label: expectString(payload.label, "summary label"),
          value: expectNumber(payload.value, "summary value"),
          source_column: expectString(payload.source_column, "summary source_column"),
          aggregation: expectSummaryAggregation(payload.aggregation),
          title: expectOptionalString(payload.title, "summary title"),
        },
      };
    case "chart": {
      const points = payload.points === undefined ? undefined : expectChartPoints(payload.points);
      const series = payload.series === undefined ? undefined : expectChartSeries(payload.series);
      if ((points === undefined) === (series === undefined)) {
        throw new TypeError("A chart must provide points or series, but not both.");
      }
      return {
        type: "chart",
        payload: {
          chart_type: expectChartType(payload.chart_type),
          x_column: expectString(payload.x_column, "chart x_column"),
          y_column: expectString(payload.y_column, "chart y_column"),
          x_label: expectString(payload.x_label, "chart x_label"),
          y_label: expectString(payload.y_label, "chart y_label"),
          title: expectOptionalString(payload.title, "chart title"),
          ...(points === undefined ? {} : { points }),
          ...(payload.series_column === undefined
            ? {}
            : { series_column: expectString(payload.series_column, "chart series_column") }),
          ...(series === undefined ? {} : { series }),
          ...(payload.bar_mode === undefined ? {} : { bar_mode: expectBarMode(payload.bar_mode) }),
          ...(payload.value_columns === undefined
            ? {}
            : { value_columns: expectStringArray(payload.value_columns, "chart value_columns") }),
        },
      };
    }
    default:
      throw new TypeError("Unsupported response block type.");
  }
}

function expectRecord(value: unknown, description: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError(`Invalid ${description}.`);
  }
  return value as Record<string, unknown>;
}

function expectArray(value: unknown, description: string): unknown[] {
  if (!Array.isArray(value)) throw new TypeError(`Invalid ${description}.`);
  return value;
}

function expectString(value: unknown, description: string): string {
  if (typeof value !== "string") throw new TypeError(`Invalid ${description}.`);
  return value;
}

function expectOptionalString(value: unknown, description: string): string | null {
  if (value === null) return null;
  return expectString(value, description);
}

function expectNumber(value: unknown, description: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError(`Invalid ${description}.`);
  }
  return value;
}

function expectStringArray(value: unknown, description: string): string[] {
  return expectArray(value, description).map((item) => expectString(item, description));
}

function expectStringRecord(value: unknown, description: string): Record<string, string> {
  return Object.fromEntries(
    Object.entries(expectRecord(value, description)).map(([key, item]) => [
      key,
      expectString(item, description),
    ]),
  );
}

function expectRecordArray(value: unknown, description: string): Array<Record<string, unknown>> {
  return expectArray(value, description).map((item) => expectRecord(item, description));
}

function expectChartPoints(value: unknown): ChartPoint[] {
  return expectArray(value, "chart points").map((item) => {
    const point = expectRecord(item, "chart point");
    const x = point.x;
    if (typeof x !== "string" && typeof x !== "number")
      throw new TypeError("Invalid chart point x.");
    return { x, y: expectNumber(point.y, "chart point y") };
  });
}

function expectChartSeries(value: unknown): ChartSeries[] {
  return expectArray(value, "chart series").map((item) => {
    const series = expectRecord(item, "chart series");
    return {
      name: expectString(series.name, "chart series name"),
      points: expectChartPoints(series.points),
    };
  });
}

function expectChartType(value: unknown): ChartType {
  if (value === "bar" || value === "line" || value === "dot") return value;
  throw new TypeError("Invalid chart type.");
}

function expectSummaryAggregation(value: unknown): SummaryAggregation {
  if (value === "average" || value === "maximum" || value === "minimum" || value === "sum") {
    return value;
  }
  throw new TypeError("Invalid summary aggregation.");
}

function expectBarMode(value: unknown): "group" {
  if (value === "group") return value;
  throw new TypeError("Invalid chart bar mode.");
}
