"""
Setup script for BluetoothStreamer Audio Player
"""

from setuptools import setup, find_packages
import os

# Read the README file
readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
long_description = ""
if os.path.exists(readme_path):
    with open(readme_path, 'r', encoding='utf-8') as f:
        long_description = f.read()

# Read requirements
requirements = []
requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
if os.path.exists(requirements_path):
    with open(requirements_path, 'r', encoding='utf-8') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="bluetoothstreamer",
    version="1.0.0",
    description="Multi-device audio player with SoundCloud streaming and latency synchronization",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/bluetoothstreamer",
    packages=find_packages(),
    py_modules=[
        'audio_sync_gui',
        'audio_sync_player',
        'streaming_service',
        'multi_device_helper'
    ],
    install_requires=requirements,
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Sound/Audio :: Players",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
    ],
    entry_points={
        'console_scripts': [
            'bluetoothstreamer=audio_sync_gui:main',
            'bluetoothstreamer-cli=audio_sync_player:main',
        ],
    },
    include_package_data=True,
    zip_safe=False,
)

