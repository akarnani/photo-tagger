"""Tests for subsurface_parser module with trip organization"""

import pytest
import tempfile
import os
from datetime import datetime

from photo_tagger.subsurface_parser import SubsurfaceParser, DiveSite, Dive


class TestSubsurfaceTripParsing:
    
    def create_test_ssrf_file(self, content):
        """Helper to create temporary SSRF file"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.ssrf', delete=False)
        temp_file.write(content)
        temp_file.close()
        return temp_file.name
    
    def test_parse_dives_in_trips(self):
        """Test parsing dives organized in trips"""
        content = '''<?xml version="1.0"?>
<divelog program='subsurface' version='3'>
<divesites>
<site uuid='site1' name='Trip Site 1' gps='21.0 -72.0'>
</site>
<site uuid='site2' name='Trip Site 2' gps='22.0 -73.0'>
</site>
</divesites>
<dives>
<trip date='2024-01-15' time='10:30:00' location='Test Location'>
<dive number='1' date='2024-01-15' time='10:30:00' duration='45:00 min' divesiteid='site1'>
</dive>
<dive number='2' date='2024-01-15' time='14:15:00' duration='38:30 min' divesiteid='site2'>
</dive>
</trip>
</dives>
</divelog>'''
        
        file_path = self.create_test_ssrf_file(content)
        try:
            parser = SubsurfaceParser(file_path)
            dives = parser.parse()
            
            assert len(dives) == 2
            assert dives[0].number == 1
            assert dives[0].site.name == 'Trip Site 1'
            assert dives[0].duration_minutes == 45
            assert dives[1].number == 2
            assert dives[1].site.name == 'Trip Site 2'
            assert dives[1].duration_minutes == 38
        finally:
            os.unlink(file_path)
    
    def test_parse_mixed_dives_and_trips(self):
        """Test parsing both standalone dives and trip-organized dives"""
        content = '''<?xml version="1.0"?>
<divelog program='subsurface' version='3'>
<divesites>
<site uuid='site1' name='Standalone Site' gps='20.0 -70.0'>
</site>
<site uuid='site2' name='Trip Site' gps='21.0 -71.0'>
</site>
</divesites>
<dive number='100' date='2024-01-10' time='10:00:00' duration='30:00' divesiteid='site1'>
</dive>
<dives>
<dive number='200' date='2024-01-20' time='10:00:00' duration='35:00' divesiteid='site1'>
</dive>
<trip date='2024-01-15' time='10:30:00' location='Test Trip'>
<dive number='150' date='2024-01-15' time='10:30:00' duration='45:00 min' divesiteid='site2'>
</dive>
</trip>
</dives>
</divelog>'''
        
        file_path = self.create_test_ssrf_file(content)
        try:
            parser = SubsurfaceParser(file_path)
            dives = parser.parse()
            
            assert len(dives) == 3
            # Should find standalone dive under root
            standalone_dive = next((d for d in dives if d.number == 100), None)
            assert standalone_dive is not None
            assert standalone_dive.site.name == 'Standalone Site'
            
            # Should find trip-organized dive
            trip_dive = next((d for d in dives if d.number == 150), None)
            assert trip_dive is not None
            assert trip_dive.site.name == 'Trip Site'
            
            # Should find standalone dive in dives section
            dives_standalone = next((d for d in dives if d.number == 200), None)
            assert dives_standalone is not None
            assert dives_standalone.site.name == 'Standalone Site'
        finally:
            os.unlink(file_path)
    
    def test_parse_duration_with_min_suffix(self):
        """Test parsing duration with 'min' suffix"""
        content = '''<?xml version="1.0"?>
<divelog program='subsurface' version='3'>
<divesites>
<site uuid='site1' name='Test Site' gps='0 0'>
</site>
</divesites>
<dives>
<trip date='2024-01-15' time='10:30:00' location='Test'>
<dive number='1' date='2024-01-15' time='10:30:00' duration='45:30 min' divesiteid='site1'>
</dive>
<dive number='2' date='2024-01-16' time='10:30:00' duration='1:15:45 min' divesiteid='site1'>
</dive>
</trip>
</dives>
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
    
    def test_multiple_trips(self):
        """Test parsing multiple trips with dives"""
        content = '''<?xml version="1.0"?>
<divelog program='subsurface' version='3'>
<divesites>
<site uuid='site1' name='Site A' gps='21.0 -72.0'>
</site>
<site uuid='site2' name='Site B' gps='22.0 -73.0'>
</site>
</divesites>
<dives>
<trip date='2024-01-15' time='10:30:00' location='Trip 1'>
<dive number='1' date='2024-01-15' time='10:30:00' duration='45:00 min' divesiteid='site1'>
</dive>
</trip>
<trip date='2024-01-20' time='14:30:00' location='Trip 2'>
<dive number='2' date='2024-01-20' time='14:30:00' duration='50:00 min' divesiteid='site2'>
</dive>
</trip>
</dives>
</divelog>'''
        
        file_path = self.create_test_ssrf_file(content)
        try:
            parser = SubsurfaceParser(file_path)
            dives = parser.parse()
            
            assert len(dives) == 2
            assert dives[0].number == 1
            assert dives[0].site.name == 'Site A'
            assert dives[1].number == 2
            assert dives[1].site.name == 'Site B'
        finally:
            os.unlink(file_path)