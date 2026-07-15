import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChallengeBuilder } from "./ChallengeBuilder";
import type { Challenge, ChallengeSummary } from "../../../types/challenge";

// Hoisted so the mock factory and the tests share one ApiError class — the
// component branches on `err instanceof api.ApiError`, which a second identical
// class would silently fail.
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
    listChallenges: vi.fn(),
    getChallenge: vi.fn(),
    duplicateChallenge: vi.fn(),
  };
});

vi.mock("../../../api/challenges", () => ({
  ApiError: mocks.ApiError,
  listChallenges: mocks.listChallenges,
  getChallenge: mocks.getChallenge,
  duplicateChallenge: mocks.duplicateChallenge,
}));

vi.mock("../../../api/themes", () => ({
  listThemes: () => Promise.resolve([]),
}));

vi.mock("../../../auth/SessionProvider", () => ({
  useSession: () => ({
    session: { affiliation: "staff" },
    loading: false,
    signOut: vi.fn(),
    refresh: vi.fn(),
  }),
}));

const PRIOR: ChallengeSummary = {
  id: 7,
  campus_id: "csub",
  name: "Fall 2025 - Stranger Things",
  semester: "Fall 2025",
  start_date: "2025-09-01",
  end_date: "2025-12-15",
  theme_id: "stranger-things",
  status: "published",
  created_at: "2025-08-01T00:00:00Z",
  updated_at: "2025-08-01T00:00:00Z",
};

const COPY: Challenge = {
  ...PRIOR,
  id: 8,
  name: "Fall 2025 - Stranger Things (Copy)",
  status: "draft",
  tasks: [],
};

/** Open the modal from the list card and return it (scoping queries away from
 *  the card's own "Duplicate" button, which stays mounted behind the overlay). */
async function openDuplicateModal() {
  render(<ChallengeBuilder />);
  await screen.findByText(PRIOR.name);
  await userEvent.click(screen.getByRole("button", { name: /duplicate/i }));
  return screen.findByRole("dialog", { name: /duplicate challenge/i });
}

describe("ChallengeBuilder — duplicate (US-14 / FR-B6)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listChallenges.mockResolvedValue([PRIOR]);
    mocks.getChallenge.mockResolvedValue({ ...PRIOR, tasks: [] });
    mocks.duplicateChallenge.mockResolvedValue(COPY);
  });

  it("offers a duplicate action on each challenge card", async () => {
    render(<ChallengeBuilder />);
    await screen.findByText(PRIOR.name);
    expect(screen.getByRole("button", { name: /duplicate/i })).toBeInTheDocument();
  });

  it("duplicating does not also open the challenge", async () => {
    // The button is a sibling of the role="button" card, so its click must not
    // bubble into the card's open handler.
    await openDuplicateModal();
    expect(mocks.getChallenge).not.toHaveBeenCalled();
  });

  it("prefills the copy's name and the original's semester", async () => {
    const modal = await openDuplicateModal();

    expect(within(modal).getByLabelText(/new challenge name/i)).toHaveValue(
      "Fall 2025 - Stranger Things (Copy)",
    );
    expect(within(modal).getByLabelText(/semester/i)).toHaveValue("Fall 2025");
  });

  it("sends an admin-chosen name, then opens the new draft", async () => {
    const modal = await openDuplicateModal();

    const name = within(modal).getByLabelText(/new challenge name/i);
    await userEvent.clear(name);
    await userEvent.type(name, "Spring 2026 Kickoff");
    const semester = within(modal).getByLabelText(/semester/i);
    await userEvent.clear(semester);
    await userEvent.type(semester, "Spring 2026");
    await userEvent.click(within(modal).getByRole("button", { name: /^duplicate$/i }));

    expect(mocks.duplicateChallenge).toHaveBeenCalledWith(7, {
      name: "Spring 2026 Kickoff",
      semester: "Spring 2026",
    });
    // Navigating to the copy's detail view is what makes it "an editable draft".
    await waitFor(() => expect(mocks.getChallenge).toHaveBeenCalledWith(8));
  });

  it("suggests one copy suffix when duplicating a copy, not two", async () => {
    mocks.listChallenges.mockResolvedValue([
      { ...PRIOR, name: "Fall 2025 - Stranger Things (Copy 2)" },
    ]);
    render(<ChallengeBuilder />);
    await screen.findByText("Fall 2025 - Stranger Things (Copy 2)");
    await userEvent.click(screen.getByRole("button", { name: /duplicate/i }));
    const modal = await screen.findByRole("dialog", { name: /duplicate challenge/i });

    expect(within(modal).getByLabelText(/new challenge name/i)).toHaveValue(
      "Fall 2025 - Stranger Things (Copy)",
    );
  });

  it("omits an untouched name so the server can derive the next free one", async () => {
    // Posting our own suggestion back would 409 on the second duplicate into the
    // same semester, instead of yielding "(Copy 2)".
    const modal = await openDuplicateModal();
    await userEvent.click(within(modal).getByRole("button", { name: /^duplicate$/i }));

    expect(mocks.duplicateChallenge).toHaveBeenCalledWith(7, {
      name: undefined,
      semester: "Fall 2025",
    });
  });

  it("keeps the modal open and shows the reason when the name collides", async () => {
    mocks.duplicateChallenge.mockRejectedValue(
      new mocks.ApiError(
        409,
        "A challenge with that name already exists for that semester",
      ),
    );

    const modal = await openDuplicateModal();
    await userEvent.click(within(modal).getByRole("button", { name: /^duplicate$/i }));

    expect(await screen.findByText(/already exists/i)).toBeInTheDocument();
    expect(
      screen.getByRole("dialog", { name: /duplicate challenge/i }),
    ).toBeInTheDocument();
    expect(mocks.getChallenge).not.toHaveBeenCalled();
  });
});
