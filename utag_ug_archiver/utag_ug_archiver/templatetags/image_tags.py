"""Template tags for optimized image loading."""

from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape

register = template.Library()


@register.simple_tag
def lazy_img(src, alt='', css_class='', width='', height='', placeholder='/static/dashboard/assets/images/placeholder.png'):
    """
    Render an img tag with lazy loading enabled.
    
    Usage:
        {% lazy_img image.url "Alt text" "img-fluid" %}
        {% lazy_img profile_pic.url alt="Profile" css_class="rounded-circle" width="200" height="200" %}
    """
    # Build attributes
    attrs = []
    
    if css_class:
        attrs.append(f'class="{escape(css_class)} lazyload"')
    else:
        attrs.append('class="lazyload"')
    
    if alt:
        attrs.append(f'alt="{escape(alt)}"')
    else:
        attrs.append('alt=""')
    
    if width:
        attrs.append(f'width="{escape(str(width))}"')
    
    if height:
        attrs.append(f'height="{escape(str(height))}"')
    
    # Use data-src for lazy loading
    attrs.append(f'data-src="{escape(src)}"')
    
    # Add low-quality placeholder
    attrs.append(f'src="{escape(placeholder)}"')
    
    # Add loading attribute for native lazy loading
    attrs.append('loading="lazy"')
    
    # Combine all attributes
    attrs_str = ' '.join(attrs)
    
    return mark_safe(f'<img {attrs_str}>')


@register.filter
def img_url(image_field, default='/static/dashboard/assets/images/users/profile.png'):
    """
    Safely get image URL with fallback.
    
    Usage:
        {{ profile_pic|img_url }}
        {{ event.featured_image|img_url:"/static/default-event.png" }}
    """
    if not image_field:
        return default
    
    try:
        return image_field.url
    except (ValueError, AttributeError):
        return default


@register.inclusion_tag('includes/lazy_image.html')
def lazy_image(src, alt='', css_class='img-fluid', width='', height=''):
    """
    Render a lazy-loaded image using an inclusion template.
    
    Usage:
        {% lazy_image event.featured_image.url "Event photo" "img-fluid rounded" %}
    """
    return {
        'src': src,
        'alt': alt,
        'css_class': css_class,
        'width': width,
        'height': height,
    }


@register.simple_tag
def img_srcset(image_field, sizes=''):
    """
    Generate responsive image srcset for different screen sizes.
    
    Usage:
        {% img_srcset event.featured_image "1200w, 800w, 400w" %}
    """
    # This is a placeholder - implement based on your thumbnail generation
    if not image_field:
        return ''
    
    try:
        return image_field.url
    except (ValueError, AttributeError):
        return ''
