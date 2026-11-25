import { useCallback, useEffect, useMemo, useState } from "preact/hooks";
import { StatusBadge } from "../components/StatusBadge";
import {
  ADD_JOB,
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

const STATUS_TABS = ["QUEUEING", "RETRYING", "SUCCESS", "FAILURE", "STOPPED"] as const;

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
      alert(e instanceof Error ? e.message : "Failed");
    } finally {
      setSubmitting(false);
    }
  }

  const isRetry = action === "RETRY";
  const btnCls = isRetry
    ? "bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-40"
    : "bg-red-600 hover:bg-red-700 text-white disabled:opacity-40";

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md border border-gray-200 dark:border-gray-700">
        <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-white">{isRetry ? "Retry All" : "Clear Jobs"}</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 font-mono mt-0.5">{taskName}</p>
          </div>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-lg">✕</button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Status</label>
            <div className="flex flex-wrap gap-2">
              {STATUS_TABS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStatuses((p) => (p.includes(s) ? p.filter((x) => x !== s) : [...p, s]))}
                  className={`text-xs px-3 py-1.5 rounded-full border font-medium transition-colors ${
                    statuses.includes(s)
                      ? "bg-indigo-600 text-white border-indigo-600"
                      : "bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1.5">Search</label>
            <input
              type="text"
              value={search}
              onInput={(e) => setSearch((e.target as HTMLInputElement).value)}
              placeholder="Filter by arguments…"
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="text-right text-sm">
            {countLoading ? (
              <span className="text-gray-400 animate-pulse">Counting…</span>
            ) : count !== null ? (
              <span className="text-gray-700 dark:text-gray-300">
                Found <b className="tabular-nums">{count}</b> job{count !== 1 ? "s" : ""}
              </span>
            ) : null}
          </div>
        </div>
        <div className="px-6 pb-6 flex gap-3">
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={submitting || count === 0 || statuses.length === 0}
            className={`flex-1 rounded-lg py-2.5 text-sm font-medium transition-colors ${btnCls}`}
          >
            {submitting ? "Processing…" : `${isRetry ? "Retry" : "Clear"} ${count ?? "?"} jobs`}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg py-2.5 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

function AddJobModal({ taskName, onClose }: { taskName: string; onClose: () => void }) {
  const [args, setArgs] = useState("{}");
  const [maxRetry, setMaxRetry] = useState(3);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function handleSubmit(e: Event) {
    e.preventDefault();
    setLoading(true);
    setErr("");
    try {
      await gql(ADD_JOB, { param: { task_name: taskName, max_retry: maxRetry, args } });
      onClose();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md border border-gray-200 dark:border-gray-700">
        <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-white">Add Job</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 font-mono mt-0.5">{taskName}</p>
          </div>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-lg">✕</button>
        </div>
        <form onSubmit={(e) => void handleSubmit(e)} className="p-6 space-y-4">
          {err && <p className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950 rounded-lg px-3 py-2">{err}</p>}
          <div>
            <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1.5">Arguments (JSON)</label>
            <textarea
              value={args}
              onInput={(e) => setArgs((e.target as HTMLTextAreaElement).value)}
              rows={5}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm font-mono bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder='{"key": "value"}'
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1.5">Max Retry</label>
            <input
              type="number"
              value={maxRetry}
              min={1}
              max={100}
              onInput={(e) => setMaxRetry(Number((e.target as HTMLInputElement).value))}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="flex gap-3 pt-1">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-50 transition-colors"
            >
              {loading ? "Adding…" : "Add Job"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg py-2.5 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function TaskPage() {
  const { searchParams, push } = useRouter();
  const taskName = searchParams.get("task_name") ?? "";
  const statusFilter = searchParams.get("statuses") ?? "";
  const page = Math.max(1, parseInt(searchParams.get("page") ?? "1", 10) || 1);

  const [actionId, setActionId] = useState<string | null>(null);
  const [search, setSearch] = useState(searchParams.get("search") ?? "");
  const [modal, setModal] = useState<"add" | "retry" | "clean" | null>(null);

  const subFilter = useMemo(
    () => ({
      page,
      limit: 10,
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
  const meta: JobMeta = rawData?.meta ?? { page: 1, limit: 10, total_pages: 1, total_records: 0 };
  const hasStoppable = jobs.some((j) => j.status === "QUEUEING" || j.status === "RETRYING");

  function setParam(key: string, value: string | undefined) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value);
    else params.delete(key);
    if (key !== "page") params.delete("page");
    push("/task?" + params.toString());
  }

  async function act(fn: () => Promise<unknown>, jobId?: string) {
    if (jobId) setActionId(jobId);
    try {
      await fn();
    } finally {
      if (jobId) setActionId(null);
    }
  }

  return (
    <div className="space-y-5">
      <nav className="flex items-center gap-2 text-sm">
        <button
          type="button"
          onClick={() => push("/")}
          className="text-gray-500 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 flex items-center gap-1 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Dashboard
        </button>
        <span className="text-gray-300 dark:text-gray-600">/</span>
        <span className="font-semibold font-mono text-gray-900 dark:text-white">{taskName || "All Tasks"}</span>
        {loading && <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse ml-1" />}
      </nav>

      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => setParam("statuses", undefined)}
          className={`text-xs px-3 py-1.5 rounded-full border font-medium transition-colors ${
            !statusFilter
              ? "bg-indigo-600 text-white border-indigo-600"
              : "bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
          }`}
        >
          All <span className="tabular-nums">({meta.total_records})</span>
        </button>
        {STATUS_TABS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setParam("statuses", s)}
            className={`text-xs px-3 py-1.5 rounded-full border font-medium transition-colors ${
              statusFilter === s
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search jobs…"
            value={search}
            onInput={(e) => setSearch((e.target as HTMLInputElement).value)}
            onKeyDown={(e) => e.key === "Enter" && setParam("search", search || undefined)}
            className="pl-9 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 w-48"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => setModal("add")}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            Add Job
          </button>
          <button
            type="button"
            onClick={() => setModal("retry")}
            className="px-3 py-2 rounded-lg border border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 text-xs font-medium hover:bg-blue-100 dark:hover:bg-blue-900 transition-colors"
          >
            🔄 Retry Failed
          </button>
          <button
            type="button"
            onClick={() => {
              if (!confirm(`Retry ALL jobs for "${taskName}" regardless of status?`)) return;
              void gql(RETRY_ALL_JOB_FORCE, { task_name: taskName });
            }}
            className="px-3 py-2 rounded-lg border border-indigo-300 dark:border-indigo-700 bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 text-xs font-medium hover:bg-indigo-100 dark:hover:bg-indigo-900 transition-colors"
          >
            ⚡ Retry All
          </button>
          <button
            type="button"
            onClick={() => {
              if (!confirm(`Stop all running/queued jobs for "${taskName}"?`)) return;
              void gql(STOP_ALL_JOB, { task_name: taskName });
            }}
            disabled={!hasStoppable}
            className="px-3 py-2 rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 text-xs font-medium hover:bg-amber-100 dark:hover:bg-amber-900 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title={!hasStoppable ? "No running or queued jobs" : "Stop all running/queued jobs"}
          >
            ⏹ Stop All
          </button>
          <button
            type="button"
            onClick={() => setModal("clean")}
            className="px-3 py-2 rounded-lg border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-950 text-red-600 dark:text-red-400 text-xs font-medium hover:bg-red-100 dark:hover:bg-red-900 transition-colors"
          >
            🗑 Clear
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden shadow-sm">
        {error ? (
          <div className="p-8 text-center text-red-500 dark:text-red-400 text-sm">{error}</div>
        ) : jobs.length === 0 && !loading ? (
          <div className="p-16 text-center">
            <p className="text-sm text-gray-400 dark:text-gray-500">No jobs found</p>
            <button
              type="button"
              onClick={() => setModal("add")}
              className="mt-3 text-xs px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition-colors"
            >
              + Add first job
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[700px]">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-800">
                  {["ID", "Status", "Retries", "Arguments", "Error", "Created", ""].map((h) => (
                    <th key={h} className={`px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide ${h === "" || h === "Retries" ? "text-center" : "text-left"}`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                {jobs.map((job) => (
                  <tr key={job.id} className={`hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors ${actionId === job.id ? "opacity-40" : ""}`}>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => push(`/job?id=${encodeURIComponent(job.id)}`)}
                        className="font-mono text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
                        title={job.id}
                      >
                        {job.id.slice(0, 8)}…
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <button type="button" onClick={() => setParam("statuses", job.status)}>
                        <StatusBadge status={job.status} />
                      </button>
                    </td>
                    <td className="px-4 py-3 text-center text-xs text-gray-500 dark:text-gray-400 tabular-nums">
                      {job.retries}/{job.max_retry}
                    </td>
                    <td className="px-4 py-3 max-w-[180px]">
                      <span className="font-mono text-xs text-gray-600 dark:text-gray-400 truncate block" title={job.arguments}>
                        {job.arguments || "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3 max-w-[180px]">
                      {job.error ? (
                        <span className="text-xs text-red-600 dark:text-red-400 truncate block" title={job.error}>{job.error}</span>
                      ) : (
                        <span className="text-gray-300 dark:text-gray-600 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
                      {job.created_at ? new Date(job.created_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => push(`/job?id=${encodeURIComponent(job.id)}`)}
                          className="px-2 py-1 rounded border border-gray-200 dark:border-gray-700 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                        >
                          Detail
                        </button>
                        <button
                          type="button"
                          onClick={() => void act(() => gql(RETRY_JOB, { job_id: job.id }), job.id)}
                          disabled={actionId === job.id || !canRetry(job.status)}
                          className="px-2 py-1 rounded border border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 text-xs hover:bg-blue-100 dark:hover:bg-blue-900 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        >
                          Retry
                        </button>
                        <button
                          type="button"
                          onClick={() => void act(() => gql(STOP_JOB, { job_id: job.id }), job.id)}
                          disabled={actionId === job.id || !canStop(job.status)}
                          className="px-2 py-1 rounded border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 text-xs hover:bg-amber-100 dark:hover:bg-amber-900 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        >
                          Stop
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            if (!confirm("Permanently delete this job?")) return;
                            void act(() => gql(DELETE_JOB, { job_id: job.id }), job.id);
                          }}
                          disabled={actionId === job.id}
                          className="px-2 py-1 rounded border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950 text-red-600 dark:text-red-400 text-xs hover:bg-red-100 dark:hover:bg-red-900 disabled:opacity-50 transition-colors"
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
        )}
      </div>

      {meta.total_pages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
          <span className="tabular-nums">Page {meta.page} of {meta.total_pages} · {meta.total_records} jobs</span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setParam("page", String(meta.page - 1))}
              disabled={meta.page <= 1}
              className="px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 transition-colors text-xs"
            >
              ← Prev
            </button>
            <button
              type="button"
              onClick={() => setParam("page", String(meta.page + 1))}
              disabled={meta.page >= meta.total_pages}
              className="px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 transition-colors text-xs"
            >
              Next →
            </button>
          </div>
        </div>
      )}

      {modal === "add" && <AddJobModal taskName={taskName} onClose={() => setModal(null)} />}
      {modal === "retry" && <MutateModal action="RETRY" taskName={taskName} onClose={() => setModal(null)} />}
      {modal === "clean" && <MutateModal action="CLEAN" taskName={taskName} onClose={() => setModal(null)} />}
    </div>
  );
}
