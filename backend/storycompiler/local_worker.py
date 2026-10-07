"""Isolated local inference process; models never load in the web server."""

import gc
import json
import sys
from pathlib import Path


def main():
    import torch
    from PIL import Image, ImageOps

    request = json.loads(Path(sys.argv[1]).read_text())
    root = Path(request["models"])
    output = Path(request["output"])
    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    if device == "mps":
        limit = request["memory_limit_gib"] * 1024**3
        torch.mps.set_per_process_memory_fraction(min(0.85, limit / torch.mps.recommended_max_memory()))
    torch.set_num_threads(4)
    if (
        request["kind"] == "video"
        and request.get("model_id", "Lightricks/LTX-Video-0.9.1") != "Lightricks/LTX-Video-0.9.1"
    ):
        from .wan_worker import run_wan

        run_wan(request, device)
        return
    generator = torch.Generator("cpu").manual_seed(request["seed"])
    if request["kind"] == "image" and request.get("model_id") == "black-forest-labs/FLUX.2-klein-4B":
        from diffusers import Flux2KleinPipeline

        pipe = Flux2KleinPipeline.from_pretrained(
            root / "flux2-klein-4b", torch_dtype=torch.bfloat16, local_files_only=True
        )
        pipe.to(device)
        pipe.vae.enable_tiling()
        if len(pipe.tokenizer(request["prompt"], add_special_tokens=False)["input_ids"]) > 960:
            raise ValueError("FLUX prompt exceeds its text budget; simplify the shot explicitly")
        refs = [Image.open(path).convert("RGB") for path in request.get("references", [])]
        width, height = request.get("size", [512, 512])
        result = pipe(
            image=refs or None,
            prompt=request["prompt"],
            height=height,
            width=width,
            num_inference_steps=4,
            guidance_scale=1.0,
            max_sequence_length=1024,
            generator=torch.Generator(device=device).manual_seed(request["seed"]),
        ).images[0]
        result.save(output)
    elif request["kind"] == "image":
        from diffusers import AutoPipelineForImage2Image, AutoPipelineForText2Image

        pipe = AutoPipelineForText2Image.from_pretrained(
            root / "sd-turbo",
            torch_dtype=torch.float16 if device != "cpu" else torch.float32,
            variant="fp16",
            local_files_only=True,
        )
        pipe.to(device)
        # Encode complete 75-token windows separately; concatenate cross-attention embeddings.
        # This keeps every identity/action constraint instead of silently truncating at 77 tokens.
        prompt = request["prompt"]
        tokens = pipe.tokenizer(prompt, truncation=False, add_special_tokens=False)["input_ids"]
        if len(tokens) > 1050:
            raise ValueError("Local image prompt exceeds its 1050-token budget; simplify the shot explicitly")
        embeddings = []
        for offset in range(0, max(1, len(tokens)), 75):
            ids = [pipe.tokenizer.bos_token_id] + tokens[offset : offset + 75] + [pipe.tokenizer.eos_token_id]
            ids += [pipe.tokenizer.pad_token_id] * (77 - len(ids))
            with torch.no_grad():
                embeddings.append(pipe.text_encoder(torch.tensor([ids], device=device))[0])
        kwargs = {
            "prompt_embeds": torch.cat(embeddings, dim=1),
            "num_inference_steps": 4,
            "guidance_scale": 0.0,
            "generator": generator,
        }
        if request.get("reference"):
            pipe = AutoPipelineForImage2Image.from_pipe(pipe)
            kwargs.update(
                image=Image.open(request["reference"]).convert("RGB").resize((512, 512)), strength=0.7
            )
        else:
            kwargs.update(height=512, width=512)
        result = pipe(**kwargs).images[0]
        result.save(output)
    else:
        from diffusers import LTXImageToVideoPipeline
        from diffusers.utils import export_to_video

        generator = torch.Generator(device=device).manual_seed(request["seed"])

        pipe = LTXImageToVideoPipeline.from_pretrained(
            root / "ltx-video", torch_dtype=torch.bfloat16, local_files_only=True
        )
        pipe.to(device)
        pipe.vae.enable_tiling()
        width, height = request.get("size", [512, 288])
        reference = ImageOps.fit(Image.open(request["reference"]).convert("RGB"), (width, height))
        if len(pipe.tokenizer(request["prompt"], add_special_tokens=False)["input_ids"]) > 1022:
            raise ValueError("Video prompt exceeds the 1024-token budget; simplify the shot explicitly")
        result = pipe(
            image=reference,
            prompt=request["prompt"],
            negative_prompt="inconsistent motion, deformed anatomy, flicker, text, watermarks",
            width=width,
            height=height,
            num_frames=97,
            frame_rate=24,
            num_inference_steps=request.get("steps", 20),
            guidance_scale=3,
            generator=generator,
            max_sequence_length=1024,
        ).frames[0]
        export_to_video(result, str(output), fps=24)
    del pipe
    gc.collect()
    print(json.dumps({"output": str(output), "device": device}), flush=True)


if __name__ == "__main__":
    main()
