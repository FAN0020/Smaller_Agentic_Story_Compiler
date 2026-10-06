# Production improvements — 7 October 2026

## Acceptance requirements

1. More usable free models, with honest capability and installation status; deploy and exercise the selected local additions.
2. Natural neural voices, separate narration and character speech, and audio timing planned before animation. Speech must never be silently cut or squeezed into four-second sentences.
3. Investigate the reference-generation restart; prevent unsafe local model loading, retain work after interruption, and verify recovery without intentionally reproducing an OS crash.
4. Remove repeated page labels and other redundant interface elements; inspect desktop and mobile rendered views.

## Restart evidence

The user's Aladdin reference job started at 01:50:08 on 7 October. Qwen3.5 9B analysis finished at 01:49:52; the old adapter kept it resident for three minutes. The FLUX log ends immediately after all components loaded, before any denoising progress. macOS rebooted at 01:52:36.

The corresponding OS panic reports a watchdog timeout (no check-ins for 91 seconds), 16 swapfiles and **LOW swap space**. This establishes an OS-level stall and scarce swap; it does not prove a sole Python or GPU-driver cause. Unquantized FLUX loading alongside the retained LLM is a plausible, preventable contributor. Previous successful runs are not evidence that this concurrent workload is safe.

## Resource controls

Local image/video admission reserves 3 GiB beyond an estimated working set and requires 10 GiB free disk. Full-precision FLUX is refused below 32 GB physical memory. A process monitor stops generation when available RAM drops below 2 GiB, disk below 8 GiB, swap growth exceeds 2 GiB, or worker RSS exceeds its budget. PyTorch MPS receives an explicit allocator cap. A shared OS-backed lease serializes Studio local inference across processes; Ollama requests now unload immediately on completion. No unrelated app or model is forcibly stopped.

These are conservative protections, not a guarantee against operating-system faults. Interrupted jobs require explicit resume. Successfully published artifacts remain intact; partial files never become completed checkpoints.

## Evidence ledger

- Resource admission and lease tests: 3 passed; provider contracts: 8 passed, including immediate Ollama unload.
- Pending: real rejected workload, runtime termination/restart evidence, new model deployment, audio and UI acceptance.
