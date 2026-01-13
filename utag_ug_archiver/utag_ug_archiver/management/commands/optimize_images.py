"""Django management command to optimize existing images."""

from django.core.management.base import BaseCommand
from django.apps import apps
from django.db.models import ImageField
from utag_ug_archiver.utils.image_optimizer import ImageOptimizer
import os


class Command(BaseCommand):
    help = 'Optimize all existing images in the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            help='Specific model to optimize (e.g., accounts.User)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        specific_model = options.get('model')
        
        self.stdout.write(self.style.SUCCESS('Starting image optimization...'))
        
        # Get all models with ImageFields
        models_to_process = []
        
        if specific_model:
            try:
                app_label, model_name = specific_model.split('.')
                model = apps.get_model(app_label, model_name)
                models_to_process.append(model)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error loading model: {e}'))
                return
        else:
            for model in apps.get_models():
                # Check if model has any ImageField
                has_image_field = any(
                    isinstance(field, ImageField)
                    for field in model._meta.get_fields()
                    if hasattr(field, 'get_internal_type')
                )
                if has_image_field:
                    models_to_process.append(model)
        
        total_optimized = 0
        total_errors = 0
        
        for model in models_to_process:
            self.stdout.write(f'\nProcessing model: {model.__name__}')
            
            # Find all ImageFields in the model
            image_fields = [
                field for field in model._meta.get_fields()
                if isinstance(field, ImageField)
            ]
            
            for obj in model.objects.all():
                for field in image_fields:
                    image_file = getattr(obj, field.name)
                    
                    if image_file and hasattr(image_file, 'path'):
                        try:
                            if os.path.exists(image_file.path):
                                if not dry_run:
                                    # Determine image type based on field name
                                    image_type = 'default'
                                    if 'profile' in field.name.lower():
                                        image_type = 'profile'
                                    elif 'executive' in field.name.lower():
                                        image_type = 'executive'
                                    elif 'event' in field.name.lower() or 'featured' in field.name.lower():
                                        image_type = 'event'
                                    elif 'news' in field.name.lower():
                                        image_type = 'news'
                                    elif 'gallery' in field.name.lower():
                                        image_type = 'gallery'
                                    
                                    # Optimize the image
                                    optimized = ImageOptimizer.optimize_image(
                                        image_file,
                                        image_type=image_type
                                    )
                                    
                                    if optimized:
                                        # Save back to the field
                                        file_name = os.path.basename(image_file.name)
                                        setattr(obj, field.name, optimized)
                                        obj.save(update_fields=[field.name])
                                        total_optimized += 1
                                        self.stdout.write(
                                            self.style.SUCCESS(
                                                f'  ✓ Optimized {model.__name__}.{obj.pk}.{field.name}'
                                            )
                                        )
                                else:
                                    self.stdout.write(
                                        f'  Would optimize {model.__name__}.{obj.pk}.{field.name}'
                                    )
                        except Exception as e:
                            total_errors += 1
                            self.stdout.write(
                                self.style.ERROR(
                                    f'  ✗ Error optimizing {model.__name__}.{obj.pk}.{field.name}: {e}'
                                )
                            )
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Optimization complete!'))
        self.stdout.write(f'  Total images optimized: {total_optimized}')
        if total_errors > 0:
            self.stdout.write(self.style.WARNING(f'  Total errors: {total_errors}'))
