"use client";

import { useState, type FormEvent } from "react";

import { ReportButton } from "@/components/safety/report-button";
import { Button } from "@/components/ds/button";
import { InlineError, Input, Textarea } from "@/components/ds/fields";
import { Panel, TopicChip } from "@/components/ds/surfaces";
import { cx } from "@/components/ui/cx";
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

// The API's limits (GOAL_TITLE_MAX_LENGTH, SKILL_NAME_MAX_LENGTH, LOG_NOTE_MAX_LENGTH).
const TITLE_MAX = 120;
const SKILL_MAX = 60;
const NOTE_MAX = 500;

const SELECT = cx(
  "rounded-input border-muted-2 bg-bg text-ink min-h-11 w-full border px-3 text-[16px] sm:text-body",
  "focus:border-green",
);

/** Section headings in the display face, at the shared display tracking. */
const SECTION_HEADING = "font-display tracking-display text-[20px] leading-tight font-extrabold";

function Alert({ message }: { message: string | null }) {
  return message ? <InlineError announce>{message}</InlineError> : null;
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
        <h2 id="goals-h" className={SECTION_HEADING}>
          Shared goals
        </h2>
        <Panel className="flex flex-col gap-4">
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
                      className="accent-green size-4 shrink-0"
                    />
                    <span
                      className={goal.status === "done" ? "text-muted line-through" : "text-ink"}
                    >
                      {goal.title}
                      {goal.due_on ? (
                        <span className="text-meta-lg text-muted"> · due {goal.due_on}</span>
                      ) : null}
                    </span>
                  </label>
                  <div className="flex flex-wrap items-center gap-3">
                    {goal.created_by !== meId ? (
                      <ReportButton
                        kind="goal"
                        targetId={goal.id}
                        blockUserId={otherId}
                        blockName={otherName}
                        compact
                      />
                    ) : null}
                    <Button
                      variant="danger"
                      size="compact"
                      disabled={busy}
                      onClick={() => deleteGoal(goal)}
                    >
                      Delete
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted">No goals yet. Add one you both want to reach.</p>
          )}
          <form onSubmit={addGoal} className="flex flex-col gap-3">
            <Input
              label="New goal"
              maxLength={TITLE_MAX}
              value={goalTitle}
              onChange={(event) => setGoalTitle(event.target.value)}
              placeholder="Ship the first version"
            />
            <Input
              label="Due date (optional)"
              type="date"
              value={goalDue}
              onChange={(event) => setGoalDue(event.target.value)}
            />
            <Button
              type="submit"
              variant="outline"
              className="self-start"
              disabled={busy || !goalTitle.trim()}
            >
              Add goal
            </Button>
          </form>
          <Alert message={errors.goals} />
        </Panel>
      </section>

      <section aria-labelledby="skills-h" className="flex flex-col gap-3">
        <h2 id="skills-h" className={SECTION_HEADING}>
          Skills to grow
        </h2>
        <Panel className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <h3 className="text-title text-ink">You</h3>
            {mySkills.length ? (
              <ul className="flex flex-wrap gap-2">
                {mySkills.map((skill) => (
                  <li key={skill.id} className="flex items-center gap-1">
                    <TopicChip>{skill.name}</TopicChip>
                    <Button
                      variant="ghost"
                      size="compact"
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
              <p className="text-meta-lg text-muted">Add a skill you want to get better at.</p>
            )}
            <form onSubmit={addSkill} className="flex flex-col gap-3">
              <Input
                label="A skill you want to grow"
                maxLength={SKILL_MAX}
                value={skillName}
                onChange={(event) => setSkillName(event.target.value)}
                placeholder="Public speaking"
              />
              <Button
                type="submit"
                variant="outline"
                className="self-start"
                disabled={busy || !skillName.trim()}
              >
                Add skill
              </Button>
            </form>
          </div>
          <div className="flex flex-col gap-2">
            <h3 className="text-title text-ink">{otherName}</h3>
            {theirSkills.length ? (
              <ul className="flex flex-wrap gap-2">
                {theirSkills.map((skill) => (
                  <li key={skill.id}>
                    <TopicChip tone="soft">{skill.name}</TopicChip>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-meta-lg text-muted">No skills added yet.</p>
            )}
          </div>
          <Alert message={errors.skills} />
        </Panel>
      </section>

      <section aria-labelledby="logs-h" className="flex flex-col gap-3">
        <h2 id="logs-h" className={SECTION_HEADING}>
          Progress notes
        </h2>
        <Panel className="flex flex-col gap-4">
          <form onSubmit={addLog} className="flex flex-col gap-3">
            <Textarea
              label="What did you do?"
              rows={2}
              maxLength={NOTE_MAX}
              showCounter={false}
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
            <label className="flex flex-col gap-1">
              <span className="text-meta-lg text-ink font-medium">About (optional)</span>
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
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-meta-lg text-muted">
                Notes are deleted {space.retention_days} days after they&apos;re written.
              </p>
              <Button type="submit" variant="outline" disabled={busy || !note.trim()}>
                Add note
              </Button>
            </div>
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
                    <p className="text-meta-lg text-muted">
                      {mine ? "You" : otherName} ·{" "}
                      <time dateTime={log.created_at} suppressHydrationWarning>
                        {when(log.created_at)}
                      </time>
                      {about ? ` · ${about}` : null}
                    </p>
                    <p className="text-ink break-words whitespace-pre-wrap">{log.note}</p>
                    {mine ? (
                      <Button
                        variant="danger"
                        size="compact"
                        className="self-start"
                        disabled={busy}
                        onClick={() => deleteLog(log)}
                      >
                        Delete
                      </Button>
                    ) : (
                      <ReportButton
                        kind="note"
                        targetId={log.id}
                        blockUserId={otherId}
                        blockName={otherName}
                        compact
                      />
                    )}
                  </li>
                );
              })}
            </ol>
          ) : (
            <p className="text-muted">No notes yet.</p>
          )}
        </Panel>
      </section>
    </div>
  );
}
