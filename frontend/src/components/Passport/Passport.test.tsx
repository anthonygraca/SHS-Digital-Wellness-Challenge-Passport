import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Passport, PassportView } from "./Passport";
import { ApiError } from "../../api/challenges";
import type {
  CheckInResult,
  Passport as PassportData,
  WeekStatus,
} from "../../types/passport";
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
// Stub the camera scanner: render a button that decodes a fixed token on click,
// so the scan flow is testable without a real camera / html5-qrcode.
vi.mock("./QrScanner", () => ({
  QrScanner: ({ onDecode }: { onDecode: (t: string) => void }) => (
    <button type="button" onClick={() => onDecode("scanned-token")}>
      simulate-scan
    </button>
  ),
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

function week(weekNo: number, status: WeekStatus, required = true) {
  return {
    weekNo,
    title: `Week ${weekNo} Portal`,
    caption: "Themed caption for the week.",
    activityType: "Screening",
    location: "SHS Clinic",
    dateStart: "2026-09-02",
    dateEnd: "2026-09-06",
    prize: "Wellness kit",
    required,
    status,
  };
}

/** A 7-week passport (all required) with the first `completed` weeks done. */
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
    requiredTotal: 7,
    requiredCompleted: completed,
    prizeEligible: completed === 7,
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

describe("PassportView prize-eligibility indicator (US-7 / FR-C5)", () => {
  it("shows 'not yet eligible' while required tasks remain", () => {
    render(<PassportView passport={passportWith(2)} />);
    expect(screen.getByText("Not yet eligible")).toBeInTheDocument();
    expect(screen.getByText(/2 of 7 required tasks complete/i)).toBeInTheDocument();
    expect(screen.queryByText("Prize eligible")).toBeNull();
  });

  it("shows 'eligible' once all required tasks are complete", () => {
    render(<PassportView passport={passportWith(7)} />);
    expect(screen.getByText("Prize eligible")).toBeInTheDocument();
    expect(screen.queryByText("Not yet eligible")).toBeNull();
  });

  it("stays eligible even when an optional task is incomplete", () => {
    // 3 required tasks (all complete) + 1 optional task left incomplete.
    const passport: PassportData = {
      challengeName: "Stranger Things Wellness Challenge",
      theme: "stranger-things",
      totalWeeks: 4,
      completedWeeks: 3,
      remainingWeeks: 1,
      requiredTotal: 3,
      requiredCompleted: 3,
      prizeEligible: true,
      weeks: [
        week(1, "complete", true),
        week(2, "complete", true),
        week(3, "complete", true),
        week(4, "available", false), // optional, not done
      ],
    };
    render(<PassportView passport={passport} />);
    expect(screen.getByText("Prize eligible")).toBeInTheDocument();
    expect(screen.queryByText("Not yet eligible")).toBeNull();
  });

  it("exposes the indicator as a status region for assistive tech", () => {
    render(<PassportView passport={passportWith(2)} />);
    expect(
      screen.getByRole("status", { name: /prize eligibility: not yet eligible/i }),
    ).toBeInTheDocument();
  });
});

describe("PassportView detail sheet (QR-only check-in)", () => {
  it("opens a detail sheet whose only check-in action is the QR scanner", async () => {
    render(<PassportView passport={passportWith(3)} onScan={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Week 4:/i }));

    const sheet = screen.getByRole("dialog");
    expect(within(sheet).getByText("Week 4 Portal")).toBeInTheDocument();
    // No manual "Check in" button — QR is the only way in.
    expect(
      within(sheet).queryByRole("button", { name: /^check in$/i }),
    ).toBeNull();
    expect(
      within(sheet).getByRole("button", { name: /scan qr to check in/i }),
    ).toBeInTheDocument();
  });

  it("opens the scanner (and closes the sheet) from the detail sheet", async () => {
    render(<PassportView passport={passportWith(3)} onScan={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Week 4:/i }));
    const sheet = screen.getByRole("dialog");
    await userEvent.click(
      within(sheet).getByRole("button", { name: /scan qr to check in/i }),
    );

    // Sheet is gone and the camera scanner (stubbed) is now mounted.
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(
      screen.getByRole("button", { name: /simulate-scan/i }),
    ).toBeInTheDocument();
  });

  it("shows a completed week as already checked in (no check-in action)", async () => {
    render(<PassportView passport={passportWith(3)} onScan={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Week 1:/i }));
    const sheet = screen.getByRole("dialog");
    expect(
      within(sheet).getByRole("button", { name: /checked in/i }),
    ).toBeDisabled();
    expect(
      within(sheet).queryByRole("button", { name: /scan qr to check in/i }),
    ).toBeNull();
  });

  it("renders a task with no date window instead of crashing (US-11 allows it)", async () => {
    const passport = passportWith(3);
    passport.weeks[3] = { ...passport.weeks[3], dateStart: null, dateEnd: null };
    render(<PassportView passport={passport} onScan={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Week 4:/i }));
    const sheet = screen.getByRole("dialog");
    expect(within(sheet).getByText("Dates TBA")).toBeInTheDocument();
  });
});

describe("Passport eligibility gate (US-2 / FR-A3)", () => {
  it("current student sees their passport", async () => {
    sessionState.session = asSession({ isCurrentStudent: true });
    const fetchData = vi.fn().mockResolvedValue(passportWith(3));

    render(<Passport fetchData={fetchData} />);

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

    render(<Passport fetchData={fetchData} />);

    expect(
      screen.getByRole("heading", { name: /not eligible to join/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).toBeNull();
    // The gate runs before the effect, so an ineligible session makes no request.
    await waitFor(() => expect(fetchData).not.toHaveBeenCalled());
  });

  it("signed-out visitor is redirected to sign-in", () => {
    sessionState.session = null;
    render(<Passport fetchData={vi.fn()} />);
    expect(screen.getByText("redirect:/")).toBeInTheDocument();
  });
});

describe("PassportView QR scan check-in (US-8)", () => {
  function resultFrom(passport: PassportData, weekNo: number): CheckInResult {
    return {
      passport,
      weekNo,
      title: `Week ${weekNo} Portal`,
      tip: "Take the stairs today — small wins add up.",
    };
  }

  async function scan() {
    await userEvent.click(
      screen.getByRole("button", { name: /scan qr to check in/i }),
    );
    await userEvent.click(screen.getByRole("button", { name: /simulate-scan/i }));
  }

  it("shows the CTA only when a scan handler is provided", () => {
    const { rerender } = render(<PassportView passport={passportWith(3)} />);
    expect(
      screen.queryByRole("button", { name: /scan qr to check in/i }),
    ).toBeNull();

    rerender(<PassportView passport={passportWith(3)} onScan={vi.fn()} />);
    expect(
      screen.getByRole("button", { name: /scan qr to check in/i }),
    ).toBeInTheDocument();
  });

  it("records a scan and shows the personalized tip on success", async () => {
    const onScan = vi
      .fn()
      .mockResolvedValue(resultFrom(passportWith(4), 4));
    render(<PassportView passport={passportWith(3)} onScan={onScan} />);

    await scan();

    expect(onScan).toHaveBeenCalledWith("scanned-token");
    const sheet = await screen.findByRole("dialog", {
      name: /check-in complete/i,
    });
    expect(within(sheet).getByText(/Week 4 Portal complete!/i)).toBeInTheDocument();
    expect(
      within(sheet).getByText(/take the stairs today/i),
    ).toBeInTheDocument();
  });

  it("shows 'Already completed this week' when the scan is a duplicate (409)", async () => {
    const onScan = vi
      .fn()
      .mockRejectedValue(new ApiError(409, "Already completed this week"));
    render(<PassportView passport={passportWith(3)} onScan={onScan} />);

    await scan();

    const sheet = await screen.findByRole("dialog", { name: /check-in failed/i });
    expect(
      within(sheet).getByRole("alert"),
    ).toHaveTextContent("Already completed this week");
  });

  it("shows the invalid-token message when the code is rejected (400)", async () => {
    const onScan = vi
      .fn()
      .mockRejectedValue(
        new ApiError(400, "This code is no longer valid, ask the attendant"),
      );
    render(<PassportView passport={passportWith(3)} onScan={onScan} />);

    await scan();

    const sheet = await screen.findByRole("dialog", { name: /check-in failed/i });
    expect(within(sheet).getByRole("alert")).toHaveTextContent(
      /this code is no longer valid, ask the attendant/i,
    );
  });
});

describe("Passport container scan wiring (US-8)", () => {
  it("refreshes the countdown after a successful scan", async () => {
    sessionState.session = asSession({ isCurrentStudent: true });
    const fetchData = vi.fn().mockResolvedValue(passportWith(3));
    const scanCheckInFn = vi.fn().mockResolvedValue({
      passport: passportWith(4),
      weekNo: 4,
      title: "Week 4 Portal",
      tip: "Nice work!",
    } satisfies CheckInResult);

    render(
      <Passport fetchData={fetchData} scanCheckInFn={scanCheckInFn} />,
    );

    expect(
      await screen.findByText(/3 of 7 complete, 4 remaining/i),
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: /scan qr to check in/i }),
    );
    await userEvent.click(screen.getByRole("button", { name: /simulate-scan/i }));

    expect(scanCheckInFn).toHaveBeenCalledWith("scanned-token");
    expect(
      await screen.findByText(/4 of 7 complete, 3 remaining/i),
    ).toBeInTheDocument();
  });
});
