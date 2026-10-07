# Resource optimization implementation TODO

Status: planned. Priority order: P0, P1, P2, then P3. Requirements recorded on October 8, 2026.

Improve generation throughput and quality by preserving complete conditioning, managing model residency, and making resource decisions from backend capabilities and measured behavior. Keep existing memory protections throughout implementation. CPU or GPU utilization is a diagnostic metric, not the production success criterion.

## P0 Fix context budgeting

- [ ] Read the effective `context_limit` from the selected model and active backend. Account for the backend's configured context window as well as the model's supported maximum; do not hardcode 16K.
- [ ] Before every call, including repair and retry calls, enforce:

  ```text
  input_tokens + reserved_output_tokens + safety_margin <= context_limit
  ```

- [ ] Count the complete serialized input, including system instructions, message formatting, schemas, and repair feedback, through the applicable tokenizer or backend adapter. If a reliable budget cannot be established, report the limitation explicitly rather than assuming the input fits.
- [ ] Ensure `max_output_tokens`, or its backend equivalent, never exceeds the remaining context after input and safety margin. Include reasoning tokens in the output reservation where the backend counts them against the same context budget.
- [ ] When over budget, first remove irrelevant scene context. Never silently remove source evidence, canon, or continuity constraints.
- [ ] If essential information still does not fit, fail explicitly with a context-budget error or request decomposition into smaller tasks. Do not rely on backend truncation.
- [ ] Test context overflow, input truncation detection, output reservation, and the remaining-context output cap. Verify that protected information survives context reduction and that retries receive the same checks.

## P0 Establish a unified Resource Capability Layer

- [ ] Detect the current backend and device capabilities automatically. Do not assume Apple Silicon, CUDA, or CPU execution.
- [ ] Expose at least `available_memory`, `device_type`, `model_context_limit`, `supported_precision`, and `unload_capability`. Distinguish shared system memory from separate device memory where applicable.
- [ ] Enable each optimization only when the capability layer confirms support. Use a safe supported fallback when it does not.
- [ ] Keep CUDA, MPS, and macOS checks inside capability or backend adapters. The business pipeline must not contain platform-specific branching.

## P0 Separate memory shortage from FAILED

- [ ] Add a formal persisted job state such as `WAITING_FOR_RESOURCES`.
- [ ] Treat temporary memory shortage as a resource wait rather than a production failure. Recheck capacity before resuming execution.
- [ ] Support cancellation, a configurable waiting timeout, and visible waiting status with the reason. Report timeout as resource-wait exhaustion rather than a model-generation failure.
- [ ] Preserve completed checkpoints while waiting, cancelling, or timing out. Define restart recovery for waiting jobs consistently with the existing recovery contract.
- [ ] Never bypass an existing out-of-memory, swap, disk, or allocator safety guard to continue a waiting job.

## P0 Preserve and refactor the memory safety guard

- [ ] Replace blanket rules such as "requires 40 GB" with estimates based on the actual device, backend, model, precision, and operation configuration.
- [ ] Account for relevant context size, resolution, frame count, reference count, active model residency, temporary allocations, and system headroom.
- [ ] Use a conservative fallback when no reliable estimate is available. Unknown capacity must not be interpreted as unlimited capacity.
- [ ] Retain admission checks and runtime protections for memory pressure, swap growth, disk headroom, and supported allocator limits. Encapsulate backend-specific mechanisms in adapters.
- [ ] Never treat "the machine did not crash" as evidence that an optimization is safe. Require resource measurements and defined safety margins.

## P1 Implement a general Model Lifecycle Manager

- [ ] Provide a common `load -> use -> release` interface.
- [ ] Manage planner, image model, video model, encoder, and decoder lifecycles through this interface.
- [ ] Encapsulate backend-specific loading and unloading behavior in adapters, including cleanup after cancellation or exceptions.
- [ ] Verify that release actually returns resources using the applicable measurement adapter. A successful unload request alone is insufficient evidence.
- [ ] If a backend cannot release resources reliably or release cannot be verified, do not force optimizations that depend on confirmed release. Use the safe supported execution path.

## P1 Implement phased loading on supported backends

- [ ] Support the execution sequence `text encoder -> embeddings -> release encoder -> generator -> decoder` when the backend and model permit it.
- [ ] Preserve every conditioning value needed by later inference, including applicable masks, negative conditioning, references, and model-specific metadata.
- [ ] Compare phased execution with the original execution using conditioning-equivalence tests and output-equivalence tests under fixed inputs and seeds. Declare numerical tolerances where bitwise equality is not supported; retain canon and conditioning invariants.
- [ ] Do not encode an LTX-specific assumption such as "saves 8.9 GiB" into the implementation or resource policy.
- [ ] Measure actual peak memory for both execution modes under the same configuration. Enable phased loading only after the measured difference, equivalence results, and safety checks justify it for that backend and model.

## P1 Reduce repeated model loading

- [ ] Execute consecutive planning calls with reusable planner residency when supported and admitted by the resource manager.
- [ ] Group independent opening-image and reference-image operations where possible. Preserve any required reference approval or dependency ordering.
- [ ] Release the image model before beginning a group of video operations.
- [ ] Generate video clips consecutively with reusable video-model residency where supported. Grouping operations does not imply simultaneous heavyweight inference.
- [ ] Preserve shot dependencies, repair semantics, checkpoint behavior, and continuity when reordering work.
- [ ] Allow an explicit exception for any shot whose dependencies require immediate `image -> video` execution.

## P1 Add resource measurement and telemetry

- [ ] Record the following for every production operation:

  ```text
  model / backend / device / context / resolution / reference_count /
  runtime / peak_memory / retries / result
  ```

- [ ] Include failed, cancelled, retried, and resource-blocked operations so telemetry does not represent successful attempts alone.
- [ ] Use platform-specific measurement adapters. Identify the scope of memory measurements, such as process memory, framework allocation, device memory, or system memory; these quantities are not interchangeable.
- [ ] Allow unavailable measurements to be `null`. Measurement failures must not crash the pipeline or weaken resource admission.
- [ ] Gradually replace heuristics with measurements from matching model, backend, and operation configurations while retaining conservative headroom.

## P2 Implement a conservative scheduler

- [ ] Permit only one heavyweight generator at a time by default.
- [ ] Do not keep the planner, image generator, and video generator resident concurrently by default.
- [ ] Allow overlap only when capability data and measurements justify it and the resource manager admits the combined workload.
- [ ] Use safe sequential execution on unknown devices or when the required measurements are unavailable.

## P2 Make CPU supporting work an optional optimization

- [ ] Allow audio, validation, and FFmpeg work to use a separate supporting-task queue.
- [ ] Enable overlap only when the resource manager confirms sufficient headroom for the combined work. Sequential execution remains the default.
- [ ] Stop launching new supporting tasks immediately when memory pressure rises. Preserve the existing runtime protections for work already in progress.
- [ ] Never run two heavyweight generators concurrently by default.

## P2 Establish production KPIs

- [ ] Record `accepted_shots / wall_clock_hour` for a defined production run or evaluation interval.
- [ ] Include retries, validation failures, and regeneration in elapsed time. Do not reset the clock or discard unsuccessful attempts when reporting throughput.
- [ ] Define acceptance using the existing quality-review contract. Technical validity alone must not count as artistic acceptance, and multiple attempts at the same shot must not inflate the accepted-shot count.
- [ ] Record quality results and acceptance rate alongside throughput so a lower quality bar cannot appear to be a speed improvement.
- [ ] Do not use CPU or GPU utilization as the final success metric.

## P3 Build a cross-platform acceptance matrix

- [ ] Cover Apple Silicon, CUDA, and CPU fallback. Performance may differ, but execution semantics must remain consistent.
- [ ] Verify all of the following on each platform:

  | Required behavior | Apple Silicon | CUDA | CPU fallback |
  | --- | --- | --- | --- |
  | No silent context truncation | Pending | Pending | Pending |
  | Memory and swap guards remain enforced | Pending | Pending | Pending |
  | Temporary resource shortage enters a waiting state instead of FAILED | Pending | Pending | Pending |
  | Waiting supports cancellation, timeout, and visible status | Pending | Pending | Pending |
  | Optimizations preserve canon and complete conditioning | Pending | Pending | Pending |
  | Unsupported optimizations use safe fallbacks | Pending | Pending | Pending |

- [ ] Record the backend, model configuration, test method, and evidence for each result. Distinguish adapter or simulated tests from real-device acceptance; mark unavailable hardware as not verified.
