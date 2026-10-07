import { useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { send } from "./api";
import type { Data } from "./api";

export default function LanguageSettings({
  form,
  catalog,
  set,
  selectCredential,
}: {
  form: Data;
  catalog: Data | null;
  set: (name: string, value: unknown) => void;
  selectCredential: (provider: string) => void;
}) {
  const [discovery, setDiscovery] = useState<Data | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const request = useRef(0);
  const provider = catalog?.models?.language_providers?.find(
    (p: Data) => p.id === form.llm_provider,
  );
  useEffect(() => {
    request.current += 1;
    setDiscovery(null);
    setLoading(false);
    setError("");
    return () => {
      request.current += 1;
    };
  }, [form.llm_provider, form.llm_endpoint]);
  async function discover() {
    const token = ++request.current;
    setLoading(true);
    setError("");
    try {
      const result = await send("/providers/language-models", {
        llm_provider: form.llm_provider,
        llm_endpoint: form.llm_endpoint,
        llm_model: form.llm_model,
      });
      if (token === request.current) setDiscovery(result);
    } catch (e) {
      if (token === request.current) setError((e as Error).message);
    } finally {
      if (token === request.current) setLoading(false);
    }
  }
  const options: Data[] = [
    ...(form.llm_provider === "ollama" ? catalog?.models?.llm || [] : []),
  ];
  for (const model of discovery?.options || []) {
    if (!options.some((item) => item.id === model.id)) options.push(model);
  }
  if (form.llm_model && !options.some((item) => item.id === form.llm_model))
    options.push({ id: form.llm_model, label: `${form.llm_model} · selected` });
  const selected = options.find((option) => option.id === form.llm_model);
  const listed = discovery?.models?.includes(form.llm_model);
  return (
    <section className="settings-section">
      <h3>Story & direction</h3>
      <label className="field">
        Language provider
        <select
          value={form.llm_provider}
          onChange={(e) => {
            const next = catalog?.models?.language_providers.find(
              (p: Data) => p.id === e.target.value,
            );
            if (!next) return;
            set("llm_provider", next.id);
            set("llm_endpoint", next.endpoint);
            set("llm_model", next.model);
            if (next.id !== "ollama") selectCredential(next.id);
          }}
        >
          {(
            catalog?.models?.language_providers || [
              { id: form.llm_provider, label: form.llm_provider },
            ]
          ).map((p: Data) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      <p className="caption">{provider?.description}</p>
      {!["openai", "openrouter"].includes(form.llm_provider) && (
        <label className="field">
          Provider endpoint
          <input
            value={form.llm_endpoint}
            onChange={(e) => set("llm_endpoint", e.target.value)}
          />
        </label>
      )}
      <div className="section-title">
        <h4>
          {form.llm_provider === "openrouter"
            ? "Free public model catalog"
            : "Available language models"}
        </h4>
        <button
          className="text-button"
          disabled={loading}
          onClick={() => void discover()}
        >
          <RefreshCw size={13} />{" "}
          {loading ? "Loading models…" : "Refresh models"}
        </button>
      </div>
      <label className="field">
        Model
        <select
          value={form.llm_model}
          onChange={(e) => set("llm_model", e.target.value)}
        >
          <option value="">Choose a model · refresh to discover</option>
          {options.map((model) => (
            <option value={model.id} key={model.id}>
              {model.label}
              {model.tier ? ` · ${model.tier}` : ""}
              {discovery?.models?.includes(model.id) ? " · listed" : ""}
            </option>
          ))}
        </select>
      </label>
      <p className="caption">
        {selected?.description}
        {selected?.context_length
          ? ` Advertised context: ${selected.context_length.toLocaleString()} tokens.`
          : ""}
      </p>
      <details>
        <summary>Enter an exact model ID</summary>
        <label className="field">
          Model ID
          <input
            value={form.llm_model}
            placeholder={
              form.llm_provider === "openrouter"
                ? "publisher/model:free"
                : "Exact server model ID"
            }
            onChange={(e) => set("llm_model", e.target.value)}
          />
        </label>
      </details>
      <div aria-live="polite">
        {error && <p className="error-banner">{error}</p>}
        {discovery && (
          <p className={discovery.reachable ? "caption" : "warning-box"}>
            {discovery.reachable
              ? `${discovery.models.length} models listed. ${listed ? "Selected model is listed; generation quality has not been checked." : "Selected model is not listed. Load it in the server or choose a listed model."}`
              : discovery.error}
            {discovery.credential_required &&
              " Save this provider's API key below before planning. Discovery uses saved credentials."}
          </p>
        )}
      </div>
      {form.llm_provider === "ollama" && (
        <>
          <p className="caption">Install the selected model before use:</p>
          <pre>ollama pull {form.llm_model || "MODEL_TAG"}</pre>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={!!form.llm_reasoning}
              disabled={
                !!discovery?.capabilities?.[form.llm_model] &&
                !discovery.capabilities[form.llm_model].includes("thinking")
              }
              onChange={(e) => set("llm_reasoning", e.target.checked)}
            />
            Reasoning for episode, scene and shot planning · supported models
            only; takes longer
          </label>
          <label className="field">
            Context size
            <select
              value={form.llm_context_tokens || 16384}
              onChange={(e) =>
                set("llm_context_tokens", Number(e.target.value))
              }
            >
              <option value={4096}>4K · limited planning context</option>
              <option value={8192}>8K · lower memory</option>
              <option value={16384}>16K · balanced</option>
              <option value={32768}>32K · more memory</option>
              <option value={65536}>64K · large machines</option>
            </select>
          </label>
        </>
      )}
      <label className="checkbox">
        <input
          type="checkbox"
          checked={form.llm_compact_recovery !== false}
          onChange={(e) => set("llm_compact_recovery", e.target.checked)}
        />
        Compact planning recovery · retry invalid episode/scene plans with the
        same model
      </label>
      <p className="caption">
        Retains all ordered source events and checks coverage and story
        fidelity. A smaller prompt may help a limited model; it cannot guarantee
        a usable plan.
      </p>
      {provider?.setup && (
        <details>
          <summary>Start this language server</summary>
          <pre>{provider.setup}</pre>
          <p className="caption">
            Download a chat model first. Local models use your memory and disk;
            no per-call API fee.
          </p>
          {provider.docs && (
            <a href={provider.docs} target="_blank" rel="noreferrer">
              Setup documentation
            </a>
          )}
        </details>
      )}
    </section>
  );
}
