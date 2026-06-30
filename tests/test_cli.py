"""Tests for the command line interface"""

from click.testing import CliRunner

from photo_tagger import __version__
from photo_tagger.cli import main


class TestCli:
    """Tests for the photo-tagger CLI"""

    def test_version_option(self):
        """--version reports the package version and exits cleanly"""
        runner = CliRunner()
        result = runner.invoke(main, ['--version'])

        assert result.exit_code == 0
        assert __version__ in result.output
