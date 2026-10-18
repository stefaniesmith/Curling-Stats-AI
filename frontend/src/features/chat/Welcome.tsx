import logoUrl from "../../../../assets/CurlChatLogo.png";

const prompts = [
  "Show Rachel Homan's stats at the 2025 Scotties.",
  "Compare Brad Jacobs and Brad Gushue from 2020-2026.",
  "Who had the highest draw percentage at the 2023 Hearts?",
];

interface WelcomeProps {
  onPrompt: (prompt: string) => void;
}

export function Welcome({ onPrompt }: WelcomeProps) {
  return (
    <section className="welcome">
      <img src={logoUrl} alt="CurlChat — Curling stats. AI insights." className="welcome-logo" />
      <p>
        Explore historical player performance with natural language, interactive charts, and
        source-grounded statistics.
      </p>
      <div className="prompt-grid">
        {prompts.map((prompt) => (
          <button key={prompt} onClick={() => onPrompt(prompt)}>
            {prompt}
            <span>→</span>
          </button>
        ))}
      </div>
    </section>
  );
}
