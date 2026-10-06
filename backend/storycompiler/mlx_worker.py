"""Apple-native quantized image inference, in a separately pinned environment."""

import json
import sys
from pathlib import Path


def main():
    import mlx.core as mx
    from mflux.models.common.config import ModelConfig
    from mflux.models.flux2.variants import Flux2Klein, Flux2KleinEdit

    request = json.loads(Path(sys.argv[1]).read_text())
    mx.set_memory_limit(int(request["memory_limit_gib"] * 1024**3))
    mx.set_cache_limit(256 * 1024**2)
    refs = request.get("references", [])
    cls = Flux2KleinEdit if refs else Flux2Klein
    model = cls(
        quantize=4,
        model_path=str(Path(request["models"]) / "flux2-klein-4b-mlx"),
        model_config=ModelConfig.flux2_klein_4b(),
    )
    tokenizer = next(iter(model.tokenizers.values()))
    # The pinned MFLUX encoder has a 512-token input. Check the fully formatted
    # prompt before its tokenizer truncates; an oversized shot needs explicit editing.
    encoded = tokenizer.tokenize(request["prompt"], max_length=513)
    if int(encoded.attention_mask.sum().item()) > 512:
        raise ValueError("MLX FLUX prompt exceeds its 512-token budget; simplify the shot explicitly")
    width, height = request["size"]
    result = model.generate_image(
        seed=request["seed"],
        prompt=request["prompt"],
        width=width,
        height=height,
        num_inference_steps=4,
        **({"image_paths": refs} if refs else {}),
    )
    result.save(request["output"])
    print(json.dumps({"device": "mlx", "peak_memory_gib": mx.get_peak_memory() / 1024**3}), flush=True)


if __name__ == "__main__":
    main()
