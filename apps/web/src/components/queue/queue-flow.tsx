"use client";

/**
 * Animated work queue overview: one lane per queue state, one dot per case.
 * Dots move between lanes when a refetch shows a case changed state. When the fullest lane runs out of room,
 * every lane switches to the same coarser scale (one dot = 5, 10, 25… cases) so lanes stay comparable.
 * React renders the lanes; FlowEngine positions and animates the dots imperatively.
 */
import { BadgeCheck, Clock3, Hand, Loader2, PauseCircle } from "lucide-react";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import type { CaseSummary } from "@/lib/types";
import { cx } from "@/components/ui/primitives";

const LANES = [
  {
    key: "needs_decision",
    label: "Needs a decision",
    hint: "A reviewer must decide a specific question",
    icon: Hand,
    color: "#a86a12",
    tone: "text-amber-700",
  },
  {
    key: "working",
    label: "Agent working",
    hint: "The agent is inspecting, checking or requesting",
    icon: Loader2,
    color: "#2563a8",
    tone: "text-blue-700",
  },
  {
    key: "waiting_customer",
    label: "Waiting for the business",
    hint: "A tracked request is outstanding",
    icon: Clock3,
    color: "#5b3fa8",
    tone: "text-violet-700",
  },
  {
    key: "paused",
    label: "Paused",
    hint: "Automation stopped with work preserved",
    icon: PauseCircle,
    color: "#c0392b",
    tone: "text-red-700",
  },
  {
    key: "complete",
    label: "Complete",
    hint: "Review summary ready for the financing process",
    icon: BadgeCheck,
    color: "#00806f",
    tone: "text-teal-800",
  },
] as const;

type LaneKey = (typeof LANES)[number]["key"];
const LANE = Object.fromEntries(LANES.map((l) => [l.key, l])) as Record<
  LaneKey,
  (typeof LANES)[number]
>;
const isLane = (key: string): key is LaneKey => key in LANE;

const STEPS = [1, 5, 10, 25, 50, 100, 250, 500, 1000];
const ROWS = 4;
const CELL = 26;
const PAD = 6;
const perRow = (width: number) => Math.max(1, Math.floor((width - PAD * 2 + 2) / CELL));
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

interface Unit {
  id: string;
  lane: LaneKey;
  cases: CaseSummary[];
  size: number;
  fill: number;
}

interface Track {
  items: CaseSummary[];
  known: Map<string, LaneKey>;
  newest: string;
  changed: string[];
}

function startTrack(items: CaseSummary[]): Track {
  const known = new Map<string, LaneKey>();
  let newest = "";
  for (const c of items) {
    if (isLane(c.status.key)) known.set(c.id, c.status.key);
    if (c.created_at > newest) newest = c.created_at;
  }
  return { items, known, newest, changed: [] };
}

// Animate cases that moved or were created since the preceding refetch.
function advanceTrack(prev: Track, items: CaseSummary[]): Track {
  const known = new Map(prev.known);
  const changed: string[] = [];
  let newest = prev.newest;
  for (const c of items) {
    const key = c.status.key;
    if (!isLane(key)) continue;
    const before = known.get(c.id);
    const moved = before === undefined ? c.created_at > prev.newest : before !== key;
    if (moved) changed.push(c.id);
    known.set(c.id, key);
    if (c.created_at > newest) newest = c.created_at;
  }
  return {
    items,
    known,
    newest,
    changed,
  };
}

function unitsFor(lane: LaneKey, members: CaseSummary[], total: number, scale: number): Unit[] {
  const sorted = [...members].sort((a, b) => a.reference.localeCompare(b.reference));
  const size = Math.max(total, sorted.length);
  const out: Unit[] = [];
  if (scale === 1) {
    for (let i = 0; i < size; i++) {
      const c = sorted[i];
      // Counts can exceed the loaded page; those cases still get a dot, without case details.
      out.push({ id: c ? c.id : `${lane}~${i}`, lane, cases: c ? [c] : [], size: 1, fill: 100 });
    }
    return out;
  }
  for (let i = 0; i < size; i += scale) {
    const n = Math.min(scale, size - i);
    out.push({
      id: `${lane}#${i / scale}`,
      lane,
      cases: sorted.slice(i, i + n),
      size: n,
      fill: (n / scale) * 100,
    });
  }
  return out;
}

type Handlers = { open: (id: string) => void; select: (lane: LaneKey) => void };
type DotUnit = Unit & { scale: number };

class FlowEngine {
  private dots = new Map<string, HTMLButtonElement>();
  private units = new WeakMap<HTMLButtonElement, DotUnit>();
  private prevPos = new Map<string, [number, number]>();
  private timers = new Set<ReturnType<typeof setTimeout>>();
  private tip: HTMLDivElement;
  handlers: Handlers = { open: () => {}, select: () => {} };

  constructor(private stage: HTMLDivElement) {
    this.tip = document.createElement("div");
    this.tip.className = "queue-flow-tip";
    this.tip.setAttribute("role", "tooltip");
    document.body.append(this.tip);
  }

  destroy() {
    for (const t of this.timers) clearTimeout(t);
    for (const node of this.dots.values()) node.remove();
    this.stage.querySelectorAll(".queue-flow-dot, .queue-flow-particle").forEach((n) => n.remove());
    this.tip.remove();
  }

  private later(fn: () => void, ms: number) {
    const t = setTimeout(() => {
      this.timers.delete(t);
      fn();
    }, ms);
    this.timers.add(t);
  }

  private place(node: HTMLElement, [x, y]: [number, number]) {
    node.style.transform = `translate(${x}px, ${y}px)`;
  }

  private showTip(node: HTMLButtonElement, event?: PointerEvent) {
    const u = this.units.get(node);
    if (!u) return;
    const lines: [string, boolean][] = [];
    if (u.scale === 1 && u.cases.length === 1) {
      const c = u.cases[0];
      lines.push([c.reference, true], [c.title, false], [LANE[u.lane].label, false]);
    } else if (u.scale === 1) {
      lines.push(
        ["1 case", true],
        [LANE[u.lane].label, false],
        ["Not on this page of results", false],
      );
    } else {
      const refs = u.cases.map((c) => c.reference.replace(/^CP-\d{4}-/, "#"));
      lines.push([plural(u.size, "case", "cases"), true], [LANE[u.lane].label, false]);
      if (refs.length) {
        lines.push([
          refs.length > 6 ? `${refs.slice(0, 6).join(", ")} +${u.size - 6}` : refs.join(", "),
          false,
        ]);
      }
      lines.push(["Click to filter the list", false]);
    }
    this.tip.replaceChildren(
      ...lines.map(([text, strong]) => {
        const row = document.createElement(strong ? "strong" : "span");
        row.textContent = text;
        return row;
      }),
    );
    const r = node.getBoundingClientRect();
    const x = event ? event.clientX : r.left + r.width / 2;
    const y = event ? event.clientY : r.top;
    this.tip.classList.add("is-visible");
    const w = this.tip.offsetWidth;
    const h = this.tip.offsetHeight;
    this.tip.style.left = `${Math.min(window.innerWidth - w - 8, Math.max(8, x + 12))}px`;
    this.tip.style.top = `${Math.max(8, y - h - 12)}px`;
  }

  private hideTip = () => this.tip.classList.remove("is-visible");

  private dot(id: string): [HTMLButtonElement, boolean] {
    const existing = this.dots.get(id);
    if (existing) return [existing, false];
    const node = document.createElement("button");
    node.type = "button";
    node.className = "queue-flow-dot";
    node.addEventListener("pointermove", (e) => this.showTip(node, e));
    node.addEventListener("focus", () => this.showTip(node));
    node.addEventListener("pointerleave", this.hideTip);
    node.addEventListener("blur", this.hideTip);
    node.addEventListener("click", () => {
      const u = this.units.get(node);
      if (!u) return;
      this.hideTip();
      if (u.scale === 1 && u.cases.length === 1) this.handlers.open(u.cases[0].id);
      else this.handlers.select(u.lane);
    });
    this.stage.append(node);
    this.dots.set(id, node);
    return [node, true];
  }

  private fly(lane: LaneKey, from: [number, number], to: [number, number]) {
    const p = document.createElement("div");
    p.className = "queue-flow-particle";
    p.style.setProperty("--dot", LANE[lane].color);
    p.style.transition = "none";
    this.place(p, from);
    this.stage.append(p);
    void p.offsetWidth;
    p.style.transition = "";
    this.place(p, to);
    p.style.opacity = "0";
    this.later(() => p.remove(), 1000);
  }

  layout(
    lanes: Record<LaneKey, Unit[]>,
    bodies: Partial<Record<LaneKey, HTMLDivElement | null>>,
    opts: { scale: number; columns: number; changed: string[]; animate: boolean },
  ) {
    const { scale, columns, animate } = opts;
    const changed = new Set(opts.changed);
    const stage = this.stage.getBoundingClientRect();
    const newPos = new Map<string, [number, number]>();
    const laneOf = new Map<string, LaneKey>();
    const seen = new Set<string>();
    const entering: [HTMLButtonElement, [number, number]][] = [];
    for (const lane of LANES) {
      const body = bodies[lane.key]?.getBoundingClientRect();
      if (!body) continue;
      lanes[lane.key].forEach((u, i) => {
        const target: [number, number] = [
          body.left - stage.left + PAD + (i % columns) * CELL,
          body.top - stage.top + PAD + Math.floor(i / columns) * CELL,
        ];
        newPos.set(u.id, target);
        for (const c of u.cases) {
          newPos.set(c.id, target);
          laneOf.set(c.id, lane.key);
        }
        const [node, fresh] = this.dot(u.id);
        this.units.set(node, { ...u, scale });
        node.style.setProperty("--dot", lane.color);
        node.style.setProperty("--fill", u.fill.toFixed(1));
        node.classList.toggle("is-partial", u.fill < 100);
        node.classList.remove("is-leaving");
        node.setAttribute(
          "aria-label",
          scale === 1 && u.cases.length === 1
            ? `${u.cases[0].reference}, ${lane.label}. Open case`
            : `${plural(u.size, "case", "cases")}, ${lane.label}. Filter the list`,
        );
        if (animate && u.cases.some((c) => changed.has(c.id))) {
          node.classList.remove("is-pulsing");
          void node.offsetWidth;
          node.classList.add("is-pulsing");
          this.later(() => node.classList.remove("is-pulsing"), 2700);
        }
        if (fresh) {
          // New dots grow out of where their first case was last drawn, so regrouping reads as a merge.
          const from = this.prevPos.get(u.cases[0]?.id ?? "");
          node.style.transition = "none";
          if (from && animate) this.place(node, from);
          else {
            this.place(node, target);
            if (animate) node.classList.add("is-entering");
          }
          entering.push([node, target]);
        } else {
          if (!animate) node.style.transition = "none";
          this.place(node, target);
        }
        seen.add(u.id);
      });
    }
    for (const [id, node] of this.dots) {
      if (seen.has(id)) continue;
      // Departing dots travel to where their cases now sit before fading, so nothing blinks out.
      const unit = this.units.get(node);
      const next = unit?.cases.map((c) => newPos.get(c.id)).find(Boolean);
      if (next && animate) this.place(node, next);
      node.classList.add("is-leaving");
      this.dots.delete(id);
      this.later(() => node.remove(), animate ? 900 : 0);
    }
    if (animate && scale > 1) {
      for (const id of changed) {
        const from = this.prevPos.get(id);
        const to = newPos.get(id);
        const lane = laneOf.get(id);
        if (from && to && lane && (from[0] !== to[0] || from[1] !== to[1]))
          this.fly(lane, from, to);
      }
    }
    requestAnimationFrame(() => {
      for (const node of this.dots.values()) void node.offsetWidth;
      for (const node of this.dots.values()) node.style.transition = "";
      requestAnimationFrame(() => {
        for (const [node, target] of entering) {
          this.place(node, target);
          node.classList.remove("is-entering");
        }
      });
    });
    this.prevPos = newPos;
  }
}

/* Tiles or flow, remembered per browser. */
const SUMMARY_KEY = "caseproof.queue.summary";
type SummaryMode = "flow" | "tiles";
const summaryListeners = new Set<() => void>();
function subscribeSummary(onChange: () => void) {
  summaryListeners.add(onChange);
  window.addEventListener("storage", onChange);
  return () => {
    summaryListeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}
const readSummary = (): SummaryMode =>
  localStorage.getItem(SUMMARY_KEY) === "tiles" ? "tiles" : "flow";

export function useQueueSummaryMode(): [SummaryMode, (mode: SummaryMode) => void] {
  const mode = useSyncExternalStore(subscribeSummary, readSummary, () => "flow" as const);
  const set = (next: SummaryMode) => {
    localStorage.setItem(SUMMARY_KEY, next);
    summaryListeners.forEach((l) => l());
  };
  return [mode, set];
}

export function QueueFlow({
  items,
  counts,
  view,
  onSelect,
  onOpen,
}: {
  items: CaseSummary[];
  counts: Record<string, number>;
  view: string;
  onSelect: (lane: string) => void;
  onOpen: (id: string) => void;
}) {
  const stageRef = useRef<HTMLDivElement>(null);
  const bodies = useRef<Partial<Record<LaneKey, HTMLDivElement | null>>>({});
  const engineRef = useRef<FlowEngine | null>(null);
  const handled = useRef<Track | null>(null);
  const [bodyWidth, setBodyWidth] = useState(0);
  const [track, setTrack] = useState(() => startTrack(items));
  if (track.items !== items) setTrack(advanceTrack(track, items));

  const totals = useMemo(() => {
    const out = Object.fromEntries(LANES.map((l) => [l.key, 0])) as Record<LaneKey, number>;
    for (const c of track.items) if (isLane(c.status.key)) out[c.status.key] += 1;
    for (const l of LANES) out[l.key] = Math.max(out[l.key], counts[l.key] ?? 0);
    return out;
  }, [track.items, counts]);
  const columns = perRow(bodyWidth);
  const scale = bodyWidth
    ? (STEPS.find((s) => Math.ceil(Math.max(...Object.values(totals)) / s) <= columns * ROWS) ??
      STEPS[STEPS.length - 1])
    : 1;
  const lanes = useMemo(() => {
    const out = {} as Record<LaneKey, Unit[]>;
    for (const l of LANES) {
      const members = track.items.filter((c) => c.status.key === l.key);
      out[l.key] = unitsFor(l.key, members, totals[l.key], scale);
    }
    return out;
  }, [track.items, totals, scale]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const engine = new FlowEngine(stage);
    engineRef.current = engine;
    const observer = new ResizeObserver(() =>
      setBodyWidth(bodies.current.needs_decision?.clientWidth ?? 0),
    );
    observer.observe(stage);
    return () => {
      observer.disconnect();
      engine.destroy();
      engineRef.current = null;
      handled.current = null;
    };
  }, []);

  useEffect(() => {
    if (engineRef.current) engineRef.current.handlers = { open: onOpen, select: onSelect };
  });

  useEffect(() => {
    const engine = engineRef.current;
    if (!engine || !bodyWidth) return;
    const fresh = handled.current !== null && handled.current !== track;
    handled.current = track;
    engine.layout(lanes, bodies.current, {
      scale,
      columns,
      changed: fresh ? track.changed : [],
      animate: fresh,
    });
  }, [track, lanes, scale, columns, bodyWidth]);

  const total = Object.values(totals).reduce((s, n) => s + n, 0);

  return (
    <div className="rounded-[var(--radius-card)] border border-line bg-paper p-4 shadow-[var(--shadow-card)]">
      <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-2">
        <span className="inline-flex items-center gap-3 rounded-full border border-line px-3 py-1 text-[12px] text-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block size-3 rounded-full bg-muted" aria-hidden />
            <b className="font-semibold text-ink">1 dot = {plural(scale, "case", "cases")}</b>
          </span>
          {scale > 1 && (
            <span className="inline-flex items-center gap-1.5">
              <span
                className="inline-block size-3 rounded-full shadow-[inset_0_0_0_1.5px_var(--color-muted)]"
                style={{ background: "conic-gradient(var(--color-muted) 40%, transparent 0)" }}
                aria-hidden
              />
              fewer than {scale}
            </span>
          )}
        </span>
        <span className="text-[12.5px] text-muted">
          <b className="text-ink">{total}</b> cases · {totals.complete} complete
          {total ? ` (${Math.round((totals.complete / total) * 100)}%)` : ""} ·{" "}
          {total - totals.complete} open
        </span>
        <span className="ml-auto text-[12px] text-subtle">
          Dots move as cases change. Hover for details.
        </span>
      </div>

      <div ref={stageRef} className="relative">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {LANES.map((l) => {
            const Icon = l.icon;
            const active = view === l.key;
            const rows = Math.max(ROWS, Math.ceil(lanes[l.key].length / columns));
            return (
              <div
                key={l.key}
                className={cx(
                  "rounded-[12px] border p-3 transition-colors",
                  active ? "border-teal-700 ring-2 ring-teal-200" : "border-line-soft",
                )}
              >
                <button
                  type="button"
                  onClick={() => onSelect(active ? "all" : l.key)}
                  aria-pressed={active}
                  className="w-full rounded-md text-left"
                >
                  <div className="flex min-h-[34px] items-start justify-between gap-2">
                    <span className="inline-flex items-start gap-1.5 text-[12.5px] font-semibold leading-[17px] text-muted">
                      <span
                        className="mt-[5px] inline-block size-2 shrink-0 rounded-full"
                        style={{ background: l.color }}
                        aria-hidden
                      />
                      {l.label}
                    </span>
                    <Icon
                      className={cx(
                        "size-4 shrink-0",
                        l.tone,
                        l.key === "working" && totals.working > 0 && "animate-spin",
                      )}
                      aria-hidden
                    />
                  </div>
                  <p
                    className={cx(
                      "mt-1.5 text-[26px] font-bold leading-none tracking-[-0.03em]",
                      totals[l.key] > 0 ? "text-ink" : "text-subtle",
                    )}
                  >
                    {totals[l.key]}
                  </p>
                  <p className="mt-1.5 line-clamp-2 min-h-[30px] text-[11.5px] leading-snug text-subtle">
                    {l.hint}
                  </p>
                </button>
                <div
                  ref={(node) => {
                    bodies.current[l.key] = node;
                  }}
                  className="mt-2 rounded-[10px] bg-[#f4f7f5]"
                  style={{ height: rows * CELL + PAD * 2 - 2 }}
                />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
