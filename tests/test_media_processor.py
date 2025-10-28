"""Tests for media_processor module"""

import pytest

from photo_tagger.media_processor import MediaProcessor
from photo_tagger.image_processor import ImageProcessor
from photo_tagger.video_processor import VideoProcessor


class TestMediaProcessor:

    def test_create_processor_for_image(self, tmp_path):
        """Test creating processor for image file"""
        # Create a temporary image file
        image_file = tmp_path / "test.jpg"
        image_file.write_bytes(b"fake jpeg content")

        processor = MediaProcessor.create_processor(str(image_file))
        assert isinstance(processor, ImageProcessor)

    def test_create_processor_for_video(self, tmp_path):
        """Test creating processor for video file"""
        # Create a temporary video file
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake mp4 content")

        processor = MediaProcessor.create_processor(str(video_file))
        assert isinstance(processor, VideoProcessor)

    def test_create_processor_unsupported_format(self, tmp_path):
        """Test creating processor for unsupported format"""
        # Create a temporary unsupported file
        unsupported_file = tmp_path / "test.txt"
        unsupported_file.write_text("not a media file")

        with pytest.raises(ValueError, match="Unsupported file format"):
            MediaProcessor.create_processor(str(unsupported_file))

    def test_get_supported_extensions(self):
        """Test getting all supported extensions"""
        extensions = MediaProcessor.get_supported_extensions()

        # Check for image formats
        assert '.jpg' in extensions
        assert '.jpeg' in extensions
        assert '.cr3' in extensions
        assert '.cr2' in extensions

        # Check for video formats
        assert '.mp4' in extensions
        assert '.mov' in extensions
        assert '.avi' in extensions

    def test_is_supported_file(self, tmp_path):
        """Test checking if file is supported"""
        # Test supported image
        jpg_file = tmp_path / "test.jpg"
        jpg_file.write_bytes(b"fake")
        assert MediaProcessor.is_supported_file(str(jpg_file)) is True

        # Test supported video
        mp4_file = tmp_path / "test.mp4"
        mp4_file.write_bytes(b"fake")
        assert MediaProcessor.is_supported_file(str(mp4_file)) is True

        # Test unsupported file
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("fake")
        assert MediaProcessor.is_supported_file(str(txt_file)) is False

    def test_find_media_files(self, tmp_path):
        """Test finding all media files in directory"""
        # Create test structure
        (tmp_path / "image1.jpg").write_bytes(b"fake")
        (tmp_path / "image2.CR3").write_bytes(b"fake")
        (tmp_path / "video1.mp4").write_bytes(b"fake")
        (tmp_path / "video2.mov").write_bytes(b"fake")
        (tmp_path / "readme.txt").write_text("not a media file")

        # Create subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "image3.jpg").write_bytes(b"fake")
        (subdir / "video3.mp4").write_bytes(b"fake")

        # Test non-recursive
        media_files = MediaProcessor.find_media_files(str(tmp_path), recursive=False)
        assert len(media_files) == 4  # Only top-level media files
        assert any("image1.jpg" in f for f in media_files)
        assert any("video1.mp4" in f for f in media_files)
        assert not any("image3.jpg" in f for f in media_files)

        # Test recursive
        media_files = MediaProcessor.find_media_files(str(tmp_path), recursive=True)
        assert len(media_files) == 6  # All media files including subdirectory
        assert any("image3.jpg" in f for f in media_files)
        assert any("video3.mp4" in f for f in media_files)

    def test_find_media_files_with_exclusion(self, tmp_path):
        """Test finding media files with folder exclusion"""
        # Create test structure
        (tmp_path / "image1.jpg").write_bytes(b"fake")

        # Create excluded directory
        output_dir = tmp_path / "Output"
        output_dir.mkdir()
        (output_dir / "image2.jpg").write_bytes(b"fake")
        (output_dir / "video1.mp4").write_bytes(b"fake")

        # Create cache directory
        cache_dir = tmp_path / "Cache"
        cache_dir.mkdir()
        (cache_dir / "image3.jpg").write_bytes(b"fake")

        # Create normal subdirectory
        normal_dir = tmp_path / "Normal"
        normal_dir.mkdir()
        (normal_dir / "image4.jpg").write_bytes(b"fake")

        # Test with exclusion
        media_files = MediaProcessor.find_media_files(
            str(tmp_path),
            recursive=True,
            excluded_folders=['Output', 'Cache']
        )

        assert len(media_files) == 2  # Only image1.jpg and Normal/image4.jpg
        assert any("image1.jpg" in f for f in media_files)
        assert any("image4.jpg" in f for f in media_files)
        assert not any("image2.jpg" in f for f in media_files)
        assert not any("image3.jpg" in f for f in media_files)
        assert not any("video1.mp4" in f for f in media_files)
