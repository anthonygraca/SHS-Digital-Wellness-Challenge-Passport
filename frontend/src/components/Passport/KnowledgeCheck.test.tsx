import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../../api/challenges";
import type {
  KnowledgeCheckItem,
  McqResult,
  ReflectionResult,
} from "../../types/assessment";
import { KnowledgeCheck } from "./KnowledgeCheck";

afterEach(() => {
  vi.clearAllMocks();
});

const PROMPT = "How often should a healthy adult have a comprehensive eye exam?";
const OPTIONS = [
  "Only when my vision seems blurry",
  "Every 1-2 years",
  "Once, when I turn 18",
  "Every 5 years",
];
const CORRECT = "Every 1-2 years";
const INCORRECT = "Once, when I turn 18";

const asItem = (over: Partial<KnowledgeCheckItem> = {}): KnowledgeCheckItem => ({
  id: 7,
  weekNo: 3,
  itemType: "mcq",
  prompt: PROMPT,
  outcomeTag: "vision-care",
  options: OPTIONS,
  yourResponse: null,
  ...over,
});

const asResult = (over: Partial<McqResult> = {}): McqResult => ({
  itemId: 7,
  outcomeTag: "vision-care",
  correct: true,
  score: 1,
  scoredBy: "auto",
  correctOption: CORRECT,
  feedback: "Correct! Nice work.",
  ...over,
});

const incorrectResult = () =>
  asResult({
    correct: false,
    score: 0,
    feedback: `Not quite — the correct answer is "${CORRECT}".`,
  });

/** Render with the given items; returns the submit spy. */
function renderCheck(items: KnowledgeCheckItem[], submit = vi.fn()) {
  const fetchItems = vi.fn().mockResolvedValue(items);
  render(<KnowledgeCheck weekNo={3} fetchItems={fetchItems} submitFn={submit} />);
  return { submit, fetchItems };
}

const option = (name: string) => screen.getByRole("radio", { name });
const submitButton = () => screen.getByRole("button", { name: /submit answer/i });

describe("MCQ knowledge check (US-18 / FR-E4)", () => {
  it("renders the prompt, the outcome tag, and every option as a radio", async () => {
    renderCheck([asItem()]);

    expect(await screen.findByText(PROMPT)).toBeInTheDocument();
    expect(screen.getByText("vision-care")).toBeInTheDocument();
    for (const text of OPTIONS) {
      expect(option(text)).toBeInTheDocument();
    }
  });

  it("cannot be submitted until an option is chosen", async () => {
    const user = userEvent.setup();
    renderCheck([asItem()]);

    expect(await screen.findByRole("button", { name: /submit answer/i })).toBeDisabled();

    await user.click(option(CORRECT));
    expect(submitButton()).toBeEnabled();
  });

  it("scores a correct answer instantly, from the submit call itself", async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockResolvedValue(asResult());
    renderCheck([asItem()], submit);

    await user.click(await screen.findByRole("radio", { name: CORRECT }));
    await user.click(submitButton());

    const result = await screen.findByRole("status");
    expect(result).toHaveTextContent(/correct/i);
    expect(result).toHaveTextContent("Correct! Nice work.");
    expect(submit).toHaveBeenCalledWith(7, CORRECT);
  });

  it("names the correct option when the answer is wrong", async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockResolvedValue(incorrectResult());
    renderCheck([asItem()], submit);

    await user.click(await screen.findByRole("radio", { name: INCORRECT }));
    await user.click(submitButton());

    // The scenario is titled "...with feedback": a verdict alone teaches nothing.
    const result = await screen.findByRole("status");
    expect(result).toHaveTextContent(/incorrect/i);
    expect(result).toHaveTextContent(CORRECT);
  });

  it("locks the options once answered — an MCQ is one attempt", async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockResolvedValue(incorrectResult());
    renderCheck([asItem()], submit);

    await user.click(await screen.findByRole("radio", { name: INCORRECT }));
    await user.click(submitButton());
    await screen.findByRole("status");

    // Visibly closed: the student can see the answer, so they must not be able to
    // quietly change theirs to match it.
    for (const text of OPTIONS) {
      expect(option(text)).toBeDisabled();
    }
    expect(
      screen.queryByRole("button", { name: /submit answer/i }),
    ).not.toBeInTheDocument();
  });

  it("shows an already-answered question's result without re-submitting", async () => {
    const submit = vi.fn();
    renderCheck(
      [
        asItem({
          yourResponse: {
            response: INCORRECT,
            score: 0,
            correct: false,
            scoredBy: "auto",
            // Null for every MCQ: that feedback is composed from the answer key at
            // scoring time and never stored, so a re-visit cannot restate it.
            feedback: null,
            ts: "2026-02-01T12:00:00Z",
          },
        }),
      ],
      submit,
    );

    const result = await screen.findByRole("status");
    expect(result).toHaveTextContent(/incorrect/i);
    expect(option(INCORRECT)).toBeChecked();
    expect(option(INCORRECT)).toBeDisabled();
    expect(submit).not.toHaveBeenCalled();
  });

  it("shows the server's own message when a submission is refused", async () => {
    const user = userEvent.setup();
    const submit = vi
      .fn()
      .mockRejectedValue(new ApiError(409, "You already answered this question"));
    renderCheck([asItem()], submit);

    await user.click(await screen.findByRole("radio", { name: CORRECT }));
    await user.click(submitButton());

    // Verbatim: a 409 is a real state the server can describe better than we can.
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You already answered this question",
    );
  });

  it("refuses to submit offline, without sending anything (US-6 / FR-C4)", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    const fetchItems = vi.fn().mockResolvedValue([asItem()]);
    render(
      <KnowledgeCheck
        weekNo={3}
        fetchItems={fetchItems}
        submitFn={submit}
        online={false}
      />,
    );

    await user.click(await screen.findByRole("radio", { name: CORRECT }));
    await user.click(submitButton());

    // "Nothing was recorded" is load-bearing copy here: an MCQ is one attempt, so a
    // student left unsure whether a failed submit counted must assume they burned it.
    const notice = await screen.findByRole("alert");
    expect(notice).toHaveTextContent(/needs a connection/i);
    expect(notice).toHaveTextContent(/nothing was recorded/i);

    // Refused before the request, not after it failed — nothing queued to replay.
    expect(submit).not.toHaveBeenCalled();
    // And the question is still open, so it can be answered on reconnect.
    expect(option(CORRECT)).toBeEnabled();
  });

  it("renders nothing for a week with no knowledge check", async () => {
    const { container } = render(
      <KnowledgeCheck
        weekNo={1}
        fetchItems={vi.fn().mockResolvedValue([])}
        submitFn={vi.fn()}
      />,
    );

    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("renders nothing, and does not throw, when the questions cannot be fetched", async () => {
    // An outage must cost the student the quiz block and not the sheet around it —
    // the check-in button lives below this component.
    const { container } = render(
      <KnowledgeCheck
        weekNo={1}
        fetchItems={vi.fn().mockRejectedValue(new Error("network down"))}
        submitFn={vi.fn()}
      />,
    );

    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("scores each question of a multi-question week independently", async () => {
    const user = userEvent.setup();
    const submit = vi
      .fn()
      .mockResolvedValueOnce(asResult({ itemId: 7 }))
      .mockResolvedValueOnce(incorrectResult());
    renderCheck([asItem({ id: 7 }), asItem({ id: 8, prompt: "Second question" })], submit);

    await screen.findByText("Second question");
    const [firstSubmit, secondSubmit] = screen.getAllByRole("button", {
      name: /submit answer/i,
    });

    // Answering the first must not disturb the second — separate radio groups,
    // separate verdicts.
    await user.click(screen.getAllByRole("radio", { name: CORRECT })[0]);
    await user.click(firstSubmit);
    await screen.findByRole("status");

    expect(secondSubmit).toBeInTheDocument();
    expect(screen.getAllByRole("radio", { name: CORRECT })[1]).toBeEnabled();
  });
});

// ---------------------------------------------------------------------------
// Reflection scoring (US-19 / FR-E5)
// ---------------------------------------------------------------------------

const REFLECTION_PROMPT =
  "What is one number from today's labs you want to change, and how?";
const WRITTEN = "My blood pressure was high, so I'll walk after dinner.";

const asReflection = (
  over: Partial<KnowledgeCheckItem> = {},
): KnowledgeCheckItem =>
  asItem({
    id: 9,
    itemType: "reflection",
    prompt: REFLECTION_PROMPT,
    outcomeTag: "know-your-numbers",
    // A reflection has nothing to choose between.
    options: [],
    ...over,
  });

const asReflectionResult = (
  over: Partial<ReflectionResult> = {},
): ReflectionResult => ({
  itemId: 9,
  outcomeTag: "know-your-numbers",
  score: 0.6,
  scoredBy: "auto",
  feedback: "A solid start. There is more to say about the specifics here.",
  ...over,
});

/** Render a reflection week; returns the reflection submit spy. */
function renderReflection(
  items: KnowledgeCheckItem[],
  submitReflectionFn = vi.fn(),
  online = true,
) {
  const fetchItems = vi.fn().mockResolvedValue(items);
  render(
    <KnowledgeCheck
      weekNo={3}
      fetchItems={fetchItems}
      submitFn={vi.fn()}
      submitReflectionFn={submitReflectionFn}
      online={online}
    />,
  );
  return { submitReflectionFn, fetchItems };
}

const textarea = () => screen.getByRole("textbox", { name: /your reflection/i });
const reflectionSubmit = () =>
  screen.getByRole("button", { name: /submit reflection/i });

describe("Reflection scoring (US-19 / FR-E5)", () => {
  it("renders a textarea rather than options", async () => {
    renderReflection([asReflection()]);

    expect(await screen.findByText(REFLECTION_PROMPT)).toBeInTheDocument();
    expect(textarea()).toBeInTheDocument();
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
  });

  it("cannot be submitted empty, or with only whitespace", async () => {
    const user = userEvent.setup();
    renderReflection([asReflection()]);

    expect(await screen.findByRole("button", { name: /submit reflection/i })).toBeDisabled();

    // Whitespace would burn the student's one attempt on nothing; the server 422s it,
    // and the button should never let it get that far.
    await user.type(textarea(), "   ");
    expect(reflectionSubmit()).toBeDisabled();

    await user.type(textarea(), "something real");
    expect(reflectionSubmit()).toBeEnabled();
  });

  it("shows the score and the Guide feedback, mapped to the outcome", async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockResolvedValue(asReflectionResult());
    renderReflection([asReflection()], submit);

    await user.type(await screen.findByRole("textbox"), WRITTEN);
    await user.click(reflectionSubmit());

    // 0.6 renders as 60% — the score is a fraction, and the mockup's "4/5" is a static
    // mock rather than a scale the API has.
    expect(await screen.findByRole("status")).toHaveTextContent("60%");
    expect(screen.getByText(/a solid start/i)).toBeInTheDocument();
    expect(screen.getByText(/mapped to outcome/i)).toHaveTextContent(
      "know-your-numbers",
    );
    expect(submit).toHaveBeenCalledWith(9, WRITTEN);
  });

  it("never says correct or incorrect — a rubric score is neither", async () => {
    const user = userEvent.setup();
    renderReflection([asReflection()], vi.fn().mockResolvedValue(asReflectionResult()));

    await user.type(await screen.findByRole("textbox"), WRITTEN);
    await user.click(reflectionSubmit());
    await screen.findByRole("status");

    // The bug the nullable `correct` exists to prevent: a 0.6 is a matter of degree,
    // and "Incorrect" would be a verdict the item cannot support.
    expect(screen.queryByText(/^incorrect$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^correct$/i)).not.toBeInTheDocument();
  });

  it("locks once scored — a reflection is one attempt", async () => {
    const user = userEvent.setup();
    renderReflection([asReflection()], vi.fn().mockResolvedValue(asReflectionResult()));

    await user.type(await screen.findByRole("textbox"), WRITTEN);
    await user.click(reflectionSubmit());
    await screen.findByRole("status");

    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /submit reflection/i }),
    ).not.toBeInTheDocument();
  });

  it("restates the stored feedback on a re-visit, unlike an MCQ", async () => {
    const submit = vi.fn();
    renderReflection(
      [
        asReflection({
          yourResponse: {
            response: WRITTEN,
            score: 0.6,
            // Null for a reflection: there is no key for it to be right or wrong against.
            correct: null,
            scoredBy: "auto",
            // Unlike an MCQ's, this one is stored — so a re-visit can restate it in full.
            feedback: "A solid start. There is more to say about the specifics here.",
            ts: "2026-02-01T12:00:00Z",
          },
        }),
      ],
      submit,
    );

    expect(await screen.findByRole("status")).toHaveTextContent("60%");
    expect(screen.getByText(/a solid start/i)).toBeInTheDocument();
    expect(screen.getByText(WRITTEN)).toBeInTheDocument();
    expect(submit).not.toHaveBeenCalled();
  });

  it("shows an overridden score as the student's score", async () => {
    // The point of the admin override: what they see is the corrected number.
    renderReflection([
      asReflection({
        yourResponse: {
          response: WRITTEN,
          score: 0.25,
          correct: null,
          scoredBy: "human",
          feedback: "A solid start. There is more to say about the specifics here.",
          ts: "2026-02-01T12:00:00Z",
        },
      }),
    ]);

    expect(await screen.findByRole("status")).toHaveTextContent("25%");
  });

  it("refuses to submit offline, without sending anything (US-6 / FR-C4)", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    renderReflection([asReflection()], submit, false);

    await user.type(await screen.findByRole("textbox"), WRITTEN);
    await user.click(reflectionSubmit());

    const notice = await screen.findByRole("alert");
    expect(notice).toHaveTextContent(/needs a connection/i);
    expect(notice).toHaveTextContent(/nothing was recorded/i);

    // Refused before the request, not after it failed — nothing queued to replay.
    expect(submit).not.toHaveBeenCalled();
    // And still writable, so it can be submitted on reconnect.
    expect(textarea()).toBeEnabled();
  });

  it("keeps the reflection editable when the scorer is down (503)", async () => {
    const user = userEvent.setup();
    const submit = vi
      .fn()
      .mockRejectedValue(
        new ApiError(
          503,
          "Scoring is unavailable right now. Nothing was recorded — try again shortly.",
        ),
      );
    renderReflection([asReflection()], submit);

    await user.type(await screen.findByRole("textbox"), WRITTEN);
    await user.click(reflectionSubmit());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /nothing was recorded/i,
    );

    // The whole point of the server storing nothing on a 503: the attempt is still
    // there. A component that locked in a `finally` would take it away anyway, and
    // the student would have no way to tell.
    expect(textarea()).toBeEnabled();
    expect(textarea()).toHaveValue(WRITTEN);
    expect(reflectionSubmit()).toBeEnabled();
  });

  it("shows the server's own message when a submission is refused", async () => {
    const user = userEvent.setup();
    const submit = vi
      .fn()
      .mockRejectedValue(new ApiError(409, "You already submitted this reflection"));
    renderReflection([asReflection()], submit);

    await user.type(await screen.findByRole("textbox"), WRITTEN);
    await user.click(reflectionSubmit());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You already submitted this reflection",
    );
  });

  it("caps the reflection at the length the server accepts", async () => {
    renderReflection([asReflection()]);
    // Mirrors MAX_REFLECTION_CHARS: past it the server 422s, and a textarea that let
    // a student write 6000 characters before saying so would be the worse messenger.
    expect(await screen.findByRole("textbox")).toHaveAttribute("maxlength", "4000");
  });

  it("renders an MCQ and a reflection on one week, each with its own submit", async () => {
    // Mockup S6 draws both cards on one screen; week 3 of the seed carries both.
    renderReflection([asItem({ id: 7 }), asReflection({ id: 9 })]);

    expect(await screen.findByText(REFLECTION_PROMPT)).toBeInTheDocument();
    expect(screen.getByText(PROMPT)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /submit answer/i })).toBeInTheDocument();
    expect(reflectionSubmit()).toBeInTheDocument();
  });
});
