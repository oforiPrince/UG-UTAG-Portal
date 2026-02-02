from django import template

register = template.Library()


@register.filter
def startswith(value, prefix):
    """Check if a string starts with a given prefix."""
    if value is None:
        return False
    return str(value).startswith(str(prefix))


@register.filter
def is_image(content_type):
    """Check if content type is an image."""
    if not content_type:
        return False
    return str(content_type).startswith('image/')
