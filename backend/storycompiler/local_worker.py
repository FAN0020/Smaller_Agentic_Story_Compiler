"""Isolated local inference process; models never load in the web server."""

import gc
import json
import sys
from pathlib import Path


def main():
    import torch
    from PIL import Image

    request = json.loads(Path(sys.argv[1]).read_text())
    root = Path(request["models"])
    output = Path(request["output"])
    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    generator = torch.Generator("cpu").manual_seed(request["seed"])
    if request["kind"] == "image":
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

        pipe = LTXImageToVideoPipeline.from_pretrained(
            root / "ltx-video", torch_dtype=torch.bfloat16, local_files_only=True
        )
        pipe.to(device)
        pipe.vae.enable_tiling()
        width, height = request.get("size", [512, 288])
        reference = Image.open(request["reference"]).convert("RGB").resize((width, height))
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
