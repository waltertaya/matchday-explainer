/** Match screen tabs: Catch me up | Stats | Why that whistle? */
export type MatchTab = "catch-up" | "stats" | "whistle";

const TABS: Array<{ id: MatchTab; label: string }> = [
  { id: "catch-up", label: "Catch me up" },
  { id: "stats", label: "Stats" },
  { id: "whistle", label: "Why that whistle?" },
];

export function MatchTabs({
  active,
  onChange,
}: {
  active: MatchTab;
  onChange: (tab: MatchTab) => void;
}) {
  return (
    <nav className="match-tabs" role="tablist" aria-label="Match screens">
      {TABS.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          className={`match-tab${active === t.id ? " is-active" : ""}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}
