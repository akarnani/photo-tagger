# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Photo-tagger is a command-line tool that applies GPS coordinates from Subsurface diving logs to RAW photo EXIF data, automatically matching photos to dive sites based on capture time. It supports CR3, CR2, JPG, JPEG, TIFF, and TIF formats.

The tool supports both legacy Subsurface file formats (with dives directly under the root) and modern trip-organized formats (with dives organized within trip elements).

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt
```

### Testing
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_image_processor.py -v

# Run specific test method
python -m pytest tests/test_matcher.py::TestDiveMatcher::test_find_matches_multiple_matches -v

# Run with coverage
python -m pytest tests/ -v --cov=photo_tagger
```

### Running the Application
```bash
# Basic usage
python -m photo_tagger.cli -s path/to/divelog.ssrf -i path/to/images/

# With dry run (recommended first step)
python -m photo_tagger.cli -s path/to/divelog.ssrf -i path/to/images/ --dry-run

# With verbose logging
python -m photo_tagger.cli -s path/to/divelog.ssrf -i path/to/images/ --verbose
```

## Architecture

The application follows a modular design with clear separation of concerns:

- **`subsurface_parser.py`**: Parses Subsurface XML files (.ssrf) to extract dive sites, GPS coordinates, and timing data. Supports both legacy format (dives under root) and modern trip-organized format (dives within `<trip>` elements)
- **`image_processor.py`**: Handles EXIF metadata reading/writing using exifread and piexif libraries
- **`matcher.py`**: Implements time-based matching logic between photos and dives, with interactive user selection for ambiguous cases
- **`cli.py`**: Command-line interface using Click framework

### Key Data Classes
- `DiveSite`: Represents dive location with GPS coordinates
- `Dive`: Contains dive timing, duration, and associated site
- `MatchedPhoto`: Links photos to dives with confidence levels

### Matching Logic
- **Within dive**: Photo taken during dive duration (exact match) - automatically selected
- **Near dive**: Photo taken within 2 hours before/after dive start
- **Smart prioritization**: `within_dive` matches automatically win over `near_dive` matches
- **Interactive selection**: User prompted only when multiple matches have same confidence level

## Sample Data

The `samples/` directory contains test files:
- `IMG_0211.CR3` - Canon RAW image file for testing photo processing
- `andrew@karnani.io.ssrf` - Subsurface diving log file (XML format) with 127 dives

## Dependencies

Core libraries:
- `exifread==3.0.0` - Reading EXIF data from images
- `piexif==1.1.3` - Writing EXIF data to images  
- `xmltodict==0.13.0` - XML parsing for Subsurface files
- `python-dateutil==2.8.2` - Date/time parsing
- `click==8.1.7` - Command-line interface
- `pytest==7.4.3` - Testing framework

## Important Development Notes

- The application handles both legacy and modern Subsurface file formats
- Time matching uses a 2-hour window around dive times for "near" matches
- Interactive prompts only appear when multiple matches have the same confidence level
- The tool is idempotent - safe to run multiple times on the same photo set
- Always test with dry-run mode first when making changes to matching logic
- EXIF writing requires proper file permissions - handle read-only files gracefully