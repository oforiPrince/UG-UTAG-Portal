"""Template tags for optimized image loading."""

from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape

register = template.Library()

# Transparent 1x1 GIF as data URI (tiny placeholder that doesn't cause broken image)
TRANSPARENT_PLACEHOLDER = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'

# Low-quality inline SVG placeholder with aspect ratio preservation
def get_svg_placeholder(width=400, height=300, bg_color='#f0f0f0'):
    """Generate an inline SVG placeholder with loading animation."""
    return f"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'%3E%3Crect fill='{bg_color.replace('#', '%23')}' width='{width}' height='{height}'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='sans-serif' font-size='14' fill='%23999'%3ELoading...%3C/text%3E%3C/svg%3E"


@register.simple_tag
def lazy_img(src, alt='', css_class='', image_type='', width='', height=''):
    """
    Render an img tag with progressive lazy loading.
    
    This uses native browser lazy loading (loading="lazy") as the primary method,
    which is supported by all modern browsers. The data-src attribute is kept
    for enhanced lazy loading via JavaScript if available.
    
    Usage:
        {% lazy_img image.url "Alt text" "img-fluid" %}
        {% lazy_img profile_pic.url "Profile" "rounded-circle" "profile" %}
        {% lazy_img event.image.url "Event" "img-fluid" "event" width="400" height="300" %}
    
    image_type options: 'profile', 'executive', 'event', 'gallery', 'news'
    """
    # Validate src - if empty or None, use placeholder
    if not src:
        src = TRANSPARENT_PLACEHOLDER
    
    # Build attributes list
    attrs = []
    
    # CSS classes - include lazyload for JS enhancement
    base_classes = f"{escape(css_class)} lazyload" if css_class else "lazyload"
    attrs.append(f'class="{base_classes}"')
    
    # Alt text is required for accessibility
    attrs.append(f'alt="{escape(alt)}"' if alt else 'alt=""')
    
    # Dimensions for preventing layout shift
    if width:
        attrs.append(f'width="{escape(str(width))}"')
    if height:
        attrs.append(f'height="{escape(str(height))}"')
    
    # IMPORTANT: Set src to actual image for native lazy loading
    # This ensures images load even if JavaScript fails
    attrs.append(f'src="{escape(src)}"')
    
    # data-src for enhanced JS lazy loading (optional enhancement)
    attrs.append(f'data-src="{escape(src)}"')
    
    # Native lazy loading - works without JavaScript
    attrs.append('loading="lazy"')
    
    # Decode async for better performance
    attrs.append('decoding="async"')
    
    # Combine all attributes
    attrs_str = ' '.join(attrs)
    
    return mark_safe(f'<img {attrs_str}>')


@register.simple_tag
def progressive_img(src, alt='', css_class='', width='', height=''):
    """
    Render an image with progressive loading using a placeholder.
    The placeholder is shown initially while the full image loads in the background.
    
    Usage:
        {% progressive_img image.url "Description" "img-fluid" "400" "300" %}
    """
    if not src:
        src = TRANSPARENT_PLACEHOLDER
    
    # Generate placeholder based on dimensions
    w = int(width) if width else 400
    h = int(height) if height else 300
    placeholder = get_svg_placeholder(w, h)
    
    attrs = []
    base_classes = f"{escape(css_class)} progressive-img" if css_class else "progressive-img"
    attrs.append(f'class="{base_classes}"')
    attrs.append(f'alt="{escape(alt)}"' if alt else 'alt=""')
    
    if width:
        attrs.append(f'width="{escape(str(width))}"')
    if height:
        attrs.append(f'height="{escape(str(height))}"')
    
    # Start with placeholder, load actual via JS
    attrs.append(f'src="{placeholder}"')
    attrs.append(f'data-src="{escape(src)}"')
    attrs.append('loading="lazy"')
    attrs.append('decoding="async"')
    
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
