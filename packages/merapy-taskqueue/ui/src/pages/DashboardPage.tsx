import type { ComponentChildren } from "preact";
import { useMemo, useState } from "preact/hooks";
import {
  ADD_JOB,
  CLEAN_JOB,
  RETRY_ALL_JOB,
  STOP_ALL_JOB,
  getGraphQLUrl,
  gql,
  type Task,
  type WorkerStats,
} from "../lib/graphql";
import { useRouter } from "../lib/router";
import { useStats } from "../lib/StatsContext";

function InfoTip({ text }: { text: string }) {
  return (
    <span className="relative group/tip inline-flex items-center cursor-default">
      <svg className="w-3 h-3 text-gray-300 dark:text-gray-600 hover:text-indigo-400 transition-colors" fill="currentColor" viewBox="0 0 20 20" aria-label={text} role="img">
        <path fillRule="evenodd" clipRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" />
      </svg>
      <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max max-w-[200px] rounded-lg bg-gray-900 dark:bg-gray-800 border border-gray-700 px-2.5 py-1.5 text-[11px] leading-snug text-gray-100 shadow-xl opacity-0 group-hover/tip:opacity-100 transition-opacity duration-150 z-50 text-center whitespace-normal">
        {text}
        <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900 dark:border-t-gray-800" />
      </span>
    </span>
  );
}

function StatPill({
  icon,
  label,
  tip,
  value,
  accent,
}: {
  icon: ComponentChildren;
  label: string;
  tip: string;
  value: ComponentChildren;
  accent: string;
}) {
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-xl border bg-white dark:bg-gray-900 shadow-sm ${accent}`}>
      <span className="flex-shrink-0">{icon}</span>
      <div className="flex flex-col min-w-0">
        <div className="flex items-center gap-1">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 leading-none">{label}</span>
          <InfoTip text={tip} />
        </div>
        <span className="text-sm font-bold tabular-nums font-mono text-gray-800 dark:text-gray-100 leading-tight mt-0.5 truncate">{value}</span>
      </div>
    </div>
  );
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

function InfoPanel({ stats, clients }: { stats: WorkerStats | null; clients: number }) {
  const fmtPct = (v: number | undefined) => (v != null ? `${v}%` : "—");
  const shortCommit = stats?.git_commit
    ? stats.git_commit.length > 12
      ? stats.git_commit.slice(0, 7)
      : stats.git_commit
    : "—";
  const buildDateDisplay = stats?.build_date
    ? stats.build_date.includes("T")
      ? stats.build_date.split("T")[0]
      : stats.build_date
    : "—";
  const iconCls = "w-4 h-4";

  return (
    <div className="rounded-2xl border border-gray-200/80 dark:border-gray-800 bg-gray-50/60 dark:bg-gray-900/40 overflow-hidden shadow-sm">
      <div className="flex items-center gap-2 px-4 pt-3 pb-2">
        <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400 dark:text-gray-600">Deployment</span>
        <div className="flex-1 h-px bg-gray-100 dark:bg-gray-800" />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 px-3 pb-3">
        <StatPill
          accent="border-violet-100 dark:border-violet-900/40"
          icon={<svg className={`${iconCls} text-violet-500`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 10V7" /></svg>}
          label="merapy"
          tip="Version installed in this service"
          value={stats?.merapy_version || "—"}
        />
        <StatPill
          accent="border-teal-100 dark:border-teal-900/40"
          icon={<svg className={`${iconCls} text-teal-500`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a2 2 0 012-2z" /></svg>}
          label="Service Version"
          tip="Semantic version or release tag (APP_VERSION)"
          value={stats?.service_version || "—"}
        />
        <StatPill
          accent="border-orange-100 dark:border-orange-900/40"
          icon={<svg className={`${iconCls} text-orange-500`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>}
          label="Build"
          tip="CI/CD build number (BUILD_NUMBER)"
          value={stats?.build_number || "—"}
        />
        <StatPill
          accent="border-amber-100 dark:border-amber-900/40"
          icon={<svg className={`${iconCls} text-amber-500`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg>}
          label="Commit"
          tip={`Git commit SHA${stats?.git_commit && stats.git_commit.length > 12 ? ` (${stats.git_commit})` : ""}`}
          value={shortCommit}
        />
        <StatPill
          accent="border-sky-100 dark:border-sky-900/40"
          icon={<svg className={`${iconCls} text-sky-500`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>}
          label="Built"
          tip={`Build timestamp${stats?.build_date && stats.build_date.includes("T") ? ` (${stats.build_date})` : ""}`}
          value={buildDateDisplay}
        />
      </div>

      <div className="flex items-center gap-2 px-4 pt-1 pb-2">
        <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400 dark:text-gray-600">Runtime</span>
        <div className="flex-1 h-px bg-gray-100 dark:bg-gray-800" />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 px-3 pb-3">
        <StatPill
          accent="border-indigo-100 dark:border-indigo-900/40"
          icon={<svg className={`${iconCls} text-indigo-500`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" /></svg>}
          label="RSS Memory"
          tip="Resident Set Size — physical RAM occupied by this process"
          value={fmtMem(stats?.memory_rss_mb)}
        />
        <StatPill
          accent="border-indigo-100 dark:border-indigo-900/40"
          icon={<svg className={`${iconCls} text-indigo-400`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M4 7h16M4 12h16M4 17h16" /></svg>}
          label="Virtual Memory"
          tip="Virtual Memory Size — total virtual address space reserved"
          value={fmtMem(stats?.memory_vms_mb)}
        />
        <StatPill
          accent="border-purple-100 dark:border-purple-900/40"
          icon={<svg className={`${iconCls} text-purple-500`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>}
          label="Memory Usage"
          tip="RSS as a percentage of total system RAM"
          value={fmtPct(stats?.memory_percent)}
        />
        <StatPill
          accent="border-blue-100 dark:border-blue-900/40"
          icon={<svg className={`${iconCls} text-blue-500`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>}
          label="CPU Usage"
          tip="CPU time used by this process since the last sample"
          value={fmtPct(stats?.cpu_percent)}
        />
        <StatPill
          accent="border-emerald-100 dark:border-emerald-900/40"
          icon={<svg className={`${iconCls} text-emerald-500`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" /></svg>}
          label="Connected Clients"
          tip="Browser tabs currently subscribed to the live dashboard feed"
          value={`${clients}`}
        />
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  bg,
  text,
  border,
  dot,
}: {
  label: string;
  value: number;
  bg: string;
  text: string;
  border: string;
  dot: string;
}) {
  return (
    <div className={`rounded-2xl border ${border} ${bg} px-4 py-3.5 flex flex-col gap-1 shadow-sm hover:shadow-md transition-shadow`}>
      <div className="flex items-center justify-between">
        <span className={`text-[10px] font-bold uppercase tracking-widest ${text} opacity-60`}>{label}</span>
        <span className={`w-2 h-2 rounded-full ${dot}`} />
      </div>
      <span className={`text-3xl font-extrabold tabular-nums ${text} leading-none`}>{value}</span>
    </div>
  );
}

function AddJobModal({ tasks, onClose }: { tasks: Task[]; onClose: () => void }) {
  const [taskName, setTaskName] = useState(tasks[0]?.name ?? "");
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
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between bg-gray-50/50 dark:bg-gray-800/30">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-white">Add Job</h2>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">Enqueue a new task job</p>
          </div>
          <button type="button" onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-sm">✕</button>
        </div>
        <form onSubmit={(e) => void handleSubmit(e)} className="p-6 space-y-4">
          {err && <p className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950 rounded-xl px-3 py-2 border border-red-100 dark:border-red-900">{err}</p>}
          <div>
            <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1.5">Task</label>
            <select
              value={taskName}
              onChange={(e) => setTaskName((e.target as HTMLSelectElement).value)}
              required
              className="w-full border border-gray-200 dark:border-gray-700 rounded-xl px-3 py-2.5 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {tasks.map((t) => (
                <option key={t.name} value={t.name}>{t.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1.5">
              Arguments <span className="text-gray-300 dark:text-gray-600 normal-case font-normal">(JSON)</span>
            </label>
            <textarea
              value={args}
              onInput={(e) => setArgs((e.target as HTMLTextAreaElement).value)}
              rows={4}
              className="w-full border border-gray-200 dark:border-gray-700 rounded-xl px-3 py-2.5 text-sm font-mono bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
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
              className="w-full border border-gray-200 dark:border-gray-700 rounded-xl px-3 py-2.5 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="flex gap-3 pt-1">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white rounded-xl py-2.5 text-sm font-semibold disabled:opacity-50 transition-all shadow-sm"
            >
              {loading ? "Adding…" : "Add Job"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex-1 border border-gray-200 dark:border-gray-700 rounded-xl py-2.5 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const STATUS_PILL: Record<string, string> = {
  queueing: "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400",
  running: "bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300",
  success: "bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300",
  failure: "bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300",
  stopped: "bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300",
};

function MiniPill({ label, count, cls }: { label: string; count: number; cls: string }) {
  if (count === 0) return null;
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full font-semibold tabular-nums ${cls}`}>
      {count} {label}
    </span>
  );
}

export function DashboardPage() {
  const { push } = useRouter();
  const [showAdd, setShowAdd] = useState(false);
  const [search, setSearch] = useState("");
  const { tasks, stats, clientCount, loading, error } = useStats();

  const totals = useMemo(
    () =>
      tasks.reduce(
        (acc, t) => ({
          total: acc.total + (t.detail.queueing + t.detail.retrying + t.detail.success + t.detail.failure + t.detail.stopped),
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

  const filtered = useMemo(
    () => (search ? tasks.filter((t) => t.name.toLowerCase().includes(search.toLowerCase())) : tasks),
    [tasks, search]
  );

  if (error && tasks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-5">
        <div className="w-14 h-14 rounded-2xl bg-red-50 dark:bg-red-950 border border-red-100 dark:border-red-900 flex items-center justify-center shadow-sm">
          <svg className="w-7 h-7 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div className="text-center space-y-1">
          <p className="font-semibold text-gray-900 dark:text-white">Cannot connect to task queue worker</p>
          <p className="text-sm text-gray-500 dark:text-gray-400">{error}</p>
          <code className="text-xs text-gray-400 dark:text-gray-500 block mt-2 font-mono">{getGraphQLUrl()}</code>
        </div>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-700 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors shadow-sm"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
        <StatCard label="Total" value={totals.total} bg="bg-white dark:bg-gray-900" text="text-gray-900 dark:text-white" border="border-gray-200 dark:border-gray-700" dot="bg-gray-400" />
        <StatCard label="Queued" value={totals.queueing} bg="bg-gray-50 dark:bg-gray-900" text="text-gray-700 dark:text-gray-300" border="border-gray-200 dark:border-gray-700" dot="bg-gray-400" />
        <StatCard label="Running" value={totals.retrying} bg="bg-blue-50 dark:bg-blue-950/60" text="text-blue-700 dark:text-blue-300" border="border-blue-200 dark:border-blue-900" dot="bg-blue-500 animate-pulse" />
        <StatCard label="Success" value={totals.success} bg="bg-emerald-50 dark:bg-emerald-950/60" text="text-emerald-700 dark:text-emerald-300" border="border-emerald-200 dark:border-emerald-900" dot="bg-emerald-500" />
        <StatCard label="Failure" value={totals.failure} bg="bg-red-50 dark:bg-red-950/60" text="text-red-700 dark:text-red-300" border="border-red-200 dark:border-red-900" dot="bg-red-500" />
        <StatCard label="Stopped" value={totals.stopped} bg="bg-amber-50 dark:bg-amber-950/60" text="text-amber-700 dark:text-amber-300" border="border-amber-200 dark:border-amber-900" dot="bg-amber-500" />
      </div>

      <InfoPanel stats={stats} clients={clientCount} />

      <div className="flex items-center justify-between gap-3">
        <div className="relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search tasks…"
            value={search}
            onInput={(e) => setSearch((e.target as HTMLInputElement).value)}
            className="pl-9 pr-3 py-2 border border-gray-200 dark:border-gray-700 rounded-xl text-sm bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 w-56 shadow-sm"
          />
        </div>
        <button
          type="button"
          onClick={() => setShowAdd(true)}
          disabled={tasks.length === 0}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white text-sm font-semibold disabled:opacity-40 transition-all shadow-sm"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Add Job
        </button>
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm">
        {loading && tasks.length === 0 ? (
          <div className="p-16 text-center">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-gray-400">Connecting…</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-16 text-center text-gray-400 dark:text-gray-500">
            <p className="text-sm">{search ? `No tasks matching "${search}"` : "No tasks registered"}</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-800 bg-gray-50/60 dark:bg-gray-800/30">
                <th className="text-left px-5 py-3 text-[11px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-widest">Task</th>
                <th className="text-left px-5 py-3 text-[11px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-widest hidden sm:table-cell">Module</th>
                <th className="text-center px-5 py-3 text-[11px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-widest">Jobs</th>
                <th className="text-left px-5 py-3 text-[11px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-widest">Status</th>
                <th className="text-right px-5 py-3 text-[11px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-widest">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50 dark:divide-gray-800/60">
              {filtered.map((task) => {
                const total = task.detail.queueing + task.detail.retrying + task.detail.success + task.detail.failure + task.detail.stopped;
                const isActive = task.detail.retrying > 0;
                const stopDisabled = task.detail.queueing === 0 && task.detail.retrying === 0;
                return (
                  <tr key={task.name} className="hover:bg-indigo-50/30 dark:hover:bg-indigo-950/20 transition-colors group">
                    <td className="px-5 py-4">
                      <button
                        type="button"
                        onClick={() => push(`/task?task_name=${encodeURIComponent(task.name)}`)}
                        className="font-mono font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-200 text-left flex items-center gap-2"
                      >
                        {isActive && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse flex-shrink-0" />}
                        {task.name}
                      </button>
                    </td>
                    <td className="px-5 py-4 text-gray-400 dark:text-gray-500 text-xs hidden sm:table-cell font-mono">{task.module_name}</td>
                    <td className="px-5 py-4 text-center">
                      <span className="inline-flex items-center justify-center w-8 h-8 rounded-xl bg-gray-100 dark:bg-gray-800 font-bold text-gray-700 dark:text-gray-300 tabular-nums text-sm">{total}</span>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex flex-wrap gap-1.5">
                        <MiniPill label="queued" count={task.detail.queueing} cls={STATUS_PILL.queueing} />
                        <MiniPill label="running" count={task.detail.retrying} cls={STATUS_PILL.running} />
                        <MiniPill label="success" count={task.detail.success} cls={STATUS_PILL.success} />
                        <MiniPill label="failed" count={task.detail.failure} cls={STATUS_PILL.failure} />
                        <MiniPill label="stopped" count={task.detail.stopped} cls={STATUS_PILL.stopped} />
                        {total === 0 && <span className="text-xs text-gray-300 dark:text-gray-700">no jobs</span>}
                      </div>
                    </td>
                    <td className="px-5 py-4 text-right">
                      <div className="flex justify-end items-center gap-1.5 opacity-70 group-hover:opacity-100 transition-opacity">
                        <button
                          type="button"
                          onClick={() => push(`/task?task_name=${encodeURIComponent(task.name)}`)}
                          className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition-colors shadow-sm"
                        >
                          View
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            if (!confirm(`Stop all running/queued jobs for "${task.name}"?`)) return;
                            void gql(STOP_ALL_JOB, { task_name: task.name });
                          }}
                          disabled={stopDisabled}
                          className="w-7 h-7 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950 text-amber-600 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-900 transition-colors flex items-center justify-center text-xs disabled:opacity-30 disabled:cursor-not-allowed"
                          title={stopDisabled ? "No running or queued jobs" : "Stop all running/queued jobs"}
                        >
                          ⏹
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            if (!confirm(`Retry all failure/stopped jobs for "${task.name}"?`)) return;
                            void gql(RETRY_ALL_JOB, { filter: { task_name: task.name, statuses: ["FAILURE", "STOPPED"] } });
                          }}
                          className="w-7 h-7 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900 transition-colors flex items-center justify-center text-xs"
                          title="Retry all failed/stopped"
                        >
                          🔄
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            if (!confirm(`Clear finished jobs for "${task.name}"?`)) return;
                            void gql(CLEAN_JOB, { filter: { task_name: task.name, statuses: ["SUCCESS", "FAILURE", "STOPPED"] } });
                          }}
                          className="w-7 h-7 rounded-lg border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors flex items-center justify-center text-xs"
                          title="Clear jobs"
                        >
                          🗑
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-[11px] text-center text-gray-300 dark:text-gray-700 font-medium tracking-wide">
        Real-time · GraphQL subscriptions · Preact + Vite
      </p>

      {showAdd && <AddJobModal tasks={tasks} onClose={() => setShowAdd(false)} />}
    </div>
  );
}
