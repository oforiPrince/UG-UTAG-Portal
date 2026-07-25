from urllib.parse import urlsplit

import nh3

ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "em",
    "h2",
    "h3",
    "h4",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "s",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
}
ALLOWED_ATTRIBUTES = {
    # nh3 owns `rel` when link_rel is configured; allowing untrusted input to
    # provide it is both unsafe and rejected by recent ammonia releases.
    "a": {"href", "title", "target"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}


def sanitize_html(value: str | None) -> str:
    if not value:
        return ""
    return nh3.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"https", "http", "mailto"},
        link_rel="noopener noreferrer",
    )


def validate_social_links(value: dict[str, str]) -> dict[str, str]:
    allowed = {"facebook", "linkedin", "twitter", "website", "x"}
    if len(value) > len(allowed):
        raise ValueError("Too many social profile links")

    cleaned: dict[str, str] = {}
    for raw_key, raw_url in value.items():
        key = raw_key.strip().lower()
        url = raw_url.strip()
        if key not in allowed:
            raise ValueError(f"Unsupported social profile: {raw_key}")
        if not url:
            continue
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or len(url) > 1_000:
            raise ValueError(f"Enter a valid website address for {key}")
        cleaned[key] = url
    return cleaned
