"""
Setup script for P2PDocs package
Peer-to-Peer Collaborative Document Editor
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="p2pdocs",
    version="1.0.7",
    author="P2PDocs Team",
    author_email="support@p2pdocs.io",
    description="A Peer-to-Peer Collaborative Document Editing System with Real-Time Synchronization",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/p2pdocs/p2pdocs",
    project_urls={
        "Bug Tracker": "https://github.com/p2pdocs/p2pdocs/issues",
        "Documentation": "https://github.com/p2pdocs/p2pdocs#readme",
        "Source Code": "https://github.com/p2pdocs/p2pdocs",
    },
    packages=find_packages(exclude=["tests", "docs", "examples"]),
    package_data={
        "p2pdocs": [],
    },
    python_requires=">=3.8",
    install_requires=[
        # Zero external dependencies - uses only Python stdlib!
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=3.0",
            "black>=22.0",
            "flake8>=4.0",
            "mypy>=0.950",
        ],
    },
    entry_points={
        "console_scripts": [
            "p2pdocs=p2pdocs.cli:main",
        ],
    },
    keywords=[
        "p2p",
        "peer-to-peer",
        "collaborative",
        "document-editor",
        "real-time",
        "synchronization",
        "networking",
        "distributed",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Communications :: File Sharing",
        "Topic :: Office/Business",
        "Topic :: System :: Networking",
        "Topic :: Utilities",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Operating System :: MacOS",
        "Environment :: X11 Applications :: GTK",
        "Natural Language :: English",
    ],
    zip_safe=False,
)
