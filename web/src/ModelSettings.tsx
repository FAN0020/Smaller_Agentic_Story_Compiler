import { useEffect, useRef, useState } from "react";
import { Check, RefreshCw, X } from "lucide-react";
import { api, send } from "./api";
import type { Data } from "./api";
import { Button, Tag } from "./components";
import LanguageSettings from "./LanguageSettings";

export default function ModelSettings({
  initial,
  characters = [],
  projectId = "",
  onClose,
  onSaved,
}: {
  initial: Data;
  characters?: Data[];
  projectId?: string;
  onClose: () => void;
  onSaved: (s: Data) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [form, setForm] = useState<Data>({ ...initial });
  const [key, setKey] = useState("");
  const [credential, setCredential] = useState("openai");
  const [status, setStatus] = useState<Data | null>(null);
  const [catalog, setCatalog] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    dialog.current?.showModal();
    void api("/providers/status")
      .then(setStatus)
      .catch((e) => setError(e.message));
    void api("/catalog")
      .then(setCatalog)
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
          keys. Providers never change automatically. Save settings, then retry
          a stopped planning job with the selected language model.
        </p>
        <LanguageSettings
          form={form}
          catalog={catalog}
          set={set}
          selectCredential={(provider) => {
            setCredential(provider);
            setKey("");
          }}
        />
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
                      ? "mlx-community/flux2-klein-4b-4bit"
                      : "gpt-image-1",
                  );
                }}
              >
                <option value="local">Local image model</option>
                <option value="openai">OpenAI image API</option>
              </select>
            </label>
            <label className="field">
              Image model
              {form.image_provider === "local" ? (
                <select
                  value={form.image_model}
                  onChange={(e) => set("image_model", e.target.value)}
                >
                  {(catalog?.models?.image || [])
                    .filter((model: Data) => model.tier !== "hosted")
                    .map((model: Data) => (
                      <option value={model.id} key={model.id}>
                        {model.label}
                      </option>
                    ))}
                </select>
              ) : (
                <input
                  value={form.image_model}
                  onChange={(e) => set("image_model", e.target.value)}
                />
              )}
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
                <option value="local">Local · free video models</option>
                <option value="openai">OpenAI · Sora</option>
                <option value="animatic">
                  Illustrated animatic · fast preview
                </option>
              </select>
            </label>
            <label className="field">
              Video model
              {form.video_provider !== "animatic" ? (
                <select
                  value={form.video_model}
                  onChange={(e) => {
                    set("video_model", e.target.value);
                    const model = catalog?.models?.video?.find(
                      (m: Data) => m.id === e.target.value,
                    );
                    if (
                      form.video_provider === "local" &&
                      model?.recommended_steps
                    )
                      set("local_steps", model.recommended_steps);
                  }}
                >
                  {(catalog?.models?.video || [])
                    .filter((model: Data) =>
                      form.video_provider === "local"
                        ? model.tier === "local"
                        : model.tier !== "local",
                    )
                    .map((model: Data) => (
                      <option value={model.id} key={model.id}>
                        {model.label}
                      </option>
                    ))}
                </select>
              ) : (
                <input value={form.video_model} readOnly />
              )}
            </label>
          </div>
          {form.video_provider === "local" && (
            <>
              <p className="caption">
                {
                  catalog?.models?.video?.find(
                    (m: Data) => m.id === form.video_model,
                  )?.description
                }
              </p>
              <p className="caption">
                {status?.local?.video_options?.find(
                  (m: Data) => m.id === form.video_model,
                )?.installed
                  ? "Checkpoint installed. Each render checks available memory before loading."
                  : "Checkpoint not installed. Use the install command below before rendering."}
              </p>
              {status?.local?.video_options?.find(
                (m: Data) => m.id === form.video_model,
              )?.resource_warning && (
                <p className="warning-box">
                  {
                    status.local.video_options.find(
                      (m: Data) => m.id === form.video_model,
                    ).resource_warning
                  }
                </p>
              )}
            </>
          )}
          {form.video_provider === "animatic" && (
            <p className="warning-box">
              An animatic uses illustrated frames, camera motion, and narration
              for editorial review. It does not generate character motion.
            </p>
          )}
          {form.video_provider === "openai" && (
            <p className="caption">
              {
                catalog?.models?.video?.find(
                  (model: Data) => model.id === form.video_model,
                )?.description
              }{" "}
              Sora input-image restrictions may prevent human-character
              references. Check your account's current model access before
              producing a series.
            </p>
          )}
          <div className="field-row">
            <label className="field">
              Speech provider
              <select
                value={form.voice_provider}
                onChange={(e) => {
                  set("voice_provider", e.target.value);
                  set("character_voices", {});
                  set(
                    "voice",
                    e.target.value === "kokoro"
                      ? "af_heart"
                      : e.target.value === "system"
                        ? "Samantha"
                        : "alloy",
                  );
                }}
              >
                <option value="kokoro">Local · Kokoro neural voices</option>
                <option value="system">Local · macOS voice</option>
                <option value="openai">OpenAI speech API</option>
                <option value="none">No synthesized speech</option>
              </select>
            </label>
            <label className="field">
              Narrator voice
              {form.voice_provider === "kokoro" ? (
                <select
                  value={form.voice}
                  onChange={(e) => set("voice", e.target.value)}
                >
                  {Object.entries(
                    status?.local?.voices || {
                      af_heart: "Heart · warm American narrator",
                    },
                  ).map(([id, label]) => (
                    <option value={id} key={id}>
                      {String(label)}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  value={form.voice}
                  disabled={form.voice_provider === "none"}
                  onChange={(e) => set("voice", e.target.value)}
                />
              )}
            </label>
          </div>
          {form.voice_provider === "kokoro" && (
            <p className="caption">
              Neural English voices run on CPU. Complete sentences flow across
              cuts; narration and dialogue are timed before animation. Delivery
              comes from voice, punctuation and pace; these voices do not
              support arbitrary emotion instructions.
            </p>
          )}
          {characters.length > 0 && form.voice_provider !== "none" && (
            <details>
              <summary>Character voices for this story</summary>
              {characters.map((character) => (
                <label className="field" key={character.id}>
                  {character.name}
                  {form.voice_provider === "kokoro" ? (
                    <select
                      value={
                        form.character_voices?.[
                          `${projectId}/${character.id}`
                        ] || ""
                      }
                      onChange={(e) =>
                        set("character_voices", {
                          ...form.character_voices,
                          [`${projectId}/${character.id}`]: e.target.value,
                        })
                      }
                    >
                      <option value="">Automatic distinct voice</option>
                      {Object.entries(status?.local?.voices || {}).map(
                        ([id, label]) => (
                          <option key={id} value={id}>
                            {String(label)}
                          </option>
                        ),
                      )}
                    </select>
                  ) : (
                    <input
                      value={
                        form.character_voices?.[
                          `${projectId}/${character.id}`
                        ] || ""
                      }
                      placeholder="Automatic"
                      onChange={(e) =>
                        set("character_voices", {
                          ...form.character_voices,
                          [`${projectId}/${character.id}`]: e.target.value,
                        })
                      }
                    />
                  )}
                </label>
              ))}
            </details>
          )}
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
                onChange={(e) => {
                  setCredential(e.target.value);
                  setKey("");
                }}
              >
                <option value="openai">OpenAI</option>
                <option value="compatible">Compatible provider</option>
                <option value="openrouter">OpenRouter · free models</option>
                <option value="lmstudio">LM Studio · optional local key</option>
                <option value="llamacpp">llama.cpp · optional local key</option>
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
            <h3>Local readiness · saved settings</h3>
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
                Language model{" "}
                {status.llm.available ? "listed" : "not available"}
              </Tag>
              <Tag success={status.local.image}>
                Image {status.local.image ? "installed" : "not installed"}
              </Tag>
              <Tag success={status.local.video}>
                Video {status.local.video ? "installed" : "not installed"}
              </Tag>
              <Tag success={status.local.speech}>
                Neural speech{" "}
                {status.local.speech ? "installed" : "not installed"}
              </Tag>
              <Tag success={status.local.ffmpeg}>FFmpeg</Tag>
              <p className="caption">
                {status.local.resources?.available} GiB available memory ·{" "}
                {status.local.free_gib} GiB free disk space. Heavy local jobs
                run one at a time.
              </p>
            </div>
          ) : (
            <p>Checking this machine…</p>
          )}
          {form.image_provider === "local" &&
            status?.local?.image_options?.find(
              (m: Data) => m.id === form.image_model,
            )?.resource_warning && (
              <p className="warning-box">
                {
                  status.local.image_options.find(
                    (m: Data) => m.id === form.image_model,
                  ).resource_warning
                }
              </p>
            )}
          <details>
            <summary>Install local models</summary>
            <p>Run from the project folder:</p>
            <pre>.venv/bin/python scripts/setup_models.py mlx-image</pre>
            <pre>uv sync --extra dev --extra local --extra speech</pre>
            <pre>.venv/bin/python scripts/setup_models.py speech</pre>
            <p>Additional local language model:</p>
            <pre>ollama pull qwen3:8b</pre>
            <p>Optional fast reference studies:</p>
            <pre>.venv/bin/python scripts/setup_models.py fast-image</pre>
            <p>
              Additional free video models (check available disk space first):
            </p>
            <pre>
              .venv/bin/python scripts/setup_models.py wan-video --dry-run
            </pre>
            <pre>.venv/bin/python scripts/setup_models.py wan-video</pre>
            <pre>.venv/bin/python scripts/setup_models.py vace-video</pre>
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
