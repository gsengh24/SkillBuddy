"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cx } from "@/components/ui/cx";
import { Tag } from "@/components/ui/tag";
import { TextArea, TextField } from "@/components/ui/text-field";
import { browserApi } from "@/lib/api/browser";
import {
  goalSchema,
  noContentSchema,
  progressLogSchema,
  skillSchema,
  type Goal,
  type ProgressLog,
  type Skill,
  type Space,
} from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { personHue } from "@/lib/design/color";

// The API's limits (GOAL_TITLE_MAX_LENGTH, SKILL_NAME_MAX_LENGTH, LOG_NOTE_MAX_LENGTH).
const TITLE_MAX = 120;
const SKILL_MAX = 60;
const NOTE_MAX = 500;

const SELECT = cx(
  "border-muted text-body text-ink min-h-11 w-full rounded-none border-0 border-b bg-transparent",
  "hover:border-ink focus:border-green-base",
);

function Alert({ message }: { message: string | null }) {
  return message ? (
    <p role="alert" className="text-small text-coral-ink font-semibold">
      {message}
    </p>
  ) : null;
}

function when(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/**
 * A pair space (ADR 0013): shared goals either person can change, the skills each person
 * wants to grow (only the owner removes them) and progress notes (only the author deletes).
 */
export function SpaceView({
  space,
  meId,
  otherId,
  otherName,
}: {
  space: Space;
  meId: string;
  otherId: string;
  otherName: string;
}) {
  const base = `/connections/${space.connection_id}/space` as const;
  const [goals, setGoals] = useState<Goal[]>(space.goals);
  const [skills, setSkills] = useState<Skill[]>(space.skills);
  const [logs, setLogs] = useState<ProgressLog[]>(space.logs);
  const [goalTitle, setGoalTitle] = useState("");
  const [goalDue, setGoalDue] = useState("");
  const [skillName, setSkillName] = useState("");
  const [note, setNote] = useState("");
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<"goals" | "skills" | "logs", string | null>>({
    goals: null,
    skills: null,
    logs: null,
  });

  async function run(section: keyof typeof errors, action: () => Promise<void>) {
    setBusy(true);
    setErrors((current) => ({ ...current, [section]: null }));
    try {
      await action();
    } catch (caught) {
      setErrors((current) => ({ ...current, [section]: describeError(caught) }));
    } finally {
      setBusy(false);
    }
  }

  const mySkills = skills.filter((skill) => skill.owner_id === meId);
  const theirSkills = skills.filter((skill) => skill.owner_id !== meId);
  const goalTitleById = new Map(goals.map((goal) => [goal.id, goal.title]));
  const skillNameById = new Map(skills.map((skill) => [skill.id, skill.name]));

  function addGoal(event: FormEvent) {
    event.preventDefault();
    const title = goalTitle.trim();
    if (!title) return;
    void run("goals", async () => {
      const goal = await browserApi(`${base}/goals`, goalSchema, {
        method: "POST",
        body: { title, due_on: goalDue || null },
      });
      setGoals((current) => [...current, goal]);
      setGoalTitle("");
      setGoalDue("");
    });
  }

  function toggleGoal(goal: Goal) {
    void run("goals", async () => {
      const saved = await browserApi(`${base}/goals/${goal.id}`, goalSchema, {
        method: "PATCH",
        body: { status: goal.status === "done" ? "open" : "done" },
      });
      setGoals((current) => current.map((item) => (item.id === saved.id ? saved : item)));
    });
  }

  function deleteGoal(goal: Goal) {
    void run("goals", async () => {
      await browserApi(`${base}/goals/${goal.id}`, noContentSchema, { method: "DELETE" });
      setGoals((current) => current.filter((item) => item.id !== goal.id));
    });
  }

  function addSkill(event: FormEvent) {
    event.preventDefault();
    const name = skillName.trim();
    if (!name) return;
    void run("skills", async () => {
      const skill = await browserApi(`${base}/skills`, skillSchema, {
        method: "POST",
        body: { name },
      });
      setSkills((current) => [...current, skill]);
      setSkillName("");
    });
  }

  function removeSkill(skill: Skill) {
    void run("skills", async () => {
      await browserApi(`${base}/skills/${skill.id}`, noContentSchema, { method: "DELETE" });
      setSkills((current) => current.filter((item) => item.id !== skill.id));
    });
  }

  function addLog(event: FormEvent) {
    event.preventDefault();
    const text = note.trim();
    if (!text) return;
    const [kind, id] = link.split(":");
    void run("logs", async () => {
      const log = await browserApi(`${base}/logs`, progressLogSchema, {
        method: "POST",
        body: {
          note: text,
          goal_id: kind === "goal" ? id : null,
          skill_id: kind === "skill" ? id : null,
        },
      });
      setLogs((current) => [log, ...current]);
      setNote("");
      setLink("");
    });
  }

  function deleteLog(log: ProgressLog) {
    void run("logs", async () => {
      await browserApi(`${base}/logs/${log.id}`, noContentSchema, { method: "DELETE" });
      setLogs((current) => current.filter((item) => item.id !== log.id));
    });
  }

  const ordered = [...goals].sort((a, b) =>
    a.status === b.status ? 0 : a.status === "open" ? -1 : 1,
  );

  return (
    <div className="flex flex-col gap-6">
      <section aria-labelledby="goals-h" className="flex flex-col gap-3">
        <h2 id="goals-h" className="text-section">
          Shared goals
        </h2>
        <Card className="flex flex-col gap-4">
          {ordered.length ? (
            <ul className="flex flex-col gap-2">
              {ordered.map((goal) => (
                <li key={goal.id} className="flex flex-wrap items-center justify-between gap-2">
                  <label className="flex min-h-11 items-center gap-3">
                    <input
                      type="checkbox"
                      checked={goal.status === "done"}
                      disabled={busy}
                      onChange={() => toggleGoal(goal)}
                      className="accent-green-base size-4 shrink-0"
                    />
                    <span
                      className={goal.status === "done" ? "text-muted line-through" : "text-ink"}
                    >
                      {goal.title}
                      {goal.due_on ? (
                        <span className="text-small text-muted"> · due {goal.due_on}</span>
                      ) : null}
                    </span>
                  </label>
                  <Button tone="danger" disabled={busy} onClick={() => deleteGoal(goal)}>
                    Delete
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted">No goals yet. Add one you both want to reach.</p>
          )}
          <form onSubmit={addGoal} className="flex flex-col gap-3">
            <TextField
              label="New goal"
              maxLength={TITLE_MAX}
              value={goalTitle}
              onChange={(event) => setGoalTitle(event.target.value)}
              placeholder="Ship the first version"
            />
            <TextField
              label="Due date (optional)"
              type="date"
              value={goalDue}
              onChange={(event) => setGoalDue(event.target.value)}
            />
            <Button type="submit" className="self-start" disabled={busy || !goalTitle.trim()}>
              Add goal
            </Button>
          </form>
          <Alert message={errors.goals} />
        </Card>
      </section>

      <section aria-labelledby="skills-h" className="flex flex-col gap-3">
        <h2 id="skills-h" className="text-section">
          Skills to grow
        </h2>
        <Card className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <h3 className="text-ink font-bold">You</h3>
            {mySkills.length ? (
              <ul className="flex flex-wrap gap-2">
                {mySkills.map((skill) => (
                  <li key={skill.id} className="flex items-center gap-1">
                    <Tag hue={personHue(meId)}>{skill.name}</Tag>
                    <Button
                      disabled={busy}
                      onClick={() => removeSkill(skill)}
                      aria-label={`Remove ${skill.name}`}
                    >
                      Remove
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-small text-muted">Add a skill you want to get better at.</p>
            )}
            <form onSubmit={addSkill} className="flex flex-col gap-3">
              <TextField
                label="A skill you want to grow"
                maxLength={SKILL_MAX}
                value={skillName}
                onChange={(event) => setSkillName(event.target.value)}
                placeholder="Public speaking"
              />
              <Button type="submit" className="self-start" disabled={busy || !skillName.trim()}>
                Add skill
              </Button>
            </form>
          </div>
          <div className="flex flex-col gap-2">
            <h3 className="text-ink font-bold">{otherName}</h3>
            {theirSkills.length ? (
              <ul className="flex flex-wrap gap-2">
                {theirSkills.map((skill) => (
                  <li key={skill.id}>
                    <Tag hue={personHue(otherId)}>{skill.name}</Tag>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-small text-muted">No skills added yet.</p>
            )}
          </div>
          <Alert message={errors.skills} />
        </Card>
      </section>

      <section aria-labelledby="logs-h" className="flex flex-col gap-3">
        <h2 id="logs-h" className="text-section">
          Progress notes
        </h2>
        <Card className="flex flex-col gap-4">
          <form onSubmit={addLog} className="flex flex-col gap-3">
            <TextArea
              label="What did you do?"
              rows={2}
              maxLength={NOTE_MAX}
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
            <label className="flex flex-col gap-1">
              <span className="text-small text-ink font-semibold">About (optional)</span>
              <select
                value={link}
                onChange={(event) => setLink(event.target.value)}
                className={SELECT}
              >
                <option value="">Nothing in particular</option>
                {goals
                  .filter((goal) => goal.status === "open")
                  .map((goal) => (
                    <option key={goal.id} value={`goal:${goal.id}`}>
                      Goal: {goal.title}
                    </option>
                  ))}
                {mySkills.map((skill) => (
                  <option key={skill.id} value={`skill:${skill.id}`}>
                    Skill: {skill.name}
                  </option>
                ))}
              </select>
            </label>
            <Button type="submit" className="self-start" disabled={busy || !note.trim()}>
              Add note
            </Button>
          </form>
          <Alert message={errors.logs} />
          {logs.length ? (
            <ol aria-label="Progress notes" className="flex flex-col gap-3">
              {logs.map((log) => {
                const mine = log.author_id === meId;
                const about = log.goal_id
                  ? goalTitleById.get(log.goal_id)
                  : log.skill_id
                    ? skillNameById.get(log.skill_id)
                    : undefined;
                return (
                  <li key={log.id} className="border-line flex flex-col gap-1 border-b pb-3">
                    <p className="text-small text-muted">
                      {mine ? "You" : otherName} ·{" "}
                      <time dateTime={log.created_at} suppressHydrationWarning>
                        {when(log.created_at)}
                      </time>
                      {about ? ` · ${about}` : null}
                    </p>
                    <p className="text-ink break-words whitespace-pre-wrap">{log.note}</p>
                    {mine ? (
                      <Button
                        tone="danger"
                        className="self-start"
                        disabled={busy}
                        onClick={() => deleteLog(log)}
                      >
                        Delete
                      </Button>
                    ) : null}
                  </li>
                );
              })}
            </ol>
          ) : (
            <p className="text-muted">No notes yet.</p>
          )}
        </Card>
      </section>
    </div>
  );
}
