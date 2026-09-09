import { useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";

interface MessageComposerProps {
  disabled: boolean;
  onSend: (message: string) => void;
}

export function MessageComposer({ disabled, onSend }: MessageComposerProps) {
  const [draft, setDraft] = useState("");

  const send = () => {
    if (!draft.trim()) return;
    onSend(draft);
    setDraft("");
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    send();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  };

  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder="Ask about a player, event, season, or statistic…"
        rows={1}
        maxLength={2_000}
        disabled={disabled}
        onKeyDown={handleKeyDown}
      />
      <button type="submit" disabled={disabled || !draft.trim()} aria-label="Send message">
        ↑
      </button>
    </form>
  );
}
