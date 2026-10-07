import { useState } from "react";
import type { Data } from "./api";
import { Button, Tag } from "./components";

const fields = [
  ["period", "Period"],
  ["country_or_region", "Country / region"],
  ["polity_or_dynasty", "Polity / dynasty"],
  ["cultural_context", "Cultural context"],
  ["architecture", "Architecture"],
  ["clothing", "Clothing"],
  ["material_culture", "Material culture"],
  ["language", "Language"],
  ["climate", "Climate"],
];

function valueOrNA(value?: string) {
  const text = value?.trim() || "";
  return ["", "na", "n/a", "unspecified"].includes(text.toLowerCase())
    ? "NA"
    : text;
}

export default function StorySettingPanel({
  bible,
  frozen,
  busy,
  editDisabled,
  onEditing,
  act,
}: {
  bible: Data;
  frozen: boolean;
  busy: boolean;
  editDisabled: boolean;
  onEditing: (editing: boolean) => void;
  act: (path: string, body: Data) => Promise<void>;
}) {
  const [draft, setDraft] = useState<Data | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const setting = draft || bible.story_setting || {};

  function close() {
    setDraft(null);
    setError("");
    onEditing(false);
  }

  async function save() {
    setSaving(true);
    setError("");
    const { style_instruction, policy, brief, source_hash, ...editable } =
      bible;
    try {
      await act("/bible", {
        _method: "PUT",
        ...editable,
        story_setting: {
          ...draft,
          visual_guidance: (draft?.visual_guidance || [])
            .map((s: string) => s.trim())
            .filter(Boolean),
          guardrails: (draft?.guardrails || [])
            .map((s: string) => s.trim())
            .filter(Boolean),
        },
      });
      close();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not save the setting. Try again.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section
      className="setting-profile"
      aria-label="Historical and cultural setting"
    >
      <div className="section-title">
        <h3>Historical & cultural setting</h3>
        <Tag>{frozen ? "Approved setting" : "Review before approval"}</Tag>
      </div>
      <p className="muted">
        Low-confidence guesses are suggestions. Edit them before approving the
        bible, or use NA when there is no evidence. NA adds no setting
        constraint; generation continues normally.
      </p>
      <div className="setting-facts">
        {fields.map(([key, label]) => {
          const item = setting[key];
          const value = valueOrNA(item?.value);
          return (
            <div key={key}>
              {draft ? (
                <label className="field">
                  {label}
                  <input
                    value={item?.value ?? "NA"}
                    disabled={busy || saving}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        [key]: {
                          value: e.target.value,
                          basis: "user_defined",
                          evidence: "",
                          confidence: "low",
                        },
                      })
                    }
                  />
                </label>
              ) : (
                <>
                  <span className="small-label">{label}</span>
                  <strong>{value}</strong>
                </>
              )}
              <Tag>
                {value === "NA"
                  ? "No setting constraint"
                  : item?.basis === "user_defined"
                    ? "Your choice"
                    : `${item?.basis || "inferred"} · ${item?.confidence || "low"} confidence`}
              </Tag>
              {value !== "NA" && item?.evidence && <p>{item.evidence}</p>}
            </div>
          );
        })}
      </div>
      {draft ? (
        <>
          <p className="muted">
            After changing a guess, update or clear its visual guidance too.
          </p>
          {[
            ["visual_guidance", "Visual guidance"],
            ["guardrails", "Consistency rules"],
          ].map(([key, label]) => (
            <label className="field" key={key}>
              {label} · one per line, optional
              <textarea
                rows={3}
                disabled={busy || saving}
                value={(draft[key] || []).join("\n")}
                onChange={(e) =>
                  setDraft({ ...draft, [key]: e.target.value.split("\n") })
                }
              />
            </label>
          ))}
          {error && <p role="alert">{error}</p>}
          <div className="action-row">
            <Button disabled={busy || saving} onClick={() => void save()}>
              {saving ? "Saving…" : "Save setting"}
            </Button>
            <Button secondary disabled={saving} onClick={close}>
              Cancel
            </Button>
          </div>
          <p className="muted">
            Save or cancel your edits before freezing the bible.
          </p>
        </>
      ) : (
        <>
          {setting.visual_guidance?.length > 0 && (
            <p>
              <strong>Visual guidance:</strong>{" "}
              {setting.visual_guidance.join(" · ")}
            </p>
          )}
          {setting.guardrails?.length > 0 && (
            <p>
              <strong>Consistency rules:</strong>{" "}
              {setting.guardrails.join(" · ")}
            </p>
          )}
          {!frozen && (
            <Button
              secondary
              disabled={busy || editDisabled}
              onClick={() => {
                setDraft(JSON.parse(JSON.stringify(bible.story_setting || {})));
                onEditing(true);
              }}
            >
              Edit setting
            </Button>
          )}
        </>
      )}
    </section>
  );
}
