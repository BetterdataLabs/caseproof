"use client";

import clsx from "clsx";
import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import {
  Dialog as RDialog,
  Tabs as RTabs,
  Tooltip as RTooltip,
  DropdownMenu as RMenu,
} from "radix-ui";
import React from "react";

export const cx = clsx;

// Buttons

type Variant = "primary" | "secondary" | "ghost" | "danger" | "subtle" | "amber";
const variants: Record<Variant, string> = {
  primary: "bg-teal-700 text-white hover:bg-teal-800 border border-teal-700 shadow-sm",
  secondary: "bg-white text-ink border border-line hover:border-teal-300 hover:bg-teal-50",
  ghost: "bg-transparent text-muted hover:bg-teal-50 hover:text-teal-800 border border-transparent",
  danger: "bg-red-600 text-white hover:bg-red-700 border border-red-600",
  subtle: "bg-teal-50 text-teal-800 hover:bg-teal-100 border border-teal-100",
  amber: "bg-amber-700 text-white hover:bg-amber-600 border border-amber-700",
};

export const Button = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: Variant;
    size?: "sm" | "md" | "lg";
    loading?: boolean;
    icon?: React.ReactNode;
  }
>(function Button(
  { variant = "primary", size = "md", loading, icon, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-[10px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-55 select-none whitespace-nowrap",
        size === "sm" && "h-8 px-3 text-[13px]",
        size === "md" && "h-10 px-4 text-sm",
        size === "lg" && "h-11 px-5 text-[15px]",
        variants[variant],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
});

// Surfaces

export function Card({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx(
        "rounded-[var(--radius-card)] border border-line bg-paper shadow-[var(--shadow-card)]",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  description,
  actions,
  icon,
  className,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "flex items-start justify-between gap-4 border-b border-line-soft px-5 py-4",
        className,
      )}
    >
      <div className="flex min-w-0 items-start gap-3">
        {icon && <div className="mt-0.5 text-teal-700">{icon}</div>}
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-ink">{title}</h2>
          {description && <p className="mt-0.5 text-[13px] text-muted">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

// Badges

type Tone = "teal" | "blue" | "amber" | "red" | "neutral" | "violet" | "navy" | "green";
const tones: Record<Tone, string> = {
  teal: "bg-teal-100 text-teal-800 border-teal-200",
  green: "bg-teal-100 text-teal-800 border-teal-200",
  blue: "bg-blue-100 text-blue-700 border-blue-200",
  amber: "bg-amber-100 text-amber-700 border-amber-200",
  red: "bg-red-100 text-red-700 border-red-200",
  neutral: "bg-[#f1f4f3] text-muted border-line",
  violet: "bg-violet-100 text-violet-700 border-[#ddd3f5]",
  navy: "bg-navy-900 text-white border-navy-900",
};

export function Badge({
  tone = "neutral",
  children,
  className,
  icon,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
  icon?: React.ReactNode;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11.5px] font-semibold leading-4 whitespace-nowrap",
        tones[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}

// States

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton", className)} aria-hidden />;
}

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      {icon && (
        <div className="mb-3 grid size-11 place-items-center rounded-full bg-teal-50 text-teal-700">
          {icon}
        </div>
      )}
      <p className="text-[15px] font-semibold text-ink">{title}</p>
      {children && <div className="mt-1 max-w-md text-sm text-muted">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
  compact,
}: {
  error: unknown;
  onRetry?: () => void;
  compact?: boolean;
}) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div
      role="alert"
      className={cx(
        "flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 text-red-700",
        compact ? "p-3 text-[13px]" : "p-4 text-sm",
      )}
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="flex-1">
        <p className="font-semibold">Could not load this view</p>
        <p className="mt-0.5 text-red-700/90">{message}</p>
      </div>
      {onRetry && (
        <Button
          size="sm"
          variant="secondary"
          icon={<RefreshCw className="size-3.5" />}
          onClick={onRetry}
        >
          Retry
        </Button>
      )}
    </div>
  );
}

export function Callout({
  tone = "teal",
  title,
  children,
  icon,
  className,
}: {
  tone?: "teal" | "amber" | "blue" | "red" | "neutral";
  title?: React.ReactNode;
  children?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  const map = {
    teal: "border-teal-700 bg-teal-50",
    amber: "border-amber-600 bg-amber-50",
    blue: "border-blue-600 bg-blue-50",
    red: "border-red-600 bg-red-50",
    neutral: "border-subtle bg-[#f5f7f6]",
  }[tone];
  return (
    <div className={cx("flex gap-3 rounded-r-xl border-l-[3px] px-4 py-3 text-sm", map, className)}>
      {icon && <div className="mt-0.5 shrink-0">{icon}</div>}
      <div className="min-w-0">
        {title && <p className="font-semibold text-ink">{title}</p>}
        {children && <div className="text-muted">{children}</div>}
      </div>
    </div>
  );
}

// Forms

export function Field({
  label,
  hint,
  error,
  children,
  htmlFor,
}: {
  label: string;
  hint?: React.ReactNode;
  error?: string;
  children: React.ReactNode;
  htmlFor?: string;
}) {
  const id = React.useId();
  const helpId = `${htmlFor ?? id}-help`;
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-[13px] font-semibold text-ink">
        {label}
      </label>
      {React.Children.map(children, (child) =>
        React.isValidElement<React.AriaAttributes>(child)
          ? React.cloneElement(child, {
              "aria-describedby":
                [child.props["aria-describedby"], hint || error ? helpId : undefined]
                  .filter(Boolean)
                  .join(" ") || undefined,
              "aria-invalid": error ? true : child.props["aria-invalid"],
            })
          : child,
      )}
      {hint && !error && (
        <p id={helpId} className="text-xs leading-relaxed text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={helpId} role="alert" className="text-xs font-medium text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}

export const inputClass =
  "w-full rounded-[10px] border border-line bg-white px-3 py-2 text-sm text-ink placeholder:text-subtle shadow-[inset_0_1px_1px_rgba(17,45,60,0.03)] focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-200 disabled:bg-canvas";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, ...rest }, ref) {
  return (
    <textarea
      ref={ref}
      className={cx(inputClass, "min-h-[84px] resize-y leading-relaxed", className)}
      {...rest}
    />
  );
});

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(function Input({ className, ...rest }, ref) {
  return <input ref={ref} className={cx(inputClass, "h-10", className)} {...rest} />;
});

export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className, children, ...rest }, ref) {
  return (
    <select
      ref={ref}
      className={cx(
        inputClass,
        "h-10 appearance-none bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2212%22 height=%2212%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%2352656c%22 stroke-width=%222%22><path d=%22m6 9 6 6 6-6%22/></svg>')] bg-[length:14px] bg-[right_12px_center] bg-no-repeat pr-9",
        className,
      )}
      {...rest}
    >
      {children}
    </select>
  );
});

// Dialog

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  wide,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: string;
  description?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <RDialog.Root open={open} onOpenChange={onOpenChange}>
      <RDialog.Portal>
        <RDialog.Overlay className="fixed inset-0 z-40 bg-navy-950/45 backdrop-blur-[2px] animate-[var(--animate-fade-in)]" />
        <RDialog.Content
          className={cx(
            "fixed left-1/2 top-1/2 z-50 flex max-h-[min(92vh,880px)] w-[calc(100vw-24px)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-2xl border border-line bg-paper shadow-[var(--shadow-pop)] animate-[var(--animate-fade-in)] focus:outline-none",
            wide ? "max-w-3xl" : "max-w-lg",
          )}
        >
          <div className="border-b border-line-soft px-6 pb-4 pt-5">
            <RDialog.Title className="text-lg font-semibold tracking-[-0.015em] text-ink">
              {title}
            </RDialog.Title>
            {description ? (
              <RDialog.Description className="mt-1 text-sm text-muted">
                {description}
              </RDialog.Description>
            ) : (
              <RDialog.Description className="sr-only">{title}</RDialog.Description>
            )}
          </div>
          <div className="scroll-thin flex-1 overflow-y-auto px-6 py-5">{children}</div>
          {footer && (
            <div className="flex flex-wrap items-center justify-end gap-2 border-t border-line-soft px-6 py-4">
              {footer}
            </div>
          )}
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  );
}

// Tabs

export function Tabs({
  value,
  onValueChange,
  tabs,
  children,
  className,
}: {
  value: string;
  onValueChange: (v: string) => void;
  tabs: { value: string; label: React.ReactNode; count?: number }[];
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <RTabs.Root value={value} onValueChange={onValueChange} className={className}>
      <RTabs.List
        className="scroll-thin flex gap-1 overflow-x-auto border-b border-line px-1"
        aria-label="Sections"
      >
        {tabs.map((t) => (
          <RTabs.Trigger
            key={t.value}
            value={t.value}
            className="relative -mb-px flex shrink-0 items-center gap-1.5 border-b-2 border-transparent px-3 py-2.5 text-[13.5px] font-semibold text-muted transition-colors hover:text-ink data-[state=active]:border-teal-700 data-[state=active]:text-teal-800"
          >
            {t.label}
            {t.count !== undefined && t.count > 0 && (
              <span className="rounded-full bg-[#eef2f0] px-1.5 text-[11px] font-bold text-muted tabular">
                {t.count}
              </span>
            )}
          </RTabs.Trigger>
        ))}
      </RTabs.List>
      {children}
    </RTabs.Root>
  );
}
export const TabPanel = RTabs.Content;

// Tooltips and menus

export function Tip({
  content,
  children,
}: {
  content: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <RTooltip.Root delayDuration={250}>
      <RTooltip.Trigger asChild>{children}</RTooltip.Trigger>
      <RTooltip.Portal>
        <RTooltip.Content
          sideOffset={6}
          className="z-50 max-w-xs rounded-lg bg-navy-900 px-2.5 py-1.5 text-xs leading-relaxed text-white shadow-[var(--shadow-pop)]"
        >
          {content}
          <RTooltip.Arrow className="fill-navy-900" />
        </RTooltip.Content>
      </RTooltip.Portal>
    </RTooltip.Root>
  );
}
export const TooltipProvider = RTooltip.Provider;

export function Menu({
  trigger,
  items,
  align = "end",
}: {
  trigger: React.ReactNode;
  items: (
    | {
        label: string;
        onSelect: () => void;
        icon?: React.ReactNode;
        danger?: boolean;
        disabled?: boolean;
      }
    | "separator"
  )[];
  align?: "start" | "end";
}) {
  return (
    <RMenu.Root>
      <RMenu.Trigger asChild>{trigger}</RMenu.Trigger>
      <RMenu.Portal>
        <RMenu.Content
          align={align}
          sideOffset={6}
          className="z-50 min-w-[220px] rounded-xl border border-line bg-paper p-1 shadow-[var(--shadow-pop)] animate-[var(--animate-fade-in)]"
        >
          {items.map((item, i) =>
            item === "separator" ? (
              <RMenu.Separator key={i} className="my-1 h-px bg-line-soft" />
            ) : (
              <RMenu.Item
                key={item.label}
                disabled={item.disabled}
                onSelect={item.onSelect}
                className={cx(
                  "flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-[13.5px] outline-none data-[disabled]:cursor-not-allowed data-[disabled]:opacity-45 data-[highlighted]:bg-teal-50",
                  item.danger ? "text-red-700" : "text-ink",
                )}
              >
                {item.icon}
                {item.label}
              </RMenu.Item>
            ),
          )}
        </RMenu.Content>
      </RMenu.Portal>
    </RMenu.Root>
  );
}

// Misc

export function Avatar({
  name,
  size = 28,
  tone = "teal",
}: {
  name: string;
  size?: number;
  tone?: "teal" | "navy" | "amber";
}) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
  const map = {
    teal: "bg-teal-100 text-teal-800",
    navy: "bg-navy-800 text-white",
    amber: "bg-amber-100 text-amber-700",
  }[tone];
  return (
    <span
      aria-hidden
      className={cx("inline-grid shrink-0 place-items-center rounded-full font-bold", map)}
      style={{ width: size, height: size, fontSize: size * 0.38 }}
    >
      {initials}
    </span>
  );
}

export function Meter({
  value,
  max,
  label,
  tone = "teal",
}: {
  value: number;
  max: number;
  label: string;
  tone?: "teal" | "amber" | "red" | "blue";
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  const fill = {
    teal: "bg-teal-700",
    amber: "bg-amber-600",
    red: "bg-red-600",
    blue: "bg-blue-600",
  }[tone];
  const track = {
    teal: "bg-teal-100",
    amber: "bg-amber-100",
    red: "bg-red-100",
    blue: "bg-blue-100",
  }[tone];
  return (
    <div
      role="meter"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label}
      className={cx("h-1.5 w-full overflow-hidden rounded-full", track)}
    >
      <div
        className={cx("h-full rounded-full transition-[width] duration-500", fill)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function Mono({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cx("font-mono text-[12px] text-muted", className)}>{children}</span>;
}

export function SectionLabel({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p className={cx("text-[11px] font-bold uppercase tracking-[0.08em] text-subtle", className)}>
      {children}
    </p>
  );
}
