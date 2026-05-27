type StatusState = "idle" | "running" | "success" | "error";

type StatusBarProps = {
  status: StatusState;
  message: string;
  elapsedMs?: number | null;
};

function formatElapsed(ms?: number | null) {
  if (!ms || ms < 0) return "00:00";
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

export function StatusBar({ status, message, elapsedMs }: StatusBarProps) {
  return (
    <div className="status-strip" role="status" aria-live="polite">
      <div className="status-strip-line" data-status={status} />
      <div className="status-strip-meta">
        <span>{message}</span>
        <span className="status-strip-time">{formatElapsed(elapsedMs)}</span>
      </div>
    </div>
  );
}

