import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";

import {
  PublicGalleryViewer,
  type PublicGalleryImage,
} from "./public-gallery-viewer";

const images: PublicGalleryImage[] = [
  {
    id: "image-1",
    url: "/image-1.jpg",
    alt_text: "Opening address",
    caption: "The opening address",
    credit: "UTAG Media",
    allow_download: true,
    download_url: "/download/image-1",
    original_filename: "opening-address.jpg",
  },
  {
    id: "image-2",
    url: "/image-2.jpg",
    alt_text: "Members at lunch",
    caption: null,
    credit: null,
    allow_download: false,
    download_url: null,
    original_filename: null,
  },
  {
    id: "image-3",
    url: "/image-3.jpg",
    alt_text: "Closing group photograph",
    caption: null,
    credit: null,
    allow_download: true,
    download_url: "/download/image-3",
    original_filename: "group-photo.jpg",
  },
];

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

describe("PublicGalleryViewer", () => {
  it("opens images in a navigable, keyboard-accessible lightbox", () => {
    render(<PublicGalleryViewer galleryTitle="Member forum" images={images} />);

    fireEvent.click(screen.getByRole("button", { name: "Open image 1 of 3" }));

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Image 1 of 3")).toBeTruthy();
    expect(
      within(dialog).getByRole("link", { name: "Download image 1" }),
    ).toBeTruthy();

    fireEvent.keyDown(dialog, { key: "ArrowRight" });

    expect(within(dialog).getByText("Image 2 of 3")).toBeTruthy();
    expect(
      within(dialog).queryByRole("link", { name: "Download image 2" }),
    ).toBeNull();

    fireEvent.keyDown(dialog, { key: "End" });
    expect(within(dialog).getByText("Image 3 of 3")).toBeTruthy();

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
