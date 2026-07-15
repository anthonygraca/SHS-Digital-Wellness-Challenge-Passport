import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../../../api/http";
import type {
  AttendanceReport,
  ParticipationReport,
  WeekCompletion,
} from "../../../types/report";
import { Reports } from "./Reports";
// vite.config.ts sets `css: true`, so these resolve to the real generated class
// names — the stacked bar's segments carry no role to query them by.
import styles from "./Reports.module.css";

const navigate = vi.fn();

const api = vi.hoisted(() => ({
  getParticipationReport: vi.fn(),
  getAttendanceReport: vi.fn(),
  exportPrizeCsv: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigate,
}));
// Partial mock: the real ApiError must survive, since the component branches on
// `instanceof` to tell "nothing published" apart from a genuine failure.
vi.mock("../../../api/reports", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../api/reports")>()),
  getParticipationReport: api.getParticipationReport,
  getAttendanceReport: api.getAttendanceReport,
  exportPrizeCsv: api.exportPrizeCsv,
}));

// jsdom implements neither, and the export hands its blob to the browser through
// both. Stubbed rather than faked: what matters is the anchor they feed.
const objectUrl = "blob:prize-list";
const createObjectURL = vi.fn();
const revokeObjectURL = vi.fn();
URL.createObjectURL = createObjectURL;
URL.revokeObjectURL = revokeObjectURL;

/** The synthetic anchor the component clicks, captured at click time. */
function captureDownload() {
  const clicked: { href: string; download: string }[] = [];
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    clicked.push({ href: this.href, download: this.download });
  });
  return clicked;
}

// resetAllMocks, not clearAllMocks: clearAllMocks leaves mockResolvedValueOnce
// queues in place, which the beforeEach defaults below would sit behind. The
// vi.mock factory closes over these same fn objects, so the wiring survives.
// restoreAllMocks first, to lift the anchor-click spy captureDownload installs —
// reset alone would leave it stubbed for every later test.
afterEach(() => {
  vi.restoreAllMocks();
  vi.resetAllMocks();
});

beforeEach(() => {
  // Re-armed here rather than at vi.fn(): resetAllMocks above wipes every mock's
  // implementation, this one included, and a createObjectURL returning undefined
  // fails as a wrong href rather than as a missing stub.
  createObjectURL.mockReturnValue(objectUrl);
  // The two cards load together under one Promise.all, so a test about the
  // funnel still needs attendance to resolve. Individual tests override.
  api.getParticipationReport.mockResolvedValue(asReport());
  api.getAttendanceReport.mockResolvedValue(asAttendance());
});

const asWeek = (week_no: number, completed_count: number): WeekCompletion => ({
  task_id: 100 + week_no,
  week_no,
  title: `Week ${week_no}`,
  required: true,
  completed_count,
});

const asReport = (over: Partial<ParticipationReport> = {}): ParticipationReport => ({
  challenge: {
    id: 1,
    name: "Stranger Things Wellness",
    semester: "Fall 2026",
    theme_id: "stranger-things",
  },
  total_enrollments: 40,
  weeks: [asWeek(1, 40), asWeek(2, 30), asWeek(3, 20), asWeek(4, 10)],
  ...over,
});

/** 91 / 9 is the design prototype's own split, so fixture and card agree. */
const asAttendance = (over: Partial<AttendanceReport> = {}): AttendanceReport => ({
  challenge: {
    id: 1,
    name: "Stranger Things Wellness",
    semester: "Fall 2026",
    theme_id: "stranger-things",
  },
  total_checkins: 100,
  methods: [
    { method: "event_qr", count: 91 },
    { method: "staff", count: 0 },
    { method: "manual", count: 9 },
  ],
  ...over,
});

/** The funnel rows, in the order they are rendered. */
const funnelRows = () =>
  within(screen.getByRole("list", { name: /per-week completion funnel/i })).getAllByRole(
    "listitem",
  );

describe("Participation & completion funnel report (US-21 / FR-F1)", () => {
  it("shows total enrollments for the active challenge", async () => {
    api.getParticipationReport.mockResolvedValue(asReport());

    render(<Reports />);

    expect(await screen.findByRole("status")).toHaveTextContent("40");
    expect(screen.getByText("Enrolled")).toBeInTheDocument();
    expect(screen.getByText(/fall 2026 · stranger things wellness/i)).toBeInTheDocument();
  });

  it("shows the count of students completing each week, as a funnel", async () => {
    api.getParticipationReport.mockResolvedValue(asReport());

    render(<Reports />);
    const rows = await screen.findByRole("list", { name: /per-week completion funnel/i });

    // Every week in week order, each with its count and share of the cohort —
    // the drop-off from 40 down to 10 read top to bottom.
    expect(within(rows).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "Week 140 · 100%",
      "Week 230 · 75%",
      "Week 320 · 50%",
      "Week 410 · 25%",
    ]);
  });

  it("sizes each bar to the share of enrolled students who finished", async () => {
    api.getParticipationReport.mockResolvedValue(asReport());

    render(<Reports />);
    await screen.findByRole("list", { name: /per-week completion funnel/i });

    const widths = funnelRows().map(
      (li) => (li.querySelector("span > span") as HTMLElement).style.width,
    );
    expect(widths).toEqual(["100%", "75%", "50%", "25%"]);
  });

  it("refreshing picks up a new check-in for week 4", async () => {
    const before = asReport();
    const after = asReport({
      weeks: [asWeek(1, 40), asWeek(2, 30), asWeek(3, 20), asWeek(4, 11)],
    });
    api.getParticipationReport.mockResolvedValueOnce(before).mockResolvedValue(after);

    render(<Reports />);
    expect(await screen.findByText("10 · 25%")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /refresh/i }));

    expect(await screen.findByText("11 · 28%")).toBeInTheDocument();
    // Only week 4 moved — the other rungs are untouched.
    expect(screen.getByText("40 · 100%")).toBeInTheDocument();
    expect(screen.getByText("30 · 75%")).toBeInTheDocument();
  });

  it("a campus with nothing published is told to publish, not shown an error", async () => {
    api.getParticipationReport.mockRejectedValue(
      new ApiError(404, "There's no active challenge for your campus right now."),
    );

    render(<Reports />);

    expect(await screen.findByText(/no published challenge yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("a challenge nobody has joined reports 0%, not NaN", async () => {
    api.getParticipationReport.mockResolvedValue(
      asReport({ total_enrollments: 0, weeks: [asWeek(1, 0), asWeek(2, 0)] }),
    );

    render(<Reports />);
    await screen.findByRole("list", { name: /per-week completion funnel/i });

    expect(funnelRows().map((li) => li.textContent)).toEqual([
      "Week 10 · 0%",
      "Week 20 · 0%",
    ]);
    expect(screen.queryByText(/NaN/)).toBeNull();
  });

  it("a challenge with no weeks says so instead of drawing an empty funnel", async () => {
    api.getParticipationReport.mockResolvedValue(asReport({ weeks: [] }));

    render(<Reports />);

    expect(await screen.findByText(/no weeks yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: /funnel/i })).toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent("40"); // enrollment still shown
  });

  it("reports a failure when there is nothing on screen yet", async () => {
    api.getParticipationReport.mockRejectedValue(new ApiError(500, "Server exploded"));

    render(<Reports />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Server exploded");
  });

  it("a failed refresh keeps the numbers already on screen", async () => {
    api.getParticipationReport
      .mockResolvedValueOnce(asReport())
      .mockRejectedValue(new ApiError(500, "Server exploded"));

    render(<Reports />);
    expect(await screen.findByText("40 · 100%")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /refresh/i }));

    // Stale numbers beat a blank screen: the admin keeps the last good read.
    expect(screen.getByText("40 · 100%")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("40");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("goes back to the challenge builder", async () => {
    api.getParticipationReport.mockResolvedValue(asReport());

    render(<Reports />);
    await userEvent.click(
      await screen.findByRole("button", { name: /challenge builder/i }),
    );

    expect(navigate).toHaveBeenCalledWith("/admin");
  });
});

/** The capture-method rows, in the order they are rendered. */
const methodRows = () =>
  within(
    screen.getByRole("list", { name: /attendance capture by method/i }),
  ).getAllByRole("listitem");

/** The sized segment of the stacked bar — the auto share made visible. */
const autoSegment = () =>
  document.querySelector(`.${styles.stackAuto}`) as HTMLElement;

describe("Auto-vs-manual attendance report (US-22 / FR-F2)", () => {
  it("breaks attendance into an automatic share and everything else", async () => {
    render(<Reports />);
    await screen.findByRole("list", { name: /attendance capture by method/i });

    // Automatic first — the number the card exists to lead with.
    expect(methodRows().map((li) => li.textContent)).toEqual([
      "Auto (event QR)91%",
      "Manual / staff9%",
    ]);
  });

  it("sizes the stacked bar to the automatic share", async () => {
    render(<Reports />);
    await screen.findByRole("list", { name: /attendance capture by method/i });

    expect(autoSegment().style.width).toBe("91%");
  });

  it("the manual share is the complement, so the bar can never overflow", async () => {
    api.getAttendanceReport.mockResolvedValue(
      asAttendance({
        total_checkins: 200,
        methods: [
          { method: "event_qr", count: 67 },
          { method: "staff", count: 0 },
          { method: "manual", count: 133 },
        ],
      }),
    );

    render(<Reports />);
    await screen.findByRole("list", { name: /attendance capture by method/i });

    // Rounding each side independently gives 34% and 67% — a 101% bar. The
    // complement is what keeps the two rows honest as one whole.
    expect(methodRows().map((li) => li.textContent)).toEqual([
      "Auto (event QR)34%",
      "Manual / staff66%",
    ]);
  });

  it("reports the raw counts the percentages come from", async () => {
    render(<Reports />);

    // The effort figure the story asks for, and the only place the reconciliation
    // between the buckets and the total is visible to a human.
    expect(
      await screen.findByText(/91 of 100 check-ins captured automatically/i),
    ).toBeInTheDocument();
  });

  it("a challenge with no check-ins says so, not 100% manual", async () => {
    api.getAttendanceReport.mockResolvedValue(
      asAttendance({
        total_checkins: 0,
        methods: [
          { method: "event_qr", count: 0 },
          { method: "staff", count: 0 },
          { method: "manual", count: 0 },
        ],
      }),
    );

    render(<Reports />);

    expect(await screen.findByText(/no check-ins recorded yet/i)).toBeInTheDocument();
    // The complement of 0% is 100%, so without the empty branch this card would
    // claim every one of zero check-ins was captured by hand.
    expect(screen.queryByText("100%")).toBeNull();
    expect(screen.queryByRole("list", { name: /attendance capture/i })).toBeNull();
    expect(screen.queryByText(/NaN/)).toBeNull();
  });

  it("a fully manual challenge reads as 0% automatic", async () => {
    api.getAttendanceReport.mockResolvedValue(
      asAttendance({
        total_checkins: 5,
        methods: [
          { method: "event_qr", count: 0 },
          { method: "staff", count: 0 },
          { method: "manual", count: 5 },
        ],
      }),
    );

    render(<Reports />);
    await screen.findByRole("list", { name: /attendance capture by method/i });

    expect(methodRows().map((li) => li.textContent)).toEqual([
      "Auto (event QR)0%",
      "Manual / staff100%",
    ]);
    // A 0% segment must collapse, not show a sliver: unlike the funnel's zero
    // week, there is no empty row to distinguish it from — the manual bar is it.
    expect(autoSegment().style.width).toBe("0%");
  });

  it("refreshing picks up newly captured QR check-ins", async () => {
    api.getAttendanceReport
      .mockResolvedValueOnce(asAttendance())
      .mockResolvedValue(
        asAttendance({
          total_checkins: 110,
          methods: [
            { method: "event_qr", count: 101 },
            { method: "staff", count: 0 },
            { method: "manual", count: 9 },
          ],
        }),
      );

    render(<Reports />);
    expect(await screen.findByText(/91 of 100/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /refresh/i }));

    expect(await screen.findByText(/101 of 110/i)).toBeInTheDocument();
    expect(methodRows()[0]).toHaveTextContent("92%");
  });

  it("a failed refresh keeps both cards on screen", async () => {
    api.getAttendanceReport
      .mockResolvedValueOnce(asAttendance())
      .mockRejectedValue(new ApiError(500, "Server exploded"));

    render(<Reports />);
    expect(await screen.findByText(/91 of 100/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /refresh/i }));

    // One failed fetch takes the whole Promise.all down, so neither card updates
    // — and neither is blanked. The funnel is still here despite the failure
    // being on the attendance side.
    expect(screen.getByText(/91 of 100/i)).toBeInTheDocument();
    expect(screen.getByText("40 · 100%")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("a campus with nothing published shows no attendance card", async () => {
    const notFound = new ApiError(
      404,
      "There's no active challenge for your campus right now.",
    );
    api.getParticipationReport.mockRejectedValue(notFound);
    api.getAttendanceReport.mockRejectedValue(notFound);

    render(<Reports />);

    expect(await screen.findByText(/no published challenge yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/attendance capture/i)).toBeNull();
  });
});

describe("Prize-eligible CSV export (US-26 / FR-F5)", () => {
  const asCsv = (filename = "prize-eligible-Fall-2026-1.csv") => ({
    blob: new Blob(["student_id,sso_subject\n"], { type: "text/csv" }),
    filename,
  });

  const exportButton = () =>
    screen.getByRole("button", { name: /export prize list \(csv\)/i });

  it("downloads the prize list under the name the server gave it", async () => {
    api.exportPrizeCsv.mockResolvedValue(asCsv());
    const clicked = captureDownload();

    render(<Reports />);
    await userEvent.click(await screen.findByRole("button", { name: /export prize/i }));

    // The filename is the server's, not rebuilt here: two admins exporting the
    // same challenge should end up with the same file on disk.
    expect(clicked).toEqual([
      { href: objectUrl, download: "prize-eligible-Fall-2026-1.csv" },
    ]);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("releases the object URL once the download is handed over", async () => {
    api.exportPrizeCsv.mockResolvedValue(asCsv());
    captureDownload();

    render(<Reports />);
    await userEvent.click(await screen.findByRole("button", { name: /export prize/i }));

    // Un-revoked object URLs pin their blob in memory for the life of the tab,
    // and an admin can export repeatedly while running a drawing.
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith(objectUrl);
  });

  it("never renders the exported rows on the dashboard", async () => {
    api.exportPrizeCsv.mockResolvedValue(asCsv());
    captureDownload();

    render(<Reports />);
    await userEvent.click(await screen.findByRole("button", { name: /export prize/i }));

    // The file is per-student; the screen stays aggregate (FR-F6). The CSV goes
    // to the downloads folder and nowhere else.
    expect(screen.queryByText(/sso_subject/i)).toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent("40");
  });

  it("says so when the export fails", async () => {
    api.exportPrizeCsv.mockRejectedValue(new ApiError(500, "Server exploded"));
    const clicked = captureDownload();

    render(<Reports />);
    await userEvent.click(await screen.findByRole("button", { name: /export prize/i }));

    // Unlike a failed refresh, a failed export has no stale copy to fall back on
    // — silence would look like a download that simply never arrived.
    expect(await screen.findByRole("alert")).toHaveTextContent("Server exploded");
    expect(clicked).toEqual([]);
  });

  it("re-enables the button after a failed export so it can be retried", async () => {
    api.exportPrizeCsv
      .mockRejectedValueOnce(new ApiError(500, "Server exploded"))
      .mockResolvedValue(asCsv());
    const clicked = captureDownload();

    render(<Reports />);
    await userEvent.click(await screen.findByRole("button", { name: /export prize/i }));
    await screen.findByRole("alert");

    expect(exportButton()).toBeEnabled();
    await userEvent.click(exportButton());

    expect(clicked).toHaveLength(1);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("offers no export when the campus has nothing published", async () => {
    api.getParticipationReport.mockRejectedValue(
      new ApiError(404, "There's no active challenge for your campus right now."),
    );

    render(<Reports />);
    await screen.findByText(/no published challenge yet/i);

    // No challenge means no drawing — a button here could only 404.
    expect(screen.queryByRole("button", { name: /export prize/i })).toBeNull();
  });
});
