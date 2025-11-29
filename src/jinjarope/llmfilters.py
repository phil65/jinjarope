from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv


load_dotenv()


def llm_generate_image(
    prompt: str,
    model: str | None = None,
    token: str | None = None,
    base_url: str | None = None,
    size: str = "1024x1024",
    quality: str = "standard",
    as_b64_json: bool = False,
    **kwargs: Any,
) -> str | None:
    """Generate an image using the LLM API and returns the URL.

    Args:
        prompt: The prompt to generate an image from.
        model: The model to use. Defaults to None.
        token: The API token. Defaults to None.
        base_url: The base URL of the API. Defaults to None.
        size: The size of the generated image. Defaults to "1024x1024".
        quality: The quality of the generated image. Defaults to "standard".
        as_b64_json: Return b64-encoded image instead of URL.
        kwargs: Additional keyword arguments passed to litellm.image_generation.

    Returns:
        The generated image response.
    """
    import litellm

    response = litellm.image_generation(
        prompt=prompt,
        model=model or os.getenv("OPENAI_IMAGE_MODEL"),
        api_key=token or os.getenv("OPENAI_API_TOKEN"),
        api_base=base_url,
        size=size,
        quality=quality,
        response_format="b64_json" if as_b64_json else "url",
        **kwargs,
    )
    # Check if the API result is valid
    if response and response.data and len(response.data) > 0:
        # TODO: <img src="data:image/png;base64,iVBORw0KG..." />
        return response.data[0].b64_json if as_b64_json else response.data[0].url
    return None


if __name__ == "__main__":
    response = llm_generate_image(
        prompt="A dog!",
        model="ollama/llava",
    )
    print(response)
    print(response)
