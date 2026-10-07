import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { avatarFill } from "@/lib/design/color";

import {
  Accordion,
  Avatar,
  BottomNav,
  Button,
  ButtonLink,
  CtaBand,
  FadeUp,
  Footer,
  HeroCell,
  HeroGrid,
  HomeIcon,
  InlineError,
  Input,
  LabelChip,
  ListRow,
  Logo,
  NumberedRows,
  Panel,
  PeopleIcon,
  PixelPattern,
  RowTile,
  SegmentedControl,
  Skeleton,
  SkeletonGroup,
  StatusBadge,
  Textarea,
  Toast,
  TopBar,
  TopicChip,
  TwoToneHeadline,
} from "./index";

vi.mock("next/navigation", () => ({ usePathname: () => "/spaces/abc" }));

describe("Button", () => {
  it("is a real button, operable from the keyboard", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Find people</Button>);
    const button = screen.getByRole("button", { name: "Find people" });
    expect(button).toHaveAttribute("type", "button");

    const user = userEvent.setup();
    await user.tab();
    expect(button).toHaveFocus();
    await user.keyboard("{Enter}");
    await user.keyboard(" ");
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it("styles each variant from tokens", () => {
    render(
      <>
        <Button variant="primary">Primary</Button>
        <Button variant="outline">Outline</Button>
        <Button variant="ghost">Ghost</Button>
      </>,
    );
    expect(screen.getByRole("button", { name: "Primary" }).className).toMatch(/\bbg-ink\b/);
    expect(screen.getByRole("button", { name: "Outline" }).className).toMatch(/\bborder-green\b/);
    expect(screen.getByRole("button", { name: "Ghost" }).className).toMatch(
      /\bborder-transparent\b/,
    );
  });

  it("is 44px high on touch screens, lifts on hover and presses to 97%", () => {
    render(<Button size="compact">Compact</Button>);
    const classes = screen.getByRole("button", { name: "Compact" }).className;
    expect(classes).toMatch(/\bh-11\b/);
    expect(classes).toMatch(/active:scale-\[\.97\]/);
    expect(classes).toMatch(/lg:hover:-translate-y-0\.5/);
  });

  it("does nothing when disabled", async () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Send
      </Button>,
    );
    await userEvent.setup().click(screen.getByRole("button", { name: "Send" }));
    expect(onClick).not.toHaveBeenCalled();
  });

  it("has a link form for navigation", () => {
    render(<ButtonLink href="/home">Open pair spaces</ButtonLink>);
    expect(screen.getByRole("link", { name: "Open pair spaces" })).toHaveAttribute("href", "/home");
  });
});

describe("Accordion", () => {
  const items = [
    { id: "name", question: "Who can see my name?", answer: "Answer one." },
    { id: "ai", question: "Does AI read my chats?", answer: "Answer two." },
  ];

  it("toggles aria-expanded and makes the answer reachable only when open", async () => {
    render(<Accordion items={items} />);
    const question = screen.getByRole("button", { name: "Who can see my name?" });
    const panel = document.getElementById(question.getAttribute("aria-controls") ?? "");
    expect(question).toHaveAttribute("aria-expanded", "false");
    expect(panel).toHaveAttribute("inert");

    const user = userEvent.setup();
    question.focus();
    await user.keyboard("{Enter}");
    expect(question).toHaveAttribute("aria-expanded", "true");
    expect(panel).not.toHaveAttribute("inert");
    expect(screen.getByRole("region", { name: "Who can see my name?" })).toHaveTextContent(
      "Answer one.",
    );

    await user.keyboard(" ");
    expect(question).toHaveAttribute("aria-expanded", "false");
  });

  it("keeps several open, or one at a time with `single`", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<Accordion items={items} />);
    await user.click(screen.getByRole("button", { name: "Who can see my name?" }));
    await user.click(screen.getByRole("button", { name: "Does AI read my chats?" }));
    expect(screen.getAllByRole("button", { expanded: true })).toHaveLength(2);
    unmount();

    render(<Accordion items={items} single />);
    await user.click(screen.getByRole("button", { name: "Who can see my name?" }));
    await user.click(screen.getByRole("button", { name: "Does AI read my chats?" }));
    expect(screen.getAllByRole("button", { expanded: true })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Does AI read my chats?" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });
});

describe("SegmentedControl", () => {
  it("is a labelled group of toggle buttons, operable from the keyboard", async () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl
        label="Filter"
        value="all"
        onChange={onChange}
        segments={[
          { value: "all", label: "All" },
          { value: "requests", label: "Requests", count: 2 },
        ]}
      />,
    );
    expect(screen.getByRole("group", { name: "Filter" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
    const requests = screen.getByRole("button", { name: "Requests 2" });
    expect(requests).toHaveAttribute("aria-pressed", "false");

    const user = userEvent.setup();
    await user.tab();
    await user.tab();
    expect(requests).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onChange).toHaveBeenCalledWith("requests");
  });
});

describe("ListRow", () => {
  it("is a link with its title, secondary line, time and a labelled unread dot", () => {
    render(
      <ul>
        <ListRow
          href="/home?item=chat-1"
          leading={<Avatar userId="u1" name="Aarav R." decorative />}
          title="Aarav R."
          secondary="2 new messages"
          time="12m"
          unread
          unreadLabel="Unread messages"
          selected
        />
      </ul>,
    );
    const link = screen.getByRole("link", { name: /Aarav R\./ });
    expect(link).toHaveAttribute("href", "/home?item=chat-1");
    expect(link).toHaveAttribute("aria-current", "true");
    expect(link).toHaveTextContent("2 new messages");
    expect(link).toHaveTextContent("12m");
    expect(screen.getByText("Unread messages")).toHaveClass("sr-only");
  });

  it("has request and intro tiles and status badges", () => {
    render(
      <>
        <RowTile kind="request" />
        <RowTile kind="intro" />
        <StatusBadge kind="request" />
        <StatusBadge kind="intro" />
      </>,
    );
    expect(screen.getByText("Request")).toHaveClass("bg-ink");
    expect(screen.getByText("Intro")).toHaveClass("bg-green-tint");
  });
});

describe("Avatar", () => {
  it("shows initials on green or ink, picked from the id only", () => {
    render(<Avatar userId="person-7" name="Meera Kapoor" />);
    const avatar = screen.getByRole("img", { name: "Meera Kapoor" });
    expect(avatar).toHaveTextContent("MK");
    expect(avatar).toHaveAttribute("data-fill", avatarFill("person-7"));
    expect(avatar.className).toMatch(
      avatarFill("person-7") === "green" ? /\bbg-green\b/ : /\bbg-ink\b/,
    );
  });

  it("can be hidden when the name is next to it", () => {
    const { container } = render(<Avatar userId="x" name="Rohan D." decorative />);
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });
});

describe("Fields", () => {
  it("labels the input and links its hint and error", () => {
    render(<Input label="Sign-in code" hint="Six digits." error="That code has expired." />);
    const input = screen.getByLabelText("Sign-in code");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("Six digits. That code has expired.");
  });

  it("counts characters in a textarea with a limit", async () => {
    render(<Textarea label="New request" maxLength={500} />);
    expect(screen.getByText("0/500")).toBeInTheDocument();
    await userEvent.setup().type(screen.getByLabelText("New request"), "learn React");
    expect(screen.getByText("11/500")).toBeInTheDocument();
  });

  it("announces errors and toasts", async () => {
    const onDismiss = vi.fn();
    render(
      <>
        <InlineError announce>We couldn&apos;t save that.</InlineError>
        <Toast onDismiss={onDismiss}>Intro sent.</Toast>
        <Toast tone="error">That didn&apos;t work.</Toast>
      </>,
    );
    expect(screen.getAllByRole("alert")).toHaveLength(2);
    expect(screen.getByRole("status")).toHaveTextContent("Intro sent.");
    await userEvent.setup().click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});

describe("Navigation", () => {
  it("marks the current bottom-nav item with aria-current", () => {
    render(
      <BottomNav
        items={[
          { href: "/home", label: "Home", icon: <HomeIcon /> },
          { href: "/spaces", label: "Spaces", icon: <PeopleIcon /> },
        ]}
      />,
    );
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Spaces" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
  });

  it("has a top bar with the logo, links and actions", () => {
    render(
      <TopBar
        links={[{ href: "/#how", label: "How it works" }]}
        currentHref="/#how"
        actions={<ButtonLink href="/login">Sign in</ButtonLink>}
      />,
    );
    expect(screen.getByRole("link", { name: "cynergi home" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "How it works" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Sign in" })).toBeInTheDocument();
  });

  it("has a footer with legal links, the contact address and the legal row", () => {
    render(<Footer productLinks={[{ href: "/#faq", label: "FAQ" }]} />);
    expect(screen.getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "Contact us" }).getAttribute("href")).toMatch(
      /^mailto:/,
    );
    expect(screen.getByText("© 2026 Cynergi")).toBeInTheDocument();
    expect(screen.queryByText(/All rights reserved/)).not.toBeInTheDocument();
  });
});

describe("Brand pieces", () => {
  it("draws the lowercase wordmark with a decorative mark", () => {
    const { container } = render(<Logo />);
    expect(screen.getByText("cynergi")).toBeInTheDocument();
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("keeps decorative art hidden from assistive technology", () => {
    const { container } = render(
      <>
        <PixelPattern />
        <Skeleton className="h-4" />
      </>,
    );
    for (const element of container.children)
      expect(element).toHaveAttribute("aria-hidden", "true");
  });

  it("announces a skeleton group once as loading", () => {
    render(
      <SkeletonGroup>
        <Skeleton />
      </SkeletonGroup>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });

  it("renders chips, panels, headlines, numbered rows, hero cells and the CTA band", () => {
    render(
      <>
        <LabelChip>Safe by default</LabelChip>
        <TopicChip>cybersecurity</TopicChip>
        <Panel tone="green">Panel</Panel>
        <TwoToneHeadline lead="Skills. Interests. Intent." rest="Matched." />
        <NumberedRows rows={[{ lead: "Skills", rest: "tell you what someone knows." }]} />
        <HeroGrid>
          <HeroCell index={2}>Cell</HeroCell>
        </HeroGrid>
        <CtaBand
          lead="Your next collaborator"
          rest="is one sentence away."
          action={{ href: "/login", label: "Find your people" }}
        />
      </>,
    );
    expect(screen.getByText("Safe by default")).toHaveClass("bg-ink");
    expect(screen.getByText("cybersecurity")).toHaveClass("border-green");
    expect(
      screen.getByRole("heading", { name: /Skills\. Interests\. Intent\./ }),
    ).toBeInTheDocument();
    expect(screen.getByRole("listitem")).toHaveAttribute("data-n", "01");
    expect(screen.getByText("Cell")).toHaveStyle({ animationDelay: "190ms" });
    expect(screen.getByRole("heading", { name: /Your next collaborator/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Find your people" })).toHaveAttribute(
      "href",
      "/login",
    );
  });
});

describe("FadeUp and reduced motion", () => {
  type Callback = (entries: { isIntersecting: boolean }[]) => void;
  let fire: Callback = () => undefined;

  function installObserver() {
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(callback: Callback) {
          fire = callback;
        }
        observe() {}
        disconnect() {}
      },
    );
  }

  function setReducedMotion(reduce: boolean) {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({ matches: reduce, addEventListener() {}, removeEventListener() {} }),
    );
  }

  afterEach(() => {
    vi.unstubAllGlobals();
    fire = () => undefined;
  });

  it("hides content that starts below the fold, then fades it up once", () => {
    installObserver();
    setReducedMotion(false);
    render(<FadeUp>Section</FadeUp>);
    const section = screen.getByText("Section");
    expect(section).toHaveAttribute("data-motion", "static");

    act(() => fire([{ isIntersecting: false }]));
    expect(section).toHaveAttribute("data-motion", "hidden");
    expect(section).toHaveClass("opacity-0");

    act(() => fire([{ isIntersecting: true }]));
    expect(section).toHaveAttribute("data-motion", "shown");
    expect(section).toHaveClass("opacity-100");
  });

  it("leaves content already on screen alone", () => {
    installObserver();
    setReducedMotion(false);
    render(<FadeUp>Section</FadeUp>);
    act(() => fire([{ isIntersecting: true }]));
    expect(screen.getByText("Section")).toHaveAttribute("data-motion", "static");
  });

  it("adds no animation classes with reduced motion", () => {
    installObserver();
    setReducedMotion(true);
    render(<FadeUp>Section</FadeUp>);
    act(() => fire([{ isIntersecting: false }]));
    const section = screen.getByText("Section");
    expect(section).toHaveAttribute("data-motion", "static");
    expect(section.className).not.toMatch(/opacity-0|translate-y-2|transition/);
  });
});
