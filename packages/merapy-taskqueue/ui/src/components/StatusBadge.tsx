interface Props {
  status: string;
}

const STATUS_MAP: Record<string, { cls: string; label: string }> = {
  QUEUEING: { cls: "", label: "Queued" },
  RETRYING: { cls: "run", label: "Running" },
  SUCCESS: { cls: "pos", label: "Success" },
  FAILURE: { cls: "neg", label: "Failed" },
  STOPPED: { cls: "warn", label: "Stopped" },
};

export function StatusBadge({ status }: Props) {
  const cfg = STATUS_MAP[status] ?? { cls: "", label: status };
  return (
    <span className={`pill ${cfg.cls}`}>
      <span className="pill-dot" aria-hidden="true" />
      {cfg.label}
    </span>
  );
}
