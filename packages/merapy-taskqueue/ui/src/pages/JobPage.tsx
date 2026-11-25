import { useMemo, useState } from "preact/hooks";
import { StatusBadge } from "../components/StatusBadge";
import {
  DELETE_JOB,
  GET_ALL_JOB,
  RETRY_JOB,
  STOP_JOB,
  SUBSCRIBE_ALL_JOB,
  canRetry,
  canStop,
  gql,
  type Job,
  type SubscribeAllJobData,
} from "../lib/graphql";
import { useRouter } from "../lib/router";
import { useSubscription } from "../lib/useSubscription";

function prettyJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

export function JobPage() {
  const { searchParams, push, back } = useRouter();
  const jobId = searchParams.get("id") ?? "";
  const [actionLoading, setActionLoading] = useState(false);

  const vars = useMemo(() => ({ filter: { job_id: jobId, limit: 1 } }), [jobId]);
  const { data: subData, loading, error } = useSubscription<SubscribeAllJobData>({
    query: SUBSCRIBE_ALL_JOB,
    variables: vars,
    pollQuery: GET_ALL_JOB,
    pollInterval: 3000,
  });

  const rawData = subData?.listen_all_job ?? subData?.get_all_job ?? null;
  const job: Job | null = rawData?.data?.[0] ?? null;
  const jaegerBaseUrl = import.meta.env.VITE_JAEGER_BASE_URL as string | undefined;

  async function act(fn: () => Promise<unknown>) {
    setActionLoading(true);
    try {
      await fn();
    } finally {
      setActionLoading(false);
    }
  }

  if (loading && !job) {
    return (
      <div className="empty-box">
        <span className="skeleton-bar" style={{ width: "180px" }} />
        <span>Loading job details…</span>
      </div>
    );
  }

  if (error && !job) {
    return (
      <div className="error-inline">
        <span>Unable to load job: {error}</span>
        <button type="button" className="btn sm" onClick={back}>Back</button>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="empty-box">
        <span>Job not found.</span>
        <button type="button" className="btn sm" onClick={back}>Back</button>
      </div>
    );
  }

  return (
    <>
      <div className="title-row">
        <div className="title-block">
          <nav className="breadcrumb" aria-label="Breadcrumb">
            <button type="button" onClick={() => push("/")}>Overview</button>
            <span aria-hidden="true">/</span>
            <button
              type="button"
              className="mono"
              onClick={() => push(`/task?task_name=${encodeURIComponent(job.task_name)}`)}
            >
              {job.task_name}
            </button>
            <span aria-hidden="true">/</span>
            <span className="mono">{job.id.slice(0, 8)}…</span>
          </nav>
          <div className="title-heading-line">
            <h1 className="page-title">Job detail</h1>
            <StatusBadge status={job.status} />
          </div>
          <p className="page-sub mono" style={{ fontSize: "13px" }}>{job.id}</p>
        </div>

        <div className="title-actions">
          {canRetry(job.status) && (
            <button
              type="button"
              className="btn primary"
              disabled={actionLoading}
              onClick={() => void act(() => gql(RETRY_JOB, { job_id: job.id }))}
            >
              Retry job
            </button>
          )}
          {canStop(job.status) && (
            <button
              type="button"
              className="btn"
              disabled={actionLoading}
              onClick={() => void act(() => gql(STOP_JOB, { job_id: job.id }))}
            >
              Stop job
            </button>
          )}
          <button
            type="button"
            className="btn danger"
            disabled={actionLoading}
            onClick={async () => {
              if (!confirm(`Permanently delete job ${job.id.slice(0, 8)}?`)) return;
              await act(() => gql(DELETE_JOB, { job_id: job.id }));
              push(`/task?task_name=${encodeURIComponent(job.task_name)}`);
            }}
          >
            Delete job
          </button>
        </div>
      </div>

      <div className="detail-grid">
        {/* Left: Payload, Result, Error */}
        <div style={{ display: "flex", flexDirection: "column", gap: "24px", minWidth: 0 }}>
          {job.error && (
            <section className="panel" aria-label="Execution error">
              <div className="panel-header">
                <h2 className="panel-title">Last error</h2>
                <span className="panel-meta num">Attempt {job.retries} of {job.max_retry}</span>
              </div>
              <pre className="code-block err">{job.error}</pre>
            </section>
          )}

          <section className="panel" aria-label="Job arguments">
            <div className="panel-header">
              <h2 className="panel-title">Arguments</h2>
              <span className="panel-meta">Input payload</span>
            </div>
            <pre className="code-block">{prettyJson(job.arguments || "{}")}</pre>
          </section>

          {job.result && (
            <section className="panel" aria-label="Job result">
              <div className="panel-header">
                <h2 className="panel-title">Result</h2>
                <span className="panel-meta">Returned output</span>
              </div>
              <pre className="code-block">{prettyJson(job.result)}</pre>
            </section>
          )}
        </div>

        {/* Right: Metadata rail */}
        <aside className="panel" aria-label="Job metadata">
          <div className="panel-header">
            <h2 className="panel-title">Execution metadata</h2>
          </div>
          <dl className="kv-list">
            <div className="kv-row">
              <dt className="kv-key">Queue</dt>
              <dd className="kv-val">
                <button
                  type="button"
                  className="task-link"
                  onClick={() => push(`/task?task_name=${encodeURIComponent(job.task_name)}`)}
                >
                  {job.task_name}
                </button>
              </dd>
            </div>
            <div className="kv-row">
              <dt className="kv-key">Attempts</dt>
              <dd className="kv-val num">
                {job.retries} <span className="cell-muted">/ {job.max_retry}</span>
              </dd>
            </div>
            <div className="kv-row">
              <dt className="kv-key">Interval</dt>
              <dd className="kv-val cell-muted">{job.interval || "—"}</dd>
            </div>
            <div className="kv-row">
              <dt className="kv-key">Created</dt>
              <dd className="kv-val num cell-muted">
                {job.created_at ? new Date(job.created_at).toLocaleString() : "—"}
              </dd>
            </div>
            <div className="kv-row">
              <dt className="kv-key">Finished</dt>
              <dd className="kv-val num cell-muted">
                {job.finished_at ? new Date(job.finished_at).toLocaleString() : "—"}
              </dd>
            </div>
            <div className="kv-row">
              <dt className="kv-key">Trace ID</dt>
              <dd className="kv-val mono" style={{ fontSize: "12px" }}>
                {job.trace_id ? (
                  jaegerBaseUrl ? (
                    <a
                      href={`${jaegerBaseUrl}/trace/${job.trace_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: "var(--accent)", textDecoration: "underline" }}
                    >
                      {job.trace_id}
                    </a>
                  ) : (
                    job.trace_id
                  )
                ) : (
                  <span className="cell-muted">—</span>
                )}
              </dd>
            </div>
          </dl>
        </aside>
      </div>
    </>
  );
}
