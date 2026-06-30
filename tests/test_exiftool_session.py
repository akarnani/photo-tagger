"""Tests for the persistent exiftool session"""

from unittest.mock import MagicMock, patch

from photo_tagger.exiftool_session import ExifToolSession


class TestExifToolSession:
    """Tests for ExifToolSession graceful behavior"""

    @patch('photo_tagger.exiftool_session.shutil.which', return_value=None)
    def test_unavailable_without_exiftool(self, mock_which):
        """Without exiftool on PATH, the session is unavailable and set_gps
        returns False so callers fall back to a sidecar."""
        with ExifToolSession() as session:
            assert session.available is False
            assert session.set_gps('/tmp/x.arw', 20.0, -86.0) is False

    @patch('photo_tagger.exiftool_session.shutil.which', return_value='/usr/bin/exiftool')
    def test_set_gps_uses_persistent_helper(self, mock_which):
        """When available, set_gps writes signed coordinates through the shared
        helper as positive values plus hemisphere refs."""
        fake_helper = MagicMock()
        with patch('exiftool.ExifToolHelper', return_value=fake_helper):
            with ExifToolSession() as session:
                assert session.available is True
                ok = session.set_gps('/tmp/dive.arw', -20.5, -86.95)

        assert ok is True
        fake_helper.set_tags.assert_called_once()
        _, kwargs = fake_helper.set_tags.call_args
        tags = kwargs['tags']
        assert tags['GPSLatitude'] == 20.5 and tags['GPSLatitudeRef'] == 'S'
        assert tags['GPSLongitude'] == 86.95 and tags['GPSLongitudeRef'] == 'W'
        # the process is shut down on context exit
        fake_helper.terminate.assert_called_once()

    @patch('photo_tagger.exiftool_session.shutil.which', return_value='/usr/bin/exiftool')
    def test_set_gps_returns_false_on_write_error(self, mock_which):
        """A failing exiftool write degrades to False rather than raising."""
        fake_helper = MagicMock()
        fake_helper.set_tags.side_effect = RuntimeError('boom')
        with patch('exiftool.ExifToolHelper', return_value=fake_helper):
            with ExifToolSession() as session:
                assert session.set_gps('/tmp/dive.arw', 20.0, -86.0) is False
