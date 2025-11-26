"""
Setup configuration for p2pdocs package.
"""

from setuptools import setup, find_packages
import os

# Read long description from README
def read_long_description():
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "A peer-to-peer collaborative text editor using CRDT"

setup(
    name="p2pdocs",
    version="1.0.14",
    author="Your Name",
    author_email="your.email@example.com",
    description="P2P Collaborative Text Editor using CRDT",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/taaha-0548/P2PDocs",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Topic :: Communications",
        "Topic :: Text Editors",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    keywords="p2p crdt collaborative editor text-editor peer-to-peer conflict-free",
    python_requires=">=3.7",
    install_requires=[
        # tkinter is built-in, no external dependencies needed
    ],
    entry_points={
        "console_scripts": [
            "p2pdocs=p2pdocs.cli:main",
        ],
    },
    project_urls={
        "Source": "https://github.com/taaha-0548/P2PDocss"
    },
)
