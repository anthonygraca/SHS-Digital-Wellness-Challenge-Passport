import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PassportView } from "./Passport";
import type { Passport, WeekStatus } from "../../types/passport";

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
function passportWith(completed: number): Passport {
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
});
