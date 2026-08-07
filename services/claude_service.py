import os
import re

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-6"

_client = None


def get_client():
    """
    Lazily create the Anthropic client so importing this module
    doesn't fail just because the API key isn't set yet (e.g. during
    tests that don't need it).
    """
    global _client

    if _client is None:
        if not CLAUDE_API_KEY:
            raise RuntimeError(
                "CLAUDE_API_KEY is not set in .env - Claude features "
                "won't work without it."
            )
        _client = Anthropic(api_key=CLAUDE_API_KEY)

    return _client


def _format_products_for_prompt(products, max_products=40):
    """
    Turns a list of ProductDB rows into a compact, readable block of
    text for the prompt. Capped at max_products to keep token usage
    and cost sane - if there are more matches than that, only the
    cheapest ones are included, since price is usually what matters
    most for comparison questions.
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


ANSWER_TOOL = {
    "name": "provide_shopping_answer",
    "description": (
        "Provide a structured answer to the user's shopping question, "
        "grounded only in the product listings provided."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "A short 1-2 sentence plain-text answer to the question.",
            },
            "recommended_product": {
                "type": ["object", "null"],
                "description": (
                    "The single best-matching product for the question. "
                    "Null if none of the listings answer the question."
                ),
                "properties": {
                    "name": {"type": "string"},
                    "website": {"type": "string"},
                    "price": {"type": "number"},
                    "rating": {"type": ["number", "null"]},
                    "reviews": {"type": ["integer", "null"]},
                    "url": {"type": "string"},
                },
                "required": ["name", "website", "price", "url"],
            },
            "alternatives": {
                "type": "array",
                "description": "Up to 3 other relevant products worth considering.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "website": {"type": "string"},
                        "price": {"type": "number"},
                        "rating": {"type": ["number", "null"]},
                        "reviews": {"type": ["integer", "null"]},
                        "url": {"type": "string"},
                        "why": {
                            "type": "string",
                            "description": "Short reason this is worth considering.",
                        },
                    },
                    "required": ["name", "website", "price", "url"],
                },
            },
            "caveats": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Important warnings, e.g. 'renewed/used device', "
                    "'low rating', 'price may be outdated'."
                ),
            },
        },
        "required": ["summary", "recommended_product", "alternatives", "caveats"],
    },
}


def ask_about_products(question, products):
    """
    Sends a natural-language question about a set of already-fetched
    products to Claude, and returns a structured dict answer (not
    freeform markdown text) - see ANSWER_TOOL above for the shape.

    `products` should be a list of ProductDB rows (or anything with
    .website .name .price .rating .reviews .product_url attributes).
    """

    if not products:
        return {
            "summary": "I couldn't find any matching products in the database to answer that question.",
            "recommended_product": None,
            "alternatives": [],
            "caveats": [],
        }

    product_block = _format_products_for_prompt(products)

    system_prompt = (
        "You are a helpful shopping assistant for a price-comparison app "
        "that tracks phone listings from Amazon.sa and Noon.com. "
        "You'll be given a list of real product listings (already scraped, "
        "with real prices in SAR) and a user question. "
        "Answer using ONLY the listings provided - never invent products, "
        "prices, or specs that aren't in the list. "
        "If the listings don't contain enough information to answer "
        "confidently, say so in the summary and leave recommended_product null. "
        "Always call the provide_shopping_answer tool with your answer."
    )

    user_message = (
        f"Here are the matching product listings:\n\n{product_block}\n\n"
        f"Question: {question}"
    )

    client = get_client()

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        system=system_prompt,
        tools=[ANSWER_TOOL],
        tool_choice={"type": "tool", "name": "provide_shopping_answer"},
        messages=[
            {"role": "user", "content": user_message},
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "provide_shopping_answer":
            return block.input

    # Shouldn't happen since tool_choice forces the tool, but just in case:
    return {
        "summary": "Claude didn't return a structured answer. Please try again.",
        "recommended_product": None,
        "alternatives": [],
        "caveats": [],
    }


COMPARISON_TOOL = {
    "name": "provide_price_comparison",
    "description": (
        "Match the same real-world phone across the Amazon and Noon "
        "listings provided, and report the price difference for each match."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "matches": {
                "type": "array",
                "description": (
                    "Products that appear to be the SAME phone "
                    "(same model, storage, color) listed on both websites."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "model_description": {
                            "type": "string",
                            "description": "e.g. 'iPhone 15 128GB Blue'",
                        },
                        "amazon": {
                            "type": ["object", "null"],
                            "properties": {
                                "name": {"type": "string"},
                                "price": {"type": "number"},
                                "url": {"type": "string"},
                            },
                            "required": ["name", "price", "url"],
                        },
                        "noon": {
                            "type": ["object", "null"],
                            "properties": {
                                "name": {"type": "string"},
                                "price": {"type": "number"},
                                "url": {"type": "string"},
                            },
                            "required": ["name", "price", "url"],
                        },
                        "cheaper_website": {
                            "type": "string",
                            "enum": ["Amazon", "Noon", "Tie"],
                            "description": (
                                "'Amazon' or 'Noon' if one is strictly cheaper, "
                                "or 'Tie' if both prices are exactly equal."
                            ),
                        },
                        "price_difference": {
                            "type": "number",
                            "description": "Absolute SAR difference between the two prices.",
                        },
                    },
                    "required": [
                        "model_description",
                        "amazon",
                        "noon",
                        "cheaper_website",
                        "price_difference",
                    ],
                },
            },
            "notes": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Short, individual plain-text points explaining why "
                    "matches were or weren't found - one specific reason per "
                    "item, e.g. 'iPhone 15 Pro Max: Amazon lists White "
                    "Titanium, Noon only has Black Titanium - no match'. "
                    "No markdown formatting (no asterisks/bold). Empty list "
                    "if there's nothing worth explaining."
                ),
            },
        },
        "required": ["matches", "notes"],
    },
}


STORAGE_PATTERN = re.compile(r"(\d+)\s*(GB|TB)", re.IGNORECASE)

COLOR_WORDS = [
    "black", "white", "blue", "silver", "gold", "purple", "green",
    "orange", "pink", "graphite", "midnight", "starlight", "desert",
    "cosmic", "sage", "rose", "red", "yellow", "natural", "grey", "gray",
]
# Note: "titanium" is deliberately excluded - it's a finish modifier that
# appears on multiple different iPhone Pro colors (Natural Titanium, Blue
# Titanium, White Titanium, Black Titanium), so including it caused
# different colors to look like a match just because both said "Titanium".


USED_CONDITION_WORDS = [
    "refurbished", "renewed", "certified pre owned", "certified pre-owned",
    "pre-owned", "pre owned", "used",
]


def _extract_storage(name):
    if not name:
        return None
    match = STORAGE_PATTERN.search(name)
    if not match:
        return None
    size, unit = match.groups()
    return f"{size.lower()}{unit.lower()}"


def _extract_colors(name):
    if not name:
        return set()
    lowered = name.lower()
    return {word for word in COLOR_WORDS if word in lowered}


def _is_used_condition(name):
    if not name:
        return False
    lowered = name.lower()
    return any(word in lowered for word in USED_CONDITION_WORDS)


def _is_plausible_match(amazon_name, noon_name):
    """
    Deterministic sanity check on top of Claude's matching, since
    exact storage/color/condition mismatches are cheap to catch in
    code and shouldn't be left entirely to the model's judgment.

    Only rejects a match when there's a CLEAR contradiction (both
    sides name a storage size and they differ, both sides name colors
    and share none, or one side is explicitly refurbished/renewed/used
    while the other isn't). If either side is ambiguous, we don't
    block the match - that avoids being overly aggressive.
    """

    amazon_storage = _extract_storage(amazon_name)
    noon_storage = _extract_storage(noon_name)
    if amazon_storage and noon_storage and amazon_storage != noon_storage:
        return False, f"storage mismatch ({amazon_storage} vs {noon_storage})"

    amazon_colors = _extract_colors(amazon_name)
    noon_colors = _extract_colors(noon_name)
    if amazon_colors and noon_colors and not (amazon_colors & noon_colors):
        return False, f"color mismatch ({amazon_colors} vs {noon_colors})"

    amazon_used = _is_used_condition(amazon_name)
    noon_used = _is_used_condition(noon_name)
    if amazon_used != noon_used:
        return False, (
            f"condition mismatch (one is refurbished/renewed/used, the other isn't: "
            f"amazon_used={amazon_used}, noon_used={noon_used})"
        )

    return True, None


def compare_prices_across_sites(query, products):
    """
    Finds the same phone model listed on both Amazon and Noon within
    `products`, and returns price-difference comparisons for each match.

    Unlike ask_about_products, this doesn't answer an open-ended
    question - it specifically looks for cross-website matches for
    the same real-world product.
    """

    amazon_products = [p for p in products if p.website == "Amazon"]
    noon_products = [p for p in products if p.website == "Noon"]

    if not amazon_products or not noon_products:
        return {
            "matches": [],
            "notes": [
                "Need listings from both Amazon and Noon to compare prices - "
                f"found {len(amazon_products)} Amazon and {len(noon_products)} "
                "Noon listing(s) for this query."
            ],
        }

    product_block = _format_products_for_prompt(products, max_products=60)

    system_prompt = (
        "You compare phone prices between Amazon.sa and Noon.com listings. "
        "You'll be given real scraped listings from both sites for the same "
        "search. Identify listings that refer to the SAME real-world phone - "
        "same model, SAME storage size, SAME color, and SAME condition. "
        "A refurbished/renewed/used listing is NOT equivalent to a new one, "
        "even if everything else matches - do not treat them as the same "
        "product. Storage, color, and condition must all match; if any of "
        "them differ or you're not sure, do NOT include it as a match. "
        "Being conservative and returning fewer matches is much better than "
        "forcing an incorrect match. For each match, report both prices. If "
        "both prices are exactly equal, set cheaper_website to 'Tie' rather "
        "than arbitrarily picking one side. Use ONLY the listings provided - "
        "never invent products, prices, or urls. For the notes field, write "
        "each reason as its own short plain-text list item (no markdown, no "
        "asterisks, no bold) rather than one long paragraph. Always call the "
        "provide_price_comparison tool with your answer."
    )

    user_message = (
        f"Search query: {query}\n\n"
        f"Listings:\n\n{product_block}\n\n"
        "Find matching phones listed on both Amazon and Noon, and compare their prices."
    )

    client = get_client()

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=system_prompt,
        tools=[COMPARISON_TOOL],
        tool_choice={"type": "tool", "name": "provide_price_comparison"},
        messages=[
            {"role": "user", "content": user_message},
        ],
    )

    result = None
    for block in response.content:
        if block.type == "tool_use" and block.name == "provide_price_comparison":
            result = block.input
            break

    if result is None:
        return {
            "matches": [],
            "notes": ["Claude didn't return a structured comparison. Please try again."],
        }

    # --- Deterministic post-processing ---
    # Never trust the model's own arithmetic or judgment where code can
    # verify it directly: recompute price_difference/cheaper_website,
    # and drop any match with a clear storage/color/condition contradiction.
    verified_matches = []
    drop_reasons = []

    for match in result.get("matches", []):
        amazon = match.get("amazon")
        noon = match.get("noon")

        if not amazon or not noon:
            continue

        plausible, reason = _is_plausible_match(amazon.get("name"), noon.get("name"))
        if not plausible:
            model_desc = match.get("model_description", "a candidate match")
            drop_reasons.append(f"{model_desc}: dropped ({reason})")
            continue

        amazon_price = amazon.get("price")
        noon_price = noon.get("price")

        if amazon_price is None or noon_price is None:
            continue

        if amazon_price == noon_price:
            match["cheaper_website"] = "Tie"
        elif amazon_price < noon_price:
            match["cheaper_website"] = "Amazon"
        else:
            match["cheaper_website"] = "Noon"

        match["price_difference"] = round(abs(amazon_price - noon_price), 2)

        verified_matches.append(match)

    notes = result.get("notes", [])
    if isinstance(notes, str):  # defensive, in case the model ignores the array type
        notes = [notes] if notes else []
    notes = list(notes) + drop_reasons

    return {
        "matches": verified_matches,
        "notes": notes,
    }


RECOMMENDATION_TOOL = {
    "name": "provide_recommendation",
    "description": (
        "Recommend the best product from a pre-filtered list of candidates "
        "that already match the user's stated preferences (budget, rating, "
        "storage, etc.)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "A short 1-2 sentence explanation of the recommendation.",
            },
            "recommended_product": {
                "type": ["object", "null"],
                "description": "The single best candidate. Null if none of the candidates are a good fit.",
                "properties": {
                    "name": {"type": "string"},
                    "website": {"type": "string"},
                    "price": {"type": "number"},
                    "rating": {"type": ["number", "null"]},
                    "reviews": {"type": ["integer", "null"]},
                    "url": {"type": "string"},
                },
                "required": ["name", "website", "price", "url"],
            },
            "alternatives": {
                "type": "array",
                "description": "Up to 3 other good candidates worth considering.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "website": {"type": "string"},
                        "price": {"type": "number"},
                        "rating": {"type": ["number", "null"]},
                        "reviews": {"type": ["integer", "null"]},
                        "url": {"type": "string"},
                        "why": {"type": "string"},
                    },
                    "required": ["name", "website", "price", "url"],
                },
            },
            "caveats": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["summary", "recommended_product", "alternatives", "caveats"],
    },
}


def recommend_product(preferences_description, candidates):
    """
    Picks and explains the best recommendation from `candidates` - a list
    of ProductDB rows that have ALREADY been filtered deterministically
    (in SQL) to match the user's budget/rating/storage/etc. Claude's job
    here is only to pick the best one and explain why, NOT to apply the
    filters itself - that keeps hard constraints (like budget) reliable
    instead of dependent on the model's judgment.

    `preferences_description` is a short plain-text summary of what was
    filtered on, e.g. "budget <= 3000 SAR, min rating 4.0, storage 128GB".
    """

    if not candidates:
        return {
            "summary": "No products matched those filters.",
            "recommended_product": None,
            "alternatives": [],
            "caveats": [],
        }

    product_block = _format_products_for_prompt(candidates, max_products=40)

    system_prompt = (
        "You are a shopping assistant for a price-comparison app. "
        "You'll be given a list of phone listings that have ALREADY been "
        "filtered to match the user's stated preferences - every listing "
        "given to you already satisfies their budget/rating/storage "
        "requirements. Your job is only to pick the single best one "
        "(considering price, rating, and review count together) and "
        "explain briefly why, plus suggest up to 3 alternatives. "
        "Use ONLY the listings provided - never invent products, prices, "
        "or urls. Always call the provide_recommendation tool."
    )

    user_message = (
        f"User's preferences: {preferences_description}\n\n"
        f"Matching candidates (already filtered):\n\n{product_block}\n\n"
        "Recommend the best one."
    )

    client = get_client()

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        system=system_prompt,
        tools=[RECOMMENDATION_TOOL],
        tool_choice={"type": "tool", "name": "provide_recommendation"},
        messages=[
            {"role": "user", "content": user_message},
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "provide_recommendation":
            return block.input

    return {
        "summary": "Claude didn't return a structured recommendation. Please try again.",
        "recommended_product": None,
        "alternatives": [],
        "caveats": [],
    }