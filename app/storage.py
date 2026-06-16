from whitenoise.storage import CompressedManifestStaticFilesStorage


class SafeCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    def stored_name(self, name, silent=False):
        try:
            return super().stored_name(name, silent=silent)
        except ValueError:
            return name