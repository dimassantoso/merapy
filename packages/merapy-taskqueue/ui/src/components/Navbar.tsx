import { useEffect, useState } from "preact/hooks";
import { useRouter } from "../lib/router";
import { useStats } from "../lib/StatsContext";

export function Navbar() {
  const [dark, setDark] = useState(false);
  const { serviceTitle } = useStats();
  const { push } = useRouter();

  useEffect(() => {
    const isDark = document.documentElement.classList.contains("dark");
    setDark(isDark);
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }

  return (
    <header className="border-b border-gray-200/80 dark:border-gray-800/80 bg-white/80 dark:bg-gray-950/80 backdrop-blur-md sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        <a
          href="/"
          onClick={(e) => {
            e.preventDefault();
            push("/");
          }}
          className="flex items-center gap-3 group min-w-0"
        >
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center flex-shrink-0 shadow-sm group-hover:shadow-indigo-200 dark:group-hover:shadow-indigo-900 transition-shadow">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
            </svg>
          </div>
          <div className="flex flex-col leading-none flex-shrink-0">
            <span className="font-semibold text-gray-900 dark:text-white text-sm tracking-tight">Merapy</span>
            <span className="text-[10px] text-gray-400 dark:text-gray-500 font-medium tracking-wide">Task Queue</span>
          </div>
          {serviceTitle && (
            <>
              <span className="h-6 w-px bg-gray-200 dark:bg-gray-700 flex-shrink-0" />
              <span className="font-bold text-sm tracking-widest text-gray-700 dark:text-gray-200 truncate uppercase">
                {serviceTitle}
              </span>
            </>
          )}
        </a>

        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="hidden sm:flex items-center gap-1.5 text-[11px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 px-2.5 py-1 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Live
          </span>

          <button
            type="button"
            onClick={toggle}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            aria-label="Toggle dark mode"
          >
            {dark ? (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
