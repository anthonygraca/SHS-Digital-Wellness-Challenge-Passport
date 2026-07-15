import { useEffect, useState } from "react";
import { ApiError } from "../../api/challenges";
import { fetchWeekItems, submitMcq } from "../../passport/assessments";
import type { KnowledgeCheckItem, McqResult } from "../../types/assessment";
import { CheckCircleIcon } from "../icons";
import styles from "./KnowledgeCheck.module.css";

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
 */
function verdictFromStored(item: KnowledgeCheckItem): Verdict | null {
  const stored = item.yourResponse;
  if (!stored) return null;
  return {
    correct: stored.correct,
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

/**
 * The knowledge check for one week of the passport, if it has one (US-18 / FR-E4).
 *
 * Lives inside the week sheet rather than on a route of its own: the student is
 * already here, having tapped the week. Renders nothing at all when the week carries
 * no questions, which is most weeks — and nothing when the fetch fails, so a quiz
 * outage never costs the student the check-in button below it.
 */
export function KnowledgeCheck({
  weekNo,
  fetchItems = fetchWeekItems,
  submitFn = submitMcq,
  online = true,
}: {
  weekNo: number;
  fetchItems?: (weekNo: number) => Promise<KnowledgeCheckItem[]>;
  submitFn?: (itemId: number, answer: string) => Promise<McqResult>;
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
    <section className={styles.section} aria-label="Knowledge check">
      <h3 className={styles.heading}>Knowledge check</h3>
      {items.map((item) => (
        // Keyed by item id so switching weeks rebuilds each question's state rather
        // than carrying the previous week's selection into it.
        <McqQuestion
          key={item.id}
          item={item}
          onSubmit={submitFn}
          online={online}
        />
      ))}
    </section>
  );
}
