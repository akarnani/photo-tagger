from setuptools import setup, find_packages

setup(
    name="photo-tagger",
    version="0.2.1",
    packages=find_packages(),
    install_requires=[
        "exifread>=3.0.0",
        "piexif>=1.1.3",
        "exiv2>=0.17.5",
        "xmltodict>=0.13.0",
        "python-dateutil>=2.8.2",
        "click>=8.1.7",
        "lxml>=5.3.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "photo-tagger=photo_tagger.cli:main",
        ],
    },
    python_requires=">=3.8",
)