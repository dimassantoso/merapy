import { useMemo } from "preact/hooks";
import {
  CLEAN_JOB,
  RETRY_ALL_JOB,
  STOP_ALL_JOB,
  getGraphQLUrl,
  gql,
  type Task,
} from "../lib/graphql";
import { useRouter } from "../lib/router";
import { useStats } from "../lib/StatsContext";

interface Props {
  searchQuery: string;
}

function fmtMem(mb: number | undefined): string {
  if (mb == null) return "—";
  const bytes = mb * 1024 * 1024;
  if (bytes < 1024) return `${bytes.toFixed(0)} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  if (bytes < 1024 ** 4) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  return `${(bytes / 1024 ** 4).toFixed(2)} TB`;
}

function dominantStatus(task: Task): { cls: string; label: string } {
  if (task.detail.failure > 0) return { cls: "neg", label: `${task.detail.failure} failed` };
  if (task.detail.retrying > 0) return { cls: "run", label: `${task.detail.retrying} running` };
  if (task.detail.queueing > 0) return { cls: "", label: `${task.detail.queueing} queued` };
  if (task.detail.stopped > 0) return { cls: "warn", label: `${task.detail.stopped} stopped` };
  if (task.detail.success > 0) return { cls: "pos", label: "Healthy" };
  return { cls: "", label: "Idle" };
}

export function DashboardPage({ searchQuery }: Props) {
  const { push } = useRouter();
  const { tasks, stats, clientCount, loading, error } = useStats();

  const totals = useMemo(
    () =>
      tasks.reduce(
        (acc, t) => ({
          total: acc.total + t.detail.queueing + t.detail.retrying + t.detail.success + t.detail.failure + t.detail.stopped,
          queueing: acc.queueing + t.detail.queueing,
          retrying: acc.retrying + t.detail.retrying,
          success: acc.success + t.detail.success,
          failure: acc.failure + t.detail.failure,
          stopped: acc.stopped + t.detail.stopped,
        }),
        { total: 0, queueing: 0, retrying: 0, success: 0, failure: 0, stopped: 0 }
      ),
    [tasks]
  );

  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return tasks;
    return tasks.filter(
      (t) => t.name.toLowerCase().includes(q) || t.module_name.toLowerCase().includes(q)
    );
  }, [tasks, searchQuery]);

  const firstFailedTask = useMemo(() => tasks.find((t) => t.detail.failure > 0), [tasks]);

  const shortCommit = stats?.git_commit
    ? stats.git_commit.length > 10
      ? stats.git_commit.slice(0, 7)
      : stats.git_commit
    : "—";
  const buildDate = stats?.build_date
    ? stats.build_date.includes("T")
      ? stats.build_date.split("T")[0]
      : stats.build_date
    : "—";

  const segments = useMemo(() => {
    if (totals.total === 0) return [];
    const items = [
      { key: "Running", count: totals.retrying, color: "var(--chart-1)" },
      { key: "Success", count: totals.success, color: "var(--chart-2)" },
      { key: "Queued", count: totals.queueing, color: "var(--chart-muted)" },
      { key: "Stopped", count: totals.stopped, color: "var(--chart-3)" },
      { key: "Failed", count: totals.failure, color: "var(--negative)" },
    ];
    return items.filter((s) => s.count > 0);
  }, [totals]);

  const serviceName = stats?.service_name || "Task Queue";

  return (
    <>
      {/* Title row + one finding */}
      <div className="title-row">
        <div className="title-block">
          <div className="title-heading-line">
            <h1 className="page-title">{serviceName}</h1>
            <span className={`pill ${totals.failure > 0 ? "neg" : totals.retrying > 0 ? "run" : "pos"}`}>
              <span className="pill-dot" aria-hidden="true" />
              {totals.failure > 0 ? "Needs attention" : totals.retrying > 0 ? "Processing" : "Healthy"}
            </span>
          </div>
          <p className="page-sub">
            {totals.failure > 0 && firstFailedTask ? (
              <>
                <span className="finding-neg">{totals.failure} failed job{totals.failure === 1 ? "" : "s"}</span>
                {` — ${firstFailedTask.name} ready for retry across ${tasks.length} registered queue${tasks.length === 1 ? "" : "s"}.`}
              </>
            ) : totals.retrying > 0 ? (
              <>
                <span className="finding-accent">{totals.retrying} job{totals.retrying === 1 ? "" : "s"} running</span>
                {` with ${totals.queueing} queued across ${tasks.length} registered queue${tasks.length === 1 ? "" : "s"}.`}
              </>
            ) : (
              `${tasks.length} registered queue${tasks.length === 1 ? "" : "s"} · ${totals.total} total jobs tracked.`
            )}
          </p>
        </div>

        {firstFailedTask && (
          <div className="title-actions">
            <button
              type="button"
              className="btn"
              onClick={() => push(`/task?task_name=${encodeURIComponent(firstFailedTask.name)}&statuses=FAILURE`)}
            >
              Inspect failed jobs
            </button>
          </div>
        )}
      </div>

      {error && tasks.length === 0 && (
        <div className="error-inline">
          <span>Cannot reach task queue GraphQL endpoint ({getGraphQLUrl()}): {error}</span>
          <button type="button" className="btn sm" onClick={() => window.location.reload()}>
            Retry
          </button>
        </div>
      )}

      {/* Live Worker Node lead card (deploy metadata left, 4 runtime cells right) */}
      <section className="worker-lead" aria-label="Worker deployment and runtime">
        <div className="worker-lead-meta">
          <div className="worker-lead-title">
            <span>{stats?.service_version ? `Release ${stats.service_version}` : "Active worker node"}</span>
            {stats?.build_number && <span className="pill">Build #{stats.build_number}</span>}
          </div>
          <div className="worker-lead-sub">
            <span className="mono">{shortCommit}</span>
            <span>·</span>
            <span>merapy {stats?.merapy_version || "—"}</span>
            <span>·</span>
            <span>Built {buildDate}</span>
          </div>
        </div>

        <div className="worker-lead-cells">
          <div className="worker-cell">
            <span className="worker-cell-label">RSS memory</span>
            <span className="worker-cell-val num">{fmtMem(stats?.memory_rss_mb)}</span>
          </div>
          <div className="worker-cell">
            <span className="worker-cell-label">Memory share</span>
            <span className="worker-cell-val num">
              {stats?.memory_percent != null ? `${stats.memory_percent}%` : "—"}
            </span>
          </div>
          <div className="worker-cell">
            <span className="worker-cell-label">CPU usage</span>
            <span className="worker-cell-val num">
              {stats?.cpu_percent != null ? `${stats.cpu_percent}%` : "—"}
            </span>
          </div>
          <div className="worker-cell">
            <span className="worker-cell-label">Live clients</span>
            <span className="worker-cell-val num">{clientCount || 1}</span>
          </div>
        </div>
      </section>

      {/* Divided KPI strip + Signature 100% Queue Composition Bar */}
      <section className="health-panel" aria-label="Queue job totals">
        <div className="kpi-strip">
          <div className="kpi-cell">
            <span className="kpi-label">Total jobs</span>
            <span className="kpi-value lead num">{totals.total}</span>
          </div>
          <div className="kpi-cell">
            <span className="kpi-label">Running</span>
            <span className={`kpi-value num ${totals.retrying > 0 ? "accent" : "zero"}`}>{totals.retrying}</span>
          </div>
          <div className="kpi-cell">
            <span className="kpi-label">Queued</span>
            <span className={`kpi-value num ${totals.queueing === 0 ? "zero" : ""}`}>{totals.queueing}</span>
          </div>
          <div className="kpi-cell">
            <span className="kpi-label">Succeeded</span>
            <span className={`kpi-value num ${totals.success === 0 ? "zero" : ""}`}>{totals.success}</span>
          </div>
          <div className="kpi-cell">
            <span className="kpi-label">Failed</span>
            <span className={`kpi-value num ${totals.failure > 0 ? "neg" : "zero"}`}>{totals.failure}</span>
          </div>
          <div className="kpi-cell">
            <span className="kpi-label">Stopped</span>
            <span className={`kpi-value num ${totals.stopped === 0 ? "zero" : ""}`}>{totals.stopped}</span>
          </div>
        </div>

        <div className="queue-bar-wrap">
          <div className="queue-bar-head">
            <span>Queue distribution</span>
            <div className="queue-bar-legend">
              {segments.length > 0 ? (
                segments.map((s) => (
                  <span key={s.key} className="legend-item num">
                    <span className="legend-dot" style={{ background: s.color }} aria-hidden="true" />
                    {s.key} {s.count}
                  </span>
                ))
              ) : (
                <span>No jobs recorded</span>
              )}
            </div>
          </div>
          <div className="queue-bar-track" role="img" aria-label="Proportional breakdown of job statuses">
            {segments.map((s) => (
              <div
                key={s.key}
                className="queue-bar-seg"
                style={{ width: `${(s.count / totals.total) * 100}%`, background: s.color }}
                title={`${s.key}: ${s.count}`}
              />
            ))}
          </div>
        </div>
      </section>

      {/* Registered tasks table — flat on sheet, no outer card box, sentence-case headers */}
      <section aria-label="Registered task queues">
        <div className="panel-header">
          <h2 className="panel-title">Registered queues</h2>
          <span className="panel-meta num">
            {filtered.length} of {tasks.length} queue{tasks.length === 1 ? "" : "s"}
          </span>
        </div>

        {loading && tasks.length === 0 ? (
          <div className="empty-box">
            <span className="skeleton-bar" style={{ width: "160px" }} />
            <span>Connecting to task queue worker…</span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty-box">
            <span>{searchQuery ? `No queues matching "${searchQuery}".` : "No task handlers registered yet."}</span>
          </div>
        ) : (
          <>
            <div className="table-wrap desktop-table">
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: "28%" }}>Queue</th>
                    <th className="col-hide-tablet">Module</th>
                    <th>State</th>
                    <th className="num">Queued</th>
                    <th className="num">Running</th>
                    <th className="num">Failed</th>
                    <th className="num">Total</th>
                    <th className="num">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((task) => {
                    const total =
                      task.detail.queueing +
                      task.detail.retrying +
                      task.detail.success +
                      task.detail.failure +
                      task.detail.stopped;
                    const state = dominantStatus(task);
                    const stopDisabled = task.detail.queueing === 0 && task.detail.retrying === 0;
                    const retryDisabled = task.detail.failure === 0 && task.detail.stopped === 0;

                    return (
                      <tr key={task.name}>
                        <td>
                          <button
                            type="button"
                            className="task-link"
                            onClick={() => push(`/task?task_name=${encodeURIComponent(task.name)}`)}
                          >
                            {task.name}
                          </button>
                        </td>
                        <td className="cell-muted mono col-hide-tablet">{task.module_name}</td>
                        <td>
                          <span className={`pill ${state.cls}`}>
                            <span className="pill-dot" aria-hidden="true" />
                            {state.label}
                          </span>
                        </td>
                        <td className="num cell-muted">{task.detail.queueing}</td>
                        <td className="num" style={{ color: task.detail.retrying > 0 ? "var(--accent)" : "var(--muted)" }}>
                          {task.detail.retrying}
                        </td>
                        <td className="num" style={{ color: task.detail.failure > 0 ? "var(--negative)" : "var(--muted)", fontWeight: task.detail.failure > 0 ? 500 : 400 }}>
                          {task.detail.failure}
                        </td>
                        <td className="num" style={{ fontWeight: 500 }}>{total}</td>
                        <td className="num">
                          <div className="row-actions">
                            <button
                              type="button"
                              className="btn text-action"
                              onClick={() => push(`/task?task_name=${encodeURIComponent(task.name)}`)}
                            >
                              Open
                            </button>
                            <button
                              type="button"
                              className="btn text-action"
                              disabled={retryDisabled}
                              onClick={() => {
                                if (!confirm(`Retry all failed and stopped jobs in "${task.name}"?`)) return;
                                void gql(RETRY_ALL_JOB, {
                                  filter: { task_name: task.name, statuses: ["FAILURE", "STOPPED"] },
                                });
                              }}
                            >
                              Retry
                            </button>
                            <button
                              type="button"
                              className="btn text-action"
                              disabled={stopDisabled}
                              onClick={() => {
                                if (!confirm(`Stop all queued and running jobs in "${task.name}"?`)) return;
                                void gql(STOP_ALL_JOB, { task_name: task.name });
                              }}
                            >
                              Stop
                            </button>
                            <button
                              type="button"
                              className="btn text-action"
                              disabled={total === 0}
                              onClick={() => {
                                if (!confirm(`Clear finished jobs in "${task.name}"?`)) return;
                                void gql(CLEAN_JOB, {
                                  filter: { task_name: task.name, statuses: ["SUCCESS", "FAILURE", "STOPPED"] },
                                });
                              }}
                            >
                              Clear
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Phone two-line list */}
            <div className="mobile-only">
              {filtered.map((task) => {
                const total =
                  task.detail.queueing +
                  task.detail.retrying +
                  task.detail.success +
                  task.detail.failure +
                  task.detail.stopped;
                const state = dominantStatus(task);
                return (
                  <div key={task.name} className="mobile-row">
                    <div className="mobile-row-main">
                      <button
                        type="button"
                        className="task-link"
                        onClick={() => push(`/task?task_name=${encodeURIComponent(task.name)}`)}
                      >
                        {task.name}
                      </button>
                      <div className="mobile-row-sub">
                        <span className="mono">{task.module_name}</span>
                        <span>·</span>
                        <span className="num">{total} jobs</span>
                        <span className={`pill ${state.cls}`}>{state.label}</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn sm"
                      onClick={() => push(`/task?task_name=${encodeURIComponent(task.name)}`)}
                    >
                      Open
                    </button>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </section>
    </>
  );
}
