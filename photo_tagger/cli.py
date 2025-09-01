"""Command line interface for photo-tagger"""

import os
import sys
import logging
from typing import Optional

import click

from .subsurface_parser import SubsurfaceParser
from .image_processor import ImageProcessor
from .matcher import InteractiveMatcher


def setup_logging(verbose: bool) -> logging.Logger:
    """Setup logging configuration"""
    logger = logging.getLogger('photo_tagger')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(levelname)s: %(message)s' if not verbose 
        else '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


@click.command()
@click.option('--subsurface-file', '-s', required=True, 
              help='Path to Subsurface diving log file (.ssrf)')
@click.option('--images-dir', '-i', required=True,
              help='Directory containing RAW image files')
@click.option('--verbose', '-v', is_flag=True,
              help='Enable verbose logging')
@click.option('--dry-run', '-n', is_flag=True,
              help='Show what would be done without making changes')
def main(subsurface_file: str, images_dir: str, verbose: bool, dry_run: bool):
    """Apply dive site GPS coordinates to photo EXIF data.
    
    This tool matches photos to dive sites based on capture time and applies
    GPS coordinates from the dive sites to the photo EXIF data.
    """
    logger = setup_logging(verbose)
    
    if dry_run:
        click.echo("DRY RUN MODE - No changes will be made to files\n")
    
    try:
        # Parse subsurface file
        logger.info(f"Parsing subsurface file: {subsurface_file}")
        parser = SubsurfaceParser(subsurface_file)
        dives = parser.parse()
        
        if not dives:
            logger.error("No dives found in subsurface file")
            sys.exit(1)
        
        logger.info(f"Found {len(dives)} dives")
        
        # Find images
        logger.info(f"Scanning for images in: {images_dir}")
        images = ImageProcessor.find_images(images_dir)
        
        if not images:
            logger.error("No supported images found in directory")
            sys.exit(1)
        
        logger.info(f"Found {len(images)} images")
        
        # Create matcher
        matcher = InteractiveMatcher(dives)
        
        # Process each image
        processed_count = 0
        skipped_count = 0
        error_count = 0
        
        for image_path in images:
            logger.info(f"Processing: {os.path.basename(image_path)}")
            
            try:
                # Get image capture time
                processor = ImageProcessor(image_path)
                capture_time = processor.get_capture_time()
                
                if not capture_time:
                    logger.warning(f"No capture time found for {os.path.basename(image_path)}")
                    skipped_count += 1
                    continue
                
                logger.debug(f"Image capture time: {capture_time}")
                
                # Check for existing GPS
                existing_gps = processor.get_current_gps()
                if existing_gps and not dry_run:
                    logger.debug(f"Existing GPS coordinates: {existing_gps}")
                
                # Find match
                match = matcher.get_user_confirmed_match(image_path)
                
                if not match:
                    logger.info(f"No dive match selected for {os.path.basename(image_path)}")
                    skipped_count += 1
                    continue
                
                # Check if dive site has GPS coordinates
                if not (match.dive.site.latitude and match.dive.site.longitude):
                    logger.warning(f"Dive site '{match.dive.site.name}' has no GPS coordinates")
                    skipped_count += 1
                    continue
                
                # Show what we're doing
                if dry_run:
                    click.echo(f"""
WOULD UPDATE: {os.path.basename(image_path)}
  Photo time: {capture_time.strftime('%Y-%m-%d %H:%M:%S')}
  Matched to: Dive #{match.dive.number} - {match.dive.site.name}
  Dive time: {match.dive.time.strftime('%Y-%m-%d %H:%M:%S')}
  GPS: {match.dive.site.latitude:.6f}, {match.dive.site.longitude:.6f}
  Confidence: {match.confidence}
  XMP Keywords: {match.dive.site.name}
""")
                    processed_count += 1
                else:
                    # Apply GPS coordinates and XMP keywords
                    logger.info(f"Applying GPS and keywords from '{match.dive.site.name}' to {os.path.basename(image_path)}")
                    
                    gps_success = False
                    xmp_success = False
                    
                    # Try to apply GPS coordinates (may fail for some RAW formats)
                    try:
                        gps_success = processor.set_gps_coordinates(
                            match.dive.site.latitude, 
                            match.dive.site.longitude,
                            dry_run=False
                        )
                        if gps_success:
                            logger.info(f"Successfully updated GPS coordinates in image file")
                    except Exception as e:
                        logger.warning(f"Could not update GPS in image file: {e}")
                    
                    # Create XMP sidecar with dive site name as keyword and GPS coordinates
                    # Include GPS in XMP if image GPS writing failed
                    try:
                        xmp_success = processor.create_xmp_sidecar(
                            keywords=[match.dive.site.name],
                            latitude=match.dive.site.latitude if not gps_success else None,
                            longitude=match.dive.site.longitude if not gps_success else None,
                            dry_run=False
                        )
                        if xmp_success:
                            if gps_success:
                                logger.info(f"Successfully created XMP sidecar with keywords")
                            else:
                                logger.info(f"Successfully created XMP sidecar with keywords and GPS coordinates")
                    except Exception as e:
                        logger.error(f"Failed to create XMP sidecar: {e}")
                    
                    # Consider it successful if at least XMP was created
                    if xmp_success:
                        processed_count += 1
                        if gps_success:
                            logger.info(f"GPS coordinates written to image file and XMP sidecar created")
                        else:
                            logger.info(f"GPS coordinates written to XMP sidecar (image format not supported)")
                    else:
                        logger.error(f"Failed to create XMP sidecar")
                        error_count += 1
                        
            except Exception as e:
                logger.error(f"Error processing {os.path.basename(image_path)}: {e}")
                error_count += 1
                continue
        
        # Summary
        click.echo(f"\n{'DRY RUN ' if dry_run else ''}SUMMARY:")
        click.echo(f"  Total images: {len(images)}")
        click.echo(f"  {'Would update' if dry_run else 'Updated'}: {processed_count}")
        click.echo(f"  Skipped: {skipped_count}")
        if error_count > 0:
            click.echo(f"  Errors: {error_count}")
        
        if error_count > 0:
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()