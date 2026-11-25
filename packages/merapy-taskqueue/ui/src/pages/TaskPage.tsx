import { useCallback, useEffect, useMemo, useState } from "preact/hooks";
import { StatusBadge } from "../components/StatusBadge";
import {
  CLEAN_JOB,
  DELETE_JOB,
  GET_ALL_JOB,
  GET_COUNT_JOB,
  RETRY_ALL_JOB,
  RETRY_ALL_JOB_FORCE,
  RETRY_JOB,
  STOP_ALL_JOB,
  STOP_JOB,
  SUBSCRIBE_ALL_JOB,
  canRetry,
  canStop,
  gql,
  type Job,
  type JobMeta,
  type SubscribeAllJobData,
} from "../lib/graphql";
import { useRouter } from "../lib/router";
import { useSubscription } from "../lib/useSubscription";

const STATUS_TABS = [
  { key: "", label: "All" },
  { key: "QUEUEING", label: "Queued" },
  { key: "RETRYING", label: "Running" },
  { key: "SUCCESS", label: "Succeeded" },
  { key: "FAILURE", label: "Failed" },
  { key: "STOPPED", label: "Stopped" },
] as const;

const STATUS_KEYS = ["QUEUEING", "RETRYING", "SUCCESS", "FAILURE", "STOPPED"] as const;

function MutateModal({
  action,
  taskName,
  onClose,
}: {
  action: "RETRY" | "CLEAN";
  taskName: string;
  onClose: () => void;
}) {
  const defaultStatuses = action === "RETRY" ? ["FAILURE", "STOPPED"] : ["SUCCESS", "FAILURE", "STOPPED"];
  const [statuses, setStatuses] = useState<string[]>(defaultStatuses);
  const [search, setSearch] = useState("");
  const [count, setCount] = useState<number | null>(null);
  const [countLoading, setCountLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const fetchCount = useCallback(async () => {
    if (statuses.length === 0) {
      setCount(0);
      return;
    }
    setCountLoading(true);
    try {
      const data = await gql<{ get_count_job: number }>(GET_COUNT_JOB, {
        filter: { task_name: taskName, statuses, search: search || undefined },
      });
      setCount(data.get_count_job);
    } catch {
      setCount(null);
    } finally {
      setCountLoading(false);
    }
  }, [taskName, statuses, search]);

  useEffect(() => {
    void fetchCount();
  }, [fetchCount]);

  async function handleSubmit() {
    setSubmitting(true);
    try {
      const filter = { task_name: taskName, statuses, search: search || undefined };
      if (action === "RETRY") await gql(RETRY_ALL_JOB, { filter });
      else await gql(CLEAN_JOB, { filter });
      onClose();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setSubmitting(false);
    }
  }

  const isRetry = action === "RETRY";

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="mutate-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-dialog">
        <div className="modal-head">
          <h2 id="mutate-title">{isRetry ? `Retry jobs in ${taskName}` : `Clear jobs in ${taskName}`}</h2>
          <button type="button" className="btn sm text-action" onClick={onClose}>Close</button>
        </div>
        <div className="modal-body">
          <div className="field">
            <label>Matching statuses</label>
            <div className="chip-group">
              {STATUS_KEYS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="chip-toggle"
                  aria-pressed={statuses.includes(s)}
                  onClick={() => setStatuses((p) => (p.includes(s) ? p.filter((x) => x !== s) : [...p, s]))}
                >
                  {s.charAt(0) + s.slice(1).toLowerCase()}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            <label htmlFor="mutate-search">Argument filter</label>
            <input
              id="mutate-search"
              type="text"
              className="input"
              value={search}
              onInput={(e) => setSearch((e.target as HTMLInputElement).value)}
              placeholder="Optional substring in arguments"
            />
          </div>
          <div className="panel-meta num">
            {countLoading
              ? "Counting matching jobs…"
              : count !== null
                ? `${count} matching job${count === 1 ? "" : "s"}`
                : "Unable to count jobs"}
          </div>
        </div>
        <div className="modal-foot">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button
            type="button"
            className={`btn ${isRetry ? "primary" : "danger"}`}
            disabled={submitting || count === 0 || statuses.length === 0}
            onClick={() => void handleSubmit()}
          >
            {submitting ? "Processing…" : `${isRetry ? "Retry" : "Clear"} ${count ?? 0} jobs`}
          </button>
        </div>
      </div>
    </div>
  );
}

interface TaskPageProps {
  onAddJob: (taskName?: string) => void;
}

export function TaskPage({ onAddJob }: TaskPageProps) {
  const { searchParams, push } = useRouter();
  const taskName = searchParams.get("task_name") ?? "";
  const statusFilter = searchParams.get("statuses") ?? "";
  const page = Math.max(1, parseInt(searchParams.get("page") ?? "1", 10) || 1);

  const [actionId, setActionId] = useState<string | null>(null);
  const [search, setSearch] = useState(searchParams.get("search") ?? "");
  const [modal, setModal] = useState<"retry" | "clean" | null>(null);

  const subFilter = useMemo(
    () => ({
      page,
      limit: 12,
      task_name: taskName || undefined,
      statuses: statusFilter ? statusFilter.split(",") : undefined,
      search: search || undefined,
    }),
    [page, taskName, statusFilter, search]
  );

  const { data: subData, loading, error } = useSubscription<SubscribeAllJobData>({
    query: SUBSCRIBE_ALL_JOB,
    variables: { filter: subFilter },
    pollQuery: GET_ALL_JOB,
    pollInterval: 3000,
  });

  const rawData = subData?.listen_all_job ?? subData?.get_all_job ?? null;
  const jobs: Job[] = rawData?.data ?? [];
  const meta: JobMeta = rawData?.meta ?? { page: 1, limit: 12, total_pages: 1, total_records: 0 };
  const hasStoppable = jobs.some((j) => j.status === "QUEUEING" || j.status === "RETRYING");

  function setParam(key: string, value: string | undefined) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value);
    else params.delete(key);
    if (key !== "page") params.delete("page");
    const qs = params.toString();
    push(qs ? `/task?${qs}` : "/task");
  }

  async function act(fn: () => Promise<unknown>, jobId?: string) {
    if (jobId) setActionId(jobId);
    try {
      await fn();
    } finally {
      if (jobId) setActionId(null);
    }
  }

  const rangeStart = meta.total_records === 0 ? 0 : (meta.page - 1) * meta.limit + 1;
  const rangeEnd = Math.min(meta.page * meta.limit, meta.total_records);

  return (
    <>
      <div className="title-row">
        <div className="title-block">
          <nav className="breadcrumb" aria-label="Breadcrumb">
            <button type="button" onClick={() => push("/")}>Overview</button>
            <span aria-hidden="true">/</span>
            <span>{taskName || "All jobs"}</span>
          </nav>
          <h1 className={`page-title ${taskName ? "mono" : ""}`}>{taskName || "All jobs"}</h1>
          <p className="page-sub num">
            {meta.total_records} job{meta.total_records === 1 ? "" : "s"}
            {statusFilter ? ` filtered by ${statusFilter.toLowerCase()}` : " in this view"}.
          </p>
        </div>

        {taskName && (
          <div className="title-actions">
            <button type="button" className="btn" onClick={() => setModal("retry")}>
              Retry failed
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => {
                if (!confirm(`Retry all jobs in "${taskName}" regardless of status?`)) return;
                void gql(RETRY_ALL_JOB_FORCE, { task_name: taskName });
              }}
            >
              Retry all
            </button>
            <button
              type="button"
              className="btn"
              disabled={!hasStoppable}
              onClick={() => {
                if (!confirm(`Stop all queued and running jobs in "${taskName}"?`)) return;
                void gql(STOP_ALL_JOB, { task_name: taskName });
              }}
            >
              Stop all
            </button>
            <button type="button" className="btn danger" onClick={() => setModal("clean")}>
              Clear
            </button>
          </div>
        )}
      </div>

      {/* Underline status tabs */}
      <div className="tabs" role="tablist" aria-label="Filter jobs by status">
        {STATUS_TABS.map((t) => (
          <button
            key={t.key || "all"}
            type="button"
            role="tab"
            className="tab-btn"
            aria-selected={statusFilter === t.key}
            onClick={() => setParam("statuses", t.key || undefined)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Filter toolbar */}
      <div className="toolbar">
        <div className="toolbar-left">
          <input
            type="search"
            className="input compact"
            placeholder="Filter by arguments…"
            aria-label="Filter jobs by arguments"
            value={search}
            onInput={(e) => setSearch((e.target as HTMLInputElement).value)}
            onKeyDown={(e) => e.key === "Enter" && setParam("search", search || undefined)}
          />
        </div>
        <div className="toolbar-right">
          <span className="panel-meta num">
            {meta.total_records > 0 ? `${rangeStart}–${rangeEnd} of ${meta.total_records}` : "0 jobs"}
          </span>
        </div>
      </div>

      {error && (
        <div className="error-inline">
          <span>Failed to load jobs: {error}</span>
          <button type="button" className="btn sm" onClick={() => window.location.reload()}>Retry</button>
        </div>
      )}

      {jobs.length === 0 && !loading ? (
        <div className="empty-box">
          <span>No jobs match the current filter.</span>
          {taskName && (
            <button type="button" className="btn sm" onClick={() => onAddJob(taskName)}>
              Enqueue first job
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="table-wrap desktop-table">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Job ID</th>
                  {!taskName && <th>Queue</th>}
                  <th>Status</th>
                  <th className="num">Attempts</th>
                  <th>Arguments</th>
                  <th>Error</th>
                  <th className="num">Created</th>
                  <th className="num">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id} style={{ opacity: actionId === job.id ? 0.45 : 1 }}>
                    <td>
                      <button
                        type="button"
                        className="task-link"
                        title={job.id}
                        onClick={() => push(`/job?id=${encodeURIComponent(job.id)}`)}
                      >
                        {job.id.slice(0, 8)}…
                      </button>
                    </td>
                    {!taskName && (
                      <td>
                        <button
                          type="button"
                          className="task-link"
                          onClick={() => push(`/task?task_name=${encodeURIComponent(job.task_name)}`)}
                        >
                          {job.task_name}
                        </button>
                      </td>
                    )}
                    <td>
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="num">
                      <span>{job.retries}</span>
                      <span className="cell-muted"> /{job.max_retry}</span>
                    </td>
                    <td>
                      <span className="cell-mono cell-muted cell-truncate" title={job.arguments}>
                        {job.arguments || "—"}
                      </span>
                    </td>
                    <td>
                      {job.error ? (
                        <span className="cell-err cell-truncate" title={job.error}>{job.error}</span>
                      ) : (
                        <span className="cell-muted">—</span>
                      )}
                    </td>
                    <td className="num cell-muted" style={{ whiteSpace: "nowrap" }}>
                      {job.created_at ? job.created_at.replace("T", " ").slice(0, 16) : "—"}
                    </td>
                    <td className="num">
                      <div className="row-actions">
                        <button
                          type="button"
                          className="btn text-action"
                          onClick={() => push(`/job?id=${encodeURIComponent(job.id)}`)}
                        >
                          Inspect
                        </button>
                        <button
                          type="button"
                          className="btn text-action"
                          disabled={actionId === job.id || !canRetry(job.status)}
                          onClick={() => void act(() => gql(RETRY_JOB, { job_id: job.id }), job.id)}
                        >
                          Retry
                        </button>
                        <button
                          type="button"
                          className="btn text-action"
                          disabled={actionId === job.id || !canStop(job.status)}
                          onClick={() => void act(() => gql(STOP_JOB, { job_id: job.id }), job.id)}
                        >
                          Stop
                        </button>
                        <button
                          type="button"
                          className="btn text-action neg"
                          disabled={actionId === job.id}
                          onClick={() => {
                            if (!confirm(`Permanently delete job ${job.id.slice(0, 8)}?`)) return;
                            void act(() => gql(DELETE_JOB, { job_id: job.id }), job.id);
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mobile-only">
            {jobs.map((job) => (
              <div key={job.id} className="mobile-row">
                <div className="mobile-row-main">
                  <button
                    type="button"
                    className="task-link"
                    onClick={() => push(`/job?id=${encodeURIComponent(job.id)}`)}
                  >
                    {job.id.slice(0, 8)}… · {job.task_name}
                  </button>
                  <div className="mobile-row-sub">
                    <StatusBadge status={job.status} />
                    <span className="num">{job.retries}/{job.max_retry} attempts</span>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn sm"
                  onClick={() => push(`/job?id=${encodeURIComponent(job.id)}`)}
                >
                  Inspect
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {meta.total_pages > 1 && (
        <div className="pager">
          <span className="num">Page {meta.page} of {meta.total_pages} · {meta.total_records} jobs</span>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              type="button"
              className="btn sm"
              disabled={meta.page <= 1}
              onClick={() => setParam("page", String(meta.page - 1))}
            >
              Previous
            </button>
            <button
              type="button"
              className="btn sm"
              disabled={meta.page >= meta.total_pages}
              onClick={() => setParam("page", String(meta.page + 1))}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {modal === "retry" && taskName && <MutateModal action="RETRY" taskName={taskName} onClose={() => setModal(null)} />}
      {modal === "clean" && taskName && <MutateModal action="CLEAN" taskName={taskName} onClose={() => setModal(null)} />}
    </>
  );
}
