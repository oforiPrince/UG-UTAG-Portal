from django import template
import json
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(is_safe=False)
def format_full_name(value):
    """Format a user object or string into the canonical display form:

    Desired format for User-like objects: "Title. Other names, Surname".
    - `title` (if present) is shown first (assumed already punctuated, but a
      trailing period is added if missing).
    - `other_name` (if present) follows the title.
    - `surname` is placed after a comma when other_name is present, or alone
      if other_name is missing.

    If a plain string is provided, return it unchanged. If the value is
    falsy, return an empty string.
    """
    if not value:
        return ''

    # If it's a model/namespace with explicit fields, build the canonical form
    try:
        title = getattr(value, 'title', None)
        other = getattr(value, 'other_name', None) or getattr(value, 'othernames', None)
        surname = getattr(value, 'surname', None) or getattr(value, 'last_name', None)

        if title or other or surname:
            parts = []
            if title:
                t = str(title).strip()
                if t and not t.endswith('.'):
                    t = t + '.'
                parts.append(t)

            name_body = ''
            if other:
                name_body = str(other).strip()

            if surname:
                if name_body:
                    name_body = f"{name_body}, {surname.strip()}"
                else:
                    name_body = surname.strip()

            if name_body:
                parts.append(name_body)

            return ' '.join([p for p in parts if p])
    except Exception:
        # Fall back to get_full_name if present
        try:
            if hasattr(value, 'get_full_name') and callable(value.get_full_name):
                return value.get_full_name()
        except Exception:
            pass

    # Final fallback: string representation
    return str(value)


@register.filter(is_safe=True)
def position_label(value):
    """Map stored executive position values to desired display labels.

    Keeps the stored value unchanged (so form submissions and comparisons
    continue to use the same canonical keys), but provides a human-friendly
    label for rendering in templates.
    """
    if not value:
        return ''
    try:
        s = str(value).strip()
        # normalize non-breaking spaces to normal spaces for matching
        s_norm = s.replace('\xa0', ' ').replace('\u00A0', ' ')
        mapping = {
            'Vice President': 'Vice-President',
            'College of Humanities Rep': 'Rep COH',
            'College of Humanities\xa0Rep': 'Rep COH',
            'College of Health Rep': 'Rep CHS',
            'College of Health\xa0Rep': 'Rep CHS',
            'College of Education Rep': 'Rep COE',
            'CBAS Rep': 'Rep CBAS',
            'CBAS\xa0Rep': 'Rep CBAS',
        }
        # Try normalized key first, then raw
        return mapping.get(s_norm, mapping.get(s, s))
    except Exception:
        return str(value)


@register.simple_tag
def get_title_choices():
    """Return the `TITLE_CHOICES` defined on the `User` model.

    Templates can use `{% get_title_choices as title_choices %}` then iterate
    over the `(value, label)` pairs so dropdowns stay in-sync with the model.
    """
    try:
        from accounts.models import User
        return getattr(User, 'TITLE_CHOICES', ())
    except Exception:
        return ()


@register.simple_tag
def title_choices_json():
    """Return `TITLE_CHOICES` as safe JSON for use in client-side scripts.

    Usage in templates:
      <script>window.TITLE_CHOICES = {% title_choices_json %};</script>
    """
    try:
        from accounts.models import User
        choices = getattr(User, 'TITLE_CHOICES', ())
        items = [{'value': v, 'label': l} for v, l in choices]
        return mark_safe(json.dumps(items))
    except Exception:
        return mark_safe('[]')
