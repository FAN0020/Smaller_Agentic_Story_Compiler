import { useState } from "react";
import { Check, Download, Play } from "lucide-react";
import { artifact } from "./api";
import type { Data } from "./api";
import { Button, Empty, Header, Tag } from "./components";

export function WatchView({
  project: p,
  navigate,
  act,
}: {
  project: Data | null;
  navigate: (s: string) => void;
  act: (path: string, body: Data) => Promise<void>;
}) {
  const [active, setActive] = useState<number | null>(null);
  const [chapter, setChapter] = useState("all");
  if (!p)
    return (
      <Empty
        title="Your screening room awaits"
        action={() => navigate("Create")}
      >
        Finished episodes will live here, together as one series.
      </Empty>
    );
  const episodes = p.episodes.filter(
    (e: Data) => p.productions[String(e.number)]?.file,
  );
  if (!episodes.length)
    return (
      <Empty title="The first screening is still ahead">
        Produce an approved episode to watch your story here.
        <p>
          <Button onClick={() => navigate("Production")}>
            Open production <Play size={15} />
          </Button>
        </p>
      </Empty>
    );
  const current =
    episodes.find((e: Data) => e.number === active) || episodes[0];
  const output = p.productions[String(current.number)];
  const chapters = [
    ...new Set(p.episodes.map((e: Data) => e.chapter)),
  ] as string[];
  return (
    <>
      <Header title={p.bible?.title || p.title}>
        {episodes.length} episode{episodes.length !== 1 ? "s" : ""} ready to
        watch.
      </Header>
      <div className="watch-grid">
        <div>
          <div className="player">
            <video
              key={output.file}
              controls
              preload="metadata"
              poster={
                output.samples?.[0]
                  ? artifact(p.id, output.samples[0])
                  : undefined
              }
            >
              <source src={artifact(p.id, output.file)} type="video/mp4" />
              {output.subtitles && (
                <track
                  kind="captions"
                  label="English"
                  srcLang="en"
                  src={artifact(p.id, output.subtitles)}
                  default
                />
              )}
            </video>
          </div>
          <div className="screening-title">
            <div>
              <p className="eyebrow">
                EPISODE {current.number} · {Math.round(output.duration)} SECONDS
              </p>
              <h2>{current.title}</h2>
            </div>
            <a
              className="button secondary small"
              href={artifact(p.id, output.file)}
              download
            >
              <Download size={15} /> Download
            </a>
          </div>
          <p>{current.summary}</p>
          <div className="watch-review">
            <Tag>
              {output.kind === "illustrated_animatic"
                ? "Illustrated animatic"
                : "Generated video"}
            </Tag>
            {output.visual_status === "human_approved" ? (
              <Tag success>Viewing review complete</Tag>
            ) : (
              <>
                <p>
                  Watch for consistent characters, readable action, clear sound,
                  and a coherent story.
                </p>
                <Button
                  secondary
                  small
                  onClick={() =>
                    void act("/approve", {
                      kind: "video",
                      numbers: [current.number],
                    })
                  }
                >
                  Mark viewing review complete <Check size={14} />
                </Button>
              </>
            )}
          </div>
        </div>
        <aside className="episode-library" aria-label="Episode library">
          <p className="eyebrow">EPISODE LIBRARY</p>
          {chapters.length > 1 && (
            <label className="field">
              Chapter
              <select
                value={chapter}
                onChange={(e) => setChapter(e.target.value)}
              >
                <option value="all">All chapters</option>
                {chapters.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
          )}
          {p.episodes
            .filter((e: Data) => chapter === "all" || e.chapter === chapter)
            .map((e: Data) => (
              <button
                key={e.number}
                className={`library-row ${current.number === e.number ? "active" : ""}`}
                disabled={!p.productions[String(e.number)]?.file}
                onClick={() => setActive(e.number)}
              >
                <span>{String(e.number).padStart(2, "0")}</span>
                <div>
                  <strong>{e.title}</strong>
                  <small>
                    {e.target_seconds / 60} min ·{" "}
                    {p.productions[String(e.number)]?.file
                      ? "Ready to watch"
                      : "Planned"}
                  </small>
                </div>
                {current.number === e.number && <Play size={15} />}
              </button>
            ))}
        </aside>
      </div>
    </>
  );
}

export function EvaluateView({
  project: p,
  navigate,
}: {
  project: Data | null;
  navigate: (s: string) => void;
}) {
  if (!p?.bible)
    return (
      <Empty title="Evidence, not guesswork" action={() => navigate("Create")}>
        Source fidelity, plan checks, and rendered-media review will appear as
        your story progresses.
      </Empty>
    );
  const plans = Object.values(p.plans) as Data[];
  const produced = Object.values(p.productions) as Data[];
  return (
    <>
      <Header title="A good story deserves a closer look.">
        Planning quality and rendered quality are reviewed separately.
      </Header>
      <div className="evaluation-grid">
        <article className="evaluation-card">
          <span className="small-label">SOURCE & INHERITANCE</span>
          <h2>{p.events.length} grounded events</h2>
          <p>
            Source quotes and offsets are preserved. Episodes inherit the frozen
            series bible.
          </p>
          <Tag success={!!p.bible_hash}>
            {p.bible_hash ? "Canon frozen" : "Review pending"}
          </Tag>
        </article>
        <article className="evaluation-card">
          <span className="small-label">PLAN VERIFICATION</span>
          <h2>
            {plans.filter((x) => !x.hard_gate_errors?.length && x.hash).length}{" "}
            checked plans
          </h2>
          <p>
            Source coverage, identity references, continuity handoffs, and exact
            timeline duration.
          </p>
          <Tag>
            {plans.length
              ? "Deterministic checks + model critic"
              : "Not yet evaluated"}
          </Tag>
        </article>
        <article className="evaluation-card">
          <span className="small-label">RENDERED VIDEO</span>
          <h2>
            {
              produced.filter((x) => x.visual_status === "human_approved")
                .length
            }{" "}
            reviewed episodes
          </h2>
          <p>
            Technical checks do not prove visual continuity or artistic quality.
            Viewing review is required.
          </p>
          <Tag>
            {produced.some((x) => x.file)
              ? "Frame evidence available"
              : "Not yet rendered"}
          </Tag>
        </article>
      </div>
      {produced.map(
        (v, i) =>
          v.file && (
            <section className="section" key={i}>
              <div className="section-title">
                <h2>Episode {i + 1} · rendered evidence</h2>
                <Tag success={v.technical_status === "passed"}>
                  Technical checks {v.technical_status}
                </Tag>
              </div>
              <div className="evidence-grid">
                {v.samples?.map((file: string, j: number) => (
                  <figure key={file}>
                    <img
                      src={artifact(p.id, file)}
                      alt={`Episode ${i + 1}, ${["opening", "middle", "ending"][j]} sampled frame`}
                    />
                    <figcaption>
                      {["Opening", "Middle", "Ending"][j]}
                    </figcaption>
                  </figure>
                ))}
              </div>
              <p className="muted">{v.audio_notes}</p>
              <p>
                <strong>Visual review:</strong>{" "}
                {v.visual_status.replaceAll("_", " ")}
              </p>
            </section>
          ),
      )}
      <section className="section">
        <h2>Grounded story events</h2>
        <div className="source-events">
          {p.events.map((e: Data) => (
            <details key={e.id}>
              <summary>{e.summary}</summary>
              <blockquote>{e.quote}</blockquote>
              <span className="caption">
                Source characters {e.source_start}–{e.source_end}
              </span>
            </details>
          ))}
        </div>
      </section>
      <details className="section">
        <summary>Production history & lineage</summary>
        <div className="audit-list">
          {p.audit.map((a: Data, i: number) => (
            <div key={i}>
              <strong>
                {(a.stage || a.action)
                  .replaceAll("-", " ")
                  .replaceAll("_", " ")}
              </strong>
              <span>
                {a.model || ""} {a.seconds ? `· ${a.seconds}s` : ""}{" "}
                {a.at ? new Date(a.at * 1000).toLocaleString() : ""}
              </span>
              {a.hash && <code>{a.hash.slice(0, 16)}</code>}
            </div>
          ))}
        </div>
      </details>
    </>
  );
}
