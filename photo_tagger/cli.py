"""Command line interface for photo-tagger"""

import os
import sys
import logging

import click

from .subsurface_parser import SubsurfaceParser
from .media_processor import MediaProcessor
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


def _check_camera_tag_warnings(dives, matched_dives, photo_timestamps):
    """Check for camera tag mismatches and print warnings

    Args:
        dives: List of all dives
        matched_dives: Set of dive numbers that had photos matched
        photo_timestamps: List of all photo capture timestamps
    """
    if not photo_timestamps:
        return

    # Determine photo date range
    oldest_photo = min(photo_timestamps)
    newest_photo = max(photo_timestamps)

    # Find dives within the photo date range
    dives_in_range = [d for d in dives if oldest_photo <= d.time <= newest_photo]

    # Find dives with matches but no "camera" tag
    untagged_with_photos = []
    for dive in dives_in_range:
        if dive.number in matched_dives and 'camera' not in dive.tags:
            untagged_with_photos.append(dive)

    # Find dives with "camera" tag but no matches
    tagged_without_photos = []
    for dive in dives_in_range:
        if 'camera' in dive.tags and dive.number not in matched_dives:
            tagged_without_photos.append(dive)

    # Print warnings if any issues found
    if untagged_with_photos or tagged_without_photos:
        click.echo("\n⚠️  CAMERA TAG WARNINGS:")

        if untagged_with_photos:
            click.echo("\n  Dives with matched photos but missing 'camera' tag:")
            for dive in untagged_with_photos:
                click.echo(f"    • Dive #{dive.number} - {dive.site.name} ({dive.time.strftime('%Y-%m-%d')})")

        if tagged_without_photos:
            click.echo("\n  Dives tagged with 'camera' but no matching photos:")
            for dive in tagged_without_photos:
                click.echo(f"    • Dive #{dive.number} - {dive.site.name} ({dive.time.strftime('%Y-%m-%d')})")


@click.command()
@click.option('--subsurface-file', '-s', required=True, 
              help='Path to Subsurface diving log file (.ssrf)')
@click.option('--images-dir', '-i', required=True,
              help='Directory containing media files (images and videos)')
@click.option('--verbose', '-v', is_flag=True,
              help='Enable verbose logging')
@click.option('--dry-run', '-n', is_flag=True,
              help='Show what would be done without making changes')
@click.option('--recursive', '-r', is_flag=True,
              help='Search for media files recursively in subdirectories')
@click.option('--exclude-folders', '-e', multiple=True,
              help='Folder names to exclude from recursive search (can be specified multiple times)')
def main(subsurface_file: str, images_dir: str, verbose: bool, dry_run: bool, recursive: bool, exclude_folders: tuple):
    """Apply dive site GPS coordinates to media file metadata.
    
    This tool matches photos and videos to dive sites based on capture time and applies
    GPS coordinates from the dive sites to the media file metadata.
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
        
        # Find media files
        excluded_folders_list = list(exclude_folders) if exclude_folders else None
        exclude_info = f" (excluding: {', '.join(excluded_folders_list)})" if excluded_folders_list else ""
        logger.info(f"Scanning for media files in: {images_dir}{'(recursive)' if recursive else ''}{exclude_info}")
        media_files = MediaProcessor.find_media_files(images_dir, recursive=recursive, excluded_folders=excluded_folders_list)
        
        if not media_files:
            logger.error("No supported media files found in directory")
            sys.exit(1)
        
        logger.info(f"Found {len(media_files)} media files")
        
        # Create matcher
        matcher = InteractiveMatcher(dives)
        
        # Process each media file
        processed_count = 0
        skipped_count = 0
        error_count = 0
        matched_dives = set()  # Track which dives had photos matched
        photo_timestamps = []  # Track all photo timestamps to determine date range

        for media_path in media_files:
            logger.info(f"Processing: {os.path.basename(media_path)}")
            
            try:
                # Create appropriate processor for the media file
                processor = MediaProcessor.create_processor(media_path)
                capture_time = processor.get_capture_time()
                
                if not capture_time:
                    logger.warning(f"No capture time found for {os.path.basename(media_path)}")
                    skipped_count += 1
                    continue

                # Track photo timestamp for date range analysis
                photo_timestamps.append(capture_time)

                logger.debug(f"Media capture time: {capture_time}")
                
                # Check for existing GPS
                existing_gps = processor.get_current_gps()
                if existing_gps and not dry_run:
                    logger.debug(f"Existing GPS coordinates: {existing_gps}")
                
                # Find match
                match = matcher.get_user_confirmed_match(media_path)

                if not match:
                    logger.info(f"No dive match selected for {os.path.basename(media_path)}")
                    skipped_count += 1
                    continue

                # Track that this dive had a photo matched to it
                matched_dives.add(match.dive.number)

                # Check if dive site has GPS coordinates
                if not (match.dive.site.latitude and match.dive.site.longitude):
                    logger.warning(f"Dive site '{match.dive.site.name}' has no GPS coordinates")
                    skipped_count += 1
                    continue
                
                # Show what we're doing
                if dry_run:
                    click.echo(f"""
WOULD UPDATE: {os.path.basename(media_path)}
  Capture time: {capture_time.strftime('%Y-%m-%d %H:%M:%S')}
  Matched to: Dive #{match.dive.number} - {match.dive.site.name}
  Dive time: {match.dive.time.strftime('%Y-%m-%d %H:%M:%S')}
  GPS: {match.dive.site.latitude:.6f}, {match.dive.site.longitude:.6f}
  Confidence: {match.confidence}
  XMP Keywords: {match.dive.site.name}
""")
                    processed_count += 1
                else:
                    # Apply GPS coordinates and XMP keywords
                    logger.info(f"Applying GPS and keywords from '{match.dive.site.name}' to {os.path.basename(media_path)}")
                    
                    gps_success = False
                    xmp_success = False
                    
                    # Try to apply GPS coordinates (may fail for some formats)
                    try:
                        gps_success = processor.set_gps_coordinates(
                            match.dive.site.latitude, 
                            match.dive.site.longitude,
                            dry_run=False
                        )
                        if gps_success:
                            logger.info("Successfully updated GPS coordinates in media file")
                    except Exception as e:
                        logger.warning(f"Could not update GPS in media file: {e}")
                    
                    # Create XMP sidecar with dive site name as keyword and GPS coordinates
                    # Include GPS in XMP if media GPS writing failed
                    try:
                        xmp_success = processor.create_xmp_sidecar(
                            keywords=[match.dive.site.name],
                            latitude=match.dive.site.latitude if not gps_success else None,
                            longitude=match.dive.site.longitude if not gps_success else None,
                            dry_run=False
                        )
                        if xmp_success:
                            if gps_success:
                                logger.info("Successfully created XMP sidecar with keywords")
                            else:
                                logger.info("Successfully created XMP sidecar with keywords and GPS coordinates")
                    except Exception as e:
                        logger.error(f"Failed to create XMP sidecar: {e}")
                    
                    # Consider it successful if at least XMP was created
                    if xmp_success:
                        processed_count += 1
                        if gps_success:
                            logger.info("GPS coordinates written to media file and XMP sidecar created")
                        else:
                            logger.info("GPS coordinates written to XMP sidecar (media format not supported)")
                    else:
                        logger.error("Failed to create XMP sidecar")
                        error_count += 1
                        
            except Exception as e:
                logger.error(f"Error processing {os.path.basename(media_path)}: {e}")
                error_count += 1
                continue
        
        # Summary
        click.echo(f"\n{'DRY RUN ' if dry_run else ''}SUMMARY:")
        click.echo(f"  Total media files: {len(media_files)}")
        click.echo(f"  {'Would update' if dry_run else 'Updated'}: {processed_count}")
        click.echo(f"  Skipped: {skipped_count}")
        if error_count > 0:
            click.echo(f"  Errors: {error_count}")

        # Camera tag analysis
        if photo_timestamps:
            _check_camera_tag_warnings(dives, matched_dives, photo_timestamps)

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