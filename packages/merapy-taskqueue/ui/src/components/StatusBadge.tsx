interface Props {
  status: string;
  size?: "sm" | "md";
}

const CONFIG: Record<string, { dot: string; bg: string; text: string; label: string }> = {
  QUEUEING: { dot: "bg-gray-400", bg: "bg-gray-100 dark:bg-gray-800", text: "text-gray-700 dark:text-gray-300", label: "Queueing" },
  RETRYING: { dot: "bg-blue-500 animate-pulse", bg: "bg-blue-50 dark:bg-blue-950", text: "text-blue-700 dark:text-blue-300", label: "Running" },
  SUCCESS: { dot: "bg-green-500", bg: "bg-green-50 dark:bg-green-950", text: "text-green-700 dark:text-green-300", label: "Success" },
  FAILURE: { dot: "bg-red-500", bg: "bg-red-50 dark:bg-red-950", text: "text-red-700 dark:text-red-300", label: "Failure" },
  STOPPED: { dot: "bg-amber-500", bg: "bg-amber-50 dark:bg-amber-950", text: "text-amber-700 dark:text-amber-300", label: "Stopped" },
};

export function StatusBadge({ status, size = "sm" }: Props) {
  const c = CONFIG[status] ?? {
    dot: "bg-gray-400",
    bg: "bg-gray-100 dark:bg-gray-800",
    text: "text-gray-600 dark:text-gray-400",
    label: status,
  };
  const pad = size === "md" ? "px-2.5 py-1" : "px-2 py-0.5";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-medium ${pad} text-xs ${c.bg} ${c.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${c.dot}`} />
      {c.label}
    </span>
  );
}
