import { useSkipPlan } from "../../lib/deep";
import "../../styles/deep.css";

/** DEEP-RESEARCH-MODE-V1 §11.2 part 1 (DR7a) — Settings: the one deep research preference, "start without showing the plan",
 *  kept in this browser (the plan card offers the same checkbox; both read one store). */
export function DeepResearchSettings() {
  const [skip, setSkip] = useSkipPlan();
  return (
    <div className="card stack">
      <h2 className="settings__title">Deep research</h2>
      <label className="plan-card__skip">
        <input type="checkbox" checked={skip} onChange={(e) => setSkip(e.target.checked)} />
        Start deep research without showing the plan
      </label>
      <p className="faint" style={{ margin: 0 }}>
        The plan lists the parts the research will cover, so you can edit them before it starts. Unless you touch it, it starts
        by itself after 10 seconds. This choice is kept in this browser.
      </p>
    </div>
  );
}
