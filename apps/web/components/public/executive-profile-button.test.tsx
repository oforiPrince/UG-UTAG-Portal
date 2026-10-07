import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

import { ExecutiveProfileButton } from "@/components/public/executive-profile-button";
import type { PublicExecutiveProfile } from "@/lib/leadership";

const profile: PublicExecutiveProfile = {
  id: "leader-1",
  full_name: "Prof Kofi Sarpong Adu-Manu",
  title: "Prof.",
  position: "Vice-President",
  portfolio: null,
  summary: null,
  biography_html: "<p>Serving members across campus.</p>",
  social_links: {},
  appointed_on: "2025-10-17",
  ended_on: null,
  term_number: 1,
  is_acting: false,
  is_active: true,
  academic_rank: "Associate Professor",
  profile_media_id: null,
  email: "ksadu-manu@ug.edu.gh",
  phone_number: null,
  school_name: "Sch. of Physical & Math. Sc.",
  college_name: null,
  department_name: "Dept. of Computer Science",
};

beforeAll(() => {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value() {
      this.setAttribute("open", "");
    },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value() {
      this.removeAttribute("open");
      this.dispatchEvent(new Event("close"));
    },
  });
});

afterEach(cleanup);

describe("executive profile modal contact", () => {
  it("shows the public email as visible mailto text", () => {
    render(<ExecutiveProfileButton profile={profile} />);
    fireEvent.click(screen.getByRole("button", { name: "View full profile" }));

    const email = screen.getByRole("link", { name: "ksadu-manu@ug.edu.gh" });
    expect(email.getAttribute("href")).toBe("mailto:ksadu-manu@ug.edu.gh");
    expect(email.textContent).toContain("ksadu-manu@ug.edu.gh");
  });

  it("hides the envelope when the public API omits email", () => {
    render(<ExecutiveProfileButton profile={{ ...profile, email: null }} />);
    fireEvent.click(screen.getByRole("button", { name: "View full profile" }));

    expect(document.querySelector("a[href^='mailto:']")).toBeNull();
  });

  it("hides the envelope when the executive has opted out of sharing email", () => {
    render(
      <ExecutiveProfileButton
        profile={{
          ...profile,
          email: "ksadu-manu@ug.edu.gh",
          show_email: false,
        }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "View full profile" }));

    expect(document.querySelector("a[href^='mailto:']")).toBeNull();
    expect(screen.queryByText("ksadu-manu@ug.edu.gh")).toBeNull();
  });
});
