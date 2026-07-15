import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ScoreOverridePanel } from "./ChallengeBuilder";
import type {
  AssessmentItem,
  AssessmentResponse,
} from "../../../types/challenge";

// Hoisted so the mock factory and the tests share one ApiError class — the component
// branches on `err instanceof api.ApiError`, which a second identical class would
// silently fail. Mirrors ChallengeBuilder.test.tsx.
const mocks = vi.hoisted(() => {
  class ApiError extends Error {
    constructor(
      public readonly status: number,
      message: string,
    ) {
      super(message);
      this.name = "ApiError";
    }
  }
  return {
    ApiError,
    listAssessmentResponses: vi.fn(),
    overrideAssessmentScore: vi.fn(),
  };
});

vi.mock("../../../api/challenges", () => ({
  ApiError: mocks.ApiError,
  listAssessmentResponses: mocks.listAssessmentResponses,
  overrideAssessmentScore: mocks.overrideAssessmentScore,
}));

vi.mock("../../../api/themes", () => ({ listThemes: () => Promise.resolve([]) }));

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
  Navigate: ({ to }: { to: string }) => <div>redirect:{to}</div>,
}));

vi.mock("../../../auth/SessionProvider", () => ({
  useSession: () => ({
    session: { affiliation: "staff" },
    loading: false,
    signOut: vi.fn(),
    refresh: vi.fn(),
  }),
}));

const REFLECTION_ITEM: AssessmentItem = {
  id: 9,
  task_id: 3,
  item_type: "reflection",
  prompt: "What is one number from today's labs you want to change, and how?",
  outcome_tag: "know-your-numbers",
  options: null,
  answer_key: null,
  rubric: "Names a specific number; names a specific doable action.",
  created_at: "2026-01-05T09:00:00Z",
  updated_at: "2026-01-05T09:00:00Z",
};

const FEEDBACK = "A solid start. There is more to say about the specifics here.";

const asResponse = (over: Partial<AssessmentResponse> = {}): AssessmentResponse => ({
  id: 41,
  student_id: 5,
  student_subject: "s1@csub.edu",
  response: "My blood pressure was high, so I'll walk after dinner.",
  score: 0.6,
  scored_by: "auto",
  ai_feedback: FEEDBACK,
  ts: "2026-02-01T12:00:00Z",
  ...over,
});

function renderPanel(item: AssessmentItem = REFLECTION_ITEM) {
  render(
    <ScoreOverridePanel
      challengeId={1}
      taskId={3}
      item={item}
      onClose={vi.fn()}
    />,
  );
}

const overrideButton = () =>
  screen.getByRole("button", { name: /override score for/i });
// By role, not label: the Override button's aria-label also contains "score".
const scoreInput = () => screen.getByRole("spinbutton");

beforeEach(() => {
  // Call history only — the implementations below survive, unlike resetAllMocks.
  vi.clearAllMocks();
  mocks.listAssessmentResponses.mockResolvedValue([asResponse()]);
  mocks.overrideAssessmentScore.mockImplementation((_c, _t, _i, id, { score }) =>
    Promise.resolve(asResponse({ id, score, scored_by: "human" })),
  );
});

describe("ScoreOverridePanel (US-19 / FR-E5)", () => {
  it("lists each response with its student, score, and how it was scored", async () => {
    renderPanel();

    const row = await screen.findByRole("listitem");
    expect(within(row).getByText("s1@csub.edu")).toBeInTheDocument();
    expect(within(row).getByText("60%")).toBeInTheDocument();
    expect(within(row).getByText("auto")).toBeInTheDocument();
    expect(within(row).getByText(/blood pressure was high/)).toBeInTheDocument();
    expect(within(row).getByText(new RegExp(FEEDBACK))).toBeInTheDocument();
  });

  it("shows only the student's subject — the only identifier that exists", async () => {
    // The no-PHI posture: Student holds no name and no campus ID number, and this
    // surface must not become the first place one appears.
    renderPanel();

    const row = await screen.findByRole("listitem");
    expect(within(row).getByText("s1@csub.edu")).toBeInTheDocument();
    expect(within(row).queryByText(/student_id/i)).not.toBeInTheDocument();
  });

  it("saves an overridden score and shows it as human-scored", async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.click(await screen.findByRole("button", { name: /override score for/i }));

    const input = scoreInput();
    await user.clear(input);
    await user.type(input, "0.25");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() =>
      expect(mocks.overrideAssessmentScore).toHaveBeenCalledWith(1, 3, 9, 41, {
        score: 0.25,
      }),
    );

    const row = await screen.findByRole("listitem");
    expect(within(row).getByText("25%")).toBeInTheDocument();
    expect(within(row).getByText("human")).toBeInTheDocument();
  });

  it("keeps the Guide feedback visible after an override", async () => {
    // With no audit table, this field beside scored_by="human" is the only trace the
    // override leaves — it says what the machine had said, which is the thing being
    // overridden.
    const user = userEvent.setup();
    renderPanel();

    await user.click(await screen.findByRole("button", { name: /override score for/i }));
    const input = scoreInput();
    await user.clear(input);
    await user.type(input, "0.25");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await screen.findByText("human");
    expect(screen.getByText(new RegExp(FEEDBACK))).toBeInTheDocument();
  });

  it("prefills the box with the current score, so a nudge is not a retype", async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.click(await screen.findByRole("button", { name: /override score for/i }));
    expect(scoreInput()).toHaveValue(0.6);
  });

  it("cancels without saving", async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.click(await screen.findByRole("button", { name: /override score for/i }));
    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(mocks.overrideAssessmentScore).not.toHaveBeenCalled();
    expect(overrideButton()).toBeInTheDocument();
  });

  it("refuses to send an empty score", async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.click(await screen.findByRole("button", { name: /override score for/i }));
    await user.clear(scoreInput());
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    expect(mocks.overrideAssessmentScore).not.toHaveBeenCalled();
    expect(screen.getByText(/between 0 and 1/i)).toBeInTheDocument();
  });

  it("shows the server's own message when a score is rejected", async () => {
    const user = userEvent.setup();
    mocks.overrideAssessmentScore.mockRejectedValue(
      new mocks.ApiError(422, "Input should be less than or equal to 1"),
    );
    renderPanel();

    await user.click(await screen.findByRole("button", { name: /override score for/i }));
    const input = scoreInput();
    await user.clear(input);
    await user.type(input, "5");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    // The server owns the bounds; it can say why better than a guess here can.
    expect(
      await screen.findByText(/less than or equal to 1/i),
    ).toBeInTheDocument();
  });

  it("says so when nobody has answered yet", async () => {
    mocks.listAssessmentResponses.mockResolvedValue([]);
    renderPanel();

    expect(await screen.findByText(/no one has answered/i)).toBeInTheDocument();
  });

  it("shows why the responses could not be loaded", async () => {
    mocks.listAssessmentResponses.mockRejectedValue(
      new mocks.ApiError(404, "Assessment item not found"),
    );
    renderPanel();

    expect(await screen.findByText(/assessment item not found/i)).toBeInTheDocument();
  });

  it("overrides an MCQ score too, which stores no feedback", async () => {
    const user = userEvent.setup();
    mocks.listAssessmentResponses.mockResolvedValue([
      asResponse({ response: "A1C", score: 0, ai_feedback: null }),
    ]);
    renderPanel({
      ...REFLECTION_ITEM,
      item_type: "mcq",
      options: ["A1C", "Fasting glucose"],
      answer_key: "A1C",
      rubric: null,
    });

    const row = await screen.findByRole("listitem");
    expect(within(row).getByText("0%")).toBeInTheDocument();
    expect(within(row).queryByText(/guide feedback/i)).not.toBeInTheDocument();

    await user.click(overrideButton());
    const input = scoreInput();
    await user.clear(input);
    await user.type(input, "1");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() =>
      expect(mocks.overrideAssessmentScore).toHaveBeenCalledWith(1, 3, 9, 41, {
        score: 1,
      }),
    );
  });
});
