"""Tests for image_processor module"""

import pytest
import tempfile
import os
from datetime import datetime
from unittest.mock import patch

from photo_tagger.image_processor import ImageProcessor


class TestImageProcessor:
    
    def test_unsupported_file_extension(self):
        """Test that unsupported file extensions raise an error"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False)
        temp_file.close()
        
        try:
            with pytest.raises(ValueError, match="Unsupported image format"):
                ImageProcessor(temp_file.name)
        finally:
            os.unlink(temp_file.name)
    
    def test_file_not_found(self):
        """Test that missing files raise an error"""
        with pytest.raises(FileNotFoundError, match="Image file not found"):
            ImageProcessor('/nonexistent/image.jpg')
    
    def test_supported_extensions(self):
        """Test that supported extensions are recognized"""
        supported_exts = ['.cr3', '.cr2', '.jpg', '.jpeg', '.tiff', '.tif']
        
        for ext in supported_exts:
            temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            temp_file.close()
            
            try:
                # Should not raise an exception
                processor = ImageProcessor(temp_file.name)
                assert processor.image_path == temp_file.name
            finally:
                os.unlink(temp_file.name)
    
    @patch('piexif.load')
    def test_get_capture_time_success(self, mock_piexif_load):
        """Test successful extraction of capture time"""
        # Mock EXIF data with datetime
        mock_exif = {
            "Exif": {
                36867: b'2024:01:15 14:30:45'  # DateTimeOriginal
            },
            "0th": {}
        }
        mock_piexif_load.return_value = mock_exif
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        temp_file.close()
        
        try:
            processor = ImageProcessor(temp_file.name)
            capture_time = processor.get_capture_time()
            
            assert capture_time == datetime(2024, 1, 15, 14, 30, 45)
        finally:
            os.unlink(temp_file.name)
    
    @patch('piexif.load')
    def test_get_capture_time_no_exif(self, mock_piexif_load):
        """Test when no EXIF datetime is available"""
        mock_exif = {"Exif": {}, "0th": {}}
        mock_piexif_load.return_value = mock_exif
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        temp_file.close()
        
        try:
            processor = ImageProcessor(temp_file.name)
            capture_time = processor.get_capture_time()
            
            assert capture_time is None
        finally:
            os.unlink(temp_file.name)
    
    @patch('piexif.load')
    def test_get_current_gps_success(self, mock_piexif_load):
        """Test successful extraction of GPS coordinates"""
        # Mock GPS EXIF data
        mock_exif = {
            "GPS": {
                1: b'N',  # GPSLatitudeRef
                2: ((21, 1), (40, 1), (37000, 1000)),  # GPSLatitude in DMS
                3: b'W',  # GPSLongitudeRef  
                4: ((72, 1), (28, 1), (11000, 1000)),  # GPSLongitude in DMS
            }
        }
        mock_piexif_load.return_value = mock_exif
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        temp_file.close()
        
        try:
            processor = ImageProcessor(temp_file.name)
            gps = processor.get_current_gps()
            
            assert gps is not None
            lat, lon = gps
            assert lat == pytest.approx(21.676944, abs=0.01)  # 21°40'37"N
            assert lon == pytest.approx(-72.469722, abs=0.01)  # 72°28'11"W (negative for West)
        finally:
            os.unlink(temp_file.name)
    
    @patch('piexif.load')
    def test_get_current_gps_no_data(self, mock_piexif_load):
        """Test when no GPS data is available"""
        mock_exif = {"GPS": {}}
        mock_piexif_load.return_value = mock_exif
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        temp_file.close()
        
        try:
            processor = ImageProcessor(temp_file.name)
            gps = processor.get_current_gps()
            
            assert gps is None
        finally:
            os.unlink(temp_file.name)
    
    def test_decimal_to_dms_conversion(self):
        """Test conversion from decimal degrees to DMS format"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        temp_file.close()
        
        try:
            processor = ImageProcessor(temp_file.name)
            
            # Test positive coordinate
            dms = processor._decimal_to_dms(21.676944)
            degrees = dms[0][0] / dms[0][1]
            minutes = dms[1][0] / dms[1][1] 
            seconds = dms[2][0] / dms[2][1]
            
            assert degrees == 21
            assert minutes == 40
            assert abs(seconds - 37) < 1  # Allow some rounding error
            
        finally:
            os.unlink(temp_file.name)
    
    def test_dms_to_decimal_conversion(self):
        """Test conversion from DMS to decimal degrees"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        temp_file.close()
        
        try:
            processor = ImageProcessor(temp_file.name)
            
            # Test DMS tuple: 21°40'37"
            dms_tuple = ((21, 1), (40, 1), (37000, 1000))
            decimal = processor._dms_to_decimal(dms_tuple)
            
            assert abs(decimal - 21.676944) < 0.01
            
        finally:
            os.unlink(temp_file.name)
    
    @patch('piexif.dump')
    @patch('piexif.insert')
    @patch('piexif.load')
    def test_set_gps_coordinates_dry_run(self, mock_load, mock_insert, mock_dump):
        """Test dry run mode doesn't modify files"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        temp_file.close()
        
        try:
            processor = ImageProcessor(temp_file.name)
            result = processor.set_gps_coordinates(21.676944, -72.469722, dry_run=True)
            
            assert result is True
            mock_load.assert_not_called()
            mock_dump.assert_not_called()
            mock_insert.assert_not_called()
        finally:
            os.unlink(temp_file.name)
    
    def test_find_images(self):
        """Test finding images in directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            jpg_file = os.path.join(temp_dir, 'test.jpg')
            cr3_file = os.path.join(temp_dir, 'test.cr3')
            txt_file = os.path.join(temp_dir, 'test.txt')
            
            for file_path in [jpg_file, cr3_file, txt_file]:
                with open(file_path, 'w') as f:
                    f.write('test')
            
            images = ImageProcessor.find_images(temp_dir)
            
            assert len(images) == 2  # Only jpg and cr3
            assert jpg_file in images
            assert cr3_file in images
            assert txt_file not in images
    
    def test_find_images_nonexistent_directory(self):
        """Test finding images in nonexistent directory"""
        with pytest.raises(FileNotFoundError, match="Directory not found"):
            ImageProcessor.find_images('/nonexistent/directory')

    def test_find_images_with_folder_exclusion(self):
        """Test finding images with folder exclusion"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test structure
            jpg_file = os.path.join(temp_dir, 'test.jpg')
            with open(jpg_file, 'w') as f:
                f.write('test')

            # Create Output subdirectory (to be excluded)
            output_dir = os.path.join(temp_dir, 'Output')
            os.makedirs(output_dir)
            output_jpg = os.path.join(output_dir, 'output.jpg')
            with open(output_jpg, 'w') as f:
                f.write('test')

            # Create Cache subdirectory (to be excluded)
            cache_dir = os.path.join(temp_dir, 'Cache')
            os.makedirs(cache_dir)
            cache_jpg = os.path.join(cache_dir, 'cache.jpg')
            with open(cache_jpg, 'w') as f:
                f.write('test')

            # Create Normal subdirectory (not excluded)
            normal_dir = os.path.join(temp_dir, 'Normal')
            os.makedirs(normal_dir)
            normal_jpg = os.path.join(normal_dir, 'normal.jpg')
            with open(normal_jpg, 'w') as f:
                f.write('test')

            # Find images with exclusion
            images = ImageProcessor.find_images(
                temp_dir,
                recursive=True,
                excluded_folders=['Output', 'Cache']
            )

            assert len(images) == 2  # test.jpg and Normal/normal.jpg
            assert jpg_file in images
            assert normal_jpg in images
            assert output_jpg not in images
            assert cache_jpg not in images

    def test_find_images_recursive_vs_nonrecursive(self):
        """Test recursive vs non-recursive image finding"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            root_jpg = os.path.join(temp_dir, 'root.jpg')
            with open(root_jpg, 'w') as f:
                f.write('test')

            # Create subdirectory
            sub_dir = os.path.join(temp_dir, 'subdir')
            os.makedirs(sub_dir)
            sub_jpg = os.path.join(sub_dir, 'sub.jpg')
            with open(sub_jpg, 'w') as f:
                f.write('test')

            # Non-recursive should only find root image
            images_nonrecursive = ImageProcessor.find_images(temp_dir, recursive=False)
            assert len(images_nonrecursive) == 1
            assert root_jpg in images_nonrecursive
            assert sub_jpg not in images_nonrecursive

            # Recursive should find both
            images_recursive = ImageProcessor.find_images(temp_dir, recursive=True)
            assert len(images_recursive) == 2
            assert root_jpg in images_recursive
            assert sub_jpg in images_recursive