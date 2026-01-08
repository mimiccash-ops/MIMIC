#!/usr/bin/env python3
"""
Asset Optimization Script
Minifies JavaScript and CSS files for production deployment
"""

import os
import re
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AssetOptimizer")


class SimpleMinifier:
    """Simple but effective minifier for JS and CSS"""
    
    @staticmethod
    def minify_js(content):
        """Minify JavaScript content"""
        # Remove comments
        content = re.sub(r'//.*?\n', '\n', content)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Remove unnecessary whitespace
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'\s*([{};:,()[\]])\s*', r'\1', content)
        
        # Remove trailing semicolons before }
        content = re.sub(r';\s*}', '}', content)
        
        return content.strip()
    
    @staticmethod
    def minify_css(content):
        """Minify CSS content"""
        # Remove comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Remove unnecessary whitespace
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'\s*([{};:,>+~])\s*', r'\1', content)
        
        # Remove last semicolon in block
        content = re.sub(r';\s*}', '}', content)
        
        return content.strip()


def optimize_assets(static_dir='static'):
    """Optimize all JS and CSS files in static directory"""
    
    static_path = Path(static_dir)
    if not static_path.exists():
        logger.error(f"Static directory not found: {static_dir}")
        return
    
    minifier = SimpleMinifier()
    total_saved = 0
    
    # Process JavaScript files
    js_files = list(static_path.glob('**/*.js'))
    js_files = [f for f in js_files if not f.name.endswith('.min.js')]
    
    for js_file in js_files:
        try:
            logger.info(f"Processing {js_file.name}...")
            
            with open(js_file, 'r', encoding='utf-8') as f:
                original = f.read()
            
            minified = minifier.minify_js(original)
            
            # Save minified version
            minified_path = js_file.parent / f"{js_file.stem}.min.js"
            with open(minified_path, 'w', encoding='utf-8') as f:
                f.write(minified)
            
            original_size = len(original)
            minified_size = len(minified)
            saved = original_size - minified_size
            saved_pct = (saved / original_size * 100) if original_size > 0 else 0
            
            total_saved += saved
            
            logger.info(f"✅ {js_file.name}: {original_size:,} → {minified_size:,} bytes "
                       f"(saved {saved:,} bytes, {saved_pct:.1f}%)")
            
        except Exception as e:
            logger.error(f"❌ Error processing {js_file.name}: {e}")
    
    # Process CSS files
    css_files = list(static_path.glob('**/*.css'))
    css_files = [f for f in css_files if not f.name.endswith('.min.css')]
    
    for css_file in css_files:
        try:
            logger.info(f"Processing {css_file.name}...")
            
            with open(css_file, 'r', encoding='utf-8') as f:
                original = f.read()
            
            minified = minifier.minify_css(original)
            
            # Save minified version
            minified_path = css_file.parent / f"{css_file.stem}.min.css"
            with open(minified_path, 'w', encoding='utf-8') as f:
                f.write(minified)
            
            original_size = len(original)
            minified_size = len(minified)
            saved = original_size - minified_size
            saved_pct = (saved / original_size * 100) if original_size > 0 else 0
            
            total_saved += saved
            
            logger.info(f"✅ {css_file.name}: {original_size:,} → {minified_size:,} bytes "
                       f"(saved {saved:,} bytes, {saved_pct:.1f}%)")
            
        except Exception as e:
            logger.error(f"❌ Error processing {css_file.name}: {e}")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ Asset optimization complete!")
    logger.info(f"📊 Total space saved: {total_saved:,} bytes ({total_saved/1024:.1f} KB)")
    logger.info(f"{'='*60}\n")


def create_production_config(template_dir='templates'):
    """Update templates to use minified assets in production"""
    
    template_path = Path(template_dir)
    if not template_path.exists():
        logger.warning(f"Template directory not found: {template_dir}")
        return
    
    logger.info("Scanning templates for asset references...")
    
    templates = list(template_path.glob('**/*.html'))
    updated_count = 0
    
    for template_file in templates:
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if already has production logic
            if "config.ENV" in content or ".min.js" in content:
                continue
            
            # Find asset includes
            js_pattern = r'<script\s+src="([^"]*(?:main|dashboard|admin)\.js)"'
            css_pattern = r'<link[^>]+href="([^"]*(?:main|dashboard|admin)\.css)"'
            
            if re.search(js_pattern, content) or re.search(css_pattern, content):
                logger.info(f"Template {template_file.name} has asset references")
                # Note: Actual template modification would require Jinja2 logic
                # This is just detection
                updated_count += 1
                
        except Exception as e:
            logger.error(f"❌ Error processing {template_file.name}: {e}")
    
    if updated_count > 0:
        logger.info(f"📝 Found {updated_count} templates with asset references")
        logger.info("💡 To use minified assets in production, update your base template with:")
        print("""
{% if config.ENV == 'production' %}
    <script src="{{ url_for('static', filename='js/main.min.js') }}"></script>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/main.min.css') }}">
{% else %}
    <script src="{{ url_for('static', filename='js/main.js') }}"></script>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/main.css') }}">
{% endif %}
        """)


def compress_images(static_dir='static'):
    """Placeholder for image optimization"""
    logger.info("\n💡 Image Optimization Tips:")
    logger.info("- Install pillow for image compression: pip install pillow")
    logger.info("- Use WebP format for better compression")
    logger.info("- Implement lazy loading for images")
    logger.info("- Consider using a CDN for static assets")


if __name__ == "__main__":
    print("=" * 60)
    print("Brain Capital - Asset Optimization")
    print("=" * 60)
    print()
    
    # Optimize JS and CSS
    optimize_assets('static')
    
    # Check templates
    create_production_config('templates')
    
    # Image tips
    compress_images('static')
    
    print()
    print("=" * 60)
    print("✅ Optimization complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Test minified assets in development")
    print("2. Update templates to use .min.js/.min.css in production")
    print("3. Add cache headers for static assets")
    print("4. Consider using a CDN for better performance")
    print()

