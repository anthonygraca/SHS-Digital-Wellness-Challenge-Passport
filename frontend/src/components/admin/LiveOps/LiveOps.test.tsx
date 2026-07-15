import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Challenge, CheckIn, Task } from "../../../types/challenge";
import { LiveOps } from "./LiveOps";

const route = vi.hoisted(() => ({
  params: { challengeId: "1", taskId: "7" } as Record<string, string>,
}));
const navigate = vi.fn();

const api = vi.hoisted(() => ({
  getChallenge: vi.fn(),
  listCheckIns: vi.fn(),
  listCheckInAudits: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useParams: () => route.params,
  useNavigate: () => navigate,
  Navigate: ({ to }: { to: string }) => <div>redirect:{to}</div>,
}));
vi.mock("../../../api/challenges", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../api/challenges")>()),
  getChallenge: api.getChallenge,
  listCheckIns: api.listCheckIns,
  listCheckInAudits: api.listCheckInAudits,
}));

afterEach(() => {
  route.params = { challengeId: "1", taskId: "7" };
  vi.clearAllMocks();
  vi.useRealTimers();
});

const asTask = (over: Partial<Task> = {}): Task => ({
  id: 7,
  challenge_id: 1,
  position: 3,
  title: "Vision Check",
  caption: "",
  activity_type: "health_screening",
  location: "SHS Clinic",
  date_window_start: null,
  date_window_end: null,
  prize: "",
  required: true,
  assessment_items: [],
  qr_token: "signed.event.token",
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-01T00:00:00Z",
  ...over,
});

const asChallenge = (over: Partial<Challenge> = {}): Challenge => ({
  id: 1,
  campus_id: "csub",
  name: "Week 3 - Vision Check",
  semester: "Fall 2026",
  start_date: "2026-09-01",
  end_date: "2026-12-15",
  theme_id: "",
  status: "published",
  tasks: [asTask()],
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-01T00:00:00Z",
  ...over,
});

const asCheckIn = (id: number, over: Partial<CheckIn> = {}): CheckIn => ({
  id,
  student_id: id,
  student_subject: `student${id}@csub.edu`,
  task_id: 7,
  ts: `2026-07-14T10:0${id % 10}:00Z`,
  method: "event_qr",
  verified_by: null,
  ...over,
});

describe("Live event dashboard (US-28 / FR-D4)", () => {
  it("generates the event QR when live ops opens", async () => {
    api.getChallenge.mockResolvedValue(asChallenge());
    api.listCheckIns.mockResolvedValue([]);

    render(<LiveOps />);

    const qr = await screen.findByLabelText("Event check-in QR for Vision Check");
    expect(qr.querySelector("svg")).not.toBeNull();
    // The event context an attendant needs to confirm they opened the right task.
    expect(screen.getByText(/week 3 · vision check · shs clinic/i)).toBeInTheDocument();
  });

  it("live count increases as students scan and check in", async () => {
    vi.useFakeTimers();
    api.getChallenge.mockResolvedValue(asChallenge());
    api.listCheckIns
      .mockResolvedValueOnce([asCheckIn(1), asCheckIn(2)])
      .mockResolvedValue([asCheckIn(1), asCheckIn(2), asCheckIn(3)]);

    render(<LiveOps />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(screen.getByRole("status")).toHaveTextContent("2");

    // Two students scan; the next poll tick picks them up.
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });

    expect(screen.getByRole("status")).toHaveTextContent("3");
    expect(
      screen.getAllByRole("listitem", { name: undefined }).length,
    ).toBeGreaterThanOrEqual(3);
  });

  it("keeps the feed anonymous — no SSO subjects on the projected screen", async () => {
    api.getChallenge.mockResolvedValue(asChallenge());
    api.listCheckIns.mockResolvedValue([asCheckIn(4)]);

    render(<LiveOps />);

    expect(await screen.findByText("Student · #4")).toBeInTheDocument();
    expect(screen.queryByText(/student4@csub\.edu/)).toBeNull();
  });

  it("Manual override opens the FR-D6 completion override panel", async () => {
    api.getChallenge.mockResolvedValue(asChallenge());
    api.listCheckIns.mockResolvedValue([]);
    api.listCheckInAudits.mockResolvedValue([]);

    render(<LiveOps />);
    await userEvent.click(
      await screen.findByRole("button", { name: /manual override/i }),
    );

    expect(
      await screen.findByRole("dialog", { name: /check-ins for vision check/i }),
    ).toBeInTheDocument();
  });

  it("a task missing from the challenge is reported, not rendered blank", async () => {
    route.params = { challengeId: "1", taskId: "999" };
    api.getChallenge.mockResolvedValue(asChallenge());
    api.listCheckIns.mockRejectedValue(new Error("404"));

    render(<LiveOps />);

    expect(
      await screen.findByText(/task not found in this challenge/i),
    ).toBeInTheDocument();
  });

  it("bounces malformed URLs back to the builder", () => {
    route.params = { challengeId: "abc", taskId: "7" };

    render(<LiveOps />);

    expect(screen.getByText("redirect:/admin")).toBeInTheDocument();
    expect(api.getChallenge).not.toHaveBeenCalled();
  });
});
