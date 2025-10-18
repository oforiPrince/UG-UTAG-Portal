from django.core.management.base import BaseCommand

from adverts.models import Placement


DEFAULT_SIZES = {
    'top': (1200, 600),
    'hero': (1200, 600),
    'sidebar': (600, 450),
    'bottom': (900, 300),
    'footer': (1200, 200),
}


class Command(BaseCommand):
    help = 'Populate recommended_width/recommended_height for Placement records if missing. Use --dry-run to preview changes.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print changes without saving')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        placements = Placement.objects.all()
        changed = 0
        for p in placements:
            if (p.recommended_width and p.recommended_height) and (p.recommended_width > 0 and p.recommended_height > 0):
                self.stdout.write(f"{p.key}: already has {p.recommended_width}x{p.recommended_height}")
                continue
            if p.key in DEFAULT_SIZES:
                w, h = DEFAULT_SIZES[p.key]
            else:
                # If unknown placement, skip
                self.stdout.write(f"{p.key}: no default size known, skipping")
                continue
            self.stdout.write(f"{p.key}: setting {w}x{h}{' (dry-run)' if dry_run else ''}")
            if not dry_run:
                p.recommended_width = w
                p.recommended_height = h
                p.save(update_fields=['recommended_width', 'recommended_height'])
                changed += 1
        self.stdout.write(self.style.SUCCESS(f"Done. Updated {changed} placements."))
