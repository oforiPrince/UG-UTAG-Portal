from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.contrib.auth.mixins import PermissionRequiredMixin
from adverts.models import Ad, AdSlot, AdvertPlan, AdvertOrder
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
import datetime
import time
try:
    from PIL import Image, ImageOps
except Exception:
    Image = None
    ImageOps = None
import logging
logger = logging.getLogger(__name__)

from dashboard.models import Announcement, Notification
from utag_ug_archiver.utils.decorators import MustLogin

class AdvertsView(PermissionRequiredMixin, View):
    template_name = 'dashboard_pages/adverts.html'
    permission_required = 'adverts.view_ad'

    @method_decorator(MustLogin)
    def get(self, request):
        # Get all adverts
        adverts = Ad.objects.select_related('slot').all()
        # All defined placements to populate modal multi-select
        placements = AdSlot.objects.all()

        # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()

        # Provide available advert plans too so the modal can offer plan selection
        from adverts.models import AdvertPlan
        plans = AdvertPlan.objects.filter(status='active')

        # Prepare context
        context = {
            'adverts': adverts,
            'placements': placements,
            'plans': plans,
            'notification_count': notification_count,
            'notifications': notifications,
        }

        # Render the template
        return render(request, self.template_name, context)
    
# Note: advert plan/advertiser management removed. Use Ad and AdSlot for simple ad management.
    
class AdvertCreateView(PermissionRequiredMixin, View):
    permission_required = 'adverts.add_ad'

    @method_decorator(MustLogin)
    def post(self, request):
        logger.debug('AdvertCreateView POST by user=%s; POST keys=%s; FILES keys=%s', getattr(request, 'user', None), list(request.POST.keys()), list(request.FILES.keys()))
        
        # Simplified advert creation: accept image, html, target_url, scheduling and placements.
        image = request.FILES.get('image')
        # accept either 'start' or 'start_date' (form variations)
        start_raw = request.POST.get('start') or request.POST.get('start_date')
        end_raw = request.POST.get('end') or request.POST.get('end_date')
        # accept either legacy 'placements' (list) or new single 'slot' input
        placements = request.POST.getlist('placements')
        slot_key = request.POST.get('slot')
        title = request.POST.get('title') or ''
        # parse priority safely
        try:
            priority = int(request.POST.get('priority') or 0)
        except (ValueError, TypeError):
            priority = 0
        status = request.POST.get('status')
        target_url = request.POST.get('target_url')
        html_content = request.POST.get('html_content')

        # Parse and validate start/end datetimes. Accept full datetime or date-only inputs.
        def _parse_input_to_dt(val, default_time=None):
            if not val:
                return None
            parsed = parse_datetime(val)
            if parsed:
                return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
            # try date-only
            parsed_date = parse_date(val)
            if parsed_date:
                t = default_time if default_time is not None else datetime.time.min
                dt = datetime.datetime.combine(parsed_date, t)
                return timezone.make_aware(dt)
            return None

        start_datetime = _parse_input_to_dt(start_raw, default_time=datetime.time.min)
        end_datetime = _parse_input_to_dt(end_raw, default_time=datetime.time.max)
        if start_raw and start_datetime is None:
            messages.error(request, 'Invalid start datetime format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM[:ss].')
            logger.warning('Advert create failed: invalid start format: %s', start_raw)
            return redirect('dashboard:adverts')
        if end_raw and end_datetime is None:
            messages.error(request, 'Invalid end datetime format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM[:ss].')
            logger.warning('Advert create failed: invalid end format: %s', end_raw)
            return redirect('dashboard:adverts')

        # Validate range
        if start_datetime and end_datetime and end_datetime <= start_datetime:
            messages.error(request, 'End datetime must be after start datetime.')
            return redirect('dashboard:adverts')

        # Validate and pick slot: prefer single 'slot' input, fall back to legacy 'placements' list
        slot_obj = None
        first = None
        if slot_key:
            slot_key = slot_key.strip()
            if slot_key:
                first = slot_key
        elif placements:
            placements = [p for p in placements if p and str(p).strip()]
            if placements:
                first = placements[0]

        # Allow header, footer placements (professional academic standard)
        allowed = {'header', 'footer', 'top', 'bottom', 'sidebar'}
        if first and first in allowed:
            slot_names = {
                'header': 'Header Banner',
                'footer': 'Footer Banner',
                'top': 'Top Banner',
                'bottom': 'Bottom Banner',
                'sidebar': 'Sidebar'
            }
            slot_name = slot_names.get(first, first.capitalize())
            slot_obj, _ = AdSlot.objects.get_or_create(key=first, defaults={'name': slot_name})
        else:
            # fallback to header slot by default (most professional)
            slot_obj, _ = AdSlot.objects.get_or_create(key='header', defaults={'name': 'Header Banner', 'width': 970, 'height': 90})

        # fallback to any existing AdSlot if none provided; if still none, create a default
        if not slot_obj:
            slot_obj = AdSlot.objects.first()
            if not slot_obj:
                slot_obj = AdSlot.objects.create(key='default', name='Default', width=728, height=90)

        # Determine required image size for this slot (prefer explicit slot width/height).
        required_w, required_h = (slot_obj.width, slot_obj.height) if slot_obj else (None, None)
        # Fallback recommended sizes if slot doesn't define them (academic website standards)
        fallback_sizes = {
            'header': (970, 90),  # Standard header banner for academic sites
            'footer': (970, 90),  # Standard footer banner
            'top': (1200, 600),
            'bottom': (900, 300),
            'sidebar': (300, 250),
        }
        if (not required_w or not required_h) and slot_obj and slot_obj.key in fallback_sizes:
            required_w, required_h = fallback_sizes.get(slot_obj.key)

        # Validate/process uploaded image if provided. If dimensions differ, auto-resize/crop to required size.
        processed_image_bytes = None
        processed_image_name = None
        if image:
            # If Pillow isn't available, warn and skip processing
            if Image is None or ImageOps is None:
                messages.warning(request, 'Pillow not installed; uploaded image will be saved without resizing.')
            else:
                try:
                    # Ensure file pointer at start
                    image.seek(0)
                except Exception:
                    pass
                try:
                    pil_img = Image.open(image).convert('RGB')
                    img_w, img_h = pil_img.size
                except Exception:
                    messages.error(request, 'Uploaded file is not a valid image.')
                    return redirect('dashboard:adverts')

                # If required dimensions are known and differ, resize/crop to fit
                if required_w and required_h and (img_w != required_w or img_h != required_h):
                    try:
                        # Use ImageOps.fit to resize and crop the image to the requested size, centered
                        fitted = ImageOps.fit(pil_img, (int(required_w), int(required_h)), method=Image.LANCZOS)
                        from io import BytesIO
                        buf = BytesIO()
                        fitted.save(buf, format='JPEG', quality=90)
                        buf.seek(0)
                        processed_image_bytes = buf.read()
                        # prefer .jpg extension for processed images
                        base_name = getattr(image, 'name', '') or f'ad_{int(time.time())}'
                        if '.' in base_name:
                            base_name = base_name.rsplit('.', 1)[0]
                        processed_image_name = f"{base_name}.jpg"
                        logger.info('Auto-resized image (original %sx%s) to %sx%s for base=%s', img_w, img_h, required_w, required_h, base_name)
                    except Exception as e:
                        logger.exception('Failed to auto-resize image: %s', e)
                        messages.warning(request, 'Uploaded image could not be auto-resized; original will be saved.')

        # Server-side requirement: if this placement typically needs a desktop image and
        # neither an image nor html_content is provided, reject the create to avoid placeholders.
        placements_require_desktop = {'header', 'footer', 'top', 'hero', 'bottom'}
        image_present = bool(processed_image_bytes) or bool(image)
        if slot_obj and slot_obj.key in placements_require_desktop and not image_present and not html_content:
            messages.error(request, 'Selected placement requires an image or HTML creative. Please upload an image.')
            logger.warning('Advert create failed: missing required image for slot=%s', slot_obj.key)
            return redirect('dashboard:adverts')

        # Create advert without relying on passing file directly to create() to avoid file-pointer issues
        try:
            advert = Ad.objects.create(
                slot=slot_obj,
                title=title,
                target_url=target_url or '',
                html_content=html_content or None,
                start=start_datetime or None,
                end=end_datetime or None,
                priority=priority,
                active=(status == 'PUBLISHED') if status else True,
                created_by=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
            )
            logger.info('Advert created id=%s by user=%s', getattr(advert, 'id', None), getattr(request, 'user', None))
        except Exception as e:
            logger.exception('Failed to create Advert: %s', e)
            messages.error(request, 'Unable to create advert; please try again or contact an administrator.')
            return redirect('dashboard:adverts')
        # Attach and save image if provided (prefer processed image bytes when available)
        if image:
            from django.core.files.base import ContentFile
            try:
                if processed_image_bytes:
                    advert.image.save(processed_image_name, ContentFile(processed_image_bytes), save=True)
                    logger.info('Saved processed image for advert id=%s as %s', advert.pk, advert.image.name)
                else:
                    try:
                        image.seek(0)
                    except Exception:
                        pass
                    content = image.read()
                    image_name = getattr(image, 'name', None) or f'ad_{advert.pk}.img'
                    advert.image.save(image_name, ContentFile(content), save=True)
                    logger.info('Saved original uploaded image for advert id=%s as %s', advert.pk, advert.image.name)
            except Exception:
                # fallback: assign and save normally
                try:
                    advert.image = image
                    advert.save()
                    logger.info('Fallback saved image for advert id=%s; image.name=%s', advert.pk, getattr(advert.image, 'name', None))
                except Exception:
                    messages.warning(request, 'Unable to save uploaded image. Please check storage configuration.')
            # Verify that the image field now contains a name; if not, try saving via default_storage
            try:
                if not advert.image or not getattr(advert.image, 'name', None):
                    from django.core.files.storage import default_storage
                    try:
                        if processed_image_bytes:
                            content = processed_image_bytes
                            safe_name = f'advertisement_images/{slot_obj.key}/ad_{advert.pk}.jpg'
                        else:
                            try:
                                image.seek(0)
                            except Exception:
                                pass
                            content = image.read()
                            safe_name = f'advertisement_images/{slot_obj.key}/ad_{advert.pk}.img'
                    except Exception:
                        content = None
                        safe_name = f'advertisement_images/{slot_obj.key}/ad_{advert.pk}.img'
                    if content:
                        path = default_storage.save(safe_name, ContentFile(content))
                        advert.image.name = path
                        advert.save(update_fields=['image'])
            except Exception:
                # final fallback: log warning to user
                messages.warning(request, 'Uploaded image could not be persisted to storage.')

        # Optionally create an AdvertOrder if plan information is present in the POST.
        # The modal currently doesn't include plan selection by default; when a plan_id
        # is supplied, create an order linking user -> plan -> advert.
        plan_id = request.POST.get('plan_id') or request.POST.get('plan')
        if plan_id and hasattr(request, 'user') and request.user.is_authenticated:
            try:
                plan = AdvertPlan.objects.get(pk=plan_id)
                # Determine paid flag from POST (accept '1'/'true'/'yes')
                paid_raw = (request.POST.get('paid') or '').lower()
                paid = paid_raw in ('1', 'true', 'yes', 'on')

                # compute start_date and end_date for the order if not provided
                start_date = None
                end_date = None
                if request.POST.get('order_start_date'):
                    try:
                        start_date = parse_date(request.POST.get('order_start_date'))
                    except Exception:
                        start_date = None
                if not start_date:
                    start_date = timezone.now().date()
                if request.POST.get('order_end_date'):
                    try:
                        end_date = parse_date(request.POST.get('order_end_date'))
                    except Exception:
                        end_date = None
                if not end_date and plan.duration_in_days:
                    end_date = start_date + datetime.timedelta(days=plan.duration_in_days)

                order = AdvertOrder.objects.create(
                    user=request.user,
                    plan=plan,
                    ad=advert,
                    status='active' if paid else 'pending',
                    paid=paid,
                    start_date=start_date,
                    end_date=end_date,
                )
                # If an order exists and plan has duration, set advert start/end datetimes from order
                try:
                    # Set advert.start to provided start_datetime if present, else to start_date at midnight
                    if start_datetime:
                        advert.start = start_datetime
                    else:
                        advert.start = timezone.make_aware(datetime.datetime.combine(start_date, datetime.time.min))
                    if end_date:
                        # set advert.end to end_date at end of day
                        advert.end = timezone.make_aware(datetime.datetime.combine(end_date, datetime.time.max))
                    elif plan.duration_in_days:
                        computed_end = start_date + datetime.timedelta(days=plan.duration_in_days)
                        advert.end = timezone.make_aware(datetime.datetime.combine(computed_end, datetime.time.max))
                    advert.save()
                except Exception:
                    # Non-fatal; order exists but advert scheduling couldn't be set — continue
                    pass
                messages.info(request, f'Advert order recorded for plan "{plan.name}".')
            except AdvertPlan.DoesNotExist:
                messages.warning(request, 'Selected advert plan not found; no order created.')

        messages.success(request, 'Advert added successfully')
        return redirect('dashboard:adverts')

    
class AdvertUpdateView(PermissionRequiredMixin, View):
    permission_required = 'adverts.change_ad'

    @method_decorator(MustLogin)
    def post(self, request):
        advert_id = request.POST.get('advert_id')
        # accept either name variant
        start_raw = request.POST.get('start') or request.POST.get('start_date')
        end_raw = request.POST.get('end') or request.POST.get('end_date')
        target_url = request.POST.get('target_url')
        plan_id = request.POST.get('plan_id')
        advertiser_id = request.POST.get('advertiser_id')
        status = request.POST.get('status')
        placements = request.POST.getlist('placements')
        # note: CTA text and impressions cap fields removed from the modal/UI
        # safe parse priority
        try:
            priority = int(request.POST.get('priority') or 0)
        except (ValueError, TypeError):
            priority = 0
        advert = Ad.objects.get(id=advert_id)

        # Parse and validate provided datetimes (accept date-only or datetime)
        def _parse_input_to_dt(val, default_time=None):
            if not val:
                return None
            parsed = parse_datetime(val)
            if parsed:
                return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
            parsed_date = parse_date(val)
            if parsed_date:
                t = default_time if default_time is not None else datetime.time.min
                dt = datetime.datetime.combine(parsed_date, t)
                return timezone.make_aware(dt)
            return None

        if start_raw:
            start_dt = _parse_input_to_dt(start_raw, default_time=datetime.time.min)
            if not start_dt:
                messages.error(request, 'Invalid start datetime format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM.')
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            advert.start = start_dt

        if end_raw:
            end_dt = _parse_input_to_dt(end_raw, default_time=datetime.time.max)
            if not end_dt:
                messages.error(request, 'Invalid end datetime format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM.')
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            advert.end = end_dt

        # Update other fields using new Ad model fields
        # use explicit title field from form (cta_text removed)
        advert.title = request.POST.get('title') or advert.title
        advert.priority = int(priority)
        advert.target_url = target_url or advert.target_url
        html_content = request.POST.get('html_content')
        if html_content is not None:
            advert.html_content = html_content.strip() if html_content.strip() else None
        advert.active = (status == 'PUBLISHED') if status else advert.active
        
        # Handle image update if provided
        image = request.FILES.get('image')
        if image:
            try:
                from django.core.files.base import ContentFile
                image.seek(0)
                content = image.read()
                image_name = getattr(image, 'name', None) or f'ad_{advert.pk}.img'
                advert.image.save(image_name, ContentFile(content), save=False)
                logger.info('Updated image for advert id=%s', advert.pk)
            except Exception as e:
                logger.exception('Failed to update image for advert id=%s: %s', advert.pk, e)
                messages.warning(request, 'Image update failed, but other changes were saved.')
        
        advert.save()

        # Update slot if placements provided (or slot key via new UI)
        slot_key = request.POST.get('slot')
        chosen = None
        if slot_key:
            chosen = slot_key.strip()
        elif placements:
            chosen = placements[0]
        if chosen in {'header', 'footer', 'top', 'bottom', 'sidebar'}:
            slot_names = {
                'header': 'Header Banner',
                'footer': 'Footer Banner',
                'top': 'Top Banner',
                'bottom': 'Bottom Banner',
                'sidebar': 'Sidebar'
            }
            slot_name = slot_names.get(chosen, chosen.capitalize())
            slot_obj, _ = AdSlot.objects.get_or_create(key=chosen, defaults={'name': slot_name})
            advert.slot = slot_obj
            advert.save()

        messages.success(request, 'Advert updated successfully')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

class AdvertDetailView(PermissionRequiredMixin, View):
    permission_required = 'adverts.view_ad'
    template_name = 'dashboard_pages/advert_detail.html'
    
    @method_decorator(MustLogin)
    def get(self, request, advert_id):
        advert = Ad.objects.get(id=advert_id)
        # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        
        context = {
            'advert': advert,
            'notifications': notifications,
            'notification_count': notification_count,
            'active_menu': 'adverts'
        }
        return render(request, self.template_name, context)
    
class AdvertDeleteView(PermissionRequiredMixin, View):
    permission_required = 'adverts.delete_ad'
    @method_decorator(MustLogin)
    def get(self, request, advert_id):
        advert = Ad.objects.get(id=advert_id)
        advert.delete()
        messages.success(request, 'Advert deleted successfully')
        return redirect('dashboard:adverts')


class PlansView(PermissionRequiredMixin, View):
    """Render the advert plans page.

    Advert plans and companies were removed from the data model during the refactor.
    This view renders the existing template so the dashboard link remains functional
    and the UI can be updated independently.
    """
    template_name = 'dashboard_pages/advert_plans.html'
    permission_required = 'adverts.view_ad'

    @method_decorator(MustLogin)
    def get(self, request):
        # keep notifications for the dashboard header
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()

        # Provide existing advert plans (if any)
        from adverts.models import AdvertPlan
        plans = AdvertPlan.objects.all()

        context = {
            'notification_count': notification_count,
            'notifications': notifications,
            'plans': plans,
        }
        return render(request, self.template_name, context)


class AdvertPlanCreateView(PermissionRequiredMixin, View):
    permission_required = 'dashboard.add_advertplan'

    @method_decorator(MustLogin)
    def post(self, request):
        name = request.POST.get('name')
        description = request.POST.get('description')
        try:
            price = float(request.POST.get('price') or 0)
        except (ValueError, TypeError):
            price = 0
        try:
            duration = int(request.POST.get('duration_in_days') or 30)
        except (ValueError, TypeError):
            duration = 30
        status = request.POST.get('status') or 'active'

        from adverts.models import AdvertPlan
        AdvertPlan.objects.create(
            name=name,
            description=description or '',
            price=price,
            duration_in_days=duration,
            status=status,
        )
        messages.success(request, 'Advert plan created.')
        return redirect('dashboard:plans')


class AdvertPlanUpdateView(PermissionRequiredMixin, View):
    permission_required = 'dashboard.change_advertplan'

    @method_decorator(MustLogin)
    def post(self, request):
        plan_id = request.POST.get('plan_id')
        from adverts.models import AdvertPlan
        plan = AdvertPlan.objects.get(id=plan_id)
        plan.name = request.POST.get('name') or plan.name
        plan.description = request.POST.get('description') or plan.description
        try:
            plan.price = float(request.POST.get('price') or plan.price)
        except (ValueError, TypeError):
            pass
        try:
            plan.duration_in_days = int(request.POST.get('duration_in_days') or plan.duration_in_days)
        except (ValueError, TypeError):
            pass
        plan.status = request.POST.get('status') or plan.status
        plan.save()
        messages.success(request, 'Advert plan updated.')
        return redirect('dashboard:plans')


class AdvertPlanDeleteView(PermissionRequiredMixin, View):
    permission_required = 'dashboard.delete_advertplan'

    @method_decorator(MustLogin)
    def get(self, request, plan_id):
        from adverts.models import AdvertPlan
        plan = AdvertPlan.objects.get(id=plan_id)
        plan.delete()
        messages.success(request, 'Advert plan deleted.')
        return redirect('dashboard:plans')
    

class AdvertOrdersView(PermissionRequiredMixin, View):
    permission_required = 'adverts.view_ad'
    template_name = 'dashboard_pages/advert_orders.html'

    @method_decorator(MustLogin)
    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        orders = AdvertOrder.objects.select_related('user', 'plan', 'ad').order_by('-created_at')
        context = {
            'notification_count': notification_count,
            'notifications': notifications,
            'orders': orders,
        }
        return render(request, self.template_name, context)
