import { useEffect, useRef, useState } from "react";
import { Check, RefreshCw, X } from "lucide-react";
import { api, send } from "./api";
import type { Data } from "./api";
import { Button, Tag } from "./components";

export default function ModelSettings({
  initial,
  onClose,
  onSaved,
}: {
  initial: Data;
  onClose: () => void;
  onSaved: (s: Data) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [form, setForm] = useState<Data>({ ...initial });
  const [key, setKey] = useState("");
  const [credential, setCredential] = useState("openai");
  const [status, setStatus] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    dialog.current?.showModal();
    void api("/providers/status")
      .then(setStatus)
      .catch((e) => setError(e.message));
  }, []);
  function set(name: string, value: unknown) {
    setForm((f) => ({ ...f, [name]: value }));
  }
  async function save() {
    setSaving(true);
    setError("");
    try {
      const { credentials, ...values } = form;
      const result = await send(
        "/settings",
        {
          ...values,
          ...(key ? { api_key: key, credential_provider: credential } : {}),
        },
        "PUT",
      );
      onSaved(result);
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <dialog
      ref={dialog}
      onCancel={onClose}
      className="settings-dialog"
      aria-labelledby="models-title"
    >
      <div className="dialog-head">
        <div>
          <p className="eyebrow">YOUR CREATIVE TOOLKIT</p>
          <h2 id="models-title">Models & production</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Close model settings"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      <div className="dialog-body">
        <p className="muted">
          Run on your machine, or connect stronger models with your own API
          keys. Providers never change automatically.
        </p>
        <section className="settings-section">
          <h3>Story & direction</h3>
          <div className="field-row">
            <label className="field">
              Language provider
              <select
                value={form.llm_provider}
                onChange={(e) => {
                  const v = e.target.value;
                  set("llm_provider", v);
                  set(
                    "llm_model",
                    v === "ollama"
                      ? "qwen3.5:4b"
                      : v === "openai"
                        ? "gpt-4.1-mini"
                        : "",
                  );
                  set(
                    "llm_endpoint",
                    v === "ollama"
                      ? "http://127.0.0.1:11434"
                      : "https://api.openai.com/v1",
                  );
                }}
              >
                <option value="ollama">Local · Ollama</option>
                <option value="openai">OpenAI API</option>
                <option value="compatible">OpenAI-compatible API</option>
              </select>
            </label>
            <label className="field">
              Model
              <input
                list="llm-models"
                value={form.llm_model}
                onChange={(e) => set("llm_model", e.target.value)}
              />
              <datalist id="llm-models">
                {(status?.llm?.models || ["qwen3.5:4b", "qwen3.5:9b"]).map(
                  (m: string) => (
                    <option key={m}>{m}</option>
                  ),
                )}
              </datalist>
            </label>
          </div>
          {form.llm_provider !== "openai" && (
            <label className="field">
              Provider endpoint
              <input
                value={form.llm_endpoint}
                onChange={(e) => set("llm_endpoint", e.target.value)}
              />
            </label>
          )}
        </section>
        <section className="settings-section">
          <h3>Visual references</h3>
          <div className="field-row">
            <label className="field">
              Image provider
              <select
                value={form.image_provider}
                onChange={(e) => {
                  set("image_provider", e.target.value);
                  set(
                    "image_model",
                    e.target.value === "local"
                      ? "stabilityai/sd-turbo"
                      : "gpt-image-1",
                  );
                }}
              >
                <option value="local">Local · Stable Diffusion Turbo</option>
                <option value="openai">OpenAI image API</option>
              </select>
            </label>
            <label className="field">
              Image model
              <input
                value={form.image_model}
                readOnly={form.image_provider === "local"}
                onChange={(e) => set("image_model", e.target.value)}
              />
            </label>
          </div>
        </section>
        <section className="settings-section">
          <h3>Episode production</h3>
          <div className="field-row">
            <label className="field">
              Video provider
              <select
                value={form.video_provider}
                onChange={(e) => {
                  set("video_provider", e.target.value);
                  set(
                    "video_model",
                    e.target.value === "openai"
                      ? "sora-2"
                      : e.target.value === "local"
                        ? "Lightricks/LTX-Video-0.9.1"
                        : "Illustrated animatic",
                  );
                }}
              >
                <option value="local">Local · LTX-Video</option>
                <option value="openai">OpenAI · Sora</option>
                <option value="animatic">
                  Illustrated animatic · fast preview
                </option>
              </select>
            </label>
            <label className="field">
              Video model
              <input
                value={form.video_model}
                readOnly={form.video_provider !== "openai"}
                onChange={(e) => set("video_model", e.target.value)}
              />
            </label>
          </div>
          {form.video_provider === "animatic" && (
            <p className="warning-box">
              An animatic uses illustrated frames, camera motion, and narration
              for editorial review. It does not generate character motion.
            </p>
          )}
          {form.video_provider === "openai" && (
            <p className="caption">
              Sora input-image restrictions may prevent human-character
              references. Check your account's current model access before
              producing a series.
            </p>
          )}
          <div className="field-row">
            <label className="field">
              Narration
              <select
                value={form.voice_provider}
                onChange={(e) => {
                  set("voice_provider", e.target.value);
                  set(
                    "voice",
                    e.target.value === "system" ? "Samantha" : "alloy",
                  );
                }}
              >
                <option value="system">Local · macOS voice</option>
                <option value="openai">OpenAI speech API</option>
                <option value="none">No synthesized narration</option>
              </select>
            </label>
            <label className="field">
              Voice
              <input
                value={form.voice}
                disabled={form.voice_provider === "none"}
                onChange={(e) => set("voice", e.target.value)}
              />
            </label>
          </div>
          <div className="field-row">
            <label className="field">
              Generation call budget
              <input
                type="number"
                min="1"
                max="10000"
                value={form.max_generation_calls}
                onChange={(e) =>
                  set("max_generation_calls", Number(e.target.value))
                }
              />
            </label>
            <label className="field">
              Local video quality steps
              <input
                type="number"
                min="8"
                max="50"
                value={form.local_steps}
                onChange={(e) => set("local_steps", Number(e.target.value))}
              />
            </label>
          </div>
          <p className="caption">
            The budget is a call-count ceiling, not a currency estimate. API
            usage is billed by the selected provider.
          </p>
        </section>
        <section className="settings-section">
          <h3>API credentials</h3>
          <div className="field-row">
            <label className="field">
              Credential for
              <select
                value={credential}
                onChange={(e) => setCredential(e.target.value)}
              >
                <option value="openai">OpenAI</option>
                <option value="compatible">Compatible provider</option>
              </select>
            </label>
            <label className="field">
              API key
              <input
                type="password"
                autoComplete="new-password"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder={
                  initial.credentials?.[credential]
                    ? "A key is saved · enter to replace"
                    : "Paste your API key"
                }
              />
            </label>
          </div>
          <p className="caption">
            Encrypted on this machine. Keys are never included in story exports,
            prompts, or browser storage.
          </p>
        </section>
        <section className="settings-section">
          <div className="section-title">
            <h3>Local readiness</h3>
            <button
              className="text-button"
              onClick={() =>
                void api("/providers/status")
                  .then(setStatus)
                  .catch((e) => setError(e.message))
              }
            >
              <RefreshCw size={13} /> Refresh
            </button>
          </div>
          {status ? (
            <div className="readiness">
              <Tag success={status.llm.available}>
                Language model {status.llm.available ? "ready" : "unavailable"}
              </Tag>
              <Tag success={status.local.image}>
                Image {status.local.image ? "installed" : "not installed"}
              </Tag>
              <Tag success={status.local.video}>
                Video {status.local.video ? "installed" : "not installed"}
              </Tag>
              <Tag success={status.local.ffmpeg}>FFmpeg</Tag>
              <p className="caption">
                {status.local.free_gib} GiB free disk space. Heavy local jobs
                run one at a time.
              </p>
            </div>
          ) : (
            <p>Checking this machine…</p>
          )}
          <details>
            <summary>Install local models</summary>
            <p>Run from the project folder:</p>
            <pre>.venv/bin/python scripts/setup_models.py all</pre>
            <p className="caption">
              Downloads official checkpoints. No per-generation API charge;
              model license terms still apply.
            </p>
          </details>
        </section>
        {error && (
          <div role="alert" className="error-banner">
            {error}
          </div>
        )}
      </div>
      <div className="dialog-footer">
        <Button secondary onClick={onClose}>
          Cancel
        </Button>
        <Button disabled={saving} onClick={() => void save()}>
          {saving ? "Saving…" : "Save model settings"} <Check size={15} />
        </Button>
      </div>
    </dialog>
  );
}
