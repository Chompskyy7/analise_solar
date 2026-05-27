import { X } from "lucide-react";

export type ToastType = "success" | "error" | "warning" | "info";

export type ToastItem = {
  id: string;
  type?: ToastType;
  title?: string;
  message: string;
};

type ToastProps = {
  toast: ToastItem;
  onClose?: (id: string) => void;
};

export function Toast({ toast, onClose }: ToastProps) {
  const type = toast.type ?? "info";
  return (
    <article className={`toast toast-type-${type}`} role="status" aria-live="polite">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <div style={{ minWidth: 0 }}>
          {toast.title ? <div className="toast-title">{toast.title}</div> : null}
          <div className="toast-message">{toast.message}</div>
        </div>
        {onClose ? (
          <button type="button" className="btn btn-secondary" onClick={() => onClose(toast.id)} aria-label="Fechar toast">
            <X size={12} />
          </button>
        ) : null}
      </div>
    </article>
  );
}

