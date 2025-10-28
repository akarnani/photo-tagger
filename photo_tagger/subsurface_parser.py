"""Parser for Subsurface diving log files"""

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class DiveSite:
    """Represents a dive site with location information"""
    uuid: str
    name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@dataclass
class Dive:
    """Represents a dive with timing and location information"""
    number: int
    date: datetime
    time: datetime
    duration_minutes: int
    site: DiveSite
    tags: List[str] = None

    def __post_init__(self):
        """Initialize tags to empty list if None"""
        if self.tags is None:
            self.tags = []


class SubsurfaceParser:
    """Parser for Subsurface XML files"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.tree = None
        self.root = None
    
    def parse(self) -> List[Dive]:
        """Parse the subsurface file and return list of dives"""
        try:
            self.tree = ET.parse(self.file_path)
            self.root = self.tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML in subsurface file: {e}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Subsurface file not found: {self.file_path}")
        
        # First parse dive sites
        sites = self._parse_dive_sites()
        
        # Then parse dives and link to sites
        dives = self._parse_dives(sites)
        
        return dives
    
    def _parse_dive_sites(self) -> Dict[str, DiveSite]:
        """Parse dive sites from the XML"""
        sites = {}
        
        divesites_elem = self.root.find('divesites')
        if divesites_elem is None:
            return sites
        
        for site_elem in divesites_elem.findall('site'):
            uuid = site_elem.get('uuid', '').strip()
            name = site_elem.get('name', '')
            gps = site_elem.get('gps', '')
            
            latitude, longitude = None, None
            if gps:
                try:
                    # GPS format appears to be "latitude longitude"
                    lat_str, lon_str = gps.split()
                    latitude = float(lat_str)
                    longitude = float(lon_str)
                except (ValueError, IndexError):
                    # Invalid GPS format, skip coordinates
                    pass
            
            sites[uuid] = DiveSite(
                uuid=uuid,
                name=name,
                latitude=latitude,
                longitude=longitude
            )
        
        return sites
    
    def _parse_dives(self, sites: Dict[str, DiveSite]) -> List[Dive]:
        """Parse dives from the XML and link to sites"""
        dives = []
        
        # First look for dives directly under root (legacy format)
        for dive_elem in self.root.findall('dive'):
            dive = self._parse_single_dive(dive_elem, sites)
            if dive:
                dives.append(dive)
        
        # Then look for dives organized in trips within <dives> section
        dives_section = self.root.find('dives')
        if dives_section is not None:
            # Look for trips within the dives section
            for trip_elem in dives_section.findall('trip'):
                for dive_elem in trip_elem.findall('dive'):
                    dive = self._parse_single_dive(dive_elem, sites)
                    if dive:
                        dives.append(dive)
            
            # Also look for any standalone dives in the dives section (not in trips)
            for dive_elem in dives_section.findall('dive'):
                dive = self._parse_single_dive(dive_elem, sites)
                if dive:
                    dives.append(dive)
        
        return dives
    
    def _parse_single_dive(self, dive_elem, sites: Dict[str, DiveSite]) -> Optional[Dive]:
        """Parse a single dive element"""
        try:
            # Parse dive attributes
            number = int(dive_elem.get('number', 0))
            date_str = dive_elem.get('date', '')
            time_str = dive_elem.get('time', '')
            duration_str = dive_elem.get('duration', '0:00')
            tags_str = dive_elem.get('tags', '')

            # Parse date and time
            dive_datetime = self._parse_datetime(date_str, time_str)
            if not dive_datetime:
                return None

            # Parse duration - handle "MM:SS min" format from Subsurface
            duration_minutes = self._parse_duration(duration_str)

            # Parse tags (comma-separated string)
            tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            
            # Find dive site
            site_uuid = dive_elem.get('divesiteid', '').strip()
            site = sites.get(site_uuid)
            
            if not site:
                # Try to find site by name in dive notes or create unnamed site
                site = DiveSite(uuid=site_uuid or f"unknown_{number}", name=f"Unknown Site {number}")
            
            dive = Dive(
                number=number,
                date=dive_datetime,
                time=dive_datetime,
                duration_minutes=duration_minutes,
                site=site,
                tags=tags
            )
            
            return dive
            
        except (ValueError, TypeError):
            # Skip invalid dives but continue processing
            return None
    
    def _parse_datetime(self, date_str: str, time_str: str) -> Optional[datetime]:
        """Parse date and time strings into datetime object"""
        if not date_str:
            return None
        
        try:
            # Parse date (format: YYYY-MM-DD)
            date_part = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Parse time (format: HH:MM:SS or HH:MM)
            if time_str:
                try:
                    if ':' in time_str:
                        if time_str.count(':') == 2:
                            time_part = datetime.strptime(time_str, '%H:%M:%S').time()
                        else:
                            time_part = datetime.strptime(time_str, '%H:%M').time()
                    else:
                        time_part = datetime.strptime(time_str, '%H').time()
                except ValueError:
                    time_part = datetime.min.time()
            else:
                time_part = datetime.min.time()
            
            return datetime.combine(date_part, time_part)
            
        except ValueError:
            return None
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string into minutes"""
        if not duration_str or duration_str == '0:00':
            return 0
        
        try:
            # Remove " min" suffix if present (Subsurface format)
            duration_clean = duration_str.replace(' min', '')
            
            # Handle formats: "MM:SS", "H:MM:SS", or just minutes
            parts = duration_clean.split(':')
            if len(parts) == 2:
                # MM:SS format - convert to minutes
                minutes = int(parts[0])
                seconds = int(parts[1])
                return minutes + (seconds // 60)
            elif len(parts) == 3:
                # H:MM:SS format
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2])
                return (hours * 60) + minutes + (seconds // 60)
            else:
                # Assume it's just minutes
                return int(duration_clean)
        except (ValueError, IndexError):
            return 0