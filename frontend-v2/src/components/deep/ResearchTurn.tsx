import type { Turn } from "../../lib/chat";
import type { Synthesizer } from "../../lib/contracts";
import { errorWords, reportModelOf, type DeepGoal, type DeepRunState } from "../../lib/deep";
import { AnswerBody } from "../AnswerBody";
import { DeepReport, ReportActions } from "./DeepReport";
import { LiveResearch } from "./LiveResearch";
import { PlanCard } from "./PlanCard";

/** DEEP-RESEARCH-MODE-V1 §11 (DR7) — one research turn in the chat thread: the question, then the plan card while the plan
 *  waits for Start, else the live research view (in place of the process rail); then the report — the tabbed report view when
 *  the answer carries a report model, else the chat's own answer body with its sources (an older backend). */

export interface ResearchHandlers {
  onStart: (goals: DeepGoal[]) => void;
  onCancel: () => void;
  onStop: () => void;
  onRunPatch: (patch: Partial<DeepRunState>) => void;
  onResearchNext: (question: string) => void;
}

export function ResearchTurnView({ t, models, onStart, onCancel, onStop, onRunPatch, onResearchNext }: {
  t: Turn; models: Synthesizer[];
} & ResearchHandlers) {
  const run = t.deepRun ?? null;
  const planning = !t.done && !!run && (run.status === "planning" || run.status === "ready");
  const report = reportModelOf(t);
  return (
    <>
      <div className="msg-user">
        <div className="msg-user__bubble">{t.question}</div>
      </div>
      <div className="msg-assistant">
        {planning && run ? <PlanCard run={run} onStart={onStart} onCancel={onCancel} onRunPatch={onRunPatch} />
          : <LiveResearch t={t} onStop={onStop} onRunPatch={onRunPatch} />}
        {t.error && <div className="answer answer-error">{errorWords(t.error)}</div>}
        {t.answerText ? (
          report ? <DeepReport t={t} report={report} onResearchNext={onResearchNext} /> : (
            <>
              <AnswerBody t={t} models={models} />
              {t.done && t.deep && <ReportActions question={t.question} text={t.answerText} citations={t.deep.citations} />}
            </>
          )
        ) : t.done && !t.error ? (
          <div className="answer empty-answer">
            The model returned no report text. Send the question again, or pick another model.
          </div>
        ) : null}
      </div>
    </>
  );
}
