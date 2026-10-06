import { useCallback, useEffect, useState } from "react";
import {
  Aperture,
  ArrowUpRight,
  BookOpen,
  Check,
  Clapperboard,
  Film,
  FlaskConical,
  FolderOpen,
  LoaderCircle,
  Plus,
  Settings2,
  X,
} from "lucide-react";
import { api, send } from "./api";
import type { Data } from "./api";
import CreateView from "./CreateView";
import PlanView from "./PlanView";
import ProductionView from "./ProductionView";
import { WatchView, EvaluateView } from "./WatchEvaluate";
import ModelSettings from "./ModelSettings";

const pages = [
  { name: "Create", icon: Plus },
  { name: "Director Plan", icon: BookOpen },
  { name: "Production", icon: Clapperboard },
  { name: "Watch", icon: Film },
  { name: "Evaluate", icon: FlaskConical },
];

export default function App() {
  const [page, setPage] = useState("Create");
  const [catalog, setCatalog] = useState<Data>({});
  const [settings, setSettings] = useState<Data>({});
  const [projects, setProjects] = useState<Data[]>([]);
  const [project, setProject] = useState<Data | null>(null);
  const [id, setId] = useState<string | null>(
    localStorage.getItem("story-project"),
  );
  const [selected, setSelected] = useState<number[]>([1]);
  const [modelDialog, setModelDialog] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [connected, setConnected] = useState(true);
  const [notice, setNotice] = useState("");
  const refresh = useCallback(async () => {
    try {
      const [list, detail] = await Promise.all([
        api<Data[]>("/projects"),
        id ? api("/projects/" + id) : Promise.resolve(null),
      ]);
      setProjects(list);
      setProject(detail);
      setConnected(true);
    } catch (e) {
      setConnected(false);
      setError((e as Error).message);
    }
  }, [id]);
  useEffect(() => {
    void Promise.all([api("/catalog"), api("/settings")])
      .then(([c, s]) => {
        setCatalog(c);
        setSettings(s);
      })
      .catch((e) => {
        setError(e.message);
        setConnected(false);
      });
  }, []);
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 2500);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    if (id) localStorage.setItem("story-project", id);
  }, [id]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 4000);
    return () => clearTimeout(timer);
  }, [notice]);
  const active = project?.jobs?.find((j: Data) =>
    ["queued", "running"].includes(j.status),
  );
  const recent = project?.jobs?.[0];
  const busy = !!active || saving;
  async function run(fn: () => Promise<unknown>) {
    setSaving(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
      throw e;
    } finally {
      setSaving(false);
    }
  }
  async function job(kind: string, extra: Data = {}) {
    if (!id) return;
    await run(async () => {
      await send(`/projects/${id}/jobs`, { kind, ...extra });
    });
  }
  async function act(path: string, body: Data) {
    if (!id) return;
    const { _method, ...data } = body;
    await run(async () => {
      await send(`/projects/${id}${path}`, data, _method || "POST");
      setNotice("Saved successfully");
    });
  }
  // Event handlers consume failures here; error text remains visible in the page.
  const safeJob = async (kind: string, extra?: Data) => {
    try {
      await job(kind, extra);
    } catch {
      /* shown in error banner */
    }
  };
  const safeAct = async (path: string, body: Data) => {
    try {
      await act(path, body);
    } catch {
      /* shown in error banner */
    }
  };
  async function create(data: Data) {
    setSaving(true);
    setError("");
    try {
      const p = await send("/projects", data);
      setId(p.id);
      setProject(p);
      setSelected([1]);
      await send(`/projects/${p.id}/jobs`, { kind: "analyze" });
      setPage("Director Plan");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  function chooseProject(p: Data) {
    setId(p.id);
    setSelected([1]);
    setPage("Director Plan");
  }
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          href="#"
          className="brand"
          onClick={(e) => {
            e.preventDefault();
            setPage("Create");
          }}
        >
          <span className="brand-mark">
            <Aperture size={23} />
          </span>
          <span>
            story<span className="brand-light">compiler</span>
            <small>YOUR STORY. IN MOTION.</small>
          </span>
        </a>
        <div className="workspace-label">
          WORKSPACE <span>LOCAL</span>
        </div>
        <nav aria-label="Main navigation">
          {pages.map((p) => (
            <button
              key={p.name}
              className={`nav-item ${page === p.name ? "active" : ""}`}
              onClick={() => setPage(p.name)}
              aria-current={page === p.name ? "page" : undefined}
            >
              <p.icon size={18} />
              <span>{p.name}</span>
              {p.name === "Create" && <span className="nav-plus">+</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-projects">
          <div className="sidebar-label">
            YOUR STORIES{" "}
            <button
              aria-label="Create a new story"
              onClick={() => setPage("Create")}
            >
              <Plus size={15} />
            </button>
          </div>
          {projects.length ? (
            projects.map((p) => (
              <button
                className={`project-link ${id === p.id ? "selected" : ""}`}
                key={p.id}
                onClick={() => chooseProject(p)}
              >
                <FolderOpen size={15} />
                <span>{p.title}</span>
              </button>
            ))
          ) : (
            <p className="no-projects">
              A new world is waiting.
              <br />
              Start your first story.
            </p>
          )}
        </div>
        <div className="sidebar-bottom">
          <button className="nav-item" onClick={() => setModelDialog(true)}>
            <Settings2 size={17} /> Models & settings
          </button>
          <div className="connection">
            <span className={`status-dot ${connected ? "" : "offline"}`} />
            <div>
              <strong>
                {connected ? "Local workspace" : "Connection lost"}
              </strong>
              <span>
                {connected
                  ? "Your stories stay with you"
                  : "Check the studio server"}
              </span>
            </div>
            <ArrowUpRight size={14} />
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <span>Studio</span>
            <span className="breadcrumb-slash">/</span>
            <strong>{page}</strong>
          </div>
          <div className="topbar-right">
            <span className="quiet-tag">PRIVATE BY DESIGN</span>
            <button
              className="settings-shortcut"
              onClick={() => setModelDialog(true)}
            >
              <span className="status-dot" />
              {settings.llm_provider === "ollama"
                ? "Local models"
                : "API models"}
              <Settings2 size={14} />
            </button>
            <span className="avatar">S</span>
          </div>
        </header>
        <main>
          <div className="content">
            {error && (
              <div role="alert" className="error-banner dismissible">
                <span>{error}</span>
                <button aria-label="Dismiss error" onClick={() => setError("")}>
                  <X size={16} />
                </button>
              </div>
            )}
            {active && (
              <div className="job-banner" role="status">
                <LoaderCircle size={18} />
                <div>
                  <strong>{active.message}</strong>
                  <div className="progress-track">
                    <span
                      style={{
                        width: `${Math.max(2, active.progress * 100)}%`,
                      }}
                    />
                  </div>
                </div>
                <span>{Math.round(active.progress * 100)}%</span>
                <button
                  onClick={() =>
                    void send("/jobs/" + active.id + "/cancel", {})
                      .then(refresh)
                      .catch((e) => setError(e.message))
                  }
                >
                  Cancel
                </button>
              </div>
            )}
            {!active &&
              recent &&
              [
                "failed",
                "interrupted",
                "cancelled",
                "review_required",
              ].includes(recent.status) && (
                <div className="recovery-banner">
                  <div>
                    <strong>
                      {recent.status === "interrupted"
                        ? "Your saved work is ready to resume"
                        : recent.message}
                    </strong>
                    {recent.error && <p>{recent.error}</p>}
                  </div>
                  <button
                    className="button secondary small"
                    disabled={saving}
                    onClick={() =>
                      void send("/jobs/" + recent.id + "/resume", {})
                        .then(refresh)
                        .catch((e) => setError(e.message))
                    }
                  >
                    Resume saved work
                  </button>
                </div>
              )}
            <div hidden={page !== "Create"}>
              <CreateView catalog={catalog} onCreate={create} busy={saving} />
            </div>
            {page === "Director Plan" && (
              <PlanView
                project={project}
                busy={busy}
                selected={selected}
                setSelected={setSelected}
                act={act}
                job={safeJob}
                navigate={setPage}
              />
            )}
            {page === "Production" && (
              <ProductionView
                project={project}
                busy={busy}
                selected={selected}
                setSelected={setSelected}
                act={safeAct}
                job={safeJob}
                navigate={setPage}
                settings={settings}
                openSettings={() => setModelDialog(true)}
              />
            )}
            {page === "Watch" && (
              <WatchView project={project} navigate={setPage} act={safeAct} />
            )}
            {page === "Evaluate" && (
              <EvaluateView project={project} navigate={setPage} />
            )}
          </div>
          <footer className="app-footer">
            <Aperture size={14} />
            <span>Small episodes. Lasting stories.</span>
            <span>STORY COMPILER STUDIO · 0.1</span>
          </footer>
        </main>
      </div>
      {modelDialog && (
        <ModelSettings
          initial={settings}
          onClose={() => setModelDialog(false)}
          onSaved={setSettings}
        />
      )}
      {notice && (
        <div className="toast" role="status">
          <Check size={16} />
          {notice}
        </div>
      )}
    </div>
  );
}
