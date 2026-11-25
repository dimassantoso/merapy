import type { ComponentChildren } from "preact";
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

function prettyJson(s: string): string {
  try {
    return JSON.stringify(JSON.parse(s), null, 2);
  } catch {
    return s;
  }
}

function DetailRow({ label, children }: { label: string; children: ComponentChildren }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-4 py-3 border-b border-gray-50 dark:border-gray-800 last:border-0">
      <dt className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide pt-0.5">{label}</dt>
      <dd className="text-sm text-gray-900 dark:text-gray-100">{children}</dd>
    </div>
  );
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
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error && !job) {
    return <div className="p-12 text-center text-red-500 dark:text-red-400 text-sm">{error}</div>;
  }

  if (!job) {
    return (
      <div className="p-12 text-center">
        <p className="text-gray-400 dark:text-gray-500 text-sm">Job not found</p>
        <button
          type="button"
          onClick={back}
          className="mt-3 text-xs px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
        >
          Go back
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <nav className="flex items-center gap-2 text-sm">
          <button
            type="button"
            onClick={() => push("/")}
            className="text-gray-500 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
          >
            Dashboard
          </button>
          <span className="text-gray-300 dark:text-gray-600">/</span>
          <button
            type="button"
            onClick={() => push(`/task?task_name=${encodeURIComponent(job.task_name)}`)}
            className="text-gray-500 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 font-mono transition-colors"
          >
            {job.task_name}
          </button>
          <span className="text-gray-300 dark:text-gray-600">/</span>
          <span className="text-gray-900 dark:text-white font-mono text-xs">{job.id.slice(0, 8)}…</span>
          {loading && <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />}
        </nav>

        <div className="flex gap-2">
          {canRetry(job.status) && (
            <button
              type="button"
              onClick={() => void act(() => gql(RETRY_JOB, { job_id: job.id }))}
              disabled={actionLoading}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium disabled:opacity-50 transition-colors"
            >
              🔄 Retry
            </button>
          )}
          {canStop(job.status) && (
            <button
              type="button"
              onClick={() => void act(() => gql(STOP_JOB, { job_id: job.id }))}
              disabled={actionLoading}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium disabled:opacity-50 transition-colors"
            >
              ⏹ Stop
            </button>
          )}
          <button
            type="button"
            onClick={async () => {
              if (!confirm("Permanently delete this job?")) return;
              await act(() => gql(DELETE_JOB, { job_id: job.id }));
              push(`/task?task_name=${encodeURIComponent(job.task_name)}`);
            }}
            disabled={actionLoading}
            className="px-3.5 py-2 rounded-lg border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-950 text-red-600 dark:text-red-400 text-sm hover:bg-red-100 dark:hover:bg-red-900 disabled:opacity-50 transition-colors"
          >
            🗑 Delete
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
          <h1 className="font-semibold text-gray-900 dark:text-white">Job Detail</h1>
          <StatusBadge status={job.status} size="md" />
        </div>
        <dl className="px-5">
          <DetailRow label="ID">
            <span className="font-mono text-xs break-all text-gray-700 dark:text-gray-300">{job.id}</span>
          </DetailRow>
          <DetailRow label="Task">
            <button
              type="button"
              onClick={() => push(`/task?task_name=${encodeURIComponent(job.task_name)}`)}
              className="font-mono text-indigo-600 dark:text-indigo-400 hover:underline"
            >
              {job.task_name}
            </button>
          </DetailRow>
          <DetailRow label="Retries">
            <span className="tabular-nums">{job.retries} / {job.max_retry}</span>
          </DetailRow>
          <DetailRow label="Interval">
            <span className="text-gray-600 dark:text-gray-400">{job.interval || "—"}</span>
          </DetailRow>
          <DetailRow label="Created">
            <span className="text-gray-600 dark:text-gray-400">{job.created_at ? new Date(job.created_at).toLocaleString() : "—"}</span>
          </DetailRow>
          <DetailRow label="Finished">
            <span className="text-gray-600 dark:text-gray-400">{job.finished_at ? new Date(job.finished_at).toLocaleString() : "—"}</span>
          </DetailRow>
          {job.trace_id && (
            <DetailRow label="Trace ID">
              {jaegerBaseUrl ? (
                <a
                  href={`${jaegerBaseUrl}/trace/${job.trace_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono text-xs text-indigo-600 dark:text-indigo-400 hover:underline break-all inline-flex items-center gap-1"
                >
                  {job.trace_id}
                </a>
              ) : (
                <span className="font-mono text-xs text-gray-600 dark:text-gray-400 break-all">{job.trace_id}</span>
              )}
            </DetailRow>
          )}
          <DetailRow label="Arguments">
            <pre className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 text-xs font-mono overflow-auto max-h-48 whitespace-pre-wrap text-gray-800 dark:text-gray-200 border border-gray-100 dark:border-gray-700">
              {prettyJson(job.arguments)}
            </pre>
          </DetailRow>
          {job.result && (
            <DetailRow label="Result">
              <pre className="bg-green-50 dark:bg-green-950 rounded-lg p-3 text-xs font-mono overflow-auto max-h-48 whitespace-pre-wrap text-green-800 dark:text-green-200 border border-green-100 dark:border-green-900">
                {prettyJson(job.result)}
              </pre>
            </DetailRow>
          )}
          {job.error && (
            <DetailRow label="Error">
              <pre className="bg-red-50 dark:bg-red-950 rounded-lg p-3 text-xs font-mono overflow-auto max-h-48 whitespace-pre-wrap text-red-700 dark:text-red-300 border border-red-100 dark:border-red-900">
                {job.error}
              </pre>
            </DetailRow>
          )}
        </dl>
      </div>
    </div>
  );
}
