"use client";
import { useEffect, useRef, useState } from "react";
import {
  LiveCancelled,
  LiveError,
  type LiveClient,
} from "@/services/live/client";
import type { SessionScope } from "@/services/live/session";
import { salesTasks } from "@/services/live/sales-tasks";
import { salesOutputs } from "@/services/live/sales-outputs";
import type { SalesSchema as S } from "@/services/live/sales-transport";
import {
  scopedThreadApi,
  type ServerThread,
  type ServerSummary,
} from "@/services/live/conversation-threads";
import { TaskCards, skillTitles, suggestSkill } from "./task-cards";
import { Fields, type Shape } from "./fields";
import { salesInputSchemas } from "@/services/generated/sales-input-schemas";
import { TaskProgress } from "./task-progress";
import { Content, OutputPanel, outputPath } from "./output-panel";
import { EnrichmentReview } from "./enrichment-review";
import { SelectedSources } from "./sources";
import { NativeResearch } from "./native-research";
export type SalesProps = {
  client: LiveClient;
  session: SessionScope;
  t: (s: string) => string;
  locale: "en" | "zh-HK";
  navigate: (s: string) => void;
};
export function salesError(error: unknown) {
  if (error instanceof LiveError) {
    if (error.code === "POLICY_BLOCKED")
      return "Policy does not allow this source or export.";
    if ([401, 403, 404].includes(error.status))
      return "Access is unavailable. Refresh permissions before continuing.";
    if (error.code === "NEEDS_INPUT")
      return "Needs input. Review the current task and add the missing information.";
    if (error.status === 409 || error.status === 412)
      return "This record changed. Review the latest revision before trying again.";
    if (error.status === 503)
      return "Configuration required. Ask an administrator to enable this capability.";
  }
  return "Outcome unknown. Retry the unchanged request to check its saved result.";
}
export function GuidedSales({
  client,
  session,
  t,
  locale,
  navigate,
  thread,
  onThread,
}: {
  thread?: ServerThread;
  onThread?: (row: ServerThread) => void;
} & SalesProps) {
  const api = salesTasks(client, session),
    identity = session.identity(),
    threads = scopedThreadApi(client, session, identity),
    outputs = salesOutputs(client, session);
  const key = thread?.id ?? "new",
    saved = api.drafts.get(key);
  const [text, setText] = useState(saved?.text ?? ""),
    [skill, setSkill] = useState(saved?.skill ?? ""),
    [args, setArgs] = useState<Record<string, S["JsonValue"]>>(
      saved?.arguments ?? {},
    ),
    [sources, setSources] = useState<S["SourceRef"][]>(saved?.sources ?? []);
  const [skills, setSkills] = useState<S["SkillDefinition"][]>([]),
    [task, setTask] = useState<S["TaskDetail"] | null>(null),
    [tasks, setTasks] = useState<S["TaskDetail"][]>([]),
    [result, setResult] = useState<S["OutputVersion"] | null>(null),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [tab, setTab] = useState("Results");
  const [preview, setPreview] = useState<S["ExecutionPreview"] | null>(null),
    [proposal, setProposal] = useState<S["ActionProposal"] | null>(null),
    [review, setReview] = useState<S["ExecutionReview"] | null>(null),
    [events, setEvents] = useState<S["TaskEvent"][]>([]),
    [guidance, setGuidance] = useState<S["CoreGuidance"] | null>(null);
  const [query, setQuery] = useState(""),
    [archived, setArchived] = useState(false),
    [discussions, setDiscussions] = useState<
      (ServerSummary & {
        pinned?: boolean;
        archived?: boolean;
      })[]
    >([]);
  const [outputReview, setOutputReview] = useState<S["OutputReview"] | null>(
      null,
    ),
    [audience, setAudience] = useState<"thread" | "project">("thread");
  const [revoked, setRevoked] = useState(false);
  const mounted = useRef(true),
    lock = useRef(false);
  const readonly = thread?.access === "viewer" || revoked;
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const selectedTask = useRef(saved?.taskId ?? "");
  const taskId = task?.id ?? "";
  const selectionEpoch = useRef(0),
    epoch = selectionEpoch.current;
  const current = () =>
    mounted.current &&
    session.isCurrent(identity) &&
    selectionEpoch.current === epoch;
  const intake = JSON.stringify({ text, skill, arguments: args, sources });
  const [baseline, setBaseline] = useState(saved?.baseline ?? intake);
  const dirty = intake !== baseline;
  function clearReviews() {
    setNotice("");
    setGuidance(null);
    setOutputReview(null);
    setPreview(null);
    setProposal(null);
    setReview(null);
    setResult(null);
    setEvents([]);
  }
  async function selectTask(id: string) {
    selectionEpoch.current++;
    selectedTask.current = id;
    clearReviews();
    setTask(null);
    lock.current = false;
    setBusy(false);
    try {
      const selected = await api.get(id);
      if (
        !mounted.current ||
        !session.isCurrent(identity) ||
        selectedTask.current !== id
      )
        return;
      setTask(selected);
      setSkill(selected.skill_id);
      setArgs(selected.arguments);
      setSources(selected.source_refs);
      setText("");
      setBaseline(
        JSON.stringify({
          text: "",
          skill: selected.skill_id,
          arguments: selected.arguments,
          sources: selected.source_refs,
        }),
      );
      const history = await api.events(id);
      const output = selected.output_ids.length
        ? await outputs.get(selected.output_ids.at(-1)!)
        : null;
      if (
        mounted.current &&
        session.isCurrent(identity) &&
        selectedTask.current === id
      ) {
        setEvents(history.events);
        setResult(output);
      }
    } catch (e) {
      if (selectedTask.current === id) setNotice(salesError(e));
    }
  }
  useEffect(() => {
    api.drafts.set(key, {
      text,
      skill,
      arguments: args,
      sources,
      taskId: selectedTask.current,
      baseline,
    });
  }, [api, key, text, skill, args, sources, baseline, taskId]);
  useEffect(() => {
    const unload = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", unload);
    return () => window.removeEventListener("beforeunload", unload);
  }, [dirty]);
  // The shell invokes the same guard for links, history traversal and scope changes.
  useEffect(
    () =>
      session.registerTransitionGuard(
        async (proceed) => {
          if (dirty && !window.confirm(t("Keep unsent text and continue?")))
            return false;
          await proceed();
          return true;
        },
        () => dirty,
      ),
    [session, dirty, t],
  );
  useEffect(() => {
    let active = true;
    void api
      .skills()
      .then((v) => {
        if (active) setSkills(v.skills);
      })
      .catch((e) => {
        if (active) setNotice(salesError(e));
      });
    if (thread)
      void api
        .list(thread.id)
        .then((v) => {
          if (active) {
            setTasks(v.items);
            const last = saved
              ? v.items.find((x) => x.id === saved.taskId)
              : v.items.at(-1);
            if (last && selectionEpoch.current === 0) {
              selectedTask.current = last.id;
              setTask(last);
              if (!saved) {
                setSkill(last.skill_id);
                setArgs(last.arguments);
                setSources(last.source_refs);
                setBaseline(
                  JSON.stringify({
                    text: "",
                    skill: last.skill_id,
                    arguments: last.arguments,
                    sources: last.source_refs,
                  }),
                );
              }
            }
          }
        })
        .catch((e) => {
          if (active) setNotice(salesError(e));
        });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Keyed thread mount owns this initial read; later reads are explicit.
  }, [api, thread?.id]); // scoped remount owns initial draft
  useEffect(() => {
    if (thread) return;
    let active = true;
    void threads
      .search(query, archived)
      .then((v) => {
        if (active) setDiscussions(v.items);
      })
      .catch((e) => {
        if (active) setNotice(salesError(e));
      });
    return () => {
      active = false;
    };
  }, [threads, query, archived, thread]);
  async function run(action: () => Promise<void>) {
    if (lock.current || !current()) return;
    lock.current = true;
    setBusy(true);
    setNotice("");
    try {
      await action();
    } catch (e) {
      if (current() && !(e instanceof LiveCancelled)) {
        setNotice(salesError(e));
        if (e instanceof LiveError && [403, 404].includes(e.status)) {
          setResult(null);
          setEvents([]);
          setTask(null);
          setTasks([]);
          setSources([]);
          setArgs({});
          setRevoked(true);
        }
        if (task && e instanceof LiveError && e.status === 409) {
          const latest = await api.get(task.id).catch(() => null);
          if (current() && latest) {
            setOutputReview(null);
            setTask(latest);
            setPreview(null);
            setReview(null);
          }
        }
      }
    } finally {
      if (current()) {
        lock.current = false;
        setBusy(false);
      }
    }
  }
  async function refresh(id = task?.id) {
    if (!id) return;
    const [latest, history] = await Promise.all([api.get(id), api.events(id)]);
    if (!current()) return;
    setTask(latest);
    setEvents(history.events);
    if (latest.output_ids.length) {
      const output = await outputs.get(latest.output_ids.at(-1)!);
      if (current()) setResult(output);
    }
  }
  function choose(id: string) {
    selectionEpoch.current++;
    lock.current = false;
    setBusy(false);
    selectedTask.current = "";
    clearReviews();
    setText((v) => v || t(skillTitles[id] ?? id));
    setSkill(id);
    setTask(null);
    setOutputReview(null);
    setResult(null);
    setArgs({});
    setPreview(null);
    setReview(null);
  }
  async function start() {
    if (readonly || !skill || !text.trim()) return;
    let row =
      thread ?? (api.recovery.get("new-thread") as ServerThread | undefined);
    if (!row) {
      row = await threads.create(text.slice(0, 80));
      if (!current()) return;
      api.recovery.set("new-thread", row);
    }
    const input = {
      thread_id: row.id,
      skill_id: skill,
      skill_version: "1",
      user_message: text,
      source_refs: sources,
      arguments: { ...args, language: locale },
    } as S["TaskInput"];
    const created = await api.start(input, row.version);
    if (!current()) return;
    selectedTask.current = created.id;
    setTask(created);
    setBaseline(JSON.stringify({ text: "", skill, arguments: args, sources }));
    setTasks((v) => [...v, created]);
    setText("");
    api.drafts.delete(key);
    api.recovery.delete("new-thread");
    setNotice("Saved to discussion");
    onThread?.(await threads.get(row.id));
    if (!thread) navigate(`/app/discussions/s/${row.id}`);
  }
  async function followup() {
    if (!task || readonly) return;
    const next = await api.followup(
      task.id,
      {
        user_message: text,
        arguments: { ...args, language: locale },
        source_refs: sources,
      },
      task.revision,
    );
    if (current()) {
      setGuidance(null);
      setOutputReview(null);
      setTask(next);
      setBaseline(
        JSON.stringify({ text: "", skill, arguments: args, sources }),
      );
      setText("");
      setPreview(null);
      setReview(null);
      setNotice("Saved to discussion");
    }
  }
  async function modelPreview() {
    if (!task) return;
    const definition = skills.find((s) => s.id === task.skill_id),
      capability = definition?.allowed_actions.find(
        (x) => !x.endsWith("_xverum"),
      );
    if (!capability) return;
    const p = {
      id: crypto.randomUUID(),
      capability,
      arguments: {
        refs: [],
        purpose: task.intake.at(-1)?.user_message ?? text,
      },
      source_versions: task.source_refs,
    } as S["ActionProposal"];
    const v = await api.preview(task.id, p);
    if (current()) {
      setProposal(p);
      setPreview(v);
      setReview(null);
    }
  }
  const definition = skills.find((s) => s.id === skill),
    editableIntake =
      task && ["needs_input", "ready_for_review"].includes(task.state);
  return (
    <section className="sales-workspace" aria-label={t("Guided sales")}>
      {!thread && <h1>{t("What would you like to accomplish?")}</h1>}
      {notice && <p role="alert">{t(notice)}</p>}
      {!thread && (
        <>
          <label>
            {t("Search discussions")}
            <input value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>
          <label>
            <input
              type="checkbox"
              checked={archived}
              onChange={(e) => setArchived(e.target.checked)}
            />
            {t("Archived")}
          </label>
          <ul>
            {discussions.map((d) => (
              <li key={d.id}>
                <button onClick={() => navigate(`/app/discussions/s/${d.id}`)}>
                  {d.title}
                </button>
                <button
                  onClick={() =>
                    void run(async () => {
                      await threads.preferences(d.id, !d.pinned, !!d.archived);
                      setDiscussions((v) =>
                        v.map((x) =>
                          x.id === d.id ? { ...x, pinned: !d.pinned } : x,
                        ),
                      );
                    })
                  }
                >
                  {t(d.pinned ? "Unpin" : "Pin")}
                </button>
                <button
                  onClick={() =>
                    void run(async () => {
                      await threads.preferences(d.id, !!d.pinned, !d.archived);
                      setDiscussions((v) => v.filter((x) => x.id !== d.id));
                    })
                  }
                >
                  {t(d.archived ? "Resume" : "Archive")}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {thread && tasks.length > 0 && (
        <label>
          {t("Saved tasks")}
          <select
            value={task?.id ?? ""}
            onChange={(e) => void selectTask(e.target.value)}
          >
            {tasks.map((v) => (
              <option key={v.id} value={v.id}>
                {t(skillTitles[v.skill_id] ?? v.skill_id)} ·{" "}
                {v.message_sequence}
              </option>
            ))}
          </select>
        </label>
      )}
      <div className="sales-layout">
        <div>
          {task && <TaskProgress task={task} t={t} />}
          {!readonly && (
            <>
              <label>
                {t("Describe your task")}
                <textarea
                  maxLength={4000}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
              </label>
              <button
                disabled={busy || !text.trim()}
                onClick={() => {
                  selectionEpoch.current++;
                  selectedTask.current = "";
                  clearReviews();
                  setSkill(suggestSkill(text, skills, t));
                  setTask(null);
                }}
              >
                {t("Review task")}
              </button>
              <label>
                {t("Chosen skill")}
                <select value={skill} onChange={(e) => choose(e.target.value)}>
                  <option value="">{t("Choose")}</option>
                  {skills.map((s) => (
                    <option key={s.id} value={s.id}>
                      {t(skillTitles[s.id] ?? s.id)}
                    </option>
                  ))}
                </select>
              </label>
              {definition && (
                <Fields
                  schema={salesInputSchemas[definition.id] as Shape}
                  value={args}
                  onChange={setArgs}
                  t={t}
                  disabled={busy}
                />
              )}
              <SelectedSources
                {...{ client, session, t, navigate, sources, setSources }}
                disabled={busy}
                onNativeSelect={(ref) => {
                  const shape = salesInputSchemas[
                    skill as keyof typeof salesInputSchemas
                  ] as Shape | undefined;
                  if (ref.kind === "buyer" && shape?.properties?.buyer_id)
                    setArgs((v) => ({ ...v, buyer_id: ref.id }));
                  if (ref.kind === "profile" && shape?.properties?.profile_id)
                    setArgs((v) => ({
                      ...v,
                      profile_id: ref.id,
                      ...(shape.properties?.profile_version
                        ? { profile_version: ref.version }
                        : {}),
                    }));
                }}
              />
              {!task && (
                <button
                  disabled={busy || !skill || !text.trim()}
                  onClick={() => void run(start)}
                >
                  {t("Save task")}
                </button>
              )}
              {editableIntake && (
                <button
                  disabled={busy || !text.trim()}
                  onClick={() => void run(followup)}
                >
                  {t("Save follow-up")}
                </button>
              )}
            </>
          )}
          {task && (
            <>
              <button disabled={busy} onClick={() => void run(() => refresh())}>
                {t("Refresh task")}
              </button>
              {!readonly && (
                <>
                  <button
                    disabled={
                      busy ||
                      ![
                        "needs_input",
                        "ready_for_review",
                        "partially_completed",
                        "completed",
                      ].includes(task.state)
                    }
                    onClick={() =>
                      void run(async () => {
                        const out = await api.prepare(task.id, task.revision);
                        if (current()) setResult(out);
                        await refresh();
                      })
                    }
                  >
                    {t("Prepare and save output")}
                  </button>
                  <button
                    disabled={busy}
                    onClick={() =>
                      void run(async () => {
                        const g = await api.guidance(task.id);
                        if (current()) setGuidance(g);
                      })
                    }
                  >
                    {t("Review next action")}
                  </button>
                  {guidance?.action.operation_id === "startRun" && (
                    <NativeResearch
                      key={task.id}
                      {...{ client, session, t, navigate, task, guidance }}
                      onSaved={() =>
                        void run(async () => {
                          if (thread) onThread?.(await threads.get(thread.id));
                          await refresh();
                        })
                      }
                    />
                  )}
                  {guidance && (
                    <>
                      <Content value={guidance.work} t={t} />
                      <Content value={guidance.missing_inputs} t={t} />
                      <button
                        onClick={() =>
                          navigate(
                            guidance.action.operation_id === "startRun"
                              ? "/app/runs"
                              : guidance.action.operation_id === "generateDraft"
                                ? "/app/outreach"
                                : guidance.action.operation_id ===
                                    "changeListMemberships"
                                  ? "/app/discover"
                                  : "/app/discover/edit",
                          )
                        }
                      >
                        {t("Open native review")}
                      </button>
                    </>
                  )}
                  <button
                    disabled={busy || task.state !== "ready_for_review"}
                    onClick={() => void run(modelPreview)}
                  >
                    {t("Review model cost")}
                  </button>
                  <button
                    disabled={busy}
                    onClick={() =>
                      void run(async () => {
                        const value = await outputs.review(task.id);
                        if (current()) {
                          setOutputReview(value);
                          setAudience("thread");
                        }
                      })
                    }
                  >
                    {t("Review output for saving")}
                  </button>
                  {outputReview && (
                    <section>
                      <Content value={outputReview.candidate.content} t={t} />
                      <label>
                        {t("Audience")}
                        <select
                          value={audience}
                          onChange={(e) =>
                            setAudience(e.target.value as "thread" | "project")
                          }
                        >
                          <option value="thread">
                            {t("Discussion audience")}
                          </option>
                          <option value="project">
                            {t("Project audience")}
                          </option>
                        </select>
                      </label>
                      {audience === "project" && (
                        <p>
                          {t(
                            "Selected changes will be visible to the project.",
                          )}
                        </p>
                      )}
                      <button
                        disabled={busy}
                        onClick={() =>
                          void run(async () => {
                            const out = await outputs.save({
                              task_id: outputReview.task_id,
                              expected_task_revision:
                                outputReview.task_revision,
                              candidate: outputReview.candidate,
                              visibility: audience,
                            });
                            if (current()) {
                              setResult(out);
                              setOutputReview(null);
                            }
                            await refresh();
                          })
                        }
                      >
                        {t("Save reviewed output")}
                      </button>
                    </section>
                  )}
                  {preview && proposal && (
                    <section>
                      <h3>{t("Model cost review")}</h3>
                      <p>
                        {preview.model_id} · {preview.route}
                      </p>
                      <p>
                        {t("Maximum USD")} {preview.max_liability_usd} ·{" "}
                        {preview.max_calls} {t("calls")}
                      </p>
                      {!review ? (
                        <button
                          disabled={busy}
                          onClick={() =>
                            void run(async () => {
                              const r = await api.review(
                                task.id,
                                { proposal, fingerprint: preview.fingerprint },
                                preview.revision,
                              );
                              if (current()) setReview(r);
                            })
                          }
                        >
                          {t("Approve this cost")}
                        </button>
                      ) : (
                        <>
                          <p>
                            {t("Expires")} {review.expires_at}
                          </p>
                          <button
                            disabled={busy}
                            onClick={() =>
                              void run(async () => {
                                await api.admit(
                                  task.id,
                                  { proposal, review_id: review.id },
                                  review.revision,
                                );
                                setPreview(null);
                                setReview(null);
                                await refresh();
                              })
                            }
                          >
                            {t("Start reviewed work")}
                          </button>
                        </>
                      )}
                    </section>
                  )}
                  {!["completed", "cancelled"].includes(task.state) && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          await api.cancel(task.id, task.revision);
                          await refresh();
                        })
                      }
                    >
                      {t("Cancel task")}
                    </button>
                  )}
                  {task.skill_id === "sales-contacts" && (
                    <EnrichmentReview
                      key={task.id}
                      {...{ client, session, t, navigate, task }}
                      onRefresh={() => void run(() => refresh())}
                    />
                  )}
                </>
              )}
            </>
          )}
          {!readonly && <TaskCards skills={skills} t={t} onSelect={choose} />}
        </div>
        <aside>
          <div role="group" aria-label={t("Output views")}>
            {["Results", "Sources", "Decisions"].map((x) => (
              <button
                key={x}
                aria-pressed={tab === x}
                onClick={() => setTab(x)}
              >
                {t(x)}
              </button>
            ))}
          </div>
          {tab === "Results" &&
            (result ? (
              <>
                <OutputPanel output={result} t={t} navigate={navigate} />
                <button
                  onClick={() =>
                    navigate(outputPath(result.id, result.revision))
                  }
                >
                  {t("Open saved output")}
                </button>
              </>
            ) : (
              task?.output_ids.map((id) => (
                <button key={id} onClick={() => navigate(outputPath(id))}>
                  {t("Open saved output")}
                </button>
              ))
            ))}
          {tab === "Sources" && (
            <Content value={task?.source_refs ?? sources} t={t} />
          )}
          {tab === "Decisions" && <Content value={events} t={t} />}
        </aside>
      </div>
    </section>
  );
}
