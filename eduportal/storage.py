from whitenoise.storage import CompressedManifestStaticFilesStorage


class LenientManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Same as whitenoise's manifest storage, but doesn't crash the build if a
    referenced static file (e.g. an old Django admin icon) is missing.
    """
    manifest_strict = False
