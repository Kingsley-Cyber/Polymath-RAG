/** A screen whose phase has not shipped yet. Says which phase, and what blocks it. */
export function PhaseStub({ phase, title, blocked }: { phase: string; title: string; blocked?: string }) {
  return (
    <div className="phase-note">
      <strong>{phase}</strong> — {title}
      {blocked && (
        <div className="banner banner--bad" style={{ marginTop: 12 }}>
          Blocked: {blocked}
        </div>
      )}
    </div>
  );
}
