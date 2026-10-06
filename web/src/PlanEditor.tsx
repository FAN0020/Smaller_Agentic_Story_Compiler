import { useState } from "react";
import type { Data } from "./api";
import { Button } from "./components";

export default function PlanEditor({
  number,
  plan,
  disabled,
  save,
}: {
  number: number;
  plan: Data;
  disabled: boolean;
  save: (revision: Data) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  return (
    <div className="plan-editor">
      {!open ? (
        <Button
          secondary
          small
          disabled={disabled}
          onClick={() => {
            setDraft(
              JSON.stringify(
                { scenes: plan.scenes, shots: plan.shots },
                null,
                2,
              ),
            );
            setError("");
            setOpen(true);
          }}
        >
          Edit episode {number} plan
        </Button>
      ) : (
        <div className="json-editor">
          <p>
            Correct actions, dialogue, camera or sound before approval. Saving
            preserves the prior revision and requires renewed approval. Keep the
            frozen identities, source coverage and timing intact.
          </p>
          <label className="field">
            Episode {number} plan JSON
            <textarea
              rows={20}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
          </label>
          {error && (
            <p className="error-banner" role="alert">
              {error}
            </p>
          )}
          <div className="action-row">
            <Button
              secondary
              disabled={disabled}
              onClick={() => setOpen(false)}
            >
              Cancel edit
            </Button>
            <Button
              disabled={disabled}
              onClick={() => {
                setError("");
                void (async () => {
                  try {
                    await save(JSON.parse(draft));
                    setOpen(false);
                  } catch (e) {
                    setError((e as Error).message);
                  }
                })();
              }}
            >
              Save plan revision
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
