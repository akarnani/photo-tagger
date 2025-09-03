"""Logic for matching photos to dive sites based on timing"""

from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass

from .subsurface_parser import Dive
from .image_processor import ImageProcessor


@dataclass
class Match:
    """Represents a match between a photo and dive"""
    image_path: str
    dive: Dive
    photo_time: datetime
    confidence: str  # "exact", "within_dive", "uncertain"


class DiveMatcher:
    """Matches photos to dives based on capture time"""
    
    def __init__(self, dives: List[Dive]):
        self.dives = sorted(dives, key=lambda d: d.time)
    
    def find_matches(self, image_path: str) -> List[Match]:
        """Find potential dive matches for a photo based on capture time"""
        processor = ImageProcessor(image_path)
        photo_time = processor.get_capture_time()
        
        if not photo_time:
            return []
        
        matches = []
        
        for dive in self.dives:
            match_type = self._check_time_overlap(photo_time, dive)
            if match_type:
                match = Match(
                    image_path=image_path,
                    dive=dive,
                    photo_time=photo_time,
                    confidence=match_type
                )
                matches.append(match)
        
        # Sort by confidence and time proximity
        return sorted(matches, key=lambda m: (
            self._confidence_priority(m.confidence),
            abs((m.photo_time - m.dive.time).total_seconds())
        ))
    
    def _check_time_overlap(self, photo_time: datetime, dive: Dive) -> Optional[str]:
        """Check if photo time overlaps with dive time"""
        dive_start = dive.time
        dive_end = dive.time + timedelta(minutes=dive.duration_minutes)
        
        # Check if photo was taken during the dive
        if dive_start <= photo_time <= dive_end:
            return "within_dive"
        
        # Check if photo was taken close to dive time (within 2 hours before/after)
        time_diff = abs((photo_time - dive_start).total_seconds()) / 3600  # hours
        if time_diff <= 2.0:
            return "near_dive"
        
        return None
    
    def _confidence_priority(self, confidence: str) -> int:
        """Return priority for sorting (lower is better)"""
        priorities = {
            "within_dive": 1,
            "near_dive": 2,
            "uncertain": 3
        }
        return priorities.get(confidence, 4)
    
    def get_best_match(self, image_path: str) -> Optional[Match]:
        """Get the best single match for a photo"""
        matches = self.find_matches(image_path)
        return matches[0] if matches else None
    
    def format_match_info(self, match: Match) -> str:
        """Format match information for display"""
        time_diff = match.photo_time - match.dive.time
        time_diff_str = self._format_timedelta(time_diff)
        
        return (f"Photo: {match.image_path}\n"
                f"  Capture time: {match.photo_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"  Dive #{match.dive.number}: {match.dive.site.name}\n"
                f"  Dive time: {match.dive.time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"  Duration: {match.dive.duration_minutes} minutes\n"
                f"  Time difference: {time_diff_str}\n"
                f"  Confidence: {match.confidence}\n"
                f"  GPS: {match.dive.site.latitude}, {match.dive.site.longitude}")
    
    def _format_timedelta(self, td: timedelta) -> str:
        """Format timedelta for human reading"""
        total_seconds = int(td.total_seconds())
        hours = abs(total_seconds) // 3600
        minutes = (abs(total_seconds) % 3600) // 60
        seconds = abs(total_seconds) % 60
        
        sign = "-" if total_seconds < 0 else "+"
        
        if hours > 0:
            return f"{sign}{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{sign}{minutes}m {seconds}s"
        else:
            return f"{sign}{seconds}s"


class InteractiveMatcher(DiveMatcher):
    """Matcher that prompts user for ambiguous cases"""
    
    def get_user_confirmed_match(self, image_path: str) -> Optional[Match]:
        """Get match with user confirmation for ambiguous cases"""
        matches = self.find_matches(image_path)
        
        if not matches:
            return None
        
        if len(matches) == 1:
            return matches[0]
        
        # Check if we have a within_dive match - if so, always prefer it
        within_dive_matches = [m for m in matches if m.confidence == "within_dive"]
        if within_dive_matches:
            # Return the best within_dive match (already sorted by proximity)
            return within_dive_matches[0]
        
        # Multiple matches with same confidence level - prompt user
        print(f"\nMultiple dive matches found for: {image_path}")
        print(f"Photo capture time: {matches[0].photo_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        for i, match in enumerate(matches[:5], 1):  # Show max 5 options
            print(f"{i}. Dive #{match.dive.number}: {match.dive.site.name}")
            print(f"   Time: {match.dive.time.strftime('%Y-%m-%d %H:%M:%S')} "
                  f"(Duration: {match.dive.duration_minutes}min)")
            if match.dive.site.latitude and match.dive.site.longitude:
                print(f"   GPS: {match.dive.site.latitude:.6f}, {match.dive.site.longitude:.6f}")
            else:
                print("   GPS: No coordinates available")
            print(f"   Confidence: {match.confidence}")
            print()
        
        print("0. Skip this photo")
        
        while True:
            try:
                choice = input("Select dive (0 to skip): ").strip()
                if choice == "0":
                    return None
                
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(matches[:5]):
                    return matches[choice_idx]
                else:
                    print("Invalid selection. Please try again.")
            except (ValueError, KeyboardInterrupt):
                print("Invalid input. Please enter a number.")
            except EOFError:
                return None