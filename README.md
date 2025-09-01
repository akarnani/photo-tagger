# Photo Tagger

A command-line tool that applies GPS coordinates from Subsurface diving logs to RAW photo EXIF data, automatically matching photos to dive sites based on capture time.

## Features

- **Automatic time-based matching**: Matches photos to dives based on capture time
- **Interactive selection**: Prompts user when multiple dives match a photo's timestamp
- **GPS coordinate embedding**: Writes dive site GPS data to photo EXIF metadata
- **Dry-run mode**: Preview changes without modifying files
- **Verbose logging**: Detailed output for troubleshooting
- **Idempotent**: Safe to run multiple times as you add new photos
- **Multiple file format support**: CR3, CR2, JPG, JPEG, TIFF, TIF

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/akarnani/photo-tagger.git
   cd photo-tagger
   ```

2. Create and activate virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Usage
```bash
python -m photo_tagger.cli -s path/to/divelog.ssrf -i path/to/images/
```

### With Dry Run (Preview Changes)
```bash
python -m photo_tagger.cli -s path/to/divelog.ssrf -i path/to/images/ --dry-run
```

### With Verbose Logging
```bash
python -m photo_tagger.cli -s path/to/divelog.ssrf -i path/to/images/ --verbose
```

### Command Line Options

- `-s, --subsurface-file`: Path to Subsurface diving log file (.ssrf) [required]
- `-i, --images-dir`: Directory containing RAW image files [required]
- `-v, --verbose`: Enable verbose logging
- `-n, --dry-run`: Show what would be done without making changes

## How It Works

1. **Parse Diving Log**: Extracts dive sites and GPS coordinates from your Subsurface file
2. **Scan Images**: Finds all supported image files in the specified directory
3. **Extract Timestamps**: Reads capture time from each photo's EXIF data
4. **Match by Time**: Links photos to dives if captured within the dive duration
5. **Handle Ambiguity**: Prompts user to select when multiple dives match
6. **Apply GPS Data**: Writes dive site coordinates to photo EXIF metadata

## Time Matching Logic

- **Within dive**: Photo taken during dive duration (exact match)
- **Near dive**: Photo taken within 2 hours before/after dive start
- **User selection**: Interactive prompt for ambiguous cases
- **No match**: Photo timestamp doesn't align with any dive

## Example Workflow

```bash
# First, do a dry run to see what will be changed
python -m photo_tagger.cli -s my_dives.ssrf -i ~/Photos/Diving/ --dry-run --verbose

# If everything looks good, apply the changes
python -m photo_tagger.cli -s my_dives.ssrf -i ~/Photos/Diving/ --verbose
```

## Sample Output

```
DRY RUN MODE - No changes will be made to files

INFO: Parsing subsurface file: samples/andrew@karnani.io.ssrf  
INFO: Found 127 dives
INFO: Scanning for images in: samples/
INFO: Found 1 images
INFO: Processing: IMG_0211.CR3

Multiple dive matches found for: samples/IMG_0211.CR3
Photo capture time: 2024-08-15 14:30:00

1. Dive #45: Spanish Anchor
   Time: 2024-08-15 10:30:00 (Duration: 45min)
   GPS: 21.645670, -72.475000
   Confidence: near_dive

2. Dive #46: Gullies  
   Time: 2024-08-15 15:45:00 (Duration: 38min)
   GPS: 21.676950, -72.469670
   Confidence: near_dive

0. Skip this photo
Select dive (0 to skip): 2

WOULD UPDATE: IMG_0211.CR3
  Photo time: 2024-08-15 14:30:00
  Matched to: Dive #46 - Gullies
  Dive time: 2024-08-15 15:45:00  
  GPS: 21.676950, -72.469670
  Confidence: near_dive

DRY RUN SUMMARY:
  Total images: 1
  Would update: 1
  Skipped: 0
```

## Testing

Run the test suite:
```bash
python -m pytest tests/ -v
```

## Architecture

- `subsurface_parser.py`: Parses Subsurface XML files
- `image_processor.py`: Handles EXIF metadata reading/writing  
- `matcher.py`: Time-based matching logic and user interaction
- `cli.py`: Command-line interface

## Error Handling

- **Missing timestamps**: Photos without EXIF datetime are skipped
- **No GPS data**: Dive sites without coordinates are skipped
- **File permissions**: Read-only files generate errors
- **Invalid XML**: Corrupted dive logs are rejected
- **Interrupted execution**: Ctrl+C exits gracefully

## Requirements

- Python 3.7+
- ExifTool (optional, for enhanced EXIF processing)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite: `python -m pytest tests/ -v`
6. Submit a pull request

## License

MIT License - see LICENSE file for details
