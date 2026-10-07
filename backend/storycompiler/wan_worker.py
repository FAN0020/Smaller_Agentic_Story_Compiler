"""Wan image-conditioned inference with separate text and video loading phases.

CPU offload alone does not free shared Mac RAM. Release the text encoder before
loading the denoiser and VAE, under the existing monitored subprocess limits.
"""

import gc
import json
from pathlib import Path

from .video_models import VACE, video_inputs, video_profile


def run_wan(request, device):
    import torch
    from diffusers import AutoencoderKLWan, UniPCMultistepScheduler, WanImageToVideoPipeline, WanVACEPipeline
    from diffusers.utils import export_to_video
    from PIL import Image, ImageOps
    from transformers import AutoTokenizer, UMT5EncoderModel

    model = request["model_id"]
    profile = video_profile(model)
    directory = Path(request["models"]) / profile["folder"]
    cls = WanVACEPipeline if model == VACE else WanImageToVideoPipeline
    tokenizer = AutoTokenizer.from_pretrained(directory / "tokenizer", local_files_only=True)
    if len(tokenizer(request["prompt"], add_special_tokens=True)["input_ids"]) > 512:
        raise ValueError(
            "Wan prompt exceeds 512 tokens; simplify the shot before rendering. No text was truncated."
        )
    dtype = torch.bfloat16 if device != "cpu" else torch.float32
    print(json.dumps({"stage": "encoding_prompt", "model": model, "device": device}), flush=True)
    encoder = (
        UMT5EncoderModel.from_pretrained(
            directory / "text_encoder",
            torch_dtype=dtype,
            local_files_only=True,
        )
        .eval()
        .to(device)
    )
    scheduler = UniPCMultistepScheduler.from_pretrained(directory / "scheduler", local_files_only=True)
    text_pipe = cls(
        tokenizer=tokenizer, text_encoder=encoder, vae=None, transformer=None, scheduler=scheduler
    )
    with torch.no_grad():
        prompt, negative = text_pipe.encode_prompt(
            request["prompt"],
            negative_prompt="deformed anatomy, flicker, text, watermark, inconsistent identity",
            max_sequence_length=512,
            device=torch.device(device),
            dtype=dtype,
        )
    prompt, negative = prompt.cpu(), negative.cpu()
    del text_pipe, encoder
    gc.collect()
    if device == "mps":
        torch.mps.empty_cache()
    elif device == "cuda":
        torch.cuda.empty_cache()

    print(json.dumps({"stage": "loading_motion_model", "model": model}), flush=True)
    vae = AutoencoderKLWan.from_pretrained(
        directory / "vae", torch_dtype=torch.float32, local_files_only=True
    )
    pipe = cls.from_pretrained(
        directory,
        text_encoder=None,
        tokenizer=tokenizer,
        vae=vae,
        torch_dtype=dtype,
        local_files_only=True,
    ).to(device)
    pipe.vae.enable_tiling(
        tile_sample_min_height=256,
        tile_sample_min_width=256,
        tile_sample_stride_height=192,
        tile_sample_stride_width=192,
    )
    width, height = request["size"]
    with Image.open(request["reference"]) as source:
        reference = ImageOps.fit(source.convert("RGB"), (width, height))
    print(json.dumps({"stage": "generating_motion", "frames": profile["frames"]}), flush=True)
    result = pipe(
        **video_inputs(model, reference),
        prompt_embeds=prompt.to(device),
        negative_prompt_embeds=negative.to(device),
        height=height,
        width=width,
        num_frames=profile["frames"],
        num_inference_steps=request["steps"],
        guidance_scale=5.0,
        generator=torch.Generator("cpu").manual_seed(request["seed"]),
        max_sequence_length=512,
    ).frames[0]
    export_to_video(result, request["output"], fps=profile["fps"])
    print(json.dumps({"output": request["output"], "device": device, "model": model}), flush=True)
