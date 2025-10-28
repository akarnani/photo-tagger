"""Image processing and EXIF metadata handling"""

import os
import piexif
import exifread
import exiv2
from datetime import datetime
from typing import Optional, Tuple, List
from lxml import etree


class ImageProcessor:
    """Handles reading and writing EXIF metadata in images"""
    
    SUPPORTED_EXTENSIONS = {'.cr3', '.cr2', '.jpg', '.jpeg', '.tiff', '.tif'}
    
    def __init__(self, image_path: str):
        self.image_path = image_path
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        # Check if file extension is supported
        ext = os.path.splitext(image_path)[1].lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported image format: {ext}")
    
    def get_capture_time(self) -> Optional[datetime]:
        """Extract the capture time from image EXIF data"""
        # First try exiv2 (best support for RAW formats including CR3)
        capture_time = self._get_capture_time_exiv2()
        if capture_time:
            return capture_time
        
        # Fallback to piexif (works with JPEG, TIFF)
        capture_time = self._get_capture_time_piexif()
        if capture_time:
            return capture_time
        
        # Last resort: exifread
        return self._get_capture_time_exifread()
    
    def _get_capture_time_exiv2(self) -> Optional[datetime]:
        """Extract capture time using exiv2 library (best for RAW formats)"""
        try:
            image = exiv2.ImageFactory.open(self.image_path)
            image.readMetadata()
            
            exif_data = image.exifData()
            
            # Try different EXIF tags in order of preference
            datetime_tags = [
                'Exif.Photo.DateTimeOriginal',    # When photo was taken (preferred)
                'Exif.Photo.DateTimeDigitized',   # When photo was digitized
                'Exif.Image.DateTime'             # File modification time
            ]
            
            for tag_name in datetime_tags:
                for tag in exif_data:
                    if tag.key() == tag_name:
                        try:
                            # EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
                            dt_str = tag.print()
                            return datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
                        except ValueError:
                            continue
            
            return None
            
        except Exception:
            return None
    
    def _get_capture_time_piexif(self) -> Optional[datetime]:
        """Extract capture time using piexif library"""
        try:
            exif_data = piexif.load(self.image_path)
            
            # Try different EXIF fields for date/time
            datetime_fields = [
                exif_data.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal),
                exif_data.get("Exif", {}).get(piexif.ExifIFD.DateTimeDigitized),
                exif_data.get("0th", {}).get(piexif.ImageIFD.DateTime)
            ]
            
            for dt_field in datetime_fields:
                if dt_field:
                    try:
                        # EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
                        dt_str = dt_field.decode('utf-8') if isinstance(dt_field, bytes) else dt_field
                        return datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
                    except (ValueError, UnicodeDecodeError):
                        continue
            
            return None
            
        except Exception:
            # Piexif failed, will try exifread
            return None
    
    def _get_capture_time_exifread(self) -> Optional[datetime]:
        """Extract capture time using exifread library (better for RAW formats)"""
        try:
            with open(self.image_path, 'rb') as f:
                tags = exifread.process_file(f)
            
            # Try different EXIF tags in order of preference
            datetime_tags = [
                'EXIF DateTimeOriginal',    # When photo was taken (preferred)
                'EXIF DateTimeDigitized',   # When photo was digitized
                'Image DateTime',           # File modification time
                'DateTime',                 # Alternative DateTime tag
                'EXIF DateTime'             # Another alternative
            ]
            
            for tag_name in datetime_tags:
                if tag_name in tags:
                    try:
                        # EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
                        dt_str = str(tags[tag_name])
                        return datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
                    except ValueError:
                        continue
            
            return None
            
        except Exception:
            return None
    
    def get_current_gps(self) -> Optional[Tuple[float, float]]:
        """Get existing GPS coordinates from image EXIF data"""
        try:
            exif_data = piexif.load(self.image_path)
            gps_data = exif_data.get("GPS")
            
            if not gps_data:
                return None
            
            # Extract latitude
            lat_ref = gps_data.get(piexif.GPSIFD.GPSLatitudeRef)
            lat_data = gps_data.get(piexif.GPSIFD.GPSLatitude)
            
            # Extract longitude  
            lon_ref = gps_data.get(piexif.GPSIFD.GPSLongitudeRef)
            lon_data = gps_data.get(piexif.GPSIFD.GPSLongitude)
            
            if not all([lat_ref, lat_data, lon_ref, lon_data]):
                return None
            
            # Convert DMS to decimal degrees
            latitude = self._dms_to_decimal(lat_data)
            longitude = self._dms_to_decimal(lon_data)
            
            # Apply hemisphere indicators
            if lat_ref == b'S':
                latitude = -latitude
            if lon_ref == b'W':
                longitude = -longitude
            
            return latitude, longitude
            
        except Exception:
            return None
    
    def set_gps_coordinates(self, latitude: float, longitude: float, dry_run: bool = False) -> bool:
        """Set GPS coordinates in image EXIF data"""
        if dry_run:
            return True
        
        # First try exiv2 (best for RAW formats including CR3)
        if self._set_gps_coordinates_exiv2(latitude, longitude):
            return True
        
        # Fallback to piexif (works with JPEG, TIFF)
        return self._set_gps_coordinates_piexif(latitude, longitude)
    
    def _set_gps_coordinates_exiv2(self, latitude: float, longitude: float) -> bool:
        """Set GPS coordinates using exiv2 library (best for RAW formats)"""
        try:
            image = exiv2.ImageFactory.open(self.image_path)
            image.readMetadata()
            
            exif_data = image.exifData()
            
            # Set GPS coordinates in EXIF format expected by exiv2
            # Convert decimal degrees to rational format (degrees, minutes, seconds)
            lat_deg, lat_min, lat_sec = self._decimal_to_dms_components(abs(latitude))
            lon_deg, lon_min, lon_sec = self._decimal_to_dms_components(abs(longitude))
            
            # Set GPS version
            exif_data['Exif.GPSInfo.GPSVersionID'] = '2 0 0 0'
            
            # Set latitude
            exif_data['Exif.GPSInfo.GPSLatitudeRef'] = 'N' if latitude >= 0 else 'S'
            exif_data['Exif.GPSInfo.GPSLatitude'] = f'{lat_deg}/1 {lat_min}/1 {int(lat_sec * 1000)}/1000'
            
            # Set longitude
            exif_data['Exif.GPSInfo.GPSLongitudeRef'] = 'E' if longitude >= 0 else 'W'
            exif_data['Exif.GPSInfo.GPSLongitude'] = f'{lon_deg}/1 {lon_min}/1 {int(lon_sec * 1000)}/1000'
            
            # Write back to file
            image.writeMetadata()
            
            return True
            
        except Exception:
            return False
    
    def _set_gps_coordinates_piexif(self, latitude: float, longitude: float) -> bool:
        """Set GPS coordinates using piexif library (for JPEG, TIFF)"""
        try:
            # Load existing EXIF data
            exif_data = piexif.load(self.image_path)
            
            # Create GPS data
            gps_data = {
                piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
                piexif.GPSIFD.GPSLatitudeRef: b'N' if latitude >= 0 else b'S',
                piexif.GPSIFD.GPSLatitude: self._decimal_to_dms(abs(latitude)),
                piexif.GPSIFD.GPSLongitudeRef: b'E' if longitude >= 0 else b'W',
                piexif.GPSIFD.GPSLongitude: self._decimal_to_dms(abs(longitude)),
            }
            
            # Update EXIF data
            exif_data["GPS"] = gps_data
            
            # Convert back to bytes
            exif_bytes = piexif.dump(exif_data)
            
            # Write back to file
            piexif.insert(exif_bytes, self.image_path)
            
            return True
            
        except Exception:
            return False
    
    def _dms_to_decimal(self, dms_tuple) -> float:
        """Convert degrees, minutes, seconds tuple to decimal degrees"""
        degrees = float(dms_tuple[0][0]) / float(dms_tuple[0][1])
        minutes = float(dms_tuple[1][0]) / float(dms_tuple[1][1])
        seconds = float(dms_tuple[2][0]) / float(dms_tuple[2][1])
        
        return degrees + (minutes / 60) + (seconds / 3600)
    
    def _decimal_to_dms(self, decimal_degrees: float) -> Tuple:
        """Convert decimal degrees to degrees, minutes, seconds tuple for EXIF"""
        degrees = int(decimal_degrees)
        minutes_float = (decimal_degrees - degrees) * 60
        minutes = int(minutes_float)
        seconds = (minutes_float - minutes) * 60
        
        # Convert to rational numbers for EXIF format
        return (
            (degrees, 1),
            (minutes, 1), 
            (int(seconds * 1000), 1000)  # Store seconds with 3 decimal places precision
        )
    
    def _decimal_to_dms_components(self, decimal_degrees: float) -> tuple:
        """Convert decimal degrees to separate degrees, minutes, seconds components"""
        degrees = int(decimal_degrees)
        minutes_float = (decimal_degrees - degrees) * 60
        minutes = int(minutes_float)
        seconds = (minutes_float - minutes) * 60
        
        return degrees, minutes, seconds
    
    @staticmethod
    def find_images(directory: str, recursive: bool = True, excluded_folders: Optional[List[str]] = None) -> list:
        """Find all supported image files in a directory
        
        Args:
            directory: Directory to search in
            recursive: If True, search recursively in subdirectories. If False, only search the specified directory.
            excluded_folders: List of folder names to exclude from search
        """
        images = []
        excluded_folders = excluded_folders or []
        
        if not os.path.exists(directory):
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if recursive:
            # Recursive search with folder exclusion
            for root, dirs, files in os.walk(directory):
                # Remove excluded directories from the search
                dirs[:] = [d for d in dirs if d not in excluded_folders]
                
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in ImageProcessor.SUPPORTED_EXTENSIONS:
                        images.append(os.path.join(root, file))
        else:
            # Non-recursive search (only in specified directory)
            try:
                files = os.listdir(directory)
                for file in files:
                    file_path = os.path.join(directory, file)
                    # Only process files, not directories
                    if os.path.isfile(file_path):
                        ext = os.path.splitext(file)[1].lower()
                        if ext in ImageProcessor.SUPPORTED_EXTENSIONS:
                            images.append(file_path)
            except OSError:
                raise FileNotFoundError(f"Cannot access directory: {directory}")
        
        return sorted(images)
    
    def create_xmp_sidecar(self, keywords: List[str], latitude: Optional[float] = None, longitude: Optional[float] = None, dry_run: bool = False) -> bool:
        """Create or update XMP sidecar file with dive site keywords"""
        if dry_run:
            return True
            
        # Generate XMP filename (same as image but with .xmp extension)
        xmp_path = os.path.splitext(self.image_path)[0] + '.xmp'
        
        try:
            if os.path.exists(xmp_path):
                # Update existing XMP file
                return self._update_existing_xmp(xmp_path, keywords, latitude, longitude)
            else:
                # Create new XMP file
                return self._create_new_xmp(xmp_path, keywords, latitude, longitude)
            
        except Exception as e:
            raise RuntimeError(f"Failed to create XMP sidecar for {self.image_path}: {e}")
    
    def _read_existing_xmp_keywords(self, xmp_path: str) -> List[str]:
        """Read existing keywords from XMP file"""
        try:
            tree = etree.parse(xmp_path)
            root = tree.getroot()
            
            # Define namespaces
            namespaces = {
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                'dc': 'http://purl.org/dc/elements/1.1/',
                'lightroom': 'http://ns.adobe.com/lightroom/1.0/'
            }
            
            keywords = []
            
            # Read from dc:subject
            dc_subjects = root.xpath('//dc:subject/rdf:Bag/rdf:li/text()', namespaces=namespaces)
            keywords.extend(dc_subjects)
            
            # Read from lightroom:hierarchicalSubject
            lr_subjects = root.xpath('//lightroom:hierarchicalSubject/rdf:Bag/rdf:li/text()', namespaces=namespaces)
            keywords.extend(lr_subjects)
            
            # Remove duplicates and return
            return list(set(keywords))
            
        except Exception:
            # If we can't read existing keywords, return empty list
            return []
    
    def _create_xmp_content(self, keywords: List[str], latitude: Optional[float] = None, longitude: Optional[float] = None) -> str:
        """Create XMP content with keywords"""
        # Create keyword list XML
        keyword_items = '\\n'.join([f'     <rdf:li>{keyword}</rdf:li>' for keyword in keywords])
        
        # Get capture time if available for DateTimeOriginal
        capture_time = self.get_capture_time()
        datetime_original = ''
        if capture_time:
            # Format as ISO 8601 with timezone (following the sample)
            datetime_original = f'   <exif:DateTimeOriginal>{capture_time.strftime("%Y-%m-%dT%H:%M:%S.00Z")}</exif:DateTimeOriginal>\\n'
        
        # Add GPS information if provided
        gps_data = ''
        if latitude is not None and longitude is not None:
            # Convert to degrees,minutes.decimal_minutes format for XMP
            lat_deg, lat_min, lat_sec = self._decimal_to_dms_components(abs(latitude))
            lon_deg, lon_min, lon_sec = self._decimal_to_dms_components(abs(longitude))
            
            # Convert seconds back to decimal minutes
            lat_decimal_min = lat_min + (lat_sec / 60.0)
            lon_decimal_min = lon_min + (lon_sec / 60.0)
            
            # XMP format: degrees,minutes.decimal_minutes followed by direction
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
        return xmp_template
    
    def _update_existing_xmp(self, xmp_path: str, keywords: List[str], latitude: Optional[float] = None, longitude: Optional[float] = None) -> bool:
        """Update existing XMP file while preserving other metadata"""
        try:
            # Parse existing XMP file
            tree = etree.parse(xmp_path)
            root = tree.getroot()
            
            # Define namespaces
            namespaces = {
                'x': 'adobe:ns:meta/',
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                'dc': 'http://purl.org/dc/elements/1.1/',
                'lightroom': 'http://ns.adobe.com/lightroom/1.0/',
                'exif': 'http://ns.adobe.com/exif/1.0/'
            }
            
            # Find or create rdf:Description element
            desc = root.find('.//rdf:Description', namespaces)
            if desc is None:
                raise ValueError("No rdf:Description element found in XMP file")
            
            # Get existing keywords and combine with new ones
            existing_keywords = self._read_existing_xmp_keywords(xmp_path)
            all_keywords = list(set(existing_keywords + keywords))
            all_keywords.sort()
            
            # Update dc:subject keywords
            self._update_xmp_keywords(desc, all_keywords, namespaces)
            
            # Update GPS coordinates if provided
            if latitude is not None and longitude is not None:
                self._update_xmp_gps(desc, latitude, longitude, namespaces)
            
            # Update DateTimeOriginal if we can get capture time
            capture_time = self.get_capture_time()
            if capture_time:
                self._update_xmp_datetime(desc, capture_time, namespaces)
            
            # Write back to file with proper XML declaration and formatting
            tree.write(xmp_path, encoding='utf-8', xml_declaration=True, pretty_print=True)
            
            return True
            
        except Exception:
            return False
    
    def _create_new_xmp(self, xmp_path: str, keywords: List[str], latitude: Optional[float] = None, longitude: Optional[float] = None) -> bool:
        """Create new XMP file using the original template method"""
        try:
            xmp_content = self._create_xmp_content(keywords, latitude, longitude)
            with open(xmp_path, 'w', encoding='utf-8') as f:
                f.write(xmp_content)
            return True
        except Exception:
            return False
    
    def _update_xmp_keywords(self, desc_element, keywords: List[str], namespaces: dict):
        """Update keyword elements in XMP Description"""
        # Update dc:subject
        dc_subject = desc_element.find('dc:subject', namespaces)
        if dc_subject is not None:
            desc_element.remove(dc_subject)
        
        # Create new dc:subject element
        dc_subject = etree.SubElement(desc_element, '{http://purl.org/dc/elements/1.1/}subject')
        dc_bag = etree.SubElement(dc_subject, '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Bag')
        for keyword in keywords:
            li = etree.SubElement(dc_bag, '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li')
            li.text = keyword
        
        # Update lightroom:hierarchicalSubject
        lr_subject = desc_element.find('lightroom:hierarchicalSubject', namespaces)
        if lr_subject is not None:
            desc_element.remove(lr_subject)
        
        # Create new lightroom:hierarchicalSubject element
        lr_subject = etree.SubElement(desc_element, '{http://ns.adobe.com/lightroom/1.0/}hierarchicalSubject')
        lr_bag = etree.SubElement(lr_subject, '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Bag')
        for keyword in keywords:
            li = etree.SubElement(lr_bag, '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li')
            li.text = keyword
    
    def _update_xmp_gps(self, desc_element, latitude: float, longitude: float, namespaces: dict):
        """Update GPS coordinates in XMP Description"""
        # Remove existing GPS elements if they exist
        for gps_tag in ['exif:GPSLatitude', 'exif:GPSLongitude']:
            existing = desc_element.find(gps_tag, namespaces)
            if existing is not None:
                desc_element.remove(existing)
        
        # Convert to degrees,minutes.decimal_minutes format for XMP
        lat_deg, lat_min, lat_sec = self._decimal_to_dms_components(abs(latitude))
        lon_deg, lon_min, lon_sec = self._decimal_to_dms_components(abs(longitude))
        
        # Convert seconds back to decimal minutes
        lat_decimal_min = lat_min + (lat_sec / 60.0)
        lon_decimal_min = lon_min + (lon_sec / 60.0)
        
        # XMP format: degrees,minutes.decimal_minutes followed by direction
        lat_dir = 'N' if latitude >= 0 else 'S'
        lon_dir = 'E' if longitude >= 0 else 'W'
        
        # Add GPS elements
        lat_elem = etree.SubElement(desc_element, '{http://ns.adobe.com/exif/1.0/}GPSLatitude')
        lat_elem.text = f'{lat_deg},{lat_decimal_min:.2f}{lat_dir}'
        
        lon_elem = etree.SubElement(desc_element, '{http://ns.adobe.com/exif/1.0/}GPSLongitude')
        lon_elem.text = f'{lon_deg},{lon_decimal_min:.2f}{lon_dir}'
    
    def _update_xmp_datetime(self, desc_element, capture_time: datetime, namespaces: dict):
        """Update DateTimeOriginal in XMP Description"""
        # Remove existing DateTimeOriginal if it exists
        existing = desc_element.find('exif:DateTimeOriginal', namespaces)
        if existing is not None:
            desc_element.remove(existing)
        
        # Add new DateTimeOriginal
        dt_elem = etree.SubElement(desc_element, '{http://ns.adobe.com/exif/1.0/}DateTimeOriginal')
        dt_elem.text = capture_time.strftime('%Y-%m-%dT%H:%M:%S.00Z')