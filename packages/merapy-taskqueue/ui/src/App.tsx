import { useState } from "preact/hooks";
import { AddJobModal } from "./components/AddJobModal";
import { Shell } from "./components/Shell";
import { RouterProvider, useRouter } from "./lib/router";
import { StatsProvider, useStats } from "./lib/StatsContext";
import { DashboardPage } from "./pages/DashboardPage";
import { JobPage } from "./pages/JobPage";
import { TaskPage } from "./pages/TaskPage";

function Workspace() {
  const { pathname } = useRouter();
  const { tasks } = useStats();
  const [searchQuery, setSearchQuery] = useState("");
  const [addModalTask, setAddModalTask] = useState<string | null>(null);

  const clean = pathname.replace(/\/+$/, "") || "/";

  return (
    <>
      <Shell
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onAddJob={() => setAddModalTask("")}
      >
        {clean === "/task" ? (
          <TaskPage onAddJob={(tn) => setAddModalTask(tn ?? "")} />
        ) : clean === "/job" ? (
          <JobPage />
        ) : (
          <DashboardPage searchQuery={searchQuery} />
        )}
      </Shell>

      {addModalTask !== null && (
        <AddJobModal
          tasks={tasks}
          defaultTask={addModalTask || undefined}
          onClose={() => setAddModalTask(null)}
        />
      )}
    </>
  );
}

export function App() {
  return (
    <RouterProvider>
      <StatsProvider>
        <Workspace />
      </StatsProvider>
    </RouterProvider>
  );
}
