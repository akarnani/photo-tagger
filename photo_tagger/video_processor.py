"""Video processing and metadata handling for movie files"""

import os
import subprocess
import json
from datetime import datetime
from typing import Optional, Tuple, List


class VideoProcessor:
    """Handles reading and writing metadata in video files using ExifTool"""
    
    SUPPORTED_EXTENSIONS = {'.mp4', '.mov', '.avi', '.m4v', '.mkv'}
    
    def __init__(self, video_path: str):
        self.video_path = video_path
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # Check if file extension is supported
        ext = os.path.splitext(video_path)[1].lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported video format: {ext}")
    
    def get_capture_time(self) -> Optional[datetime]:
        """Extract the capture time from video metadata"""
        try:
            # Use exiftool to extract creation time metadata
            cmd = ['exiftool', '-j', '-CreateDate', '-DateTimeOriginal', '-MediaCreateDate', '-CreationDate', self.video_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return None
            
            metadata = json.loads(result.stdout)[0]
            
            # Try different date fields in order of preference
            date_fields = ['DateTimeOriginal', 'MediaCreateDate', 'CreateDate', 'CreationDate']
            
            for field in date_fields:
                if field in metadata:
                    date_str = metadata[field]
                    try:
                        # Handle various datetime formats from ExifTool
                        # Common formats: "2023:10:15 14:30:25", "2023-10-15 14:30:25"
                        for fmt in ['%Y:%m:%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y:%m:%d %H:%M:%S%z']:
                            try:
                                return datetime.strptime(date_str, fmt)
                            except ValueError:
                                continue
                    except ValueError:
                        continue
            
            return None
            
        except Exception:
            return None
    
    def get_current_gps(self) -> Optional[Tuple[float, float]]:
        """Get existing GPS coordinates from video metadata"""
        try:
            cmd = ['exiftool', '-j', '-GPSLatitude', '-GPSLongitude', '-GPSLatitudeRef', '-GPSLongitudeRef', self.video_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return None
            
            metadata = json.loads(result.stdout)[0]
            
            # Check if GPS data exists
            if 'GPSLatitude' not in metadata or 'GPSLongitude' not in metadata:
                return None
            
            latitude = float(metadata['GPSLatitude'])
            longitude = float(metadata['GPSLongitude'])
            
            # Apply hemisphere references if available
            if 'GPSLatitudeRef' in metadata and metadata['GPSLatitudeRef'] == 'S':
                latitude = -latitude
            if 'GPSLongitudeRef' in metadata and metadata['GPSLongitudeRef'] == 'W':
                longitude = -longitude
            
            return latitude, longitude
            
        except Exception:
            return None
    
    def set_gps_coordinates(self, latitude: float, longitude: float, dry_run: bool = False) -> bool:
        """Set GPS coordinates in video metadata using ExifTool"""
        if dry_run:
            return True
        
        try:
            # Prepare ExifTool command to set GPS coordinates
            lat_ref = 'N' if latitude >= 0 else 'S'
            lon_ref = 'E' if longitude >= 0 else 'W'
            
            cmd = [
                'exiftool',
                f'-GPSLatitude={abs(latitude)}',
                f'-GPSLatitudeRef={lat_ref}',
                f'-GPSLongitude={abs(longitude)}',
                f'-GPSLongitudeRef={lon_ref}',
                '-overwrite_original',  # Don't create backup files
                self.video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0
            
        except Exception:
            return False
    
    def create_xmp_sidecar(self, keywords: List[str], latitude: Optional[float] = None, longitude: Optional[float] = None, dry_run: bool = False) -> bool:
        """Create XMP sidecar file for video with keywords and GPS data"""
        if dry_run:
            return True
        
        # Generate XMP filename (same as video but with .xmp extension)
        xmp_path = os.path.splitext(self.video_path)[0] + '.xmp'
        
        try:
            # Create keyword list XML
            keyword_items = '\n'.join([f'     <rdf:li>{keyword}</rdf:li>' for keyword in keywords])
            
            # Get capture time if available for DateTimeOriginal
            capture_time = self.get_capture_time()
            datetime_original = ''
            if capture_time:
                # Format as ISO 8601 with timezone
                datetime_original = f'   <exif:DateTimeOriginal>{capture_time.strftime("%Y-%m-%dT%H:%M:%S.00Z")}</exif:DateTimeOriginal>\n'
            
            # Add GPS information if provided
            gps_data = ''
            if latitude is not None and longitude is not None:
                # Convert to degrees,minutes.decimal_minutes format for XMP
                lat_deg = int(abs(latitude))
                lat_min_float = (abs(latitude) - lat_deg) * 60
                lat_min = int(lat_min_float)
                lat_sec = (lat_min_float - lat_min) * 60
                lat_decimal_min = lat_min + (lat_sec / 60.0)
                
                lon_deg = int(abs(longitude))
                lon_min_float = (abs(longitude) - lon_deg) * 60
                lon_min = int(lon_min_float)
                lon_sec = (lon_min_float - lon_min) * 60
                lon_decimal_min = lon_min + (lon_sec / 60.0)
                
                lat_dir = 'N' if latitude >= 0 else 'S'
                lon_dir = 'E' if longitude >= 0 else 'W'
                
                gps_data = f'''   <exif:GPSLatitude>{lat_deg},{lat_decimal_min:.2f}{lat_dir}</exif:GPSLatitude>
   <exif:GPSLongitude>{lon_deg},{lon_decimal_min:.2f}{lon_dir}</exif:GPSLongitude>
'''
            
            xmp_template = f'''<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 5.5.0">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:lightroom="http://ns.adobe.com/lightroom/1.0/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:exif="http://ns.adobe.com/exif/1.0/">
   <xmp:Rating>0</xmp:Rating>
   <lightroom:hierarchicalSubject>
    <rdf:Bag>
{keyword_items}
    </rdf:Bag>
   </lightroom:hierarchicalSubject>
   <dc:subject>
    <rdf:Bag>
{keyword_items}
    </rdf:Bag>
   </dc:subject>
{datetime_original}{gps_data}  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
'''
            
            with open(xmp_path, 'w', encoding='utf-8') as f:
                f.write(xmp_template)
            
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def find_videos(directory: str, recursive: bool = True, excluded_folders: Optional[List[str]] = None) -> list:
        """Find all supported video files in a directory
        
        Args:
            directory: Directory to search in
            recursive: If True, search recursively in subdirectories
            excluded_folders: List of folder names to exclude from search
        """
        videos = []
        excluded_folders = excluded_folders or []
        
        if not os.path.exists(directory):
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if recursive:
            # Recursive search
            for root, dirs, files in os.walk(directory):
                # Remove excluded directories from the search
                dirs[:] = [d for d in dirs if d not in excluded_folders]
                
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in VideoProcessor.SUPPORTED_EXTENSIONS:
                        videos.append(os.path.join(root, file))
        else:
            # Non-recursive search (only in specified directory)
            try:
                files = os.listdir(directory)
                for file in files:
                    file_path = os.path.join(directory, file)
                    # Only process files, not directories
                    if os.path.isfile(file_path):
                        ext = os.path.splitext(file)[1].lower()
                        if ext in VideoProcessor.SUPPORTED_EXTENSIONS:
                            videos.append(file_path)
            except OSError:
                raise FileNotFoundError(f"Cannot access directory: {directory}")
        
        return sorted(videos)