import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MessageComposer } from "./MessageComposer";

describe("MessageComposer", () => {
  it("sends with Enter and clears the draft", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<MessageComposer disabled={false} onSend={onSend} />);

    const composer = screen.getByPlaceholderText(/ask about a player/i);
    await user.type(composer, "Show Brier results{Enter}");

    expect(onSend).toHaveBeenCalledWith("Show Brier results");
    expect(composer).toHaveValue("");
  });

  it("keeps a newline when Shift+Enter is pressed", async () => {
    const user = userEvent.setup();
    render(<MessageComposer disabled={false} onSend={vi.fn()} />);

    const composer = screen.getByPlaceholderText(/ask about a player/i);
    await user.type(composer, "Compare players{Shift>}{Enter}{/Shift}by wins");

    expect(composer).toHaveValue("Compare players\nby wins");
  });

  it("does not submit blank drafts and disables input while sending", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(<MessageComposer disabled={false} onSend={onSend} />);

    await user.type(screen.getByPlaceholderText(/ask about a player/i), "   ");
    expect(screen.getByRole("button", { name: /send message/i })).toBeDisabled();
    expect(onSend).not.toHaveBeenCalled();

    rerender(<MessageComposer disabled onSend={onSend} />);
    expect(screen.getByPlaceholderText(/ask about a player/i)).toBeDisabled();
  });
});
