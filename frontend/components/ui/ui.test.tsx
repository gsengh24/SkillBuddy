import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { personHue } from "@/lib/design/color";
import { hues } from "@/lib/design/tokens";

import {
  Avatar,
  Badge,
  BadgeDot,
  Button,
  ButtonLink,
  Card,
  HeroPanel,
  initialsFor,
  IntentChip,
  Logo,
  MatchNumeral,
  StrengthBar,
  Tag,
  TextArea,
  TextField,
  TextLink,
  TintPill,
  WhyBox,
} from "./index";

describe("Button", () => {
  it("is a real button: outline pill, type=button by default, colour-only hover", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Find matches</Button>);
    const button = screen.getByRole("button", { name: "Find matches" });

    await userEvent.setup().click(button);

    expect(onClick).toHaveBeenCalledOnce();
    expect(button).toHaveAttribute("type", "button");
    expect(button.className).toMatch(/\brounded-full\b/);
    expect(button.className).toMatch(/\bborder-ink\b/);
    expect(button.className).toMatch(/\bbg-transparent\b/);
    expect(button.className).toMatch(/\bh-11\b/); // 44px touch target by default
    expect(button.className).not.toMatch(/transition|animate/);
  });

  it("supports submit, danger, a person's hue and disabled", () => {
    render(
      <>
        <Button type="submit">Send</Button>
        <Button tone="danger">Delete</Button>
        <Button hue="coral">Connect</Button>
        <Button disabled>Off</Button>
      </>,
    );
    expect(screen.getByRole("button", { name: "Send" })).toHaveAttribute("type", "submit");
    expect(screen.getByRole("button", { name: "Delete" }).className).toMatch(/border-coral-ink/);
    const connect = screen.getByRole("button", { name: "Connect" });
    expect(connect.style.getPropertyValue("--hue-ink")).toBe(hues.coral.ink);
    expect(connect.className).toMatch(/text-\(--hue-ink\)/);
    expect(screen.getByRole("button", { name: "Off" })).toBeDisabled();
  });

  it("ButtonLink and TextLink are links", () => {
    render(
      <>
        <ButtonLink href="/login">Sign in</ButtonLink>
        <TextLink href="/terms">Terms</TextLink>
      </>,
    );
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: "Terms" }).className).toMatch(/text-green-ink/);
  });
});

describe("IntentChip", () => {
  it("is a static label with a colour dot", () => {
    render(<IntentChip intent="mentor" />);
    expect(screen.getByText("Mentor")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("is a toggle button when interactive", async () => {
    const onToggle = vi.fn();
    const { rerender } = render(<IntentChip intent="explore" onToggle={onToggle} />);
    const chip = screen.getByRole("button", { name: "Explore" });
    expect(chip).toHaveAttribute("aria-pressed", "false");

    await userEvent.setup().click(chip);
    expect(onToggle).toHaveBeenCalledOnce();

    rerender(<IntentChip intent="explore" onToggle={onToggle} selected />);
    expect(chip).toHaveAttribute("aria-pressed", "true");
    expect(chip.className).toMatch(/bg-paper/);
    expect(chip.style.getPropertyValue("--hue-ink")).toBe(hues.teal.ink);
  });
});

describe("Avatar", () => {
  it("shows initials in the person's hue and is named for screen readers", () => {
    const id = "8d3f4b2a-0000-4000-8000-000000000001";
    render(<Avatar userId={id} name="Aarav Sharma" />);
    const avatar = screen.getByRole("img", { name: "Aarav Sharma" });
    expect(avatar).toHaveTextContent("AS");
    expect(avatar.style.getPropertyValue("--hue-tint")).toBe(hues[personHue(id)].tint);
  });

  it("can be decorative", () => {
    const { container } = render(<Avatar userId="x" name="Someone" decorative />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });

  it.each([
    ["Aarav Sharma", "AS"],
    ["mehak", "M"],
    ["rohan.dutta@example.com", "RD"],
    ["Ana Maria Lopez", "AM"],
  ])("initials for %s are %s", (name, initials) => {
    expect(initialsFor(name)).toBe(initials);
  });
});

describe("StrengthBar", () => {
  it("is a meter with its value, clamped to 0-100", () => {
    render(
      <>
        <StrengthBar value={78} hue="amber" label="Profile complete" />
        <StrengthBar value={140} hue="green" label="Over" />
      </>,
    );
    const meter = screen.getByRole("meter", { name: "Profile complete" });
    expect(meter).toHaveAttribute("aria-valuenow", "78");
    expect(meter).toHaveAttribute("aria-valuetext", "78%");
    expect(screen.getByRole("meter", { name: "Over" })).toHaveAttribute("aria-valuenow", "100");
    expect(meter.style.getPropertyValue("--hue-track")).toBe(hues.amber.track);
    const fill = meter.firstElementChild as HTMLElement;
    expect(fill.style.width).toBe("78%");
    expect(fill.style.backgroundImage).toContain("repeating-linear-gradient");
  });
});

describe("text-bearing components use ink colours, never base", () => {
  it("MatchNumeral reads as a match percentage in the hue's ink", () => {
    const { container } = render(<MatchNumeral value={92} hue="coral" />);
    expect(container).toHaveTextContent("92% match");
    const numeral = container.firstElementChild as HTMLElement;
    expect(numeral.className).toMatch(/text-\(--hue-ink\)/);
    expect(numeral.className).not.toMatch(/--hue-base/);
  });

  it("WhyBox, Tag and TintPill", () => {
    render(
      <>
        <WhyBox hue="violet">You share civic tech.</WhyBox>
        <Tag hue="teal">Mentoring</Tag>
        <TintPill hue="blue">A study partner</TintPill>
      </>,
    );
    expect(screen.getByText("Why you two")).toBeInTheDocument();
    expect(screen.getByText("You share civic tech.")).toBeInTheDocument();
    expect(screen.getByText("Mentoring").className).toMatch(/border-\(--hue-edge\)/);
    expect(screen.getByText("A study partner").className).toMatch(/bg-\(--hue-tint\)/);
  });
});

describe("surfaces", () => {
  it("Card and HeroPanel render content; the rings are decorative", () => {
    const { container } = render(
      <>
        <Card>Card body</Card>
        <HeroPanel>Hero body</HeroPanel>
      </>,
    );
    expect(screen.getByText("Card body").className).toMatch(/rounded-card/);
    expect(screen.getByText("Hero body")).toBeInTheDocument();
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg?.querySelectorAll("circle")).toHaveLength(5);
  });
});

describe("TextField and TextArea", () => {
  it("label the field and describe hint and error", () => {
    render(
      <>
        <TextField label="Email address" hint="We send a code." error="Enter a valid email." />
        <TextArea label="About you" />
      </>,
    );
    const field = screen.getByLabelText("Email address");
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAccessibleDescription("We send a code. Enter a valid email.");
    expect(field.className).toMatch(/border-b/);
    expect(screen.getByLabelText("About you").tagName).toBe("TEXTAREA");
  });

  it("keeps a caller's own aria-describedby", () => {
    render(
      <>
        <p id="outside">Outside message</p>
        <TextField label="Code" aria-describedby="outside" />
      </>,
    );
    expect(screen.getByLabelText("Code")).toHaveAccessibleDescription("Outside message");
  });
});

describe("Badge", () => {
  it("shows a count with a spoken label, caps at 99+, hides at zero", () => {
    const { rerender, container } = render(<Badge count={2} label="unread messages" />);
    expect(screen.getByText("2 unread messages")).toHaveClass("sr-only");
    expect(container.firstElementChild?.className).toMatch(/bg-badge/);

    rerender(<Badge count={140} label="unread messages" />);
    expect(screen.getByText("99+")).toBeInTheDocument();

    rerender(<Badge count={0} label="unread messages" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("dot is labelled or hidden", () => {
    const { container } = render(
      <>
        <BadgeDot label="new activity" />
        <BadgeDot />
      </>,
    );
    expect(screen.getByText("new activity")).toBeInTheDocument();
    expect(container.children[1]).toHaveAttribute("aria-hidden", "true");
  });
});

describe("Logo", () => {
  it("shows the product name with decorative rings", () => {
    const { container } = render(<Logo />);
    expect(screen.getByText("Cynergi")).toBeInTheDocument();
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });
});
