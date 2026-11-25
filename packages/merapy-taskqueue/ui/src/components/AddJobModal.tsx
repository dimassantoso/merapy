import { useState } from "preact/hooks";
import { ADD_JOB, gql, type Task } from "../lib/graphql";

interface Props {
  tasks: Task[];
  defaultTask?: string;
  onClose: () => void;
}

export function AddJobModal({ tasks, defaultTask, onClose }: Props) {
  const [taskName, setTaskName] = useState(defaultTask || tasks[0]?.name || "");
  const [args, setArgs] = useState("{}");
  const [maxRetry, setMaxRetry] = useState(3);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState("");

  async function handleSubmit(e: Event) {
    e.preventDefault();
    setSubmitting(true);
    setErr("");
    try {
      await gql(ADD_JOB, { param: { task_name: taskName, max_retry: maxRetry, args } });
      onClose();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Failed to enqueue job");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="add-job-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-dialog">
        <div className="modal-head">
          <h2 id="add-job-title">Enqueue job</h2>
          <button type="button" className="btn sm text-action" onClick={onClose} aria-label="Close dialog">
            Close
          </button>
        </div>
        <form onSubmit={(e) => void handleSubmit(e)}>
          <div className="modal-body">
            {err && <div className="error-inline">{err}</div>}
            <div className="field">
              <label htmlFor="add-job-task">Task queue</label>
              <select
                id="add-job-task"
                className="input mono"
                value={taskName}
                onChange={(e) => setTaskName((e.target as HTMLSelectElement).value)}
                required
              >
                {tasks.map((t) => (
                  <option key={t.name} value={t.name}>{t.name}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="add-job-args">Arguments (JSON)</label>
              <textarea
                id="add-job-args"
                className="input mono"
                value={args}
                onInput={(e) => setArgs((e.target as HTMLTextAreaElement).value)}
                rows={4}
                placeholder='{"order_id": 1042}'
              />
            </div>
            <div className="field">
              <label htmlFor="add-job-retry">Maximum retries</label>
              <input
                id="add-job-retry"
                type="number"
                className="input num"
                value={maxRetry}
                min={1}
                max={100}
                onInput={(e) => setMaxRetry(Number((e.target as HTMLInputElement).value))}
              />
              <span className="field-hint">Between 1 and 100 attempts before marking failed.</span>
            </div>
          </div>
          <div className="modal-foot">
            <button type="button" className="btn" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn primary" disabled={submitting || !taskName}>
              {submitting ? "Enqueuing…" : "Enqueue job"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
