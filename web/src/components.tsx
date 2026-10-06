import { ArrowRight, Check, LoaderCircle, Sparkles } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import type { Data } from "./api";

export function Button({
  children,
  onClick,
  disabled = false,
  secondary = false,
  small = false,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  secondary?: boolean;
  small?: boolean;
  type?: "button" | "submit";
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`button ${secondary ? "secondary" : ""} ${small ? "small" : ""}`}
    >
      {children}
    </button>
  );
}
export function Tag({
  children,
  success = false,
}: {
  children: ReactNode;
  success?: boolean;
}) {
  return (
    <span className={`tag ${success ? "success" : ""}`}>
      {success && <Check size={12} />} {children}
    </span>
  );
}
export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: () => void;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Sparkles size={28} />
      </div>
      <h2>{title}</h2>
      <div className="empty-copy">{children}</div>
      {action && (
        <Button onClick={action}>
          Start a story <ArrowRight size={16} />
        </Button>
      )}
    </div>
  );
}
export function Busy({ text }: { text: string }) {
  return (
    <span className="busy">
      <LoaderCircle size={15} />
      {text}
    </span>
  );
}
export function Header({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {children && <p className="subtitle">{children}</p>}
      </div>
      {action}
    </div>
  );
}

export function Landscape({
  variant = "watercolor",
  large = false,
}: {
  variant?: string;
  large?: boolean;
}) {
  return (
    <svg
      className={`landscape ${variant} ${large ? "large" : ""}`}
      viewBox="0 0 360 190"
      aria-hidden="true"
    >
      <rect width="360" height="190" className="sky" />
      <circle cx="268" cy="47" r="21" className="sun" />
      <path
        d="M0 109 Q38 68 67 82 L129 26 Q150 9 181 61 L228 99 L277 60 Q310 42 360 83 V190 H0Z"
        className="mountain-back"
      />
      <path
        d="M103 54 L129 26 Q148 13 165 38 L183 64 160 55 146 45 131 65Z"
        className="snow"
      />
      <path
        d="M0 128 Q48 82 79 116 Q139 150 201 108 Q270 71 360 120 V190H0Z"
        className="mountain-front"
      />
      <path
        d="M0 153 Q67 127 149 151 Q239 177 360 134 V190H0Z"
        className="water"
      />
      <path
        d="M0 172 Q70 149 116 174 Q180 200 224 183 Q299 157 360 166V190H0Z"
        className="land"
      />
      <g className="trees">
        <path d="M35 169V94L13 140H28L10 156H35L62 153 44 135H54Z" />
        <path d="M321 161V105L303 136H315L300 151H341L329 136H337Z" />
      </g>
      <path
        d="M190 172 Q212 169 235 169 M225 178H259 M90 156H134"
        fill="none"
        className="ripples"
      />
    </svg>
  );
}

export function EpisodePicker({
  count,
  selected,
  setSelected,
}: {
  count: number;
  selected: number[];
  setSelected: (n: number[]) => void;
}) {
  const [draft, setDraft] = useState(selected.join(", "));
  const [editing, setEditing] = useState(false);
  const [countDraft, setCountDraft] = useState("");
  const [editingCount, setEditingCount] = useState(false);
  useEffect(() => {
    if (!editing) setDraft(selected.join(", "));
  }, [selected, editing]);
  useEffect(() => {
    if (!editingCount) {
      const fromStart = selected.every((n, i) => n === i + 1);
      setCountDraft(
        fromStart && selected.length ? String(selected.length) : "",
      );
    }
  }, [selected, editingCount]);
  const choices = [
    { key: "one", label: "1 episode · test", numbers: [1] },
    {
      key: "five",
      label: "First 5",
      numbers: Array.from({ length: Math.min(5, count) }, (_, i) => i + 1),
    },
    {
      key: "all",
      label: `All ${count}`,
      numbers: Array.from({ length: count }, (_, i) => i + 1),
    },
  ];
  return (
    <div className="episode-picker">
      <div className="segmented">
        {choices.map((c, index) => (
          <button
            key={c.key}
            onClick={() => {
              setEditing(false);
              setDraft(c.numbers.join(", "));
              setSelected(c.numbers);
            }}
            aria-pressed={
              JSON.stringify(selected) === JSON.stringify(c.numbers) &&
              !choices
                .slice(0, index)
                .some(
                  (other) =>
                    JSON.stringify(other.numbers) === JSON.stringify(selected),
                )
            }
          >
            {c.label}
          </button>
        ))}
      </div>
      <label className="inline-field">
        First N episodes
        <input
          type="number"
          min={1}
          max={count}
          aria-label="Custom episode count"
          placeholder="Count"
          value={countDraft}
          onFocus={() => setEditingCount(true)}
          onBlur={() => setEditingCount(false)}
          onChange={(e) => {
            setCountDraft(e.target.value);
            const amount = Number(e.target.value);
            setSelected(
              Number.isInteger(amount) && amount >= 1 && amount <= count
                ? Array.from({ length: amount }, (_, i) => i + 1)
                : [],
            );
          }}
        />
      </label>
      <label className="inline-field">
        Custom episodes{" "}
        <input
          aria-label="Custom episode numbers"
          placeholder="e.g. 1, 3, 5"
          value={draft}
          onFocus={() => setEditing(true)}
          onBlur={() => setEditing(false)}
          onChange={(e) => {
            setDraft(e.target.value);
            const nums = e.target.value
              .split(",")
              .map((x) => Number(x.trim()))
              .filter((n) => Number.isInteger(n) && n > 0 && n <= count);
            setSelected([...new Set(nums)]);
          }}
        />
      </label>
    </div>
  );
}

export function EmotionCurve({
  beats,
  duration,
}: {
  beats: Data[];
  duration: number;
}) {
  if (!beats?.length) return null;
  const points = beats
    .map(
      (b) =>
        `${Math.min(1, b.seconds / duration) * 270 + 10},${70 - b.intensity * 5}`,
    )
    .join(" ");
  return (
    <div className="emotion-curve">
      <svg
        viewBox="0 0 290 90"
        role="img"
        aria-label={`Emotion curve: ${beats.map((b) => `${b.emotion} at ${b.seconds} seconds`).join(", ")}`}
      >
        <path d="M10 70H280" stroke="#dedfd4" />
        <polyline
          points={points}
          fill="none"
          stroke="#487063"
          strokeWidth="2"
        />
        {beats.map((b, i) => (
          <circle
            key={i}
            cx={Math.min(1, b.seconds / duration) * 270 + 10}
            cy={70 - b.intensity * 5}
            r="3"
            fill="#487063"
          />
        ))}
      </svg>
      <div className="curve-labels">
        <span>Opening</span>
        <span>Emotional progression</span>
        <span>{duration}s</span>
      </div>
    </div>
  );
}
