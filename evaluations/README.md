# Model evaluation

`cases.v1.json` pins the user-provided sources by SHA-256. The lion/mouse story is the development regression case; remaining stories are protected cases, not prompt-tuning inputs. Their presence in the manifest does **not** mean model evaluation passed.

For a real run, use the application with the recorded brief and selected model. Preserve the project export, model audit, plan attempts, approvals, generation receipts and rendered media. Record the Git revision, prompt version, model digest, inference parameters, elapsed time and result per stage. Inspect source semantics and actual output independently of the model's own critic. Reject true source contradictions; document critic false positives separately. A schema pass is not a quality score.

The local workspace keeps development runs under `.studio/` and `output/evaluation/`; these are excluded from Git because they contain user story content and large model/media artifacts. The committed verification report records aggregate evidence and limitations. Do not fabricate passed protected cases from unit tests, mock adapters, text-plan reviews, or a single motion clip.
