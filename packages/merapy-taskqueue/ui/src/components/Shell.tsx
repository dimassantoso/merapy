import type { ComponentChildren } from "preact";
import { useEffect, useState } from "preact/hooks";
import { useRouter } from "../lib/router";
import { useStats } from "../lib/StatsContext";

interface ShellProps {
  children: ComponentChildren;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onAddJob: () => void;
}

function MerapyMark() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <rect x="2" y="3" width="11" height="3" rx="1.5" fill="var(--accent)" />
      <rect x="2" y="8.5" width="16" height="3" rx="1.5" fill="var(--text)" />
      <rect x="7" y="14" width="11" height="3" rx="1.5" fill="var(--accent)" opacity="0.65" />
    </svg>
  );
}

export function Shell({ children, searchQuery, onSearchChange, onAddJob }: ShellProps) {
  const { pathname, searchParams, push } = useRouter();
  const { tasks, stats, clientCount, error } = useStats();
  const [menuOpen, setMenuOpen] = useState(false);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.getAttribute("data-theme") === "dark");
  }, []);

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    if (next) {
      document.documentElement.setAttribute("data-theme", "dark");
      localStorage.setItem("merapy-theme", "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
      localStorage.setItem("merapy-theme", "light");
    }
  }

  function go(to: string) {
    setMenuOpen(false);
    push(to);
  }

  const cleanPath = pathname.replace(/\/+$/, "") || "/";
  const activeTask = cleanPath === "/task" ? searchParams.get("task_name") ?? "" : "";
  const serviceName = stats?.service_name || "merapy-worker";

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? "open" : ""}`} aria-label="Primary navigation">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px" }}>
          <a
            href="/"
            className="brand-row"
            style={{ flex: 1, minWidth: 0 }}
            onClick={(e) => {
              e.preventDefault();
              go("/");
            }}
          >
            <MerapyMark />
            <div style={{ minWidth: 0 }}>
              <div className="brand-name">Merapy</div>
              <div className="brand-scope mono">{serviceName}</div>
            </div>
          </a>
          <button
            type="button"
            className="btn sm sidebar-close"
            onClick={() => setMenuOpen(false)}
            aria-label="Close navigation"
          >
            Close
          </button>
        </div>

        <nav>
          <div className="nav-group-label">Console</div>
          <button
            type="button"
            className="nav-item"
            aria-current={cleanPath === "/" ? "page" : undefined}
            onClick={() => go("/")}
          >
            <span className="nav-item-main">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
              <span className="nav-item-label">Overview</span>
            </span>
          </button>

          <button
            type="button"
            className="nav-item"
            aria-current={cleanPath === "/task" && !activeTask ? "page" : undefined}
            onClick={() => go("/task")}
          >
            <span className="nav-item-main">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h10" />
              </svg>
              <span className="nav-item-label">All jobs</span>
            </span>
          </button>

          {tasks.length > 0 && (
            <>
              <div className="nav-group-label">Queues</div>
              {tasks.map((t) => {
                const isSelected = cleanPath === "/task" && activeTask === t.name;
                return (
                  <button
                    key={t.name}
                    type="button"
                    className="nav-item"
                    aria-current={isSelected ? "page" : undefined}
                    onClick={() => go(`/task?task_name=${encodeURIComponent(t.name)}`)}
                  >
                    <span className="nav-item-main">
                      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
                      </svg>
                      <span className="nav-item-label mono" style={{ fontSize: "13px" }}>{t.name}</span>
                    </span>
                    {t.detail.failure > 0 && (
                      <span className="nav-count-neg" title={`${t.detail.failure} failed jobs`}>
                        {t.detail.failure}
                      </span>
                    )}
                  </button>
                );
              })}
            </>
          )}
        </nav>

        <div className="sidebar-footer">
          <div className="live-indicator">
            <span className={`live-dot ${error ? "err" : ""}`} aria-hidden="true" />
            <span>
              {error ? "Disconnected" : `Live feed · ${clientCount || 1} client${(clientCount || 1) === 1 ? "" : "s"}`}
            </span>
          </div>
          <button
            type="button"
            className="nav-item"
            onClick={toggleTheme}
            aria-label="Toggle color theme"
          >
            <span className="nav-item-main">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                {dark ? (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                )}
              </svg>
              <span className="nav-item-label">{dark ? "Light theme" : "Dark theme"}</span>
            </span>
          </button>
        </div>
      </aside>

      <header className="topbar">
        <div className="topbar-left">
          <button
            type="button"
            className="btn sm menu-btn"
            onClick={() => setMenuOpen(true)}
            aria-label="Open navigation menu"
          >
            Menu
          </button>
          <div className="topbar-search">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="search"
              placeholder="Filter queues by name or module"
              aria-label="Filter queues by name or module"
              value={searchQuery}
              onInput={(e) => onSearchChange((e.target as HTMLInputElement).value)}
            />
          </div>
        </div>

        <div className="topbar-right">
          <button
            type="button"
            className="btn primary"
            onClick={onAddJob}
            disabled={tasks.length === 0}
          >
            Add job
          </button>
        </div>
      </header>

      <main className="work-sheet">
        <div className="sheet-inner">{children}</div>
      </main>
    </div>
  );
}
