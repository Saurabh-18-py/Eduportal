from whitenoise.storage import CompressedManifestStaticFilesStorage


class LenientManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Same as whitenoise's manifest storage, but doesn't crash the whole build
    if a referenced static file is missing (e.g. an old Django admin icon
    referenced by admin/css/base.css that isn't shipped in newer Django
    versions). Missing files are skipped with a warning instead.
    """

    def post_process(self, *args, **kwargs):
        for name, hashed_name, processed in super().post_process(*args, **kwargs):
            if isinstance(processed, Exception):
                print(f"Warning: skipping static file that could not be processed: {name} ({processed})")
                continue
            yield name, hashed_name, processed
