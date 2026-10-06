import { useState } from "react";
import { ArrowRight, Check, Clapperboard, RefreshCw } from "lucide-react";
import { artifact } from "./api";
import type { Data } from "./api";
import { Button, Empty, EpisodePicker, Header, Tag } from "./components";

type Props = {
  project: Data | null;
  busy: boolean;
  selected: number[];
  setSelected: (n: number[]) => void;
  act: (path: string, body: Data) => Promise<void>;
  job: (kind: string, extra?: Data) => Promise<void>;
  navigate: (p: string) => void;
  settings: Data;
  openSettings: () => void;
};
export default function ProductionView({
  project: p,
  busy,
  selected,
  setSelected,
  act,
  job,
  navigate,
  settings,
  openSettings,
}: Props) {
  const [accept, setAccept] = useState(false);
  if (!p?.episodes.length)
    return (
      <Empty
        title="Give your story a plan first"
        action={() => navigate("Create")}
      >
        Freeze the shared series bible and plan the episode structure before
        production.
      </Empty>
    );
  const entities = [...p.bible.characters, ...p.bible.locations];
  const allRefs = entities.every((e: Data) => p.references[e.id]);
  const allPlans =
    selected.length > 0 &&
    selected.every(
      (n) =>
        p.plans[String(n)] &&
        ["ready", "review_required"].includes(p.plans[String(n)].status),
    );
  const allApproved =
    allPlans && selected.every((n) => p.plans[String(n)].approved_hash);
  const findings = selected.flatMap(
    (n) => p.plans[String(n)]?.critique?.findings || [],
  );
  const blocking = findings.some((f: Data) => f.severity === "error");
  return (
    <>
      <Header eyebrow="THE PRODUCTION STUDIO" title="Make the world tangible.">
        Approve the look. Refine the direction. Bring each episode to the
        screen.
      </Header>
      <div className="model-strip">
        <div className="model-icon">
          <Clapperboard size={21} />
        </div>
        <div>
          <strong>
            {settings.video_provider === "animatic"
              ? "Illustrated animatic"
              : settings.video_provider === "local"
                ? "Local video production"
                : "API video production"}
          </strong>
          <span>
            {settings.llm_model} · {settings.image_model} ·{" "}
            {settings.video_model}
          </span>
        </div>
        <button className="text-button" onClick={openSettings}>
          Change models
        </button>
      </div>
      <EpisodePicker
        count={p.episodes.length}
        selected={selected}
        setSelected={setSelected}
      />
      <section className="section">
        <div className="section-heading">
          <span className="step-number">01</span>
          <div>
            <h2>Meet your characters. Explore your world.</h2>
            <p>
              These visual references become the shared look of the entire
              series.
            </p>
          </div>
          {p.references_hash && <Tag success>Approved & frozen</Tag>}
        </div>
        <div className="reference-grid">
          {entities.map((e: Data) => {
            const r = p.references[e.id];
            return (
              <article className="reference-card" key={e.id}>
                {r ? (
                  <a
                    href={artifact(p.id, r.file)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <img
                      src={artifact(p.id, r.file)}
                      alt={`${e.name} visual reference`}
                    />
                  </a>
                ) : (
                  <div className="reference-placeholder">
                    <span>{e.name.replace(/^The /, "")[0]}</span>
                    <small>Awaiting reference</small>
                  </div>
                )}
                <div className="reference-copy">
                  <span className="small-label">
                    {e.costume !== undefined ? "CHARACTER" : "LOCATION"}
                  </span>
                  <h3>{e.name}</h3>
                  {r && !p.references_hash && (
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={() => void job("references", { only: e.id })}
                    >
                      <RefreshCw size={12} /> Regenerate
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
        {!p.references_hash && (
          <div className="action-row">
            <p className="muted">
              Check identity, style, scale, and recurring details.
            </p>
            {allRefs ? (
              <Button
                disabled={busy}
                onClick={() => void act("/approve", { kind: "references" })}
              >
                <Check size={15} /> Approve all references
              </Button>
            ) : (
              <Button disabled={busy} onClick={() => void job("references")}>
                Generate visual references <ArrowRight size={16} />
              </Button>
            )}
          </div>
        )}
      </section>
      <section className="section">
        <div className="section-heading">
          <span className="step-number">02</span>
          <div>
            <h2>Give every shot a purpose</h2>
            <p>
              Scenes establish intent. Shots turn that intent into action,
              camera, performance, and sound.
            </p>
          </div>
        </div>
        {!allPlans && (
          <div className="direction-placeholder">
            <Clapperboard size={24} />
            <div>
              <strong>Ready for the director's pass</strong>
              <p>
                Design {selected.length || "your"} selected episode
                {selected.length !== 1 ? "s" : ""}, then inspect every scene and
                shot.
              </p>
            </div>
            <Button
              disabled={busy || !selected.length}
              onClick={() => void job("direct", { numbers: selected })}
            >
              Direct selected episodes
            </Button>
          </div>
        )}
        {selected.map((n) => {
          const plan = p.plans[String(n)];
          if (!plan) return null;
          return (
            <div className="shot-plan" key={n}>
              <div className="section-title">
                <h3>
                  Episode {n} · {p.episodes[n - 1]?.title}
                </h3>
                <Tag success={!!plan.approved_hash}>
                  {plan.approved_hash
                    ? "Plan approved"
                    : plan.status.replaceAll("_", " ")}
                </Tag>
              </div>
              {plan.scenes.map((scene: Data) => (
                <details className="scene" key={scene.id}>
                  <summary>
                    <span className="scene-mark" />
                    <strong>{scene.title}</strong>
                    <span>
                      {scene.duration}s ·{" "}
                      {
                        plan.shots.filter((s: Data) => s.scene_id === scene.id)
                          .length
                      }{" "}
                      shots
                    </span>
                  </summary>
                  <div className="scene-intent">
                    <p>
                      <strong>Purpose:</strong> {scene.purpose}
                    </p>
                    <p>
                      <strong>Geography:</strong> {scene.geography}
                    </p>
                    <p>
                      <strong>Light & sound:</strong> {scene.lighting} ·{" "}
                      {scene.sound_intent}
                    </p>
                  </div>
                  {plan.shots
                    .filter((s: Data) => s.scene_id === scene.id)
                    .map((s: Data, i: number) => (
                      <article className="shot" key={s.id}>
                        <div className="shot-index">
                          {String(i + 1).padStart(2, "0")}
                          <small>{s.duration}s</small>
                        </div>
                        <div>
                          <div className="shot-tags">
                            <Tag>
                              {s.purpose.replaceAll("_", " ").toLowerCase()}
                            </Tag>
                            <span>
                              {s.camera.size} · {s.camera.movement}
                            </span>
                          </div>
                          <p className="shot-action">{s.action}</p>
                          <p className="muted">
                            {s.camera.angle}{" "}
                            {s.camera.lens && `· ${s.camera.lens}`} ·{" "}
                            {s.camera.motivation}
                          </p>
                          {s.narration && (
                            <p className="narration">“{s.narration}”</p>
                          )}
                          <details>
                            <summary>Performance, continuity & sound</summary>
                            <p>
                              {s.performance
                                .map((x: Data) => x.behavior)
                                .join(" · ")}
                            </p>
                            <p>
                              <strong>Sound:</strong>{" "}
                              {Object.values(s.sound)
                                .filter((x) => typeof x === "string" && x)
                                .join(" · ")}
                            </p>
                            <p>
                              <strong>Continuity locks:</strong>{" "}
                              {s.locked.join(" · ")}
                            </p>
                            <div className="state-handoff">
                              <pre>
                                {JSON.stringify(s.start_state, null, 2)}
                              </pre>
                              <ArrowRight size={16} />
                              <pre>{JSON.stringify(s.end_state, null, 2)}</pre>
                            </div>
                          </details>
                        </div>
                      </article>
                    ))}
                </details>
              ))}
              {plan.hard_gate_errors?.map((e: string, i: number) => (
                <div className="error-banner" key={i}>
                  {e}
                </div>
              ))}
              {plan.critique && (
                <div className="critic">
                  <strong>Director's review</strong>
                  <p>{plan.critique.summary}</p>
                  {plan.critique.findings.map((f: Data, i: number) => (
                    <p
                      key={i}
                      className={f.severity === "error" ? "finding-error" : ""}
                    >
                      <strong>
                        {f.severity === "error"
                          ? "Needs attention"
                          : "Suggestion"}
                        :
                      </strong>{" "}
                      {f.finding} {f.repair}
                    </p>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        {allPlans && !allApproved && (
          <div className="approval-bar">
            {blocking && (
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={accept}
                  onChange={(e) => setAccept(e.target.checked)}
                />{" "}
                I have reviewed the findings and accept this plan.
              </label>
            )}
            <Button
              disabled={busy || (blocking && !accept)}
              onClick={() =>
                void act("/approve", {
                  kind: "plans",
                  numbers: selected,
                  accept_findings: accept,
                })
              }
            >
              Approve selected plans <Check size={15} />
            </Button>
          </div>
        )}
      </section>
      <section className="render-section">
        <div>
          <p className="eyebrow">03 · ACTION</p>
          <h2>Let the story move.</h2>
          <p>
            {settings.video_provider === "animatic"
              ? "Create an editorial preview from illustrated frames and narration."
              : "Generate individually directed clips, then assemble complete episodes."}
          </p>
          <span className="muted">
            {selected.length} episode{selected.length !== 1 ? "s" : ""} ·{" "}
            {(selected.length * p.brief.target_seconds) / 60} min total ·
            completed clips are saved
          </span>
        </div>
        <Button
          disabled={busy || !allApproved || !p.references_hash}
          onClick={() => void job("render", { numbers: selected })}
        >
          Produce {selected.length === 1 ? "episode" : "episodes"}{" "}
          <ArrowRight size={17} />
        </Button>
      </section>
      {Object.values(p.productions).some((v: any) => v.file) && (
        <div className="action-row">
          <span>Rendered episodes are ready for viewing review.</span>
          <Button secondary onClick={() => navigate("Watch")}>
            Go to your screening room <ArrowRight size={16} />
          </Button>
        </div>
      )}
    </>
  );
}
