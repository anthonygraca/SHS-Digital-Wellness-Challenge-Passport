import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Passport, PassportView } from "./Passport";
import type { Passport as PassportData, WeekStatus } from "../../types/passport";
import type { Session } from "../../types/session";

const sessionState = vi.hoisted(() => ({
  session: null as Session | null,
  loading: false,
}));
const signOut = vi.fn();

vi.mock("../../auth/SessionProvider", () => ({
  useSession: () => ({ ...sessionState, signOut, refresh: vi.fn() }),
}));
vi.mock("react-router-dom", () => ({
  Navigate: ({ to }: { to: string }) => <div>redirect:{to}</div>,
}));

afterEach(() => {
  sessionState.session = null;
  sessionState.loading = false;
  vi.clearAllMocks();
});

const asSession = (over: Partial<Session>): Session => ({
  subject: "abc@csub.edu",
  affiliation: "student",
  isCurrentStudent: true,
  ...over,
});

function week(weekNo: number, status: WeekStatus) {
  return {
    weekNo,
    title: `Week ${weekNo} Portal`,
    caption: "Themed caption for the week.",
    activityType: "Screening",
    location: "SHS Clinic",
    dateStart: "2026-09-02",
    dateEnd: "2026-09-06",
    prize: "Wellness kit",
    required: true,
    status,
  };
}

/** A 7-week passport with the first `completed` weeks done (sequential unlock). */
function passportWith(completed: number): PassportData {
  const weeks = Array.from({ length: 7 }, (_, i) => {
    const n = i + 1;
    const status: WeekStatus =
      n <= completed ? "complete" : n === completed + 1 ? "available" : "locked";
    return week(n, status);
  });
  return {
    challengeName: "Stranger Things Wellness Challenge",
    theme: "stranger-things",
    totalWeeks: 7,
    completedWeeks: completed,
    remainingWeeks: 7 - completed,
    weeks,
  };
}

describe("PassportView (US-5 / FR-C2, FR-C3)", () => {
  it("renders a tile for every week", () => {
    render(<PassportView passport={passportWith(3)} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(7);
  });

  it("shows the progress countdown in the required format", () => {
    render(<PassportView passport={passportWith(3)} />);
    expect(
      screen.getByText(/3 of 7 complete, 4 remaining/i),
    ).toBeInTheDocument();
  });

  it("marks weeks complete / available / locked (future weeks locked)", () => {
    render(<PassportView passport={passportWith(3)} />);
    // 3 complete, 1 available (the earliest incomplete), 3 locked.
    expect(screen.getAllByText("Complete")).toHaveLength(3);
    expect(screen.getByText("Available")).toBeInTheDocument();
    expect(screen.getAllByText("Locked")).toHaveLength(3);
  });

  it("updates the countdown after a new completion", () => {
    const { rerender } = render(<PassportView passport={passportWith(3)} />);
    expect(screen.getByText(/3 of 7 complete, 4 remaining/i)).toBeInTheDocument();

    rerender(<PassportView passport={passportWith(4)} />);
    expect(screen.getByText(/4 of 7 complete, 3 remaining/i)).toBeInTheDocument();
    expect(screen.getAllByText("Complete")).toHaveLength(4);
  });

  it("exposes a progressbar reflecting completion", () => {
    render(<PassportView passport={passportWith(3)} />);
    const bar = screen.getByRole("progressbar", { name: /weeks complete/i });
    expect(bar).toHaveAttribute("aria-valuenow", "3");
    expect(bar).toHaveAttribute("aria-valuemax", "7");
  });
});

describe("PassportView check-in (event detail + manual unlock)", () => {
  it("opens a detail sheet with a check-in button when a tile is clicked", async () => {
    render(<PassportView passport={passportWith(3)} onCheckIn={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Week 4:/i }));

    const sheet = screen.getByRole("dialog");
    expect(within(sheet).getByText("Week 4 Portal")).toBeInTheDocument();
    expect(
      within(sheet).getByRole("button", { name: /^check in$/i }),
    ).toBeInTheDocument();
  });

  it("checks in the selected week", async () => {
    const onCheckIn = vi.fn().mockResolvedValue(undefined);
    render(<PassportView passport={passportWith(3)} onCheckIn={onCheckIn} />);

    await userEvent.click(screen.getByRole("button", { name: /Week 4:/i }));
    const sheet = screen.getByRole("dialog");
    await userEvent.click(
      within(sheet).getByRole("button", { name: /^check in$/i }),
    );

    expect(onCheckIn).toHaveBeenCalledTimes(1);
    expect(onCheckIn).toHaveBeenCalledWith(4);
  });

  it("allows manual unlock: a locked week is still tappable and checkable", async () => {
    const onCheckIn = vi.fn().mockResolvedValue(undefined);
    render(<PassportView passport={passportWith(3)} onCheckIn={onCheckIn} />);

    // Week 6 is locked, but the tile still opens and offers a check-in.
    await userEvent.click(screen.getByRole("button", { name: /Week 6:/i }));
    const sheet = screen.getByRole("dialog");
    await userEvent.click(
      within(sheet).getByRole("button", { name: /^check in$/i }),
    );

    expect(onCheckIn).toHaveBeenCalledWith(6);
  });

  it("shows a completed week as already checked in (no active check-in)", async () => {
    render(<PassportView passport={passportWith(3)} onCheckIn={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Week 1:/i }));
    const sheet = screen.getByRole("dialog");
    expect(
      within(sheet).getByRole("button", { name: /checked in/i }),
    ).toBeDisabled();
    expect(
      within(sheet).queryByRole("button", { name: /^check in$/i }),
    ).toBeNull();
  });

  it("renders a task with no date window instead of crashing (US-11 allows it)", async () => {
    const passport = passportWith(3);
    passport.weeks[3] = { ...passport.weeks[3], dateStart: null, dateEnd: null };
    render(<PassportView passport={passport} onCheckIn={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Week 4:/i }));
    const sheet = screen.getByRole("dialog");
    expect(within(sheet).getByText("Dates TBA")).toBeInTheDocument();
  });
});

describe("Passport eligibility gate (US-2 / FR-A3)", () => {
  it("current student sees their passport", async () => {
    sessionState.session = asSession({ isCurrentStudent: true });
    const fetchData = vi.fn().mockResolvedValue(passportWith(3));

    render(<Passport fetchData={fetchData} checkInFn={vi.fn()} />);

    expect(
      await screen.findByText(/3 of 7 complete, 4 remaining/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/not eligible to join/i)).toBeNull();
  });

  it("non-current student is blocked and never fetches a passport", async () => {
    sessionState.session = asSession({
      affiliation: "alum",
      isCurrentStudent: false,
    });
    const fetchData = vi.fn().mockResolvedValue(passportWith(3));

    render(<Passport fetchData={fetchData} checkInFn={vi.fn()} />);

    expect(
      screen.getByRole("heading", { name: /not eligible to join/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).toBeNull();
    // The gate runs before the effect, so an ineligible session makes no request.
    await waitFor(() => expect(fetchData).not.toHaveBeenCalled());
  });

  it("signed-out visitor is redirected to sign-in", () => {
    sessionState.session = null;
    render(<Passport fetchData={vi.fn()} checkInFn={vi.fn()} />);
    expect(screen.getByText("redirect:/")).toBeInTheDocument();
  });
});
