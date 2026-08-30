import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PublicFooter } from "@/components/public/public-footer";

describe("PublicFooter", () => {
  afterEach(cleanup);

  it("links to the University of Ghana research website", () => {
    render(
      <PublicFooter
        contact={{
          email: "utagoffice@ug.edu.gh",
          phone: "+233 (0) 24 427 7275",
          address: "University of Ghana, Legon, Accra",
          office_hours: "Monday–Friday, 9:00 AM–5:00 PM",
        }}
        features={{
          "association-pulse": true,
          "public-resources": true,
          "public-gallery": true,
        }}
        settings={{
          copyright_name: "University of Ghana Branch of UTAG",
          membership_note: "Representing teaching and research staff.",
        }}
      />,
    );

    expect(
      screen.getByRole("link", { name: "UG Research" }).getAttribute("href"),
    ).toBe("https://ugresearch.ug.edu.gh/");
  });
});
