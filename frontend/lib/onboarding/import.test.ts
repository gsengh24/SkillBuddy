import { describe, expect, it } from "vitest";

import { checkPdf, PDF_MAX_BYTES, PdfReadError } from "./pdf-text";
import { redact } from "./redact";
import { spotSkills } from "./spot";

// Synthetic only: no real person, address or number.
const RESUME = `Aarav Rust
aarav.rust@example.com | +91 98765 43210 | linkedin.com/in/aarav-example
Address: 12 Example Street, Patiala 147001
Second-year CSE student. Built apps with React and Flutter, 2023 - 2025.
Skills: Figma, UI design, Firebase, Public speaking
Interests: Hackathons, ML, chess, street photography`;

describe("redact", () => {
  it("removes the header name, email, phone, links and address lines", () => {
    const { text, removed } = redact(RESUME);
    expect(text).not.toMatch(/Aarav|example\.com|98765|43210|linkedin|Patiala|147001/i);
    expect(removed).toBeGreaterThanOrEqual(5);
    // The rest is kept, including years.
    expect(text).toContain("Built apps with React and Flutter, 2023 - 2025.");
    expect(text).toContain("Skills: Figma");
  });

  it("keeps a one-line paste, which is a sentence and not a header", () => {
    expect(redact("React Developer").text).toBe("React Developer");
  });

  it("removes labelled names, web links and long digit runs anywhere", () => {
    const { text } = redact(
      "About me\nName: Test Person\nSee https://example.dev/me or www.example.org.\nCall 9876543210.",
    );
    expect(text).not.toMatch(/Test Person|example|9876543210/);
  });
});

describe("spotSkills", () => {
  it("finds listed names in order, splits interests out, and maps short forms", () => {
    const found = spotSkills(redact(RESUME).text, ["Firebase"]);
    expect(found.skills).toEqual([
      "React",
      "Flutter",
      "Figma",
      "UI design",
      "Firebase",
      "Public speaking",
      // "ML" is the listed skill, so it is offered rather than an interest.
      "Machine learning",
    ]);
    expect(found.interests).toEqual(["Hackathons", "Chess", "Photography"]);
  });

  it("matches whole words only", () => {
    expect(spotSkills("I write JavaScript and C++, not Java.", ["JavaScript"]).skills).toEqual([
      "JavaScript",
      "C++",
      "Java",
    ]);
    expect(spotSkills("Reactive programming in Pythonic style", []).skills).toEqual([]);
  });

  it("never suggests a surname once the header is removed", () => {
    expect(spotSkills(redact(RESUME).text, ["Rust"]).skills).not.toContain("Rust");
    // Without redaction it would have.
    expect(spotSkills(RESUME, ["Rust"]).skills).toContain("Rust");
  });

  it("skips names too general to mean a skill", () => {
    expect(spotSkills("Languages: English, Hindi", ["Languages", "Hindi"]).skills).toEqual([
      "Hindi",
    ]);
  });
});

describe("checkPdf", () => {
  it("refuses files over 2 MB and files that aren't PDFs", () => {
    const big = new File([new Uint8Array(PDF_MAX_BYTES + 1)], "cv.pdf", {
      type: "application/pdf",
    });
    expect(() => checkPdf(big)).toThrow(PdfReadError);
    expect(() => checkPdf(new File(["x"], "cv.docx", { type: "application/msword" }))).toThrow(
      "Choose a PDF file.",
    );
    expect(() => checkPdf(new File(["%PDF"], "cv.pdf", { type: "" }))).not.toThrow();
  });
});
