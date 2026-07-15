import { useEffect, useState } from "react";
import { ApiError } from "../../api/challenges";
import {
  fetchWeekItems,
  submitMcq,
  submitReflection,
} from "../../passport/assessments";
import type {
  KnowledgeCheckItem,
  McqResult,
  ReflectionResult,
} from "../../types/assessment";
import { AutoAwesomeIcon, CheckCircleIcon } from "../icons";
import styles from "./KnowledgeCheck.module.css";

/** The cap the server enforces (MAX_REFLECTION_CHARS). Mirrored so the box can say so. */
const MAX_REFLECTION_CHARS = 4000;

/** What the student is shown once an item is answered, however they got here. */
interface Verdict {
  correct: boolean;
  feedback: string;
  chosen: string;
}

/**
 * A verdict rebuilt from an answer stored on a previous visit.
 *
 * `yourResponse` carries no feedback line and no correct option — the server only
 * composes those at the moment of scoring. Rather than have the API restate them on
 * every read, a re-visit says what it can prove: what you picked and whether it was
 * right. A student who wants the answer text saw it when they answered.
 *
 * A reflection re-visit is not like this — see {@link ReflectionQuestion}.
 */
function verdictFromStored(item: KnowledgeCheckItem): Verdict | null {
  const stored = item.yourResponse;
  if (!stored) return null;
  return {
    // Non-null for an MCQ by construction: the server sends `correct` for exactly the
    // item type this component renders.
    correct: stored.correct === true,
    chosen: stored.response,
    feedback: stored.correct
      ? "You answered this correctly."
      : "You answered this incorrectly.",
  };
}

function verdictFromResult(result: McqResult, chosen: string): Verdict {
  return { correct: result.correct, feedback: result.feedback, chosen };
}

/**
 * One auto-scored multiple-choice question (US-18 / FR-E4).
 *
 * Submitting scores instantly — the verdict comes back from the POST, so there is no
 * spinner-then-result dance. An item is one attempt, so the options lock once answered
 * and stay locked across re-opens; that is what lets the feedback name the correct
 * option without turning the quiz into a guessing game.
 */
function McqQuestion({
  item,
  onSubmit,
  online,
}: {
  item: KnowledgeCheckItem;
  onSubmit: (itemId: number, answer: string) => Promise<McqResult>;
  online: boolean;
}) {
  const [choice, setChoice] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<Verdict | null>(() =>
    verdictFromStored(item),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const answered = verdict !== null;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (choice === null || answered) return;
    if (!online) {
      // Refuse before the request, the same way check-in and scanning do (US-6 /
      // FR-C4) — nothing queued, nothing optimistic, the item still unanswered.
      //
      // Saying "nothing was recorded" matters more here than anywhere else in the
      // app: an MCQ is one attempt, so a student left guessing whether a failed
      // submit counted has to assume they burned it. Offline a fetch rejects rather
      // than resolving !ok, so without this the catch below would tell them only
      // that something went wrong.
      setError(
        "Answering needs a connection. Nothing was recorded — reconnect and try again.",
      );
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await onSubmit(item.id, choice);
      setVerdict(verdictFromResult(result, choice));
    } catch (err) {
      // Show the server's own copy — it knows why better than we do, and a 409
      // ("You already answered this question") is a real state, not a glitch.
      setError(
        err instanceof ApiError ? err.message : "Could not submit your answer.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className={styles.card} onSubmit={handleSubmit}>
      <span className={styles.tag}>{item.outcomeTag}</span>

      <fieldset className={styles.fieldset} disabled={answered || submitting}>
        <legend className={styles.prompt}>{item.prompt}</legend>
        {item.options.map((option) => {
          const selected = answered
            ? verdict.chosen === option
            : choice === option;
          return (
            <label
              key={option}
              className={styles.option}
              data-selected={selected}
              data-verdict={
                answered && selected ? (verdict.correct ? "correct" : "incorrect") : undefined
              }
            >
              <input
                type="radio"
                name={`mcq-${item.id}`}
                value={option}
                checked={selected}
                onChange={() => setChoice(option)}
              />
              <span>{option}</span>
            </label>
          );
        })}
      </fieldset>

      {answered ? (
        <p
          className={styles.result}
          data-correct={verdict.correct}
          role="status"
        >
          <span className={styles.resultIcon} aria-hidden="true">
            {verdict.correct ? <CheckCircleIcon size={18} /> : "✕"}
          </span>
          <span>
            <strong className={styles.resultHeading}>
              {verdict.correct ? "Correct" : "Incorrect"}
            </strong>
            <span className={styles.resultFeedback}>{verdict.feedback}</span>
          </span>
        </p>
      ) : (
        <>
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
          <button
            type="submit"
            className={styles.submit}
            disabled={choice === null || submitting}
          >
            {submitting ? "Scoring…" : "Submit answer"}
          </button>
        </>
      )}
    </form>
  );
}

/** What a scored reflection shows, whether just submitted or read back. */
interface ReflectionVerdict {
  score: number;
  feedback: string;
  written: string;
}

/**
 * A reflection's verdict rebuilt from a previous visit.
 *
 * Unlike {@link verdictFromStored}, this one restates the feedback in full — a
 * reflection's feedback is *stored* (`ai_feedback`), whereas an MCQ's is composed from
 * the answer key at scoring time and never kept. So a re-visit can say everything the
 * original submit said. The asymmetry is the schema's, not this component's.
 */
function reflectionVerdictFromStored(
  item: KnowledgeCheckItem,
): ReflectionVerdict | null {
  const stored = item.yourResponse;
  if (!stored) return null;
  return {
    score: stored.score,
    written: stored.response,
    feedback: stored.feedback ?? "This reflection has been scored.",
  };
}

/** 0..1 as a percentage. The mockup's "4/5" is a static mock; the score is a fraction. */
function asPercent(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/**
 * One free-text reflection, scored against a rubric (US-19 / FR-E5).
 *
 * Sibling of {@link McqQuestion} and deliberately shaped like it: one card, its own
 * submit, its own failure. The mockup draws a single Submit under both cards, but a
 * shared button that half-succeeds — MCQ stored, reflection 503 — has no honest state to
 * render, and each item is separately one-attempt anyway.
 *
 * The lock engages on success only. A 503 means the scorer could not answer and nothing
 * was stored, so the textarea must stay editable — locking in a `finally` would take the
 * student's attempt away over an outage that explicitly did not spend it.
 */
function ReflectionQuestion({
  item,
  onSubmit,
  online,
}: {
  item: KnowledgeCheckItem;
  onSubmit: (itemId: number, text: string) => Promise<ReflectionResult>;
  online: boolean;
}) {
  const [text, setText] = useState("");
  const [verdict, setVerdict] = useState<ReflectionVerdict | null>(() =>
    reflectionVerdictFromStored(item),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const answered = verdict !== null;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (answered || !text.trim()) return;
    if (!online) {
      // Refuse before the request, the same way the MCQ card and check-in do (US-6 /
      // FR-C4). Offline a fetch rejects rather than resolving !ok, so without this the
      // catch below would tell the student only that something went wrong — and a
      // reflection is one attempt, so "nothing was recorded" is the part that matters.
      setError(
        "Scoring needs a connection. Nothing was recorded — reconnect and try again.",
      );
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await onSubmit(item.id, text);
      setVerdict({
        score: result.score,
        feedback: result.feedback,
        written: text,
      });
    } catch (err) {
      // The server's own copy. A 503 says the scorer is down and nothing was stored; a
      // 409 says this was already submitted. Both are real states the student can act
      // on, and neither survives being flattened into a generic apology.
      setError(
        err instanceof ApiError ? err.message : "Could not score your reflection.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className={styles.card} onSubmit={handleSubmit}>
      <span className={styles.tag}>{item.outcomeTag}</span>
      <p className={styles.prompt}>{item.prompt}</p>

      {answered ? (
        <>
          <p className={styles.written}>{verdict.written}</p>

          <div className={styles.scoreTile} role="status">
            <strong className={styles.scoreValue}>
              {asPercent(verdict.score)}
            </strong>
            <span className={styles.scoreLabel}>Reflection rubric</span>
          </div>

          <div className={styles.guide}>
            <span className={styles.guideHeading}>
              <AutoAwesomeIcon size={16} />
              Guide feedback
            </span>
            <span className={styles.guideBody}>{verdict.feedback}</span>
            <span className={styles.guideOutcome}>
              Mapped to outcome: <strong>{item.outcomeTag}</strong>
            </span>
          </div>
        </>
      ) : (
        <>
          <label className={styles.textareaLabel} htmlFor={`reflection-${item.id}`}>
            Your reflection
          </label>
          <textarea
            id={`reflection-${item.id}`}
            className={styles.textarea}
            value={text}
            maxLength={MAX_REFLECTION_CHARS}
            disabled={submitting}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type your reflection…"
          />
          <span className={styles.counter} aria-hidden="true">
            {text.length} / {MAX_REFLECTION_CHARS}
          </span>

          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
          <button
            type="submit"
            className={styles.submit}
            disabled={!text.trim() || submitting}
          >
            {submitting ? "Scoring…" : "Submit reflection"}
          </button>
        </>
      )}
    </form>
  );
}

/**
 * The assessment for one week of the passport, if it has one (FR-E4 / FR-E5).
 *
 * Lives inside the week sheet rather than on a route of its own: the student is
 * already here, having tapped the week. Renders nothing at all when the week carries
 * no items, which is most weeks — and nothing when the fetch fails, so an assessment
 * outage never costs the student the check-in button below it.
 */
export function KnowledgeCheck({
  weekNo,
  fetchItems = fetchWeekItems,
  submitFn = submitMcq,
  submitReflectionFn = submitReflection,
  online = true,
}: {
  weekNo: number;
  fetchItems?: (weekNo: number) => Promise<KnowledgeCheckItem[]>;
  submitFn?: (itemId: number, answer: string) => Promise<McqResult>;
  submitReflectionFn?: (
    itemId: number,
    text: string,
  ) => Promise<ReflectionResult>;
  /** Drives the refusal to start a network action (US-6 / FR-C4). */
  online?: boolean;
}) {
  const [items, setItems] = useState<KnowledgeCheckItem[]>([]);

  useEffect(() => {
    let active = true;
    void fetchItems(weekNo)
      // fetchWeekItems already answers [] on failure; this catch is for anything
      // that gets past it, so a broken quiz fetch can never take the sheet with it.
      .catch(() => [])
      .then((fetched) => {
        if (active) setItems(fetched);
      });
    return () => {
      active = false;
    };
  }, [weekNo, fetchItems]);

  if (items.length === 0) return null;

  return (
    <section className={styles.section} aria-label="Assessment">
      {/* "Assessment" rather than "Knowledge check" since FR-E5: the section now holds
          reflections too, and the mockup's S6 calls the screen Assessment. The types
          keep the older name for a reason spelled out in schemas/assessment.py. */}
      <h3 className={styles.heading}>Assessment</h3>
      {items.map((item) =>
        // Keyed by item id so switching weeks rebuilds each question's state rather
        // than carrying the previous week's selection into it.
        item.itemType === "reflection" ? (
          <ReflectionQuestion
            key={item.id}
            item={item}
            onSubmit={submitReflectionFn}
            online={online}
          />
        ) : (
          <McqQuestion
            key={item.id}
            item={item}
            onSubmit={submitFn}
            online={online}
          />
        ),
      )}
    </section>
  );
}
