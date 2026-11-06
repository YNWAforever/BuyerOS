import { useEffect, useRef, useState } from "react";
import { xverumClient } from "@/services/live/xverum";
import type { SalesSchema as S } from "@/services/live/sales-transport";
import { salesTasks } from "@/services/live/sales-tasks";
import { Connections } from "./connections";
import { Content, nativePath } from "./output-panel";
import { salesError, type SalesProps } from "./workspace";
export function EnrichmentReview({
  client,
  session,
  t,
  navigate,
  task,
  onRefresh,
}: {
  task: S["TaskDetail"];
  onRefresh: () => void;
} & Omit<SalesProps, "locale">) {
  const active = useRef(true);
  useEffect(
    () => () => {
      active.current = false;
    },
    [],
  );
  const api = xverumClient(client, session),
    tasks = salesTasks(client, session);
  const [stages, setStages] = useState<S["XverumTaskStage"][]>([]);
  const [connections, setConnections] = useState<S["ConnectionBinding"][]>([]),
    [connection, setConnection] = useState(""),
    [query, setQuery] = useState(""),
    [target, setTarget] = useState<"company" | "people">("company"),
    [quote, setQuote] = useState<S["XverumQuote"] | null>(null),
    [receipt, setReceipt] = useState<S["XverumReceipt"] | null>(null),
    [receiptId, setReceiptId] = useState(""),
    [searchReceipt, setSearchReceipt] = useState(""),
    [candidates, setCandidates] = useState<
      (S["XverumCompanyCard"] | S["XverumPersonCard"])[]
    >([]),
    [selected, setSelected] = useState<string[]>([]),
    [reviewIds, setReviewIds] = useState<string[]>([]),
    [reviewIdentity, setReviewIdentity] = useState(""),
    [previousProposal, setPreviousProposal] = useState<string | null>(null),
    [email, setEmail] = useState(false),
    [proposal, setProposal] = useState<S["EnrichmentProposal"] | null>(null),
    [fields, setFields] = useState<S["EnrichmentApply"]["selected_fields"]>([]),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  useEffect(() => {
    let active = true;
    void Promise.all([api.connections(), api.stages(task.id)])
      .then(([v, s]) => {
        if (active) {
          setConnections(v.connections);
          setStages(s.items);
        }
      })
      .catch((e) => {
        if (active) setNotice(salesError(e));
      });
    return () => {
      active = false;
    };
  }, [api, task.id]);
  async function run(fn: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setNotice("");
    try {
      await fn();
    } catch (e) {
      if (active.current && session.isCurrent(api.identity)) {
        setNotice(salesError(e));
        setCandidates([]);
        setProposal(null);
      }
    } finally {
      if (active.current && session.isCurrent(api.identity)) setBusy(false);
    }
  }
  async function applyReviewedFields() {
    if (!proposal) return;
    const ref = await api.apply({
      proposal_id: proposal.id,
      buyer_version: proposal.buyer_version,
      selected_fields: fields,
    });
    if (!active.current || !session.isCurrent(api.identity)) return;
    const remaining=reviewIds.filter(id=>id!==reviewIdentity);
    setPreviousProposal(proposal.id);
    setReviewIds(remaining);
    setReviewIdentity(remaining[0]??"");
    setProposal(null);
    setFields([]);
    onRefresh();
    if(!remaining.length) navigate(nativePath(ref));
  }
  const buyer = String(task.arguments.buyer_id ?? "");
  return (
    <section>
      <h3>{t("Enrich buyer profile")}</h3>
      {notice && <p role="alert">{t(notice)}</p>}
      {stages.map((stage) => (
        <button
          key={stage.receipt.id}
          disabled={busy}
          onClick={() => {
            const remaining=(stage.selected_ids??[]).filter(id=>!(stage.reviewed_ids??[]).includes(id));
            setReviewIds(remaining);
            setReviewIdentity(remaining[0]??"");
            setPreviousProposal(stage.previous_proposal_id??null);
            setReceiptId(stage.receipt.id);
            setReceipt(stage.receipt);
            setSearchReceipt(
              stage.stage === "search"
                ? stage.receipt.id
                : (stage.search_receipt_id ?? ""),
            );
            setQuote(null);
            setCandidates([]);
            setSelected([]);
            setProposal(null);
            setFields([]);
          }}
        >
          {t("Resume " + stage.stage)}
        </button>
      ))}
      <Connections
        {...{ connections, t }}
        value={connection}
        onChange={(v) => {
          setConnection(v);
          setQuote(null);
        }}
      />
      <label>
        {t("Search")}
        <input
          value={query}
          maxLength={500}
          onChange={(e) => {
            setQuery(e.target.value);
            setQuote(null);
          }}
        />
      </label>
      <label>
        {t("Search for")}
        <select
          value={target}
          onChange={(e) => {
            setTarget(e.target.value as "company" | "people");
            setQuote(null);
          }}
        >
          <option value="company">{t("Company")}</option>
          <option value="people">{t("People")}</option>
        </select>
      </label>
      <button
        disabled={busy || !connection || !buyer || !query.trim()}
        onClick={() =>
          void run(async () => {
            setQuote(
              await api.quoteSearch({
                stage: "search",
                buyer_id: buyer,
                connection_id: connection,
                query,
                target,
                search_receipt_id: null,
                selected_ids: [],
                include_email: false,
              }),
            );
          })
        }
      >
        {t("Review search cost")}
      </button>
      {quote && (
        <>
          <h4>
            {t(
              quote.stage === "search" ? "Search approval" : "Detail approval",
            )}
          </h4>
          <Content value={quote.tool_plan} t={t} />
          <p>
            {t("Maximum provider credits")} {quote.max_credits} · {t("Expires")}{" "}
            {quote.expires_at}
          </p>
          <button
            disabled={busy}
            onClick={() =>
              void run(async () => {
                const key = "quote-approval:" + quote.id;
                let revision = api.recovery.get(key) as number | undefined;
                if (revision === undefined) {
                  revision = (await tasks.get(task.id)).revision;
                  api.recovery.set(key, revision);
                }
                const r = await api.confirm(task.id, quote, revision);
                api.recovery.delete(key);
                if (!active.current) return;
                setReviewIds(quote.stage==="detail"?[...quote.provider_ids]:[]);
                setReviewIdentity(quote.stage==="detail"?(quote.provider_ids[0]??""):"");
                setPreviousProposal(null);
                setReceiptId(r.id);
                if (quote.stage === "search") setSearchReceipt(r.id);
                setQuote(null);
                onRefresh();
              })
            }
          >
            {t("Approve quoted lookup")}
          </button>
        </>
      )}
      {receiptId && (
        <>
          <button
            disabled={busy}
            onClick={() =>
              void run(async () => {
                const r = await api.receipt(receiptId);
                setReceipt(r);
                if (
                  r.dispatch_state === "settled" &&
                  receiptId === searchReceipt
                ) {
                  const c = await api.candidates(receiptId);
                  setCandidates(c.results);
                }
              })
            }
          >
            {t("Check lookup")}
          </button>
          {receipt && (
            <p role="status">
              {t(receipt.dispatch_state.replaceAll("_", " "))} ·{" "}
              {t("Held credits")} {receipt.held_credits} · {t("Used credits")}{" "}
              {receipt.credits_used ?? t("Unknown")}
            </p>
          )}
        </>
      )}
      {candidates.map((c) => (
        <label key={c.id}>
          <input
            type="checkbox"
            checked={selected.includes(c.id)}
            disabled={
              busy || (!selected.includes(c.id) && selected.length >= (target === "company" ? 1 : 3))
            }
            onChange={(e) => {
              setSelected(
                e.target.checked
                  ? [...selected, c.id]
                  : selected.filter((id) => id !== c.id),
              );
              setQuote(null);
            }}
          />
          <Content value={c} t={t} />
        </label>
      ))}
      {candidates.length > 0 && (
        <>
          <label>
            <input
              type="checkbox"
              checked={email}
              disabled={target !== "people"}
              onChange={(e) => {
                setEmail(e.target.checked);
                setQuote(null);
              }}
            />
            {t("Include business email lookup")}
          </label>
          <button
            disabled={busy || !selected.length}
            onClick={() =>
              void run(async () => {
                setQuote(
                  await api.quoteDetails({
                    stage: "detail",
                    buyer_id: null,
                    connection_id: null,
                    query: null,
                    target: null,
                    search_receipt_id: searchReceipt,
                    selected_ids: selected,
                    include_email: email,
                  }),
                );
              })
            }
          >
            {t("Review detail cost")}
          </button>
        </>
      )}
      {reviewIds.length>1 && <label>{t("Person")}<select value={reviewIdentity} onChange={e=>{setReviewIdentity(e.target.value);setProposal(null);setFields([]);}}>{reviewIds.map(id=><option key={id} value={id}>{candidates.map(c=>({id:c.id,name:'full_name' in c?c.full_name:c.company_name})).find(c=>c.id===id)?.name??id}</option>)}</select></label>}
      {receipt?.dispatch_state === "settled" && receiptId !== searchReceipt && (
        <button
          disabled={busy}
          onClick={() =>
            void run(async () => {
              const value = await api.propose({
                buyer_id: buyer,
                receipt_ids: [receiptId],
                selected_id: reviewIdentity || null,
                previous_proposal_id: previousProposal,
                task_id: task.id,
              });
              if (active.current) {
                setProposal(value);
                setFields([]);
              }
            })
          }
        >
          {t("Review fields")}
        </button>
      )}
      {proposal && (
        <>
          <p>{t(proposal.identity_match)}</p>
          {proposal.fields.map((f) => (
            <label key={f.field}>
              <input
                type="checkbox"
                checked={fields.includes(f.field)}
                disabled={
                  busy ||
                  proposal.identity_match !== "resolved" ||
                  f.status === "unknown"
                }
                onChange={(e) =>
                  setFields(
                    e.target.checked
                      ? [...fields, f.field]
                      : fields.filter((x) => x !== f.field),
                  )
                }
              />
              {t(f.field.replaceAll("_", " "))}:{" "}
              {f.existing_value ?? t("Unknown")} →{" "}
              {f.proposed_value ?? t("Unknown")} · {t(f.status)}
            </label>
          ))}
          <p>{t("Selected changes will be visible to the project.")}</p>
          <button
            disabled={
              busy || !fields.length || proposal.identity_match !== "resolved"
            }
            onClick={() => void run(applyReviewedFields)}
          >
            {t("Save selected fields")}
          </button>
        </>
      )}
    </section>
  );
}
