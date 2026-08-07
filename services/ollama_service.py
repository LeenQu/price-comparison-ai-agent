import json

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2"


def _format_products_for_prompt(products, max_products=40):
    """
    Same formatting approach as claude_service - compact, readable
    listing block, cheapest-first, capped to keep the prompt small
    (local models generally have smaller context windows and are
    slower, so keeping this tight matters more here than with Claude).
    """

    trimmed = sorted(
        products,
        key=lambda p: (p.price is None, p.price),
    )[:max_products]

    lines = []
    for p in trimmed:
        lines.append(
            f"- [{p.website}] {p.name} | price: {p.price} SAR | "
            f"rating: {p.rating} ({p.reviews} reviews) | url: {p.product_url}"
        )

    return "\n".join(lines)


def _empty_answer(summary):
    return {
        "summary": summary,
        "recommended_product": None,
        "alternatives": [],
        "caveats": [],
    }


def ask_about_products_ollama(question, products):
    """
    Local-model equivalent of claude_service.ask_about_products.
    Returns the same structured dict shape (summary, recommended_product,
    alternatives, caveats), but runs entirely on your local Ollama
    instance instead of calling the Claude API - free, no API key,
    but generally lower quality and slower than Claude on the same task.

    Requires Ollama running locally (default: http://localhost:11434)
    with a model pulled - see OLLAMA_MODEL above.
    """

    if not products:
        return _empty_answer(
            "I couldn't find any matching products in the database to answer that question."
        )

    product_block = _format_products_for_prompt(products)

    # Ollama's `format: "json"` guarantees syntactically valid JSON output,
    # but NOT a specific schema - so the exact shape has to be spelled out
    # in the prompt itself, and the result should be parsed defensively.
    system_prompt = (
        "You are a shopping assistant for a price-comparison app tracking "
        "phone listings from Amazon.sa and Noon.com. You will be given real "
        "product listings and a question. Answer using ONLY the listings "
        "given - never invent products, prices, or specs.\n\n"
        "Respond with ONLY a JSON object in exactly this shape, no other text:\n"
        "{\n"
        '  "summary": "1-2 sentence plain text answer",\n'
        '  "recommended_product": {"name": "...", "website": "...", '
        '"price": 0.0, "rating": 0.0, "reviews": 0, "url": "..."} or null,\n'
        '  "alternatives": [{"name": "...", "website": "...", "price": 0.0, '
        '"rating": 0.0, "reviews": 0, "url": "...", "why": "..."}],\n'
        '  "caveats": ["short warning strings, e.g. renewed device, low rating"]\n'
        "}"
    )

    user_message = (
        f"Listings:\n\n{product_block}\n\n"
        f"Question: {question}"
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "format": "json",
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            },
            timeout=120,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Couldn't reach Ollama at "
            f"{OLLAMA_URL} - is it installed and running? "
            "Run 'ollama serve' or open the Ollama app, and make sure "
            f"you've pulled a model (e.g. 'ollama pull {OLLAMA_MODEL}')."
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(
            "Ollama took too long to respond (over 120s). "
            "The model may be too large for this machine, or still loading."
        )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Ollama request failed: {e}")

    raw_content = response.json().get("message", {}).get("content", "")

    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        return _empty_answer(
            "The local model didn't return valid structured output. "
            "Raw response: " + raw_content[:300]
        )

    # Defensive defaults in case the model omits a field despite instructions
    return {
        "summary": parsed.get("summary", ""),
        "recommended_product": parsed.get("recommended_product"),
        "alternatives": parsed.get("alternatives", []) or [],
        "caveats": parsed.get("caveats", []) or [],
    }