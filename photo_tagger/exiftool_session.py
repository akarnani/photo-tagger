"""Persistent exiftool process for batched metadata writes.

exiftool pays a per-invocation startup cost (Perl interpreter + module load).
Spawning a fresh process for every file is wasteful on a large run, so this
module keeps a single exiftool process alive (via its ``-stay_open`` mode,
wrapped by PyExifTool) for the whole run and feeds every file through it.

Use as a context manager. If exiftool or PyExifTool isn't available, the
session degrades gracefully: ``available`` is False and ``set_gps`` returns
False so callers fall back to writing GPS into an XMP sidecar.
"""

import shutil


class ExifToolSession:
    """A reusable exiftool process for embedding GPS across many files."""

    def __init__(self):
        self._helper = None

    @property
    def available(self) -> bool:
        """True when a live exiftool process is ready to accept writes."""
        return self._helper is not None

    def __enter__(self) -> "ExifToolSession":
        if shutil.which('exiftool'):
            try:
                from exiftool import ExifToolHelper
                helper = ExifToolHelper()
                helper.run()  # start the persistent process now
                self._helper = helper
            except Exception:
                self._helper = None
        return self

    def __exit__(self, *exc) -> bool:
        if self._helper is not None:
            try:
                self._helper.terminate()
            except Exception:
                pass
            self._helper = None
        return False

    def set_gps(self, image_path: str, latitude: float, longitude: float) -> bool:
        """Embed GPS coordinates into image_path via the shared process.

        Returns False (rather than raising) if the session isn't available or
        the write fails, so the caller can fall back to an XMP sidecar.
        """
        if self._helper is None:
            return False

        lat_ref = 'N' if latitude >= 0 else 'S'
        lon_ref = 'E' if longitude >= 0 else 'W'

        try:
            self._helper.set_tags(
                [image_path],
                tags={
                    'GPSLatitude': abs(latitude),
                    'GPSLatitudeRef': lat_ref,
                    'GPSLongitude': abs(longitude),
                    'GPSLongitudeRef': lon_ref,
                },
                params=['-overwrite_original'],
            )
            return True
        except Exception:
            return False
