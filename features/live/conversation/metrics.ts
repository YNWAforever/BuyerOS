/**
 * Increment 3.6: bounded per-project turn metrics and budget honesty.
 *
 * The server returns aggregates only; this module validates the shape strictly
 * (an unexpected or missing field is never rendered as a number) and formats it
 * for the context-panel dashboard. Money/credits are formatted from server
 * decimal strings — the UI never invents a tariff or a conversion.
 */
export const METRICS_WINDOW_DAYS = 7;
const MAX_DAYS = 30;
const STATUSES = ['completed', 'needs_input', 'needs_approval', 'failed',
  'outcome_unknown', 'cancelled'] as const;
export type TurnStatusRow = (typeof STATUSES)[number];
export type TurnMetrics = {
  window_days: number;
  generated_at: string;
  turns: { total: number; by_status: Partial<Record<TurnStatusRow, number>> };
  latency_ms: { samples: number; p50: number | null; p95: number | null; max: number | null };
  proposals: {
    total: number;
    by_capability: Record<string, number>;
    by_decision: Record<string, number>;
    awaiting_decision: number;
  };
  tool_activity: { by_state: Record<string, number>; outcome_unknown: number };
  model: { unavailable_turns: number };
  budget: {
    priced_proposals: number;
    unknown_price_proposals: number;
    no_cost_proposals: number;
    may_incur_provider_charges: number;
    estimated: { unit: string; amount: string }[];
  };
};
export class MetricsUnverified extends Error {}
function check(value: unknown): asserts value { if (!value) throw new MetricsUnverified(); }
function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function count(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) >= 0;
}
function counts(value: unknown, allowed?: readonly string[]): Record<string, number> {
  check(object(value));
  const rows: Record<string, number> = {};
  for (const [key, item] of Object.entries(value)) {
    check(count(item) && (!allowed || allowed.includes(key)));
    rows[key] = item as number;
  }
  return rows;
}
function latency(value: unknown): number | null {
  if (value === null) return null;
  check(count(value));
  return value as number;
}
function amount(value: unknown): string {
  check(typeof value === 'string' && /^\d+(\.\d{1,4})?$/.test(value));
  return value as string;
}
/** `/v1/workspaces/{ws}/projects/{pj}/conversation-turns/metrics?window_days=N` */
export function metricsPath(workspace: string, project: string, windowDays = METRICS_WINDOW_DAYS): string | null {
  if (!workspace.trim() || !project.trim()) return null;
  const days = Number.isSafeInteger(windowDays) && windowDays >= 1 && windowDays <= MAX_DAYS
    ? windowDays : METRICS_WINDOW_DAYS;
  return `/v1/workspaces/${encodeURIComponent(workspace)}/projects/${encodeURIComponent(project)}` +
    `/conversation-turns/metrics?window_days=${days}`;
}
export function readTurnMetrics(value: unknown): TurnMetrics {
  check(object(value));
  const turns = value.turns, latencyMs = value.latency_ms, proposals = value.proposals;
  const tool = value.tool_activity, model = value.model, budget = value.budget;
  check(count(value.window_days) && value.window_days >= 1 && value.window_days <= MAX_DAYS);
  check(typeof value.generated_at === 'string' && value.generated_at.length <= 64);
  check(object(turns) && count(turns.total));
  const byStatus = counts(turns.by_status, STATUSES);
  check(Object.values(byStatus).reduce((sum, row) => sum + row, 0) === turns.total);
  check(object(latencyMs) && count(latencyMs.samples));
  check(object(proposals) && count(proposals.total) && count(proposals.awaiting_decision));
  const byDecision = counts(proposals.by_decision);
  const byCapability = counts(proposals.by_capability);
  check(object(tool) && count(tool.outcome_unknown));
  const byState = counts(tool.by_state);
  check(object(model) && count(model.unavailable_turns));
  check(object(budget) && count(budget.priced_proposals) &&
    count(budget.unknown_price_proposals) && count(budget.no_cost_proposals) &&
    count(budget.may_incur_provider_charges) && Array.isArray(budget.estimated));
  const estimated = budget.estimated.map((row) => {
    check(object(row) && (row.unit === 'USD' || row.unit === 'credits'));
    return { unit: row.unit as string, amount: amount(row.amount) };
  });
  return {
    window_days: value.window_days as number,
    generated_at: value.generated_at as string,
    turns: { total: turns.total as number, by_status: byStatus as TurnMetrics['turns']['by_status'] },
    latency_ms: {
      samples: latencyMs.samples as number,
      p50: latency(latencyMs.p50), p95: latency(latencyMs.p95), max: latency(latencyMs.max),
    },
    proposals: {
      total: proposals.total as number, by_capability: byCapability,
      by_decision: byDecision, awaiting_decision: proposals.awaiting_decision as number,
    },
    tool_activity: { by_state: byState, outcome_unknown: tool.outcome_unknown as number },
    model: { unavailable_turns: model.unavailable_turns as number },
    budget: {
      priced_proposals: budget.priced_proposals as number,
      unknown_price_proposals: budget.unknown_price_proposals as number,
      no_cost_proposals: budget.no_cost_proposals as number,
      may_incur_provider_charges: budget.may_incur_provider_charges as number,
      estimated,
    },
  };
}
/** Honest duration: no sample renders an em dash, never "0 ms". */
export function formatLatency(ms: number | null, locale: 'en' | 'zh-HK' = 'en'): string {
  if (ms === null) return '—';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const seconds = ms / 1000;
  const text = seconds >= 10 ? String(Math.round(seconds)) : seconds.toFixed(1);
  return locale === 'zh-HK' ? `${text} 秒` : `${text} s`;
}
/** Server decimal string -> display string; keeps exact precision, trims zeros. */
export function formatMetricAmount(value: string): string {
  if (!/^\d+(\.\d{1,4})?$/.test(value)) return '—';
  const [whole, fraction] = value.split('.');
  const trimmed = (fraction ?? '').replace(/0+$/, '');
  return trimmed ? `${whole}.${trimmed}` : whole;
}
/** Rows for the status breakdown, in contract order, zero rows first-class. */
export function statusRows(metrics: TurnMetrics): { status: TurnStatusRow; count: number }[] {
  return STATUSES.map((status) => ({ status, count: metrics.turns.by_status[status] ?? 0 }));
}
export function hasTurnSamples(metrics: TurnMetrics): boolean {
  return metrics.turns.total > 0 && metrics.latency_ms.samples > 0;
}
