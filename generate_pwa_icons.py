"""
Generate PWA icons from the SVG logo

This script generates all required icon sizes for the PWA manifest.
Run this script after placing your source logo (mimic-logo.svg or a 512x512 PNG).

Requirements:
    pip install Pillow cairosvg

Usage:
    python generate_pwa_icons.py
"""

import os
import sys
from pathlib import Path

# Icon sizes required for PWA
ICON_SIZES = [72, 96, 128, 144, 152, 192, 384, 512]
MASKABLE_SIZES = [192, 512]
SHORTCUT_SIZE = 96
BADGE_SIZE = 72


def generate_icons_from_svg(svg_path: str, output_dir: str):
    """Generate PNG icons from SVG source"""
    try:
        import cairosvg
        from PIL import Image
        from io import BytesIO
    except ImportError:
        print("❌ Required packages not installed!")
        print("Run: pip install Pillow cairosvg")
        return False
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"📁 Output directory: {output_dir}")
    print()
    
    # Generate standard icons
    print("Generating standard icons...")
    for size in ICON_SIZES:
        output_path = os.path.join(output_dir, f'icon-{size}x{size}.png')
        try:
            # Convert SVG to PNG at specific size
            png_data = cairosvg.svg2png(
                url=svg_path,
                output_width=size,
                output_height=size
            )
            
            # Save
            with open(output_path, 'wb') as f:
                f.write(png_data)
            
            print(f"  ✅ icon-{size}x{size}.png")
        except Exception as e:
            print(f"  ❌ icon-{size}x{size}.png: {e}")
    
    # Generate maskable icons (with padding for safe area)
    print()
    print("Generating maskable icons...")
    for size in MASKABLE_SIZES:
        output_path = os.path.join(output_dir, f'icon-maskable-{size}x{size}.png')
        try:
            # For maskable icons, the safe area is typically 80% of the icon
            # So we render the icon at 80% and add 10% padding on each side
            inner_size = int(size * 0.7)  # Icon takes 70% of total size
            padding = (size - inner_size) // 2
            
            # Convert SVG to smaller PNG
            png_data = cairosvg.svg2png(
                url=svg_path,
                output_width=inner_size,
                output_height=inner_size
            )
            
            # Create image with padding and background
            inner_img = Image.open(BytesIO(png_data))
            
            # Create background (dark theme)
            bg_color = (10, 10, 15, 255)  # #0a0a0f
            final_img = Image.new('RGBA', (size, size), bg_color)
            
            # Paste icon centered
            final_img.paste(inner_img, (padding, padding), inner_img if inner_img.mode == 'RGBA' else None)
            
            # Save
            final_img.save(output_path, 'PNG')
            
            print(f"  ✅ icon-maskable-{size}x{size}.png")
        except Exception as e:
            print(f"  ❌ icon-maskable-{size}x{size}.png: {e}")
    
    # Generate shortcut icons
    print()
    print("Generating shortcut icons...")
    shortcut_icons = [
        ('shortcut-dashboard.png', '📊'),
        ('shortcut-messages.png', '💬'),
        ('shortcut-login.png', '🔐')
    ]
    
    for filename, emoji in shortcut_icons:
        output_path = os.path.join(output_dir, filename)
        try:
            # Create simple colored background with the main icon
            png_data = cairosvg.svg2png(
                url=svg_path,
                output_width=SHORTCUT_SIZE - 20,
                output_height=SHORTCUT_SIZE - 20
            )
            
            inner_img = Image.open(BytesIO(png_data))
            bg_color = (15, 15, 24, 255)  # #0f0f18
            final_img = Image.new('RGBA', (SHORTCUT_SIZE, SHORTCUT_SIZE), bg_color)
            final_img.paste(inner_img, (10, 10), inner_img if inner_img.mode == 'RGBA' else None)
            final_img.save(output_path, 'PNG')
            
            print(f"  ✅ {filename}")
        except Exception as e:
            print(f"  ❌ {filename}: {e}")
    
    # Generate badge icon (for notifications)
    print()
    print("Generating badge icon...")
    badge_path = os.path.join(output_dir, f'badge-{BADGE_SIZE}x{BADGE_SIZE}.png')
    try:
        png_data = cairosvg.svg2png(
            url=svg_path,
            output_width=BADGE_SIZE,
            output_height=BADGE_SIZE
        )
        with open(badge_path, 'wb') as f:
            f.write(png_data)
        print(f"  ✅ badge-{BADGE_SIZE}x{BADGE_SIZE}.png")
    except Exception as e:
        print(f"  ❌ badge-{BADGE_SIZE}x{BADGE_SIZE}.png: {e}")
    
    # Generate action icons for notifications
    print()
    print("Generating notification action icons...")
    action_icons = ['action-open.png', 'action-dismiss.png']
    for filename in action_icons:
        output_path = os.path.join(output_dir, filename)
        try:
            png_data = cairosvg.svg2png(
                url=svg_path,
                output_width=48,
                output_height=48
            )
            with open(output_path, 'wb') as f:
                f.write(png_data)
            print(f"  ✅ {filename}")
        except Exception as e:
            print(f"  ❌ {filename}: {e}")
    
    return True


def generate_placeholder_icons(output_dir: str):
    """Generate simple placeholder icons using PIL only"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("❌ Pillow not installed!")
        print("Run: pip install Pillow")
        return False
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"📁 Output directory: {output_dir}")
    print()
    print("⚠️  cairosvg not available, generating placeholder icons...")
    print()
    
    # Colors
    bg_color = (10, 10, 15)  # Dark background
    accent_color = (0, 245, 255)  # Neon cyan
    
    # Generate icons
    print("Generating placeholder icons...")
    for size in ICON_SIZES:
        output_path = os.path.join(output_dir, f'icon-{size}x{size}.png')
        try:
            img = Image.new('RGB', (size, size), bg_color)
            draw = ImageDraw.Draw(img)
            
            # Draw simple M shape
            margin = size // 6
            mid_x = size // 2
            mid_y = size // 2
            
            # Left V
            draw.polygon([
                (margin, margin),
                (mid_x - margin//2, mid_y),
                (margin, size - margin)
            ], fill=accent_color)
            
            # Right V
            draw.polygon([
                (size - margin, margin),
                (mid_x + margin//2, mid_y),
                (size - margin, size - margin)
            ], fill=accent_color)
            
            # Center bar
            bar_width = size // 8
            draw.rectangle([
                mid_x - bar_width//2, mid_y - size//6,
                mid_x + bar_width//2, mid_y + size//6
            ], fill=(255, 45, 146))  # Neon pink
            
            img.save(output_path, 'PNG')
            print(f"  ✅ icon-{size}x{size}.png")
        except Exception as e:
            print(f"  ❌ icon-{size}x{size}.png: {e}")
    
    # Generate maskable icons
    print()
    print("Generating maskable icons...")
    for size in MASKABLE_SIZES:
        output_path = os.path.join(output_dir, f'icon-maskable-{size}x{size}.png')
        try:
            img = Image.new('RGB', (size, size), bg_color)
            draw = ImageDraw.Draw(img)
            
            # Smaller icon for maskable (safe area)
            inner_size = int(size * 0.6)
            offset = (size - inner_size) // 2
            
            margin = inner_size // 6
            mid_x = size // 2
            mid_y = size // 2
            
            # Left V
            draw.polygon([
                (offset + margin, offset + margin),
                (mid_x - margin//2, mid_y),
                (offset + margin, size - offset - margin)
            ], fill=accent_color)
            
            # Right V
            draw.polygon([
                (size - offset - margin, offset + margin),
                (mid_x + margin//2, mid_y),
                (size - offset - margin, size - offset - margin)
            ], fill=accent_color)
            
            # Center bar
            bar_width = inner_size // 8
            draw.rectangle([
                mid_x - bar_width//2, mid_y - inner_size//6,
                mid_x + bar_width//2, mid_y + inner_size//6
            ], fill=(255, 45, 146))
            
            img.save(output_path, 'PNG')
            print(f"  ✅ icon-maskable-{size}x{size}.png")
        except Exception as e:
            print(f"  ❌ icon-maskable-{size}x{size}.png: {e}")
    
    # Generate other icons
    print()
    print("Generating other icons...")
    
    other_icons = [
        (f'badge-{BADGE_SIZE}x{BADGE_SIZE}.png', BADGE_SIZE),
        ('shortcut-dashboard.png', SHORTCUT_SIZE),
        ('shortcut-messages.png', SHORTCUT_SIZE),
        ('shortcut-login.png', SHORTCUT_SIZE),
        ('action-open.png', 48),
        ('action-dismiss.png', 48)
    ]
    
    for filename, size in other_icons:
        output_path = os.path.join(output_dir, filename)
        try:
            img = Image.new('RGB', (size, size), bg_color)
            draw = ImageDraw.Draw(img)
            
            # Simple M
            margin = size // 5
            draw.polygon([
                (margin, margin),
                (size//2, size//2),
                (margin, size - margin)
            ], fill=accent_color)
            draw.polygon([
                (size - margin, margin),
                (size//2, size//2),
                (size - margin, size - margin)
            ], fill=accent_color)
            
            img.save(output_path, 'PNG')
            print(f"  ✅ {filename}")
        except Exception as e:
            print(f"  ❌ {filename}: {e}")
    
    return True


def main():
    print("=" * 60)
    print("              PWA Icon Generator")
    print("=" * 60)
    print()
    
    # Determine paths
    script_dir = Path(__file__).parent
    svg_path = script_dir / 'static' / 'mimic-logo.svg'
    output_dir = script_dir / 'static' / 'icons'
    
    print(f"Source SVG: {svg_path}")
    print(f"Output dir: {output_dir}")
    print()
    
    # Check if SVG exists
    if not svg_path.exists():
        print(f"⚠️  SVG not found at {svg_path}")
        print("   Generating placeholder icons instead...")
        print()
        success = generate_placeholder_icons(str(output_dir))
    else:
        # Try to use cairosvg for best quality
        try:
            import cairosvg
            success = generate_icons_from_svg(str(svg_path), str(output_dir))
        except ImportError:
            print("⚠️  cairosvg not installed")
            print("   For best quality icons, run: pip install cairosvg")
            print()
            success = generate_placeholder_icons(str(output_dir))
    
    print()
    if success:
        print("=" * 60)
        print("✅ Icon generation complete!")
        print("=" * 60)
        print()
        print("Icons generated in: static/icons/")
        print()
        print("For better quality icons, you can:")
        print("1. Install cairosvg: pip install cairosvg")
        print("2. Create a 512x512 PNG and use online tools")
        print("3. Use design tools like Figma or Photoshop")
    else:
        print("❌ Icon generation failed!")
        print()
        print("You may need to:")
        print("1. Install Pillow: pip install Pillow")
        print("2. Install cairosvg: pip install cairosvg")


if __name__ == '__main__':
    main()
