import { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "destructive";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  loading?: boolean;
  leftIcon?: ReactNode;
  loadingText?: string;
};

export function Button({
  variant = "primary",
  loading = false,
  leftIcon,
  loadingText = "Processando...",
  className = "",
  children,
  disabled,
  ...props
}: ButtonProps) {
  const isDisabled = disabled || loading;
  const classes = ["btn", `btn-${variant}`, loading ? "is-loading" : "", className].filter(Boolean).join(" ");

  return (
    <button {...props} className={classes} disabled={isDisabled}>
      {loading ? (
        <>
          <span className="btn-spinner" aria-hidden />
          <span>{loadingText}</span>
        </>
      ) : (
        <>
          {leftIcon ? <span aria-hidden>{leftIcon}</span> : null}
          {children}
        </>
      )}
    </button>
  );
}

