import logging

from whitenoise.storage import CompressedManifestStaticFilesStorage

logger = logging.getLogger(__name__)


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    A storage backend that hashes static file names for cache busting
    but silently skips files with missing references (e.g., source maps).

    This prevents collectstatic from crashing when a JS file references a
    .map file that doesn't exist in the static directory.
    """
    manifest_strict = False

    def post_process(self, *args, **kwargs):
        for name, hashed_name, processed in super().post_process(*args, **kwargs):
            if isinstance(processed, Exception):
                logger.warning(
                    "Skipping post-processing of '%s': %s", name, processed
                )
                # Yield a non-error tuple so collectstatic continues
                yield name, None, False
            else:
                yield name, hashed_name, processed
