"""Unified media processing for both images and videos"""

import os
from typing import Optional, List, Union

from .image_processor import ImageProcessor
from .video_processor import VideoProcessor


class MediaProcessor:
    """Factory class to handle both images and videos uniformly"""
    
    @staticmethod
    def create_processor(file_path: str) -> Union[ImageProcessor, VideoProcessor]:
        """Create appropriate processor based on file extension"""
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext in ImageProcessor.SUPPORTED_EXTENSIONS:
            return ImageProcessor(file_path)
        elif ext in VideoProcessor.SUPPORTED_EXTENSIONS:
            return VideoProcessor(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
    
    @staticmethod
    def find_media_files(directory: str, recursive: bool = True, excluded_folders: Optional[List[str]] = None) -> List[str]:
        """Find all supported media files (images and videos) in a directory
        
        Args:
            directory: Directory to search in
            recursive: If True, search recursively in subdirectories
            excluded_folders: List of folder names to exclude from search
        
        Returns:
            List of file paths for all supported media files
        """
        # Find both images and videos
        images = ImageProcessor.find_images(directory, recursive, excluded_folders)
        videos = VideoProcessor.find_videos(directory, recursive, excluded_folders)
        
        # Combine and sort all media files
        all_media = images + videos
        return sorted(all_media)
    
    @staticmethod
    def get_supported_extensions() -> set:
        """Get all supported file extensions"""
        return ImageProcessor.SUPPORTED_EXTENSIONS | VideoProcessor.SUPPORTED_EXTENSIONS
    
    @staticmethod
    def is_supported_file(file_path: str) -> bool:
        """Check if a file is supported by any processor"""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in MediaProcessor.get_supported_extensions()