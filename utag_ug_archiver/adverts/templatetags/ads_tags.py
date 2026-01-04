from django import template
from django.template.loader import render_to_string
from ..models import AdSlot

register = template.Library()


@register.inclusion_tag('adverts/ad_snippet.html', takes_context=True)
def render_ad_slot(context, slot_key):
    """Fetch the highest priority live ad for the slot_key and render snippet.

    Usage in template: {% render_ad_slot 'sidebar_300x250' %}
    """
    try:
        slot = AdSlot.objects.get(key=slot_key)
    except AdSlot.DoesNotExist:
        return {'ad': None}

    ads = slot.ads.all()
    # filter live
    live_ads = [a for a in ads if a.is_live()]
    if not live_ads:
        return {'ad': None}
    # choose highest priority first; ordering in model ensures this but keep safe
    ad = sorted(live_ads, key=lambda a: (-a.priority, -a.created_at.timestamp()))[0]
    # register an impression asynchronously would be ideal; we increment when template renders
    try:
        ad.impression()
    except Exception:
        # don't break page if DB update fails
        pass

    return {'ad': ad, 'request': context.get('request')}
