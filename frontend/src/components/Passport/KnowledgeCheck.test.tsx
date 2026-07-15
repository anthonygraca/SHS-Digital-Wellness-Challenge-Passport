import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../../api/challenges";
import type { KnowledgeCheckItem, McqResult } from "../../types/assessment";
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
