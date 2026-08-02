import logging

from whitenoise.storage import CompressedManifestStaticFilesStorage

logger = logging.getLogger(__name__)


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    A storage backend that hashes static file names for cache busting
    but silently skips files with missing references (e.g., source maps).

    - collectstatic: skips post-processing errors (missing .map files, etc.)
    - template rendering: returns the unhashed URL for any file not in the
      manifest instead of raising ValueError (e.g., a referenced image that
      was deleted from the static directory).
    """
    manifest_strict = False

    def stored_name(self, name):
        """
        Return the hashed name from the manifest. If the file is missing
        from the manifest AND can't be hashed on-the-fly (file doesn't
        exist on disk), fall back to the original unhashed name so templates
        don't crash with a 500 error.
        """
        try:
            return super().stored_name(name)
        except ValueError:
            logger.warning(
                "Static file '%s' not found in manifest and not on disk; "
                "serving unhashed URL.",
                name,
            )
            return name

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
