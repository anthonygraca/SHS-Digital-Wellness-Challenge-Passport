import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Passport, PassportView } from "./Passport";
import { ThemeProvider } from "../../theme/ThemeProvider";
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
// Partial mock: only the engagement write path is stubbed. The rest of the module
// must stay real — the container's fetchPassport/checkIn/scanCheckIn are what these
// tests drive through props. Without this stub, opening a week would fire a real
// fetch at jsdom; it would be swallowed and harmless, but it would also be silent,
// and US-23's instrumentation is worth asserting rather than assuming.
const passportApi = vi.hoisted(() => ({ recordContentView: vi.fn() }));
vi.mock("../../passport/passport", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../passport/passport")>()),
  recordContentView: passportApi.recordContentView,
}));

// The sheet mounts KnowledgeCheck with its real defaults, so stub the fetch it makes.
// Defaults to no questions — most weeks have none, and that is the shape every other
// test in this file assumes. KnowledgeCheck.test.tsx owns the quiz behaviour itself.
const assessments = vi.hoisted(() => ({
  fetchWeekItems: vi.fn(),
  submitMcq: vi.fn(),
  submitReflection: vi.fn(),
}));
vi.mock("../../passport/assessments", () => assessments);

beforeEach(() => {
  assessments.fetchWeekItems.mockResolvedValue([]);
  passportApi.recordContentView.mockResolvedValue(undefined);
});

afterEach(() => {
  sessionState.session = null;
  sessionState.loading = false;
  vi.clearAllMocks();
});

/**
 * jsdom reports navigator.onLine === true and offers no way to set it, so tests
 * redefine the property. It is global mutable state — the US-6 blocks below restore
 * it in their own afterEach so it cannot leak into the rest of the suite.
 *
 * Sets the property only, deliberately: useOnlineStatus reads it when it mounts, and
 * every test here sets the connection before rendering. Dispatching the online /
 * offline event too would push a state update into whatever is still mounted — and
 * a describe-level afterEach runs before Testing Library's cleanup, so the restore
 * would land on a live component outside act(). The event path is covered where it
 * belongs, in useOnlineStatus.test.tsx.
 */
function setOnline(value: boolean) {
  Object.defineProperty(navigator, "onLine", { value, configurable: true });
}

/**
 * How a fetch fails with no connection: it REJECTS. It does not resolve with a
 * !res.ok response, which is why fetchPassport's null-on-failure guard is no help
 * offline and the caller has to catch.
 */
const offline = () => new TypeError("Failed to fetch");

const asSession = (over: Partial<Session>): Session => ({
  subject: "abc@csub.edu",
  affiliation: "student",
  isCurrentStudent: true,
  student_id: 1,
  ...over,
});

function week(weekNo: number, status: WeekStatus, required = true) {
  return {
    weekNo,
    taskId: weekNo, // Map weekNo to taskId for tests
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
    themeConfig: null,
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
      themeConfig: null,
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

describe("PassportView knowledge check (US-18 / FR-E4)", () => {
  const mcq = {
    id: 7,
    weekNo: 4,
    prompt: "How often should a healthy adult have an eye exam?",
    outcomeTag: "vision-care",
    options: ["Every 1-2 years", "Once, when I turn 18"],
    yourResponse: null,
  };

  it("shows the tapped week's knowledge check inside the sheet", async () => {
    assessments.fetchWeekItems.mockResolvedValue([mcq]);
    render(<PassportView passport={passportWith(3)} onCheckIn={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Week 4:/i }));

    const sheet = screen.getByRole("dialog");
    expect(await within(sheet).findByText(mcq.prompt)).toBeInTheDocument();
    // The sheet must ask for the week it opened, not the first or the last.
    expect(assessments.fetchWeekItems).toHaveBeenCalledWith(4);
  });

  it("still offers check-in for a week with no knowledge check", async () => {
    render(<PassportView passport={passportWith(3)} onCheckIn={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Week 4:/i }));

    // The quiz does not gate the core loop: no questions, no missing button.
    const sheet = screen.getByRole("dialog");
    expect(
      within(sheet).getByRole("button", { name: /^check in$/i }),
    ).toBeInTheDocument();
    expect(within(sheet).queryByText(/knowledge check/i)).not.toBeInTheDocument();
  });
});

describe("Passport theming (US-13 / FR-B4)", () => {
  const themeConfig = {
    id: "stranger-things",
    palette: { primary: "#ff4438" },
    logoUrl: "https://cdn.example.edu/st-logo.png",
    heroUrl: null,
    appTitle: "Upside Down Passport",
    tagline: "Step through the first portal.",
    copyTone: "dark, retro-80s",
  };

  afterEach(() => {
    document.documentElement.style.cssText = "";
    delete document.documentElement.dataset.theme;
  });

  it("renders the theme's logo and copy", () => {
    render(
      <ThemeProvider>
        <PassportView passport={{ ...passportWith(3), themeConfig }} />
      </ThemeProvider>,
    );

    expect(screen.getByText("Upside Down Passport")).toBeInTheDocument();
    expect(screen.getByText("Step through the first portal.")).toBeInTheDocument();
    expect(document.querySelector("img")).toHaveAttribute("src", themeConfig.logoUrl);
  });

  it("falls back to the default copy and shows no logo when unthemed", () => {
    render(
      <ThemeProvider>
        <PassportView passport={passportWith(3)} />
      </ThemeProvider>,
    );

    expect(screen.getByText("Wellness Passport")).toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
  });

  it("applies the fetched theme's palette to the document", async () => {
    // The whole point of US-13: the skin arrives as data on the passport.
    sessionState.session = asSession({ isCurrentStudent: true });
    const fetchData = vi.fn().mockResolvedValue({
      ...passportWith(3),
      themeConfig,
    });

    render(
      <ThemeProvider>
        <Passport fetchData={fetchData} checkInFn={vi.fn()} />
      </ThemeProvider>,
    );

    await screen.findByText(/3 of 7 complete, 4 remaining/i);
    await waitFor(() => {
      expect(
        document.documentElement.style.getPropertyValue("--wp-primary"),
      ).toBe("#ff4438");
    });
    expect(document.documentElement.dataset.theme).toBe("stranger-things");
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

/**
 * Binds Scenarios 2 and 3 of docs/features.md § US-6 (FR-C4).
 *
 * Scenario 1 (installability) has no DOM to assert — its manifest preconditions are
 * pinned in src/pwa/manifest.test.ts, and the install itself is checked by hand
 * against a preview build, since jsdom runs no service worker.
 *
 * "I see my last-synced weeks and progress from cache" is bound as: a load whose
 * fetch rejects still renders the countdown and tiles from the previous load. The
 * rejection — not navigator.onLine — is what stands in for "no network connection",
 * because that is precisely what the browser does offline: fetch throws rather than
 * returning a failed response.
 */
describe("Passport offline viewing (US-6 / FR-C4)", () => {
  afterEach(() => {
    localStorage.clear();
    setOnline(true);
  });

  /** Seeds the snapshot the way the app does: one successful online load. */
  async function loadOnceOnline() {
    const { unmount } = render(
      <Passport fetchData={vi.fn().mockResolvedValue(passportWith(3))} checkInFn={vi.fn()} />,
    );
    await screen.findByText(/3 of 7 complete, 4 remaining/i);
    unmount();
  }

  it("Scenario: Offline shows last-synced progress — weeks and progress come from cache", async () => {
    sessionState.session = asSession({ isCurrentStudent: true });
    await loadOnceOnline();

    setOnline(false);
    render(<Passport fetchData={vi.fn().mockRejectedValue(offline())} checkInFn={vi.fn()} />);

    expect(
      await screen.findByText(/3 of 7 complete, 4 remaining/i),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(7);
    expect(screen.getAllByText("Complete")).toHaveLength(3);
  });

  it("Scenario: Offline shows last-synced progress — and an offline indicator", async () => {
    sessionState.session = asSession({ isCurrentStudent: true });
    await loadOnceOnline();

    setOnline(false);
    render(<Passport fetchData={vi.fn().mockRejectedValue(offline())} checkInFn={vi.fn()} />);

    await screen.findByText(/3 of 7 complete, 4 remaining/i);
    expect(screen.getByRole("status", { name: /offline/i })).toBeInTheDocument();
  });

  it("shows no indicator when the passport loaded live", async () => {
    sessionState.session = asSession({ isCurrentStudent: true });
    render(
      <Passport fetchData={vi.fn().mockResolvedValue(passportWith(3))} checkInFn={vi.fn()} />,
    );

    await screen.findByText(/3 of 7 complete, 4 remaining/i);
    expect(screen.queryByRole("status", { name: /offline/i })).toBeNull();
  });

  it("says we're offline, not that there's no challenge, when nothing was ever synced", async () => {
    // The pre-existing empty state claims the student has no active challenge. With
    // no connection we never reached the server to ask, so that would be a guess —
    // and for anyone opening the installed app on a bad signal, a wrong one.
    sessionState.session = asSession({ isCurrentStudent: true });
    setOnline(false);

    render(<Passport fetchData={vi.fn().mockRejectedValue(offline())} checkInFn={vi.fn()} />);

    expect(await screen.findByText(/you're offline and haven't synced/i)).toBeInTheDocument();
    expect(screen.queryByText(/no active challenge yet/i)).toBeNull();
  });

  it("does not hang on the spinner when offline with nothing cached", async () => {
    sessionState.session = asSession({ isCurrentStudent: true });
    setOnline(false);

    render(<Passport fetchData={vi.fn().mockRejectedValue(offline())} checkInFn={vi.fn()} />);

    await waitFor(() =>
      expect(screen.queryByText(/loading your passport/i)).toBeNull(),
    );
  });
});

describe("PassportView offline action gating (US-6 / FR-C4)", () => {
  it("Scenario: scanning offline — I am told the action requires a connection", async () => {
    const onScan = vi.fn();
    render(<PassportView passport={passportWith(3)} onScan={onScan} online={false} />);

    await userEvent.click(
      screen.getByRole("button", { name: /scan qr to check in/i }),
    );

    const sheet = await screen.findByRole("dialog", { name: /connection required/i });
    expect(within(sheet).getByRole("alert")).toHaveTextContent(
      /scanning a qr code needs a connection/i,
    );
  });

  it("Scenario: scanning offline — no invalid check-in is queued as complete", async () => {
    const onScan = vi.fn();
    render(<PassportView passport={passportWith(3)} onScan={onScan} online={false} />);

    await userEvent.click(
      screen.getByRole("button", { name: /scan qr to check in/i }),
    );

    // The scanner never mounts, so its stub's simulate-scan button is absent — the
    // camera never starts and the token never reaches a handler. Nothing is queued.
    expect(screen.queryByRole("button", { name: /simulate-scan/i })).toBeNull();
    expect(onScan).not.toHaveBeenCalled();
  });

  it("refuses a manual check-in offline, and records nothing", async () => {
    const onCheckIn = vi.fn();
    render(<PassportView passport={passportWith(3)} onCheckIn={onCheckIn} online={false} />);

    await userEvent.click(screen.getByRole("button", { name: /Week 4:/i }));
    await userEvent.click(
      within(screen.getByRole("dialog", { name: /week 4/i })).getByRole("button", {
        name: /^check in$/i,
      }),
    );

    const notice = await screen.findByRole("dialog", { name: /connection required/i });
    expect(within(notice).getByRole("alert")).toHaveTextContent(
      /checking in needs a connection/i,
    );
    expect(onCheckIn).not.toHaveBeenCalled();
    // The week keeps the status the server last gave it — nothing optimistic.
    expect(screen.getAllByText("Complete")).toHaveLength(3);
  });

  it("leaves both actions working when online", async () => {
    const onScan = vi.fn();
    render(<PassportView passport={passportWith(3)} onScan={onScan} />);

    await userEvent.click(
      screen.getByRole("button", { name: /scan qr to check in/i }),
    );

    expect(screen.getByRole("button", { name: /simulate-scan/i })).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: /connection required/i })).toBeNull();
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
      <Passport
        fetchData={fetchData}
        checkInFn={vi.fn()}
        scanCheckInFn={scanCheckInFn}
      />,
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

describe("PassportView content-view instrumentation (US-23 / FR-F3)", () => {
  it("records a view when a week's detail sheet is opened", async () => {
    render(<PassportView passport={passportWith(3)} onCheckIn={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Week 4:/i }));

    // The engagement report counts nothing unless this fires — it is the only
    // thing that puts a week_detail row in the table.
    expect(passportApi.recordContentView).toHaveBeenCalledTimes(1);
    expect(passportApi.recordContentView).toHaveBeenCalledWith(4, "week_detail");
  });

  it("records a second view when the same week is opened again", async () => {
    render(<PassportView passport={passportWith(3)} onCheckIn={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Week 4:/i }));
    await userEvent.keyboard("{Escape}");
    await userEvent.click(screen.getByRole("button", { name: /Week 4:/i }));

    // Views, not viewers: re-reading a week is engagement, not a duplicate. The
    // API has no unique constraint for exactly this reason.
    expect(passportApi.recordContentView).toHaveBeenCalledTimes(2);
  });

  it("records nothing when no week is opened", async () => {
    render(<PassportView passport={passportWith(3)} onCheckIn={vi.fn()} />);

    // Guards against instrumenting a render rather than a read — an effect on the
    // selected week would fire here, and twice per open under StrictMode.
    expect(passportApi.recordContentView).not.toHaveBeenCalled();
  });

  it("opens the sheet even when recording the view fails", async () => {
    passportApi.recordContentView.mockRejectedValue(new Error("offline"));
    render(<PassportView passport={passportWith(3)} onCheckIn={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Week 4:/i }));

    // Telemetry does not get to break a student's passport. A lost view costs the
    // admin one count; a thrown one would cost the student their week.
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
