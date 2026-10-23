"""
Setup configuration for c2g.
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
    name="c2g",
    version="0.1.0",
    author="c2g Contributors",
    author_email="",
    description="Code 2gether — peer-to-peer collaborative text editor using CRDT",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/sultanshahdev/c2g",
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
            "c2g=c2g.cli:main",
        ],
    },
    project_urls={
        "Source": "https://github.com/sultanshahdev/c2g"
    },
)
