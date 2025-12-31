from django.shortcuts import  get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DeleteView, View
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages
from django.db.models import Max
from gallery.models import Gallery, Image
from gallery.forms import GalleryForm, ImageUploadForm
from dashboard.models import Notification
from utag_ug_archiver.utils.decorators import MustLogin
import logging

logger = logging.getLogger(__name__)

class GalleryListView(PermissionRequiredMixin, ListView):
    model = Gallery
    template_name = 'dashboard_pages/gallery.html'
    context_object_name = 'galleries'
    permission_required = 'gallery.view_gallery'
    paginate_by = 10

    @method_decorator(MustLogin)
    def get(self, request, *args, **kwargs):
        # Get notifications for header
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        
        # Optimize queryset with prefetch_related and only fetch needed fields
        galleries = Gallery.objects.prefetch_related(
            'images'
        ).only(
            'id', 'title', 'description', 'created_at', 'is_active'
        ).order_by('-created_at')
        
        context = {
            'galleries': galleries,
            'notification_count': notification_count,
            'notifications': notifications,
        }
        return self.render_to_response(context)

class GalleryCreateView(PermissionRequiredMixin, CreateView):
    model = Gallery
    form_class = GalleryForm
    permission_required = 'gallery.add_gallery'
    success_url = reverse_lazy('dashboard:gallery')

    @method_decorator(MustLogin)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'message': 'Gallery added successfully!'}, status=201)
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'errors': form.errors}, status=400)
        return response

@method_decorator(csrf_exempt, name='dispatch')
class ImageUploadView(PermissionRequiredMixin, CreateView):
    model = Image
    form_class = ImageUploadForm
    permission_required = 'gallery.add_image'

    @method_decorator(MustLogin)
    def post(self, request, *args, **kwargs):
        gallery_id = request.POST.get('gallery_id')
        if not gallery_id:
            return JsonResponse({'errors': {'gallery_id': ['Gallery ID is required']}}, status=400)
        
        gallery = get_object_or_404(Gallery, id=gallery_id)
        form = self.form_class(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                image = form.save(commit=False)
                image.gallery = gallery
                # Set order to be last in gallery
                max_order = Image.objects.filter(gallery=gallery).aggregate(
                    max_order=Max('order')
                )['max_order'] or 0
                image.order = max_order + 1
                image.save()
                
                # Thumbnail and optimization are handled in model's save() method
                logger.info(f'Image {image.id} uploaded to gallery {gallery.id}')
                
                return JsonResponse({
                    'message': 'Image uploaded and optimized successfully!',
                    'image_id': image.id,
                    'thumbnail_url': image.get_thumbnail_url(),
                    'image_url': image.get_absolute_url()
                }, status=201)
            except Exception as e:
                logger.exception(f'Error uploading image: {e}')
                return JsonResponse({'errors': {'__all__': [f'Error processing image: {str(e)}']}}, status=500)
        else:
            return JsonResponse({'errors': form.errors}, status=400)

@method_decorator(MustLogin, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class DeleteGalleryView(PermissionRequiredMixin, View):
    permission_required = 'gallery.delete_gallery'
    
    def delete(self, request, gallery_id):
        """Delete a gallery and its associated images."""
        gallery = get_object_or_404(Gallery, id=gallery_id)
        gallery.delete()
        return JsonResponse({'message': 'Gallery deleted successfully!'}, status=200)
    
    def post(self, request, gallery_id):
        """Handle POST requests for deletion (for compatibility)."""
        return self.delete(request, gallery_id)
    
@method_decorator(csrf_exempt, name='dispatch')
class EditGalleryView(PermissionRequiredMixin, View):
    """
    Handle retrieving and updating gallery details.
    """
    permission_required = 'gallery.change_gallery'

    @method_decorator(MustLogin)
    def get(self, request, gallery_id):
        """
        Retrieve gallery details, including images.
        """
        gallery = get_object_or_404(Gallery, id=gallery_id)
        images = [
            {
                'id': image.id,
                'image': image.get_absolute_url(),
                'thumbnail': image.get_thumbnail_url(),
                'caption': image.caption,
                'uploaded_at': image.uploaded_at.isoformat(),
            }
            for image in gallery.images.all().order_by('order', '-uploaded_at')
        ]
        return JsonResponse({
            'gallery': {
                'id': gallery.id,
                'title': gallery.title,
                'description': gallery.description,
                'is_active': gallery.is_active,
                'images': images,
            }
        }, status=200)
        
    @method_decorator(MustLogin)
    def post(self, request, gallery_id):
        """
        Update gallery details.
        """
        gallery = get_object_or_404(Gallery, id=gallery_id)
        form = GalleryForm(request.POST, instance=gallery)
        if form.is_valid():
            form.save()
            return JsonResponse({'message': 'Gallery updated successfully!'}, status=200)
        else:
            return JsonResponse({'errors': form.errors}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class DeleteImageView(PermissionRequiredMixin, View):
    """
    Handle deleting a specific image.
    """
    permission_required = 'gallery.delete_image'

    @method_decorator(MustLogin)
    def delete(self, request, image_id):
        """
        Delete an image by ID.
        """
        image = get_object_or_404(Image, id=image_id)
        image.delete()
        logger.info(f'Image {image_id} deleted by user {request.user.id}')
        return JsonResponse({'message': 'Image deleted successfully!'}, status=200)
    
    @method_decorator(MustLogin)
    def post(self, request, image_id):
        """Handle POST requests for deletion (for compatibility)."""
        return self.delete(request, image_id)
    
@method_decorator(csrf_exempt, name='dispatch')
class ViewGalleryDetails(PermissionRequiredMixin, View):
    """
    Class-based view to handle retrieving gallery details, including associated images.
    """
    permission_required = 'gallery.view_gallery'

    @method_decorator(MustLogin)
    def get(self, request, gallery_id):
        # Retrieve the gallery or return a 404 if not found
        gallery = get_object_or_404(Gallery, id=gallery_id)

        # Prepare the images data
        images = [
            {
                'id': image.id,
                'image': image.get_absolute_url(),
                'thumbnail': image.get_thumbnail_url(),
                'caption': image.caption,
            }
            for image in gallery.images.all().order_by('order', '-uploaded_at')
        ]

        # Prepare the gallery data
        data = {
            'gallery': {
                'id': gallery.id,
                'title': gallery.title,
                'description': gallery.description or 'No description available.',
                'is_active': gallery.is_active,
                'images': images,
            }
        }
        return JsonResponse(data, status=200)