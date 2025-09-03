"""Tests for matcher module"""

from datetime import datetime
from unittest.mock import patch, MagicMock

from photo_tagger.matcher import DiveMatcher, InteractiveMatcher, Match
from photo_tagger.subsurface_parser import Dive, DiveSite


class TestDiveMatcher:
    
    def create_test_dives(self):
        """Create test dives for matching"""
        site1 = DiveSite(uuid='site1', name='Morning Dive', latitude=21.0, longitude=-72.0)
        site2 = DiveSite(uuid='site2', name='Afternoon Dive', latitude=22.0, longitude=-73.0)
        
        dive1 = Dive(
            number=1,
            date=datetime(2024, 1, 15, 9, 0, 0),
            time=datetime(2024, 1, 15, 9, 0, 0),
            duration_minutes=45,
            site=site1
        )
        
        dive2 = Dive(
            number=2,
            date=datetime(2024, 1, 15, 14, 0, 0),
            time=datetime(2024, 1, 15, 14, 0, 0),
            duration_minutes=50,
            site=site2
        )
        
        return [dive1, dive2]
    
    @patch('photo_tagger.matcher.ImageProcessor')
    def test_find_matches_within_dive(self, mock_processor_class):
        """Test finding matches for photos taken during dive"""
        # Mock image processor
        mock_processor = MagicMock()
        mock_processor.get_capture_time.return_value = datetime(2024, 1, 15, 9, 20, 0)  # 20 min into first dive
        mock_processor_class.return_value = mock_processor
        
        dives = self.create_test_dives()
        matcher = DiveMatcher(dives)
        
        matches = matcher.find_matches('test_image.jpg')
        
        assert len(matches) == 1
        assert matches[0].confidence == 'within_dive'
        assert matches[0].dive.number == 1
        assert matches[0].dive.site.name == 'Morning Dive'
    
    @patch('photo_tagger.matcher.ImageProcessor')
    def test_find_matches_near_dive(self, mock_processor_class):
        """Test finding matches for photos taken near dive time"""
        # Mock image processor - photo taken 1 hour before dive
        mock_processor = MagicMock()
        mock_processor.get_capture_time.return_value = datetime(2024, 1, 15, 8, 0, 0)  # 1 hour before first dive
        mock_processor_class.return_value = mock_processor
        
        dives = self.create_test_dives()
        matcher = DiveMatcher(dives)
        
        matches = matcher.find_matches('test_image.jpg')
        
        assert len(matches) == 1
        assert matches[0].confidence == 'near_dive'
        assert matches[0].dive.number == 1
    
    @patch('photo_tagger.matcher.ImageProcessor')
    def test_find_matches_no_match(self, mock_processor_class):
        """Test no matches for photos taken far from dive times"""
        # Mock image processor - photo taken days before dive
        mock_processor = MagicMock()
        mock_processor.get_capture_time.return_value = datetime(2024, 1, 10, 12, 0, 0)  # Days before
        mock_processor_class.return_value = mock_processor
        
        dives = self.create_test_dives()
        matcher = DiveMatcher(dives)
        
        matches = matcher.find_matches('test_image.jpg')
        
        assert len(matches) == 0
    
    @patch('photo_tagger.matcher.ImageProcessor')
    def test_find_matches_no_capture_time(self, mock_processor_class):
        """Test handling photos without capture time"""
        # Mock image processor - no capture time available
        mock_processor = MagicMock()
        mock_processor.get_capture_time.return_value = None
        mock_processor_class.return_value = mock_processor
        
        dives = self.create_test_dives()
        matcher = DiveMatcher(dives)
        
        matches = matcher.find_matches('test_image.jpg')
        
        assert len(matches) == 0
    
    @patch('photo_tagger.matcher.ImageProcessor')
    def test_find_matches_multiple_matches(self, mock_processor_class):
        """Test multiple potential matches sorted by confidence"""
        # Mock image processor - photo taken between two dives (closer to both)
        mock_processor = MagicMock()
        mock_processor.get_capture_time.return_value = datetime(2024, 1, 15, 11, 0, 0)  # Between dives, 2h from first, 3h from second
        mock_processor_class.return_value = mock_processor
        
        dives = self.create_test_dives()
        matcher = DiveMatcher(dives)
        
        matches = matcher.find_matches('test_image.jpg')
        
        # Should find only one match (within 2h window of first dive only)
        assert len(matches) == 1
        assert matches[0].confidence == 'near_dive'
        # Only the first dive (9:00) is within 2 hours of 11:00
        assert matches[0].dive.number == 1
    
    @patch('photo_tagger.matcher.ImageProcessor')
    def test_get_best_match(self, mock_processor_class):
        """Test getting the single best match"""
        mock_processor = MagicMock()
        mock_processor.get_capture_time.return_value = datetime(2024, 1, 15, 9, 20, 0)
        mock_processor_class.return_value = mock_processor
        
        dives = self.create_test_dives()
        matcher = DiveMatcher(dives)
        
        best_match = matcher.get_best_match('test_image.jpg')
        
        assert best_match is not None
        assert best_match.confidence == 'within_dive'
        assert best_match.dive.number == 1
    
    def test_format_match_info(self):
        """Test formatting match information for display"""
        dives = self.create_test_dives()
        match = Match(
            image_path='test_image.jpg',
            dive=dives[0],
            photo_time=datetime(2024, 1, 15, 9, 20, 0),
            confidence='within_dive'
        )
        
        matcher = DiveMatcher(dives)
        info = matcher.format_match_info(match)
        
        assert 'test_image.jpg' in info
        assert '2024-01-15 09:20:00' in info
        assert 'Morning Dive' in info
        assert 'within_dive' in info
        assert '21.0, -72.0' in info


class TestInteractiveMatcher:
    
    def create_test_dives(self):
        """Create test dives for matching"""
        site1 = DiveSite(uuid='site1', name='Site One', latitude=21.0, longitude=-72.0)
        site2 = DiveSite(uuid='site2', name='Site Two', latitude=22.0, longitude=-73.0)
        
        dive1 = Dive(
            number=1,
            date=datetime(2024, 1, 15, 9, 0, 0),
            time=datetime(2024, 1, 15, 9, 0, 0),
            duration_minutes=45,
            site=site1
        )
        
        dive2 = Dive(
            number=2,
            date=datetime(2024, 1, 15, 11, 30, 0),  # Closer to first dive for multi-match scenarios
            time=datetime(2024, 1, 15, 11, 30, 0),
            duration_minutes=50,
            site=site2
        )
        
        return [dive1, dive2]
    
    @patch('photo_tagger.matcher.ImageProcessor')
    def test_single_match_no_prompt(self, mock_processor_class):
        """Test that single matches don't prompt user"""
        mock_processor = MagicMock()
        mock_processor.get_capture_time.return_value = datetime(2024, 1, 15, 9, 20, 0)  # Only matches first dive
        mock_processor_class.return_value = mock_processor
        
        dives = self.create_test_dives()
        matcher = InteractiveMatcher(dives)
        
        match = matcher.get_user_confirmed_match('test_image.jpg')
        
        assert match is not None
        assert match.dive.number == 1
    
    @patch('photo_tagger.matcher.ImageProcessor')
    @patch('builtins.input', return_value='1')
    def test_multiple_matches_user_selection(self, mock_input, mock_processor_class):
        """Test user selection when multiple matches exist"""
        mock_processor = MagicMock()
        mock_processor.get_capture_time.return_value = datetime(2024, 1, 15, 10, 15, 0)  # Between dives, within 2h of both
        mock_processor_class.return_value = mock_processor
        
        dives = self.create_test_dives()
        matcher = InteractiveMatcher(dives)
        
        match = matcher.get_user_confirmed_match('test_image.jpg')
        
        assert match is not None
        assert match.dive.number == 1  # User selected option 1, which is dive 1 (first in sorted order)
    
    @patch('photo_tagger.matcher.ImageProcessor')
    @patch('builtins.input', return_value='0')
    def test_multiple_matches_user_skip(self, mock_input, mock_processor_class):
        """Test user choosing to skip when multiple matches exist"""
        mock_processor = MagicMock()
        mock_processor.get_capture_time.return_value = datetime(2024, 1, 15, 10, 15, 0)  # Between both dives, within 2h of both
        mock_processor_class.return_value = mock_processor
        
        dives = self.create_test_dives()
        matcher = InteractiveMatcher(dives)
        
        match = matcher.get_user_confirmed_match('test_image.jpg')
        
        assert match is None
    
    @patch('photo_tagger.matcher.ImageProcessor')
    @patch('builtins.input', side_effect=['invalid', '2'])
    def test_multiple_matches_invalid_then_valid_input(self, mock_input, mock_processor_class):
        """Test handling of invalid input followed by valid selection"""
        mock_processor = MagicMock()
        mock_processor.get_capture_time.return_value = datetime(2024, 1, 15, 10, 15, 0)  # Between both dives, within 2h of both
        mock_processor_class.return_value = mock_processor
        
        dives = self.create_test_dives()
        matcher = InteractiveMatcher(dives)
        
        match = matcher.get_user_confirmed_match('test_image.jpg')
        
        assert match is not None
        assert match.dive.number == 2  # User selected option 2 (dive 2 is second in sorted order)
    
    @patch('photo_tagger.matcher.ImageProcessor')
    def test_within_dive_prioritized_over_near_dive(self, mock_processor_class):
        """Test that within_dive matches are prioritized over near_dive without prompting"""
        mock_processor = MagicMock()
        mock_processor.get_capture_time.return_value = datetime(2024, 1, 15, 9, 20, 0)  # During first dive
        mock_processor_class.return_value = mock_processor
        
        # Create dives where photo is within first dive but near second dive
        site1 = DiveSite(uuid='site1', name='Within Dive Site', latitude=21.0, longitude=-72.0)
        site2 = DiveSite(uuid='site2', name='Near Dive Site', latitude=22.0, longitude=-73.0)
        
        dive1 = Dive(
            number=1,
            date=datetime(2024, 1, 15, 9, 0, 0),
            time=datetime(2024, 1, 15, 9, 0, 0),
            duration_minutes=45,  # 9:00-9:45, photo at 9:20 is within
            site=site1
        )
        
        dive2 = Dive(
            number=2,
            date=datetime(2024, 1, 15, 10, 30, 0),
            time=datetime(2024, 1, 15, 10, 30, 0),
            duration_minutes=30,  # 10:30-11:00, photo at 9:20 is near (1h10m before)
            site=site2
        )
        
        dives = [dive1, dive2]
        matcher = InteractiveMatcher(dives)
        
        # This should return the within_dive match without prompting
        match = matcher.get_user_confirmed_match('test_image.jpg')
        
        assert match is not None
        assert match.dive.number == 1
        assert match.confidence == 'within_dive'
        assert match.dive.site.name == 'Within Dive Site'