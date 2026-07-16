import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { CrisisResources as CrisisResourcesData } from "../../types/guide";
import CrisisResources from "./CrisisResources";

afterEach(() => {
  vi.clearAllMocks();
});

const RESOURCES: CrisisResourcesData = {
  headline: "You're not alone",
  resources: [
    {
      role: "lifeline",
      name: "988 Suicide & Crisis Lifeline",
      phone: "988",
      detail: "Call or text, 24/7. Free and confidential.",
    },
    {
      role: "campus_counseling",
      name: "CSUB Counseling",
      phone: "(661) 654-3366",
      detail: null,
    },
    {
      role: "shs_front_desk",
      name: "SHS front desk",
      phone: "(661) 654-2394",
      detail: null,
    },
  ],
};

const ok = () => vi.fn().mockResolvedValue(RESOURCES);
const failing = () => vi.fn().mockRejectedValue(new Error("offline"));

describe("CrisisResources", () => {
  it("shows a trigger without opening the dialog", () => {
    render(<CrisisResources fetchResources={ok()} />);

    expect(screen.getByRole("button", { name: /get help now/i })).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("does not fetch until the student opens it", () => {
    // Mounting the passport is not a deliberate act; opening this card is. A request on
    // every page load tells anything watching traffic that this student looked.
    const fetchResources = ok();
    render(<CrisisResources fetchResources={fetchResources} />);

    expect(fetchResources).not.toHaveBeenCalled();
  });

  it("lists every resource as a tel: link, lifeline first", async () => {
    const user = userEvent.setup();
    render(<CrisisResources fetchResources={ok()} />);

    await user.click(screen.getByRole("button", { name: /get help now/i }));

    const links = await screen.findAllByRole("link");
    expect(links.map((l) => l.getAttribute("href"))).toEqual([
      "tel:988",
      "tel:6616543366",
      "tel:6616542394",
    ]);

    // Server order, rendered as given. The lifeline is the number that is right for
    // every campus and staffed around the clock, so it must not sort anywhere else.
    expect(links[0].textContent).toContain("988 Suicide & Crisis Lifeline");
  });

  it("strips formatting from the dial string but shows it to the reader", async () => {
    const user = userEvent.setup();
    render(<CrisisResources fetchResources={ok()} />);

    await user.click(screen.getByRole("button", { name: /get help now/i }));
    const counseling = await screen.findByRole("link", {
      name: /CSUB Counseling/i,
    });

    // A dialler cannot take "(661) 654-3366"; a person reads it more easily than
    // "6616543366". The href and the label are allowed to disagree, and here they must.
    expect(counseling.getAttribute("href")).toBe("tel:6616543366");
    expect(counseling.textContent).toContain("(661) 654-3366");
  });

  it("still shows 988 when the API is unreachable", async () => {
    // The point of the fallback: a card that opens empty because a fetch failed is worse
    // than no card — the student pressed the button that promised help and got nothing.
    const user = userEvent.setup();
    render(<CrisisResources fetchResources={failing()} />);

    await user.click(screen.getByRole("button", { name: /get help now/i }));

    const link = await screen.findByRole("link");
    expect(link.getAttribute("href")).toBe("tel:988");
  });

  it("does not invent campus numbers when the API is unreachable", async () => {
    // The campus numbers are per-campus deploy config and this bundle is built once for
    // every campus. A guessed number in a crisis card is worse than a missing one.
    const user = userEvent.setup();
    render(<CrisisResources fetchResources={failing()} />);

    await user.click(screen.getByRole("button", { name: /get help now/i }));
    await screen.findByRole("link");

    expect(screen.queryByText(/661/)).toBeNull();
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });

  it("carries the educational-only disclaimer the mock draws beside the card", async () => {
    const user = userEvent.setup();
    render(<CrisisResources fetchResources={ok()} />);

    await user.click(screen.getByRole("button", { name: /get help now/i }));

    expect(await screen.findByText(/not medical advice/i)).toBeTruthy();
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    render(<CrisisResources fetchResources={ok()} />);

    await user.click(screen.getByRole("button", { name: /get help now/i }));
    expect(await screen.findByRole("dialog")).toBeTruthy();

    await user.keyboard("{Escape}");

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("closes on the close button", async () => {
    const user = userEvent.setup();
    render(<CrisisResources fetchResources={ok()} />);

    await user.click(screen.getByRole("button", { name: /get help now/i }));
    await user.click(await screen.findByRole("button", { name: /close/i }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("moves focus into the dialog when it opens", async () => {
    const user = userEvent.setup();
    render(<CrisisResources fetchResources={ok()} />);

    await user.click(screen.getByRole("button", { name: /get help now/i }));

    const close = await screen.findByRole("button", { name: /close/i });
    await waitFor(() => expect(document.activeElement).toBe(close));
  });

  it("fetches once across repeated opens", async () => {
    const fetchResources = ok();
    const user = userEvent.setup();
    render(<CrisisResources fetchResources={fetchResources} />);

    await user.click(screen.getByRole("button", { name: /get help now/i }));
    await screen.findAllByRole("link");
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: /get help now/i }));
    await screen.findAllByRole("link");

    expect(fetchResources).toHaveBeenCalledTimes(1);
  });
});
