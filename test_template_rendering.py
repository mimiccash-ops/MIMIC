#!/usr/bin/env python3
"""
Test template rendering to check if static_version works
"""
import sys
import os
sys.path.insert(0, '/var/www/mimic')

from app import app

with app.test_request_context('http://localhost/'):
    # Test if static_version is available in template context
    from flask import render_template_string
    
    template = '''
    <script src="{{ static_version('js/main.min.js') }}"></script>
    <script src="{{ static_version('js/push.js') }}"></script>
    <script src="{{ static_version('js/chat.js') }}"></script>
    '''
    
    try:
        html = render_template_string(template)
        print("✅ Template rendered successfully:")
        print(html)
        
        # Check if scripts are in output
        if 'main.min.js' in html:
            print("\n✅ main.min.js found in output")
        else:
            print("\n❌ main.min.js NOT found in output")
            
        if 'push.js' in html:
            print("✅ push.js found in output")
        else:
            print("❌ push.js NOT found in output")
            
        if 'chat.js' in html:
            print("✅ chat.js found in output")
        else:
            print("❌ chat.js NOT found in output")
            
    except Exception as e:
        print(f"❌ Error rendering template: {e}")
        import traceback
        traceback.print_exc()
