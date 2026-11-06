"use client";
import { useEffect, useState } from "react";
import { salesTasks } from "@/services/live/sales-tasks";
import { salesOutputs } from "@/services/live/sales-outputs";
import type { SalesSchema as S } from "@/services/live/sales-transport";
import { downloadExport } from "@/services/live/exports";
import { OutputPanel, outputPath } from "./output-panel";
import { salesError, type SalesProps } from "./workspace";
import { conversationHomeEnabled } from "../conversation-home";
import { useSalesCapability } from "./capability";
import { FormalDraft } from "./formal-draft";
import { NativeAction } from "./native-action";
export function SalesDocuments({
  client,
  session,
  t,
  navigate,
  pathname,
  native,
  admissionEnabled = conversationHomeEnabled(
    process.env.NEXT_PUBLIC_CONVERSATION_HOME,
  ),
}: {
  admissionEnabled?: boolean;
  pathname?: string;
  native?: S["NativeRef"];
} & Omit<SalesProps, "locale">) {
  const admissionAllowed =
    useSalesCapability(client, session, admissionEnabled) && admissionEnabled;
  const identity = session.identity(),
    api = salesOutputs(client, session);
  const [canEdit, setCanEdit] = useState(false);
  const [rows, setRows] = useState<S["OutputVersion"][]>([]),
    [versions, setVersions] = useState<S["OutputVersion"][]>([]),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [artifact, setArtifact] = useState<S["NativeRef"] | null>(null);
  const artifactId =
    artifact?.id ??
    (typeof window === "undefined"
      ? null
      : new URLSearchParams(window.location.search).get("export"));
  const parts = pathname?.split("/") ?? [],
    id = parts[3],
    revision = parts[4] === "versions" ? Number(parts[5]) : undefined;
  useEffect(() => {
    let active = true;
    void (
      id
        ? api.get(id, revision).then((v) => [v])
        : api.list(native).then((v) => v.items)
    )
      .then((v) => {
        if (active) setRows(v);
      })
      .catch((e) => {
        if (active) setNotice(salesError(e));
      });
    if (id)
      void api
        .permissions(id)
        .then((p) => {
          if (active) setCanEdit(p.can_edit);
        })
        .catch(() => {
          if (active) setCanEdit(false);
        });
    if (id)
      void api
        .versions(id)
        .then((v) => {
          if (active) setVersions(v.outputs);
        })
        .catch(() => {});
    return () => {
      active = false;
    };
  }, [api, id, revision, native]);
  async function run(fn: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setNotice("");
    try {
      await fn();
    } catch (e) {
      if (session.isCurrent(identity)) {
        setNotice(salesError(e));
        setArtifact(null);
      }
    } finally {
      if (session.isCurrent(identity)) setBusy(false);
    }
  }
  async function approveExport(
    output: S["OutputVersion"],
    format: "markdown" | "pdf",
  ) {
    const ref = await api.export(output.id, {
      revision: output.revision,
      format,
      approved: true,
    });
    if (session.isCurrent(identity)) setArtifact(ref);
  }
  return (
    <section className="sales-workspace">
      <h1>{t(native ? "Linked outputs" : "Documents")}</h1>
      {notice && <p role="alert">{t(notice)}</p>}
      {id && (
        <label>
          {t("Revision")}
          <select
            value={revision ?? rows[0]?.revision ?? ""}
            onChange={(e) => navigate(outputPath(id, Number(e.target.value)))}
          >
            {versions.map((v) => (
              <option key={v.revision} value={v.revision}>
                {v.revision}
              </option>
            ))}
          </select>
        </label>
      )}
      {rows.map((o) => (
        <div key={o.id + o.revision}>
          {id ? (
            <>
              {admissionAllowed && (
                <button
                  onClick={() => {
                    salesTasks(client, session).drafts.set("new", {
                      text: "",
                      sources: [
                        {
                          id: o.id,
                          version: o.revision,
                          kind: "output",
                          locator: "output:" + o.id,
                          retention_class: "durable",
                        },
                      ],
                    });
                    navigate("/app/discussions/new");
                  }}
                >
                  {t("New discussion with this output")}
                </button>
              )}
              <OutputPanel output={o} t={t} navigate={navigate} />
              {o.availability === "available" && (
                <>
                  {canEdit && (
                    <NativeAction
                      output={o}
                      api={api}
                      t={t}
                      onSaved={() => setNotice("Saved to buyer")}
                    />
                  )}
                  <p>{t("Export the selected revision?")}</p>
                  {(["markdown", "pdf"] as const).map((format) => (
                    <button
                      key={format}
                      disabled={busy}
                      onClick={() => void run(() => approveExport(o, format))}
                    >
                      {t("Approve export")} · {format.toUpperCase()}
                    </button>
                  ))}
                  {canEdit &&
                    ["outreach_preparation", "followup_preparation"].includes(
                      o.kind,
                    ) && (
                      <FormalDraft
                        {...{ client, session, t, navigate }}
                        output={o}
                      />
                    )}
                </>
              )}
            </>
          ) : (
            <button onClick={() => navigate(outputPath(o.id, o.revision))}>
              {t(o.kind.replaceAll("_", " "))} · {o.revision}
            </button>
          )}
        </div>
      ))}
      {artifactId && (
        <>
          <button
            disabled={busy}
            onClick={() =>
              void run(async () => {
                const blob = await downloadExport(client, session, artifactId);
                if (session.isCurrent(identity)) {
                  const url = URL.createObjectURL(blob),
                    a = document.createElement("a");
                  a.href = url;
                  a.download =
                    blob.type === "application/pdf"
                      ? "report.pdf"
                      : "report.md";
                  a.click();
                  setTimeout(() => URL.revokeObjectURL(url), 1000);
                }
              })
            }
          >
            {t("Open authorised export")}
          </button>
          {admissionAllowed && (
            <button onClick={() => navigate("/app/discussions/new")}>
              {t("New discussion")}
            </button>
          )}
        </>
      )}
    </section>
  );
}
