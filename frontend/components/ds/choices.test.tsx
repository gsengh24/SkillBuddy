import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { ChoiceCard, ChoiceChip, RadioSegments, StepProgress } from "./index";

describe("ChoiceChip", () => {
  it("is a toggle button with aria-pressed, in both tones", async () => {
    const onToggle = vi.fn();
    render(
      <>
        <ChoiceChip pressed={false} onToggle={onToggle}>
          Python
        </ChoiceChip>
        <ChoiceChip pressed tone="ink" onToggle={onToggle} label="Want SQL">
          SQL
        </ChoiceChip>
      </>,
    );
    const python = screen.getByRole("button", { name: "Python" });
    expect(python).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Want SQL" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await userEvent.click(python);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });
});

describe("ChoiceCard", () => {
  it("names itself by its title and shows whether it is picked", async () => {
    const onToggle = vi.fn();
    render(
      <ChoiceCard
        pressed
        onToggle={onToggle}
        icon={<svg />}
        title="Mentor"
        line="Learn from, or guide, someone further along."
      />,
    );
    const card = screen.getByRole("button", { name: /Mentor/ });
    expect(card).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(card);
    expect(onToggle).toHaveBeenCalled();
  });
});

describe("StepProgress", () => {
  it("is a progressbar that reads as step n of total", () => {
    render(<StepProgress step={2} total={4} label="Profile setup" />);
    const bar = screen.getByRole("progressbar", { name: "Profile setup" });
    expect(bar).toHaveAttribute("aria-valuenow", "2");
    expect(bar).toHaveAttribute("aria-valuetext", "Step 2 of 4");
  });
});

function Hours() {
  const [value, setValue] = useState<"a" | "b" | "c" | null>(null);
  return (
    <RadioSegments
      label="Hours a week"
      options={[
        { value: "a", label: "1–3" },
        { value: "b", label: "4–6" },
        { value: "c", label: "7–10" },
      ]}
      value={value}
      onChange={setValue}
    />
  );
}

describe("RadioSegments", () => {
  it("is a radiogroup: click picks, arrow keys move and pick, one tab stop", async () => {
    render(<Hours />);
    expect(screen.getByRole("radiogroup", { name: "Hours a week" })).toBeInTheDocument();
    const radios = screen.getAllByRole("radio");
    expect(radios.map((r) => r.getAttribute("tabindex"))).toEqual(["0", "-1", "-1"]);

    await userEvent.click(screen.getByRole("radio", { name: "4–6" }));
    expect(screen.getByRole("radio", { name: "4–6" })).toHaveAttribute("aria-checked", "true");

    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("radio", { name: "7–10" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "7–10" })).toHaveFocus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("radio", { name: "1–3" })).toHaveAttribute("aria-checked", "true");
  });
});
