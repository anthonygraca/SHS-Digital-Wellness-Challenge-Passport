import { useEffect, useRef, useState } from "react";
import { fetchCrisisResources } from "../../api/guide";
import type { CrisisResource, CrisisResources } from "../../types/guide";
import { EmergencyIcon, PhoneIcon } from "../icons";
import styles from "./CrisisResources.module.css";

/**
 * The last-resort card, used when the API cannot be reached (FR-E3 / NFR-8).
 *
 * A crisis affordance that opens an empty dialog because a fetch failed is worse than no
 * affordance: the student pressed the button that promised help and got a spinner. 988 is
 * a constant on the server for the same reason it is hard-coded here — it is national, so
 * a client that has never spoken to this deployment still knows it.
 *
 * The campus numbers are deliberately absent rather than guessed. They are per-campus
 * deploy config (NFR-4), this bundle does not know which campus it is serving, and a
 * plausible wrong number in a crisis card is worse than a missing one.
 */
const OFFLINE_FALLBACK: CrisisResources = {
  headline: "You're not alone",
  resources: [
    {
      role: "lifeline",
      name: "988 Suicide & Crisis Lifeline",
      phone: "988",
      detail: "Call or text, 24/7. Free and confidential.",
    },
  ],
};

/** Strip a phone number to what a dialler can take: digits, and a leading +. */
function telHref(phone: string): string {
  const cleaned = phone.replace(/[^\d+]/g, "");
  return `tel:${cleaned}`;
}

function ResourceLink({ resource }: { resource: CrisisResource }) {
  const isLifeline = resource.role === "lifeline";
  return (
    <a
      className={`${styles.resource} ${isLifeline ? styles.lifeline : ""}`}
      href={telHref(resource.phone)}
    >
      <PhoneIcon size={20} />
      <span className={styles.resourceText}>
        <span className={styles.resourceName}>{resource.name}</span>
        <span className={styles.resourcePhone}>{resource.phone}</span>
        {resource.detail && (
          <span className={styles.resourceDetail}>{resource.detail}</span>
        )}
      </span>
    </a>
  );
}

/**
 * A persistent "Get help now" affordance and the crisis card it opens (FR-E3 / NFR-8).
 *
 * docs/frontend-design-prompt.md calls for "a visible crisis-resources affordance". The
 * design mock puts it inside the guide chat, as a link in the "educational only — not
 * medical advice" banner. There is no chat on this branch (that is US-16), so it lives on
 * the passport instead — which is also the better place for it: a student who already
 * knows they need a person should not have to open a chatbot and type a disclosure to be
 * handed a phone number. The mock's disclaimer copy travels into the dialog footer so the
 * card keeps the framing it was drawn with.
 *
 * The resources are fetched rather than hard-coded because the campus numbers are
 * per-campus deploy config (NFR-4) and this bundle is built once for every campus. Only
 * 988 is knowable client-side, which is exactly what OFFLINE_FALLBACK carries.
 *
 * `fetchResources` is injected with a default, matching KnowledgeCheck — the tests drive
 * the failure paths through it rather than by mocking fetch.
 */
export default function CrisisResources({
  fetchResources = fetchCrisisResources,
}: {
  fetchResources?: () => Promise<CrisisResources>;
}) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<CrisisResources | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Fetched when the dialog opens, not on mount: this component renders on every
  // passport screen, and a request nobody asked for on every page load is a request that
  // says "this student looked at the crisis card" to anything watching traffic. Opening
  // it is a deliberate act; mounting the passport is not.
  useEffect(() => {
    if (!open || data) return;
    let cancelled = false;
    void fetchResources()
      .then((r) => !cancelled && setData(r))
      // The card must open with something. See OFFLINE_FALLBACK.
      .catch(() => !cancelled && setData(OFFLINE_FALLBACK));
    return () => {
      cancelled = true;
    };
  }, [open, data, fetchResources]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    closeRef.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const card = data ?? OFFLINE_FALLBACK;

  return (
    <>
      <button
        type="button"
        className={styles.trigger}
        onClick={() => setOpen(true)}
      >
        <EmergencyIcon size={18} />
        Get help now
      </button>

      {open && (
        <div className={styles.backdrop} onClick={() => setOpen(false)}>
          <div
            className={styles.sheet}
            role="dialog"
            aria-modal="true"
            aria-label="Crisis resources"
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.sheetHandle} aria-hidden="true" />
            <button
              type="button"
              ref={closeRef}
              className={styles.close}
              onClick={() => setOpen(false)}
              aria-label="Close"
            >
              ✕
            </button>

            <h2 className={styles.title}>
              <EmergencyIcon size={22} />
              {card.headline}
            </h2>
            <p className={styles.lede}>
              Reach out right now — these are free, confidential, and staffed by
              people who want to hear from you. If you are in immediate danger,
              call 911.
            </p>

            <ul className={styles.list}>
              {card.resources.map((resource) => (
                <li key={resource.role}>
                  <ResourceLink resource={resource} />
                </li>
              ))}
            </ul>

            {/* The mock's guide disclaimer, kept with the card it was drawn beside. */}
            <p className={styles.footnote}>
              This app is educational only — <strong>not medical advice</strong>
              , and no diagnosis. For health questions, contact Student Health
              Services.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
