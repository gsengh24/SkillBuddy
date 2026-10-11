import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { MAX_PHRASES } from "@/lib/profile/limits";

import { TagEditor } from "./tag-editor";

function Harness({
  search,
  initial = [],
}: {
  search?: (query: string) => Promise<string[]>;
  initial?: string[];
}) {
  const [tags, setTags] = useState(initial);
  return (
    <TagEditor
      label="I can help with"
      inputLabel="Add a skill"
      placeholder="Add a skill"
      tags={tags}
      suggestions={["Writing"]}
      search={search}
      onChange={setTags}
    />
  );
}

const input = () => screen.getByRole("combobox", { name: "Add a skill" });

describe("TagEditor typeahead", () => {
  it("shows matching names while typing and adds the one clicked", async () => {
    const search = vi.fn().mockResolvedValue(["Python", "PyTorch"]);
    const user = userEvent.setup();
    render(<Harness search={search} />);

    await user.type(input(), "py");
    const option = await screen.findByRole("option", { name: "PyTorch" });
    await user.click(option);

    expect(search).toHaveBeenLastCalledWith("py");
    expect(screen.getByRole("button", { name: "Remove PyTorch" })).toBeInTheDocument();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(input()).toHaveValue("");
  });

  it("picks with the arrow keys and Enter", async () => {
    const user = userEvent.setup();
    render(<Harness search={() => Promise.resolve(["Python", "PyTorch"])} />);

    await user.type(input(), "py");
    await screen.findByRole("listbox");
    await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");

    expect(screen.getByRole("button", { name: "Remove PyTorch" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove Python" })).not.toBeInTheDocument();
  });

  it("still adds a skill the list does not know", async () => {
    const user = userEvent.setup();
    render(<Harness search={() => Promise.resolve([])} />);

    await user.type(input(), "Sourdough baking{Enter}");

    expect(screen.getByRole("button", { name: "Remove Sourdough baking" })).toBeInTheDocument();
  });

  it("adds what was typed when no suggestion is highlighted", async () => {
    const user = userEvent.setup();
    render(<Harness search={() => Promise.resolve(["Python"])} />);

    await user.type(input(), "py");
    await screen.findByRole("listbox");
    await user.keyboard("{Enter}");

    expect(screen.getByRole("button", { name: "Remove py" })).toBeInTheDocument();
  });

  it("closes the list on Escape", async () => {
    const user = userEvent.setup();
    render(<Harness search={() => Promise.resolve(["Python"])} />);

    await user.type(input(), "py");
    await screen.findByRole("listbox");
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("leaves out names that are already tags", async () => {
    const user = userEvent.setup();
    render(<Harness search={() => Promise.resolve(["Python", "PyTorch"])} initial={["python"]} />);

    await user.type(input(), "py");

    expect(await screen.findByRole("option", { name: "PyTorch" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Python" })).not.toBeInTheDocument();
  });

  it("carries on quietly when the search fails", async () => {
    const search = vi.fn().mockRejectedValue(new Error("offline"));
    const user = userEvent.setup();
    render(<Harness search={search} />);

    await user.type(input(), "py");
    await vi.waitFor(() => expect(search).toHaveBeenCalled());
    await user.keyboard("{Enter}");

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove py" })).toBeInTheDocument();
  });

  it("shows the quick-add chips only while nothing is typed", async () => {
    const user = userEvent.setup();
    render(<Harness search={() => Promise.resolve([])} />);

    expect(screen.getByRole("button", { name: "Add Writing" })).toBeInTheDocument();
    await user.type(input(), "w");
    expect(screen.queryByRole("button", { name: "Add Writing" })).not.toBeInTheDocument();
  });

  it("stops asking once the cap is reached", () => {
    const search = vi.fn().mockResolvedValue(["Python"]);
    const tags = Array.from({ length: MAX_PHRASES }, (_, i) => `Skill ${i}`);
    render(<Harness search={search} initial={tags} />);

    expect(input()).toBeDisabled();
    expect(search).not.toHaveBeenCalled();
  });
});
