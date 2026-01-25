#!/usr/bin/env python3
"""
Test static file versioning
"""
import sys
import os
sys.path.insert(0, '/var/www/mimic')

from app import app, static_file_version

with app.app_context():
    print("Testing static file versioning:")
    print(f"tailwind.css: {static_file_version('css/tailwind.css')}")
    print(f"main.min.css: {static_file_version('css/main.min.css')}")
    print(f"chat.css: {static_file_version('css/chat.css')}")
    print(f"main.js: {static_file_version('js/main.js')}")
