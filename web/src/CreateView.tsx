import { useRef, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Check,
  FileText,
  Film,
  Leaf,
  Upload,
  X,
} from "lucide-react";
import { api } from "./api";
import type { Data } from "./api";
import { Button, Header, Landscape } from "./components";

export default function CreateView({
  catalog,
  onCreate,
  busy,
}: {
  catalog: Data;
  onCreate: (data: Data) => Promise<void>;
  busy: boolean;
}) {
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("");
  const [filename, setFilename] = useState("");
  const [mode, setMode] = useState("general");
  const [style, setStyle] = useState("watercolor");
  const [seconds, setSeconds] = useState(120);
  const [age, setAge] = useState("6–9");
  const [direction, setDirection] = useState("");
  const [fidelity, setFidelity] = useState("faithful");
  const [aspect, setAspect] = useState("16:9");
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  async function readFile(f: File) {
    setError("");
    if (!/\.(txt|md)$/i.test(f.name) || f.size > 2_000_000) {
      setError("Choose a UTF-8 .txt or .md file smaller than 2 MB.");
      return;
    }
    try {
      const text = new TextDecoder("utf-8", { fatal: true }).decode(
        await f.arrayBuffer(),
      );
      setSource(text);
      setFilename(f.name);
      if (!title) setTitle(f.name.replace(/\.[^.]+$/, ""));
    } catch {
      setError(
        "This file is not UTF-8 text. Please export it as a UTF-8 .txt file.",
      );
    }
  }
  async function sample(name: string) {
    if (!name) return;
    const data = await api("/samples/" + encodeURIComponent(name));
    setSource(data.source);
    setFilename(name);
    setTitle(data.source.split("\n")[0]);
  }
  const chosen = catalog.styles?.find((s: Data) => s.id === style);
  return (
    <>
      <Header
        eyebrow="YOUR DIRECTOR'S DESK"
        title="A little story. A whole world."
      >
        Turn the stories you love into beautifully directed short episodes.
      </Header>
      <div className="create-grid">
        <div className="create-main">
          <section className="section">
            <div className="section-heading">
              <span className="step-number">01</span>
              <div>
                <h2>Start with your story</h2>
                <p>A fable, a mystery, an entire novel. Bring your words.</p>
              </div>
            </div>
            <div
              className={`upload ${dragging ? "dragging" : ""} ${source ? "has-file" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                if (e.dataTransfer.files[0])
                  void readFile(e.dataTransfer.files[0]);
              }}
            >
              <input
                ref={file}
                type="file"
                accept=".txt,.md,text/plain"
                onChange={(e) =>
                  e.target.files?.[0] && void readFile(e.target.files[0])
                }
                aria-label="Upload story text"
                className="file-input"
              />
              {source ? (
                <>
                  <FileText size={29} />
                  <strong>{filename || title || "Your story"}</strong>
                  <span>
                    {source.trim().split(/\s+/).length.toLocaleString()} words ·
                    ready to adapt
                  </span>
                  <button
                    className="text-button"
                    onClick={() => {
                      setSource("");
                      setFilename("");
                    }}
                  >
                    Replace story <X size={13} />
                  </button>
                </>
              ) : (
                <>
                  <div className="upload-icon">
                    <Upload size={23} />
                  </div>
                  <strong>Drop your story here</strong>
                  <span>UTF-8 .txt or .md · up to 2 MB</span>
                  <Button secondary small onClick={() => file.current?.click()}>
                    Browse files
                  </Button>
                </>
              )}
            </div>
            <div className="sample-line">
              <BookOpen size={15} />
              <label htmlFor="sample">Need a starting point?</label>
              <select
                id="sample"
                value=""
                onChange={(e) =>
                  void sample(e.target.value).catch((x) => setError(x.message))
                }
              >
                <option value="">Try a sample story</option>
                {catalog.samples?.map((s: Data) => (
                  <option key={s.file} value={s.file}>
                    {s.title}
                  </option>
                ))}
              </select>
            </div>
            <details className="paste">
              <summary>Or paste your story</summary>
              <textarea
                aria-label="Story text"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                placeholder="Once upon a time…"
                rows={7}
              />
            </details>
            <label className="field">
              Project title
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Give your story a working title"
                maxLength={200}
              />
            </label>
          </section>
          <section className="section">
            <div className="section-heading">
              <span className="step-number">02</span>
              <div>
                <h2>Choose your audience</h2>
                <p>The same story can be told in different ways.</p>
              </div>
            </div>
            <div className="mode-grid">
              <button
                className={`mode-card ${mode === "general" ? "selected" : ""}`}
                onClick={() => setMode("general")}
                aria-pressed={mode === "general"}
              >
                <Film size={21} />
                <strong>General stories</strong>
                <span>
                  Compelling hooks, emotional turns, and cinematic direction.
                </span>
                {mode === "general" && (
                  <Check className="selection-check" size={15} />
                )}
              </button>
              <button
                className={`mode-card ${mode === "children" ? "selected" : ""}`}
                onClick={() => setMode("children")}
                aria-pressed={mode === "children"}
              >
                <Leaf size={21} />
                <strong>Children's stories</strong>
                <span>
                  Clear storytelling, gentle pacing, and a little wonder.
                </span>
                {mode === "children" && (
                  <Check className="selection-check" size={15} />
                )}
              </button>
            </div>
            <div className="field-row">
              <label className="field">
                Episode length
                <select
                  value={seconds}
                  onChange={(e) => setSeconds(Number(e.target.value))}
                >
                  {[60, 120, 180, 240].map((n) => (
                    <option key={n} value={n}>
                      {n / 60} minute{n > 60 ? "s" : ""}
                    </option>
                  ))}
                </select>
              </label>
              {mode === "children" ? (
                <label className="field">
                  Age range
                  <select value={age} onChange={(e) => setAge(e.target.value)}>
                    {["3–5", "6–9", "10–12"].map((a) => (
                      <option key={a}>{a}</option>
                    ))}
                  </select>
                </label>
              ) : (
                <label className="field">
                  Format
                  <select
                    value={aspect}
                    onChange={(e) => setAspect(e.target.value)}
                  >
                    <option value="16:9">Landscape · 16:9</option>
                    <option value="9:16">Portrait · 9:16</option>
                  </select>
                </label>
              )}
            </div>
          </section>
        </div>
        <aside className="create-aside">
          <div className="preview-art">
            <Landscape large variant={style} />
            <div className="art-label">THE WORLD BEGINS WITH A STORY</div>
          </div>
          <div className="aside-body">
            <p className="eyebrow">FROM PAGE TO SCREEN</p>
            <h2>
              You imagine.
              <br />
              Your studio brings it to life.
            </h2>
            <ol className="journey">
              <li>
                <span>1</span>
                <div>
                  <strong>A world that stays yours</strong>
                  <p>
                    Shared characters, locations, and visual style across every
                    episode.
                  </p>
                </div>
              </li>
              <li>
                <span>2</span>
                <div>
                  <strong>A director for every beat</strong>
                  <p>
                    Purposeful scenes, expressive shots, and source-grounded
                    story arcs.
                  </p>
                </div>
              </li>
              <li>
                <span>3</span>
                <div>
                  <strong>Your approval comes first</strong>
                  <p>
                    Review the look and the plan before any episode is produced.
                  </p>
                </div>
              </li>
            </ol>
            <div className="local-note">
              <span className="status-dot" />
              <p>
                Made for your machine.
                <br />
                <span>Local models or your own API keys.</span>
              </p>
            </div>
          </div>
        </aside>
      </div>
      <section className="section styles-section">
        <div className="section-heading">
          <span className="step-number">03</span>
          <div>
            <h2>Find your visual language</h2>
            <p>One consistent look, from the first frame to the final scene.</p>
          </div>
          <span className="quiet-tag">8 painting styles</span>
        </div>
        <div className="style-grid">
          {catalog.styles?.map((s: Data) => (
            <button
              key={s.id}
              className={`style-card ${style === s.id ? "selected" : ""}`}
              onClick={() => setStyle(s.id)}
              aria-pressed={style === s.id}
            >
              <Landscape variant={s.id} />
              <div>
                <strong>{s.name}</strong>
                <span>{s.description}</span>
              </div>
              {style === s.id && (
                <span className="style-check">
                  <Check size={13} />
                </span>
              )}
            </button>
          ))}
        </div>
        <p className="caption">
          Illustrative style swatches. Your actual characters and scenes are
          generated for your review.
        </p>
      </section>
      <details className="advanced">
        <summary>
          Make it your own <span>Adaptation & additional direction</span>
        </summary>
        <div className="field-row">
          <label className="field">
            Adaptation policy
            <select
              value={fidelity}
              onChange={(e) => setFidelity(e.target.value)}
            >
              <option value="faithful">Faithful to the source</option>
              <option value="balanced">Balanced adaptation</option>
              <option value="creative">Creative interpretation</option>
            </select>
          </label>
          <label className="field">
            Format
            <select value={aspect} onChange={(e) => setAspect(e.target.value)}>
              <option value="16:9">Landscape · 16:9</option>
              <option value="9:16">Portrait · 9:16</option>
            </select>
          </label>
        </div>
        <label className="field">
          Your direction
          <textarea
            rows={3}
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
            placeholder="A quiet sense of mystery. Warm autumn colors. Let the small moments breathe…"
            maxLength={2000}
          />
        </label>
      </details>
      {error && (
        <div role="alert" className="error-banner">
          {error}
        </div>
      )}
      <div className="create-footer">
        <p>
          <strong>{chosen?.name}</strong>
          <span>
            {" "}
            · {mode === "children" ? `Ages ${age}` : "General stories"} ·{" "}
            {seconds / 60}-minute episodes
          </span>
        </p>
        <Button
          disabled={!source.trim() || busy}
          onClick={() =>
            void onCreate({
              title: title || "Untitled story",
              source,
              brief: {
                mode,
                style,
                target_seconds: seconds,
                age_range: age,
                fidelity,
                direction,
                aspect,
              },
            })
          }
        >
          Discover your story <ArrowRight size={17} />
        </Button>
      </div>
    </>
  );
}
