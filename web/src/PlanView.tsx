import { useState } from "react";
import { ArrowRight, Check, Download, LockKeyhole } from "lucide-react";
import type { Data } from "./api";
import {
  Button,
  Empty,
  EmotionCurve,
  EpisodePicker,
  Header,
  Tag,
} from "./components";

type Props = {
  project: Data | null;
  busy: boolean;
  selected: number[];
  setSelected: (n: number[]) => void;
  act: (path: string, body: Data) => Promise<void>;
  job: (kind: string, extra?: Data) => Promise<void>;
  navigate: (page: string) => void;
};
export default function PlanView({
  project: p,
  busy,
  selected,
  setSelected,
  act,
  job,
  navigate,
}: Props) {
  const [edit, setEdit] = useState(false);
  const [draft, setDraft] = useState("");
  if (!p)
    return (
      <Empty title="Your story starts here" action={() => navigate("Create")}>
        Add a story to discover its world, characters, and episode structure.
      </Empty>
    );
  const b = p.bible;
  return (
    <>
      <Header
        title={b?.title || p.title}
        action={
          <a
            className="button secondary small"
            href={`/api/projects/${p.id}/export`}
            download
          >
            <Download size={14} /> Export plan
          </a>
        }
      >
        {b?.logline || "Reading the source and discovering its story world."}
      </Header>
      {!b ? (
        <Empty title="A world is taking shape">
          The complete source is read in sections. Your shared bible will appear
          here for review.
          {!busy && (
            <p>
              <Button onClick={() => void job("analyze")}>Analyze story</Button>
            </p>
          )}
        </Empty>
      ) : (
        <>
          <div className="plan-summary">
            <div>
              <span className="eyebrow">STORY WORLD</span>
              <h2>{b.genre}</h2>
              <p>{b.themes.join(" · ")}</p>
            </div>
            <div className="summary-metrics">
              <div>
                <strong>{b.characters.length}</strong>
                <span>characters</span>
              </div>
              <div>
                <strong>{b.locations.length}</strong>
                <span>locations</span>
              </div>
              <div>
                <strong>
                  {p.episodes.length || `~${p.estimated_episode_count || 1}`}
                </strong>
                <span>
                  {p.episodes.length ? "episodes" : "estimated episodes"}
                </span>
              </div>
            </div>
            {p.bible_hash ? (
              <Tag success>
                <LockKeyhole size={12} /> Bible frozen
              </Tag>
            ) : (
              <Tag>Awaiting your approval</Tag>
            )}
          </div>
          <section className="section">
            <div className="section-title">
              <h2>The shared series bible</h2>
              <Tag>
                {p.brief.mode === "children"
                  ? `Children · ages ${p.brief.age_range}`
                  : "General drama"}
              </Tag>
            </div>
            <p className="muted">
              Every episode inherits these identities, the visual style, and the
              directing rules.
            </p>
            <div className="entity-grid">
              {b.characters.map((c: Data) => (
                <article className="entity-card" key={c.id}>
                  <div className="entity-monogram">
                    {c.name.replace(/^The /, "").slice(0, 1)}
                  </div>
                  <div>
                    <h3>{c.name}</h3>
                    <p>{c.appearance}</p>
                    <details>
                      <summary>Character details</summary>
                      <dl>
                        <dt>From the story</dt>
                        <dd>{c.source_facts}</dd>
                        <dt>Costume</dt>
                        <dd>{c.costume}</dd>
                        <dt>Performance & voice</dt>
                        <dd>
                          {c.acting} {c.voice}
                        </dd>
                        <dt>Design choices</dt>
                        <dd>{c.design_choices}</dd>
                      </dl>
                    </details>
                  </div>
                </article>
              ))}
            </div>
            <div className="location-list">
              {b.locations.map((l: Data) => (
                <div key={l.id}>
                  <span className="small-label">LOCATION</span>
                  <h3>{l.name}</h3>
                  <p>{l.appearance}</p>
                  <details>
                    <summary>Geography & light</summary>
                    <p>{l.geography}</p>
                    <p>{l.lighting}</p>
                  </details>
                </div>
              ))}
            </div>
            <details className="plan-details">
              <summary>Directing rules, style & adaptation notes</summary>
              <div className="two-columns">
                <div>
                  <h3>Direction</h3>
                  <ul>
                    {b.directing_principles.map((x: string, i: number) => (
                      <li key={i}>{x}</li>
                    ))}
                  </ul>
                  <p>{b.style_instruction}</p>
                </div>
                <div>
                  <h3>Adaptation choices</h3>
                  <ul>
                    {b.adaptation_notes.map((x: string, i: number) => (
                      <li key={i}>{x}</li>
                    ))}
                  </ul>
                  {b.content_warnings.length > 0 && (
                    <div className="warning-box">
                      {b.content_warnings.join(" ")}
                    </div>
                  )}
                </div>
              </div>
            </details>
            {!p.bible_hash && (
              <>
                <div className="action-row">
                  <Button
                    secondary
                    disabled={busy}
                    onClick={() => {
                      const {
                        style_instruction,
                        policy,
                        brief,
                        source_hash,
                        ...editable
                      } = b;
                      setDraft(JSON.stringify(editable, null, 2));
                      setEdit(!edit);
                    }}
                  >
                    Edit bible
                  </Button>
                  <Button
                    disabled={busy}
                    onClick={() =>
                      void act("/approve", { kind: "bible" })
                        .then(() => navigate("Production"))
                        .catch(() => {})
                    }
                  >
                    <LockKeyhole size={15} /> Freeze bible & design references{" "}
                    <ArrowRight size={16} />
                  </Button>
                </div>
                {edit && (
                  <div className="json-editor">
                    <label className="field">
                      Bible content
                      <textarea
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        rows={18}
                      />
                    </label>
                    <Button
                      secondary
                      onClick={() => {
                        try {
                          void act("/bible", {
                            _method: "PUT",
                            ...JSON.parse(draft),
                          })
                            .then(() => setEdit(false))
                            .catch(() => {});
                        } catch {
                          alert("Enter valid JSON before saving.");
                        }
                      }}
                    >
                      Save bible edits
                    </Button>
                  </div>
                )}
              </>
            )}
            {p.bible_hash &&
              p.episodes.length === 0 &&
              !busy &&
              (p.references_hash ? (
                <Button onClick={() => void job("episodes")}>
                  Plan episode structure <ArrowRight size={16} />
                </Button>
              ) : (
                <Button onClick={() => navigate("Production")}>
                  Design & approve visual references <ArrowRight size={16} />
                </Button>
              ))}
          </section>
          {p.episodes.length > 0 && (
            <section className="section">
              <div className="section-title">
                <div>
                  <p className="eyebrow">THE SERIES</p>
                  <h2>
                    {p.episodes.length} episode
                    {p.episodes.length !== 1 ? "s" : ""}. One connected story.
                  </h2>
                </div>
                <Tag>All source events covered</Tag>
              </div>
              <EpisodePicker
                count={p.episodes.length}
                selected={selected}
                setSelected={setSelected}
              />
              <div className="episode-list">
                {p.episodes.map((ep: Data) => (
                  <article
                    className={`episode-card ${selected.includes(ep.number) ? "selected" : ""}`}
                    key={ep.number}
                  >
                    <div className="episode-heading">
                      <button
                        className="episode-number"
                        aria-label={`Select episode ${ep.number}`}
                        aria-pressed={selected.includes(ep.number)}
                        onClick={() =>
                          setSelected(
                            selected.includes(ep.number)
                              ? selected.filter((n) => n !== ep.number)
                              : [...selected, ep.number].sort((a, b) => a - b),
                          )
                        }
                      >
                        {selected.includes(ep.number) ? (
                          <Check size={19} />
                        ) : (
                          String(ep.number).padStart(2, "0")
                        )}
                      </button>
                      <div>
                        <span className="small-label">
                          {ep.chapter} · {ep.target_seconds / 60} MIN
                        </span>
                        <h3>{ep.title}</h3>
                      </div>
                      {p.plans[String(ep.number)]?.approved_hash && (
                        <Tag success>Plan approved</Tag>
                      )}
                    </div>
                    <p>{ep.summary}</p>
                    <div className="episode-hook">
                      <span>Opening hook</span>
                      <p>{ep.hook}</p>
                    </div>
                    <EmotionCurve
                      beats={ep.emotion_curve}
                      duration={ep.target_seconds}
                    />
                    <details>
                      <summary>Story mechanics & continuity</summary>
                      <dl>
                        <dt>Hook latency</dt>
                        <dd>{ep.hook_latency}s</dd>
                        <dt>Reversals</dt>
                        <dd>
                          {ep.reversal_beats.join(" · ") ||
                            "No forced reversal; follows the source."}
                        </dd>
                        <dt>Audience / character knowledge gap</dt>
                        <dd>{ep.audience_character_knowledge_gap}</dd>
                        <dt>Ending</dt>
                        <dd>{ep.episode_boundary_hook}</dd>
                        <dt>Setup → payoff</dt>
                        <dd>{ep.setup_to_payoff_distance}</dd>
                      </dl>
                      {ep.open_loop_ledger.map((l: Data, i: number) => (
                        <p key={i}>
                          <strong>Open loop:</strong> {l.question}{" "}
                          {l.payoff_event_id
                            ? "· payoff tracked"
                            : "· carried forward"}
                        </p>
                      ))}
                    </details>
                  </article>
                ))}
              </div>
              <div className="action-row">
                <span className="muted">
                  {selected.length} episode{selected.length !== 1 ? "s" : ""}{" "}
                  selected
                </span>
                <Button
                  disabled={!selected.length}
                  onClick={() => navigate("Production")}
                >
                  Build your episodes <ArrowRight size={16} />
                </Button>
              </div>
            </section>
          )}
        </>
      )}
    </>
  );
}
