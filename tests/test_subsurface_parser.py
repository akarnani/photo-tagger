"""Tests for subsurface_parser module"""

import pytest
import tempfile
import os
from datetime import datetime

from photo_tagger.subsurface_parser import SubsurfaceParser


class TestSubsurfaceParser:
    
    def create_test_ssrf_file(self, content):
        """Helper to create temporary SSRF file"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.ssrf', delete=False)
        temp_file.write(content)
        temp_file.close()
        return temp_file.name
    
    def test_parse_simple_dive(self):
        """Test parsing a simple dive with site"""
        content = '''<?xml version="1.0"?>
<divelog program='subsurface' version='3'>
<divesites>
<site uuid='site1' name='Test Site' gps='21.676950 -72.469670'>
</site>
</divesites>
<dive number='1' date='2024-01-15' time='10:30:00' duration='45:00' divesiteid='site1'>
</dive>
</divelog>'''
        
        file_path = self.create_test_ssrf_file(content)
        try:
            parser = SubsurfaceParser(file_path)
            dives = parser.parse()
            
            assert len(dives) == 1
            dive = dives[0]
            assert dive.number == 1
            assert dive.date == datetime(2024, 1, 15, 10, 30, 0)
            assert dive.duration_minutes == 45
            assert dive.site.name == 'Test Site'
            assert dive.site.latitude == pytest.approx(21.676950)
            assert dive.site.longitude == pytest.approx(-72.469670)
        finally:
            os.unlink(file_path)
    
    def test_parse_multiple_dives(self):
        """Test parsing multiple dives"""
        content = '''<?xml version="1.0"?>
<divelog program='subsurface' version='3'>
<divesites>
<site uuid='site1' name='First Site' gps='21.0 -72.0'>
</site>
<site uuid='site2' name='Second Site' gps='22.0 -73.0'>
</site>
</divesites>
<dive number='1' date='2024-01-15' time='10:30:00' duration='45:00' divesiteid='site1'>
</dive>
<dive number='2' date='2024-01-16' time='14:15:00' duration='38:30' divesiteid='site2'>
</dive>
</divelog>'''
        
        file_path = self.create_test_ssrf_file(content)
        try:
            parser = SubsurfaceParser(file_path)
            dives = parser.parse()
            
            assert len(dives) == 2
            assert dives[0].site.name == 'First Site'
            assert dives[1].site.name == 'Second Site'
            assert dives[1].date == datetime(2024, 1, 16, 14, 15, 0)
        finally:
            os.unlink(file_path)
    
    def test_parse_dive_without_gps(self):
        """Test parsing dive site without GPS coordinates"""
        content = '''<?xml version="1.0"?>
<divelog program='subsurface' version='3'>
<divesites>
<site uuid='site1' name='No GPS Site'>
</site>
</divesites>
<dive number='1' date='2024-01-15' time='10:30:00' duration='45:00' divesiteid='site1'>
</dive>
</divelog>'''
        
        file_path = self.create_test_ssrf_file(content)
        try:
            parser = SubsurfaceParser(file_path)
            dives = parser.parse()
            
            assert len(dives) == 1
            dive = dives[0]
            assert dive.site.name == 'No GPS Site'
            assert dive.site.latitude is None
            assert dive.site.longitude is None
        finally:
            os.unlink(file_path)
    
    def test_parse_invalid_gps(self):
        """Test parsing with invalid GPS format"""
        content = '''<?xml version="1.0"?>
<divelog program='subsurface' version='3'>
<divesites>
<site uuid='site1' name='Bad GPS Site' gps='invalid coords'>
</site>
</divesites>
<dive number='1' date='2024-01-15' time='10:30:00' duration='45:00' divesiteid='site1'>
</dive>
</divelog>'''
        
        file_path = self.create_test_ssrf_file(content)
        try:
            parser = SubsurfaceParser(file_path)
            dives = parser.parse()
            
            assert len(dives) == 1
            dive = dives[0]
            assert dive.site.latitude is None
            assert dive.site.longitude is None
        finally:
            os.unlink(file_path)
    
    def test_parse_duration_formats(self):
        """Test parsing different duration formats"""
        content = '''<?xml version="1.0"?>
<divelog program='subsurface' version='3'>
<divesites>
<site uuid='site1' name='Test Site' gps='0 0'>
</site>
</divesites>
<dive number='1' date='2024-01-15' time='10:30:00' duration='45:30' divesiteid='site1'>
</dive>
<dive number='2' date='2024-01-16' time='10:30:00' duration='1:15:45' divesiteid='site1'>
</dive>
</divelog>'''
        
        file_path = self.create_test_ssrf_file(content)
        try:
            parser = SubsurfaceParser(file_path)
            dives = parser.parse()
            
            assert len(dives) == 2
            assert dives[0].duration_minutes == 45  # 45:30 -> 45 minutes
            assert dives[1].duration_minutes == 75  # 1:15:45 -> 75 minutes
        finally:
            os.unlink(file_path)
    
    def test_file_not_found(self):
        """Test handling of missing file"""
        with pytest.raises(FileNotFoundError):
            parser = SubsurfaceParser('/nonexistent/file.ssrf')
            parser.parse()
    
    def test_invalid_xml(self):
        """Test handling of invalid XML"""
        content = '''<?xml version="1.0"?>
<divelog>
  <unclosed_tag>
</divelog>'''
        
        file_path = self.create_test_ssrf_file(content)
        try:
            parser = SubsurfaceParser(file_path)
            with pytest.raises(ValueError, match="Invalid XML"):
                parser.parse()
        finally:
            os.unlink(file_path)