import { Navbar } from "./components/Navbar";
import { RouterProvider, useRouter } from "./lib/router";
import { StatsProvider } from "./lib/StatsContext";
import { DashboardPage } from "./pages/DashboardPage";
import { JobPage } from "./pages/JobPage";
import { TaskPage } from "./pages/TaskPage";

function PageSwitch() {
  const { pathname } = useRouter();
  const clean = pathname.replace(/\/+$/, "") || "/";
  if (clean === "/task") return <TaskPage />;
  if (clean === "/job") return <JobPage />;
  return <DashboardPage />;
}

export function App() {
  return (
    <RouterProvider>
      <StatsProvider>
        <Navbar />
        <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
          <PageSwitch />
        </main>
      </StatsProvider>
    </RouterProvider>
  );
}
