from django.shortcuts import  get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DeleteView, View
from django.utils.decorators import method_decorator
from gallery.models import Gallery, Image
from gallery.forms import GalleryForm, ImageUploadForm

class GalleryListView(ListView):
    model = Gallery
    template_name = 'dashboard_pages/gallery.html'
    context_object_name = 'galleries'
    paginate_by = 10

    def get_queryset(self):
        return Gallery.objects.prefetch_related('images').order_by('-created_at')

class GalleryCreateView(CreateView):
    model = Gallery
    form_class = GalleryForm

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.is_ajax():
            return JsonResponse({'message': 'Gallery added successfully!'}, status=201)
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.is_ajax():
            return JsonResponse({'errors': form.errors}, status=400)
        return response

@method_decorator(csrf_exempt, name='dispatch')
class ImageUploadView(CreateView):
    model = Image
    form_class = ImageUploadForm

    def form_valid(self, form):
        gallery_id = self.request.POST.get('gallery_id')
        gallery = get_object_or_404(Gallery, id=gallery_id)
        form.instance.gallery = gallery
        response = super().form_valid(form)
        if self.request.is_ajax():
            return JsonResponse({'message': 'Image uploaded successfully!'}, status=201)
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.is_ajax():
            return JsonResponse({'errors': form.errors}, status=400)
        return response

class GalleryDeleteView(DeleteView):
    model = Gallery
    template_name = 'dashboard_pages/gallery_confirm_delete.html'  # Create a separate confirmation template if needed

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if self.request.is_ajax():
            return JsonResponse({'message': 'Gallery deleted successfully!'}, status=200)
        return redirect(self.success_url)
    
@method_decorator(csrf_exempt, name='dispatch')
class EditGalleryView(View):
    """
    Handle retrieving and updating gallery details.
    """

    def get(self, request, gallery_id):
        """
        Retrieve gallery details, including images.
        """
        gallery = get_object_or_404(Gallery, id=gallery_id)
        images = [
            {
                'id': image.id,
                'image': image.get_absolute_url(),
                'caption': image.caption,
            }
            for image in gallery.images.all()
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
class DeleteImageView(View):
    """
    Handle deleting a specific image.
    """

    def delete(self, request, image_id):
        """
        Delete an image by ID.
        """
        image = get_object_or_404(Image, id=image_id)
        image.delete()
        return JsonResponse({'message': 'Image deleted successfully!'}, status=200)
    
@method_decorator(csrf_exempt, name='dispatch')
class ViewGalleryDetails(View):
    """
    Class-based view to handle retrieving gallery details, including associated images.
    """

    def get(self, request, gallery_id):
        # Retrieve the gallery or return a 404 if not found
        gallery = get_object_or_404(Gallery, id=gallery_id)

        # Prepare the images data
        images = [
            {
                'id': image.id,
                'image': image.get_absolute_url(),
                'caption': image.caption,
            }
            for image in gallery.images.all()
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