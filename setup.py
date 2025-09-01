from setuptools import setup, find_packages

setup(
    name="photo-tagger",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "exifread>=3.0.0",
        "piexif>=1.1.3",
        "xmltodict>=0.13.0",
        "python-dateutil>=2.8.2",
        "click>=8.1.7",
    ],
    entry_points={
        "console_scripts": [
            "photo-tagger=photo_tagger.cli:main",
        ],
    },
    python_requires=">=3.8",
)