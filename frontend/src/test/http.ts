type StreamEvent = { type: string; payload: object };

export const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

export const sseEvent = ({ type, payload }: StreamEvent, lineEnding = "\n") =>
  `event: ${type}${lineEnding}data: ${JSON.stringify(payload)}${lineEnding}${lineEnding}`;

export const streamResponse = (events: StreamEvent[]) =>
  streamResponseChunks(events.map((event) => sseEvent(event)));

export const streamResponseChunks = (chunks: string[], status = 200) => {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  });
  return new Response(body, { status, headers: { "Content-Type": "text/event-stream" } });
};
