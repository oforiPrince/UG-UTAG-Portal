from django.core.management.base import BaseCommand

from adverts.models import AdSlot


DEFAULT_SIZES = {
    'top': (1200, 600),
    'hero': (1200, 600),
    'sidebar': (600, 450),
    'bottom': (900, 300),
    'footer': (1200, 200),
}


class Command(BaseCommand):
    help = 'Populate width/height for AdSlot records if missing. Use --dry-run to preview changes.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print changes without saving')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        created = 0
        updated = 0

        # Ensure all default keys exist as AdSlot records
        for key, (w, h) in DEFAULT_SIZES.items():
            slot, was_created = AdSlot.objects.get_or_create(key=key, defaults={'name': key, 'width': w, 'height': h})
            if was_created:
                created += 1
                self.stdout.write(f"{key}: created AdSlot with {w}x{h}{' (dry-run)' if dry_run else ''}")
                # If dry-run we don't want to persist what get_or_create already created; but get_or_create persisted it.
                # To honor dry-run fully we should not have created; instead we will report and skip saving when dry_run True.
                if dry_run:
                    # undo creation
                    slot.delete()
                    created -= 1
            else:
                # If exists but missing sizes, set them
                if not (slot.width and slot.height and slot.width > 0 and slot.height > 0):
                    self.stdout.write(f"{key}: setting {w}x{h}{' (dry-run)' if dry_run else ''}")
                    if not dry_run:
                        slot.width = w
                        slot.height = h
                        slot.save(update_fields=['width', 'height'])
                        updated += 1

        # Also update any adslots present that correspond to DEFAULT_SIZES but were not handled above (safety)
        for p in AdSlot.objects.filter(key__in=list(DEFAULT_SIZES.keys())):
            if (p.width and p.height) and (p.width > 0 and p.height > 0):
                continue
            w, h = DEFAULT_SIZES.get(p.key)
            if not w or not h:
                continue
            self.stdout.write(f"{p.key}: setting {w}x{h}{' (dry-run)' if dry_run else ''}")
            if not dry_run:
                p.width = w
                p.height = h
                p.save(update_fields=['width', 'height'])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Done. Created {created} ad slots, updated {updated} ad slots."))
