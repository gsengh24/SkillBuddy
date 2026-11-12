import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PdfReadError, type PdfText } from "@/lib/onboarding/pdf-text";

import { ImportShortcut } from "./import-shortcut";

// Synthetic resume text, as PDF.js would return it.
const TEXT = `Riya Example
riya@example.com · +91 90000 00000
Built a campus events app in React Native and Firebase. Figma for screens.
Hackathons most weekends.`;

const loadNames = () => Promise.resolve(["Firebase"]);
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function pdf(name = "resume.pdf", bytes = 184 * 1024): File {
  return new File([new Uint8Array(bytes)], name, { type: "application/pdf" });
}

describe("resume import (screen 6)", () => {
  it("reads the file on the device, shows the steps, then the suggestions", async () => {
    let finish: (value: PdfText) => void = () => {};
    const readPdf = vi.fn((_: File, onPage: (done: number, total: number) => void) => {
      onPage(0, 1);
      return new Promise<PdfText>((resolve) => {
        finish = resolve;
      });
    });
    const onUse = vi.fn();
    render(
      <ImportShortcut
        mode="resume"
        onUse={onUse}
        onCancel={vi.fn()}
        loadNames={loadNames}
        readPdf={readPdf}
      />,
    );
    expect(
      screen.getByText("Up to 2 MB. Read in your browser, never uploaded or stored."),
    ).toBeVisible();
    await userEvent.upload(screen.getByLabelText("Choose a resume PDF"), pdf());

    expect(screen.getByRole("heading", { level: 1, name: /Reading your resume/ })).toBeVisible();
    expect(screen.getByText("resume.pdf")).toBeVisible();
    expect(screen.getByText("1 page · 184 KB")).toBeVisible();
    expect(screen.getByRole("progressbar", { name: "Reading your resume" })).toBeVisible();
    expect(
      screen.getByText(
        "We remove phone numbers, emails and addresses before anything else happens.",
      ),
    ).toBeVisible();

    finish({ text: TEXT, pages: 1 });
    expect(await screen.findByRole("heading", { level: 1, name: /We found these/ })).toBeVisible();
    const skills = screen.getByRole("group", { name: "Skills you offer" });
    expect(
      within(skills)
        .getAllByRole("button")
        .map((chip) => chip.textContent),
    ).toEqual(["React", "Firebase", "Figma"]);
    expect(screen.getByRole("status")).toHaveTextContent("4 kept");
    await userEvent.click(within(skills).getByRole("button", { name: "Figma" }));
    expect(screen.getByRole("status")).toHaveTextContent("3 kept");
    await userEvent.click(screen.getByRole("button", { name: /Use these/ }));
    expect(onUse).toHaveBeenCalledWith({
      skills: ["React", "Firebase"],
      interests: ["Hackathons"],
    });
    // Nothing was fetched or sent: the name list came from loadNames, the text stayed here.
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("explains a file it can't use and stays on the pick screen", async () => {
    const readPdf = vi.fn(() =>
      Promise.reject(new PdfReadError("too_big", "That file is over 2 MB. Try a smaller PDF.")),
    );
    render(
      <ImportShortcut
        mode="resume"
        onUse={vi.fn()}
        onCancel={vi.fn()}
        loadNames={loadNames}
        readPdf={readPdf}
      />,
    );
    await userEvent.upload(screen.getByLabelText("Choose a resume PDF"), pdf());
    expect(await screen.findByText("That file is over 2 MB. Try a smaller PDF.")).toBeVisible();
    expect(screen.getByRole("heading", { level: 1, name: /Import your resume/ })).toBeVisible();
  });

  it("cancels while reading and ignores the late result", async () => {
    let finish: (value: PdfText) => void = () => {};
    const readPdf = vi.fn(
      () =>
        new Promise<PdfText>((resolve) => {
          finish = resolve;
        }),
    );
    render(
      <ImportShortcut
        mode="resume"
        onUse={vi.fn()}
        onCancel={vi.fn()}
        loadNames={loadNames}
        readPdf={readPdf}
      />,
    );
    await userEvent.upload(screen.getByLabelText("Choose a resume PDF"), pdf());
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    finish({ text: TEXT, pages: 1 });
    await Promise.resolve();
    expect(screen.getByRole("heading", { level: 1, name: /Import your resume/ })).toBeVisible();
    expect(screen.queryByRole("heading", { name: /We found these/ })).toBeNull();
  });
});

describe("paste anything (screen 7)", () => {
  it("caps the text, finds skills, and says when none were found", async () => {
    render(
      <ImportShortcut mode="paste" onUse={vi.fn()} onCancel={vi.fn()} loadNames={loadNames} />,
    );
    const box = screen.getByLabelText("Text about you");
    expect(box).toHaveAttribute("maxLength", "2000");
    expect(screen.getByRole("button", { name: "Find my skills" })).toBeDisabled();
    await userEvent.type(box, "I like long walks.");
    await userEvent.click(screen.getByRole("button", { name: "Find my skills" }));
    expect(await screen.findByText(/We didn't spot any skills we know/)).toBeVisible();
    expect(screen.getByRole("button", { name: /Use these/ })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Start over" }));
    expect(screen.getByLabelText("Text about you")).toHaveValue("I like long walks.");
  });
});
