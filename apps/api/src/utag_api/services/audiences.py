def includes_general_public(audiences: list[dict[str, str]]) -> bool:
    return any(audience.get("type") == "general_public" for audience in audiences)
