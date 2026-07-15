import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../../../api/http";
import type { ParticipationReport, WeekCompletion } from "../../../types/report";
import { Reports } from "./Reports";

const navigate = vi.fn();

const api = vi.hoisted(() => ({
  getParticipationReport: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigate,
}));
// Partial mock: the real ApiError must survive, since the component branches on
// `instanceof` to tell "nothing published" apart from a genuine failure.
vi.mock("../../../api/reports", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../api/reports")>()),
  getParticipationReport: api.getParticipationReport,
}));

afterEach(() => {
  vi.clearAllMocks();
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
