"""
Banner Generator for Influencer Dashboard.

Generates dynamic promotional banners using Pillow.
Banners display user's PnL, referral code, and platform branding.
"""

import io
import os
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import Pillow
try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logger.warning("Pillow not installed. Banner generation will be disabled.")


# ==================== BANNER CONFIGURATIONS ====================

BANNER_CONFIGS = {
    'landscape': {
        'size': (1200, 630),  # Social media standard
        'description': 'Landscape (1200x630) - Perfect for social media',
    },
    'square': {
        'size': (1080, 1080),  # Instagram square
        'description': 'Square (1080x1080) - Instagram posts',
    },
    'story': {
        'size': (1080, 1920),  # Stories format
        'description': 'Story (1080x1920) - Instagram/Facebook Stories',
    },
    'leaderboard': {
        'size': (728, 90),  # Standard leaderboard
        'description': 'Leaderboard (728x90) - Website banner',
    },
    'sidebar': {
        'size': (300, 250),  # Medium rectangle
        'description': 'Sidebar (300x250) - Website sidebar',
    },
}

# Color scheme (Cyberpunk theme matching MIMIC brand)
COLORS = {
    'background_dark': (5, 5, 8),
    'background_gradient': (15, 15, 24),
    'cyan': (0, 240, 255),
    'green': (0, 255, 136),
    'purple': (138, 43, 226),
    'yellow': (255, 200, 0),
    'red': (255, 68, 68),
    'white': (255, 255, 255),
    'white_dim': (200, 200, 210),
    'border_cyan': (0, 240, 255),
}


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """
    Get a font for text rendering.
    Falls back to default font if custom fonts aren't available.
    """
    # Try to load a modern font
    font_candidates = [
        # Common system fonts
        'arial.ttf',
        'Arial.ttf',
        'DejaVuSans.ttf',
        'FreeSans.ttf',
        'LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/segoeui.ttf',
    ]
    
    if bold:
        font_candidates = [
            'arialbd.ttf',
            'Arial Bold.ttf',
            'DejaVuSans-Bold.ttf',
            'FreeSansBold.ttf',
            'LiberationSans-Bold.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            'C:/Windows/Fonts/arialbd.ttf',
            'C:/Windows/Fonts/segoeuib.ttf',
        ] + font_candidates
    
    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except (OSError, IOError):
            continue
    
    # Fallback to default font
    return ImageFont.load_default()


def draw_gradient_background(draw: ImageDraw.Draw, size: Tuple[int, int]):
    """Draw a gradient background"""
    width, height = size
    
    for y in range(height):
        # Calculate gradient color
        progress = y / height
        r = int(COLORS['background_dark'][0] + (COLORS['background_gradient'][0] - COLORS['background_dark'][0]) * progress)
        g = int(COLORS['background_dark'][1] + (COLORS['background_gradient'][1] - COLORS['background_dark'][1]) * progress)
        b = int(COLORS['background_dark'][2] + (COLORS['background_gradient'][2] - COLORS['background_dark'][2]) * progress)
        
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def draw_glow_effect(img: Image.Image, position: Tuple[int, int], color: Tuple[int, int, int], radius: int = 50):
    """Draw a subtle glow effect at position"""
    from PIL import ImageFilter
    
    # Create glow layer
    glow = Image.new('RGBA', img.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    
    x, y = position
    for i in range(radius, 0, -5):
        alpha = int(30 * (1 - i / radius))
        glow_draw.ellipse(
            [x - i, y - i, x + i, y + i],
            fill=(*color, alpha)
        )
    
    # Blur the glow
    glow = glow.filter(ImageFilter.GaussianBlur(radius=10))
    
    # Composite
    return Image.alpha_composite(img.convert('RGBA'), glow)


def draw_border(draw: ImageDraw.Draw, size: Tuple[int, int], color: Tuple[int, int, int], width: int = 2):
    """Draw a border around the image"""
    w, h = size
    # Draw border
    draw.rectangle([0, 0, w-1, h-1], outline=color, width=width)
    # Add corner accents
    corner_size = 20
    # Top left
    draw.line([(0, corner_size), (0, 0), (corner_size, 0)], fill=color, width=3)
    # Top right
    draw.line([(w-corner_size, 0), (w-1, 0), (w-1, corner_size)], fill=color, width=3)
    # Bottom left
    draw.line([(0, h-corner_size), (0, h-1), (corner_size, h-1)], fill=color, width=3)
    # Bottom right
    draw.line([(w-corner_size, h-1), (w-1, h-1), (w-1, h-corner_size)], fill=color, width=3)


def generate_banner(
    banner_type: str = 'landscape',
    referral_code: str = 'MIMIC',
    username: str = None,
    total_pnl: float = 0.0,
    total_roi: float = 0.0,
    top_apy: float = None,
    referral_count: int = 0,
    total_commission: float = 0.0,
) -> Optional[bytes]:
    """
    Generate a promotional banner.
    
    Args:
        banner_type: One of 'landscape', 'square', 'story', 'leaderboard', 'sidebar'
        referral_code: User's referral code
        username: Username to display (optional)
        total_pnl: Total PnL in USD
        total_roi: Total ROI percentage
        top_apy: Platform's top APY
        referral_count: Number of referrals
        total_commission: Total commission earned
        
    Returns:
        PNG image bytes or None if generation fails
    """
    if not PILLOW_AVAILABLE:
        logger.error("Pillow not available for banner generation")
        return None
    
    if banner_type not in BANNER_CONFIGS:
        banner_type = 'landscape'
    
    config = BANNER_CONFIGS[banner_type]
    size = config['size']
    width, height = size
    
    try:
        # Create base image
        img = Image.new('RGB', size, COLORS['background_dark'])
        draw = ImageDraw.Draw(img)
        
        # Draw gradient background
        draw_gradient_background(draw, size)
        
        # Draw border
        draw_border(draw, size, COLORS['border_cyan'])
        
        # Determine layout based on banner type
        if banner_type in ('landscape', 'square'):
            _draw_main_banner(draw, size, referral_code, username, total_pnl, total_roi, top_apy, referral_count, total_commission)
        elif banner_type == 'story':
            _draw_story_banner(draw, size, referral_code, username, total_pnl, total_roi, top_apy)
        elif banner_type in ('leaderboard', 'sidebar'):
            _draw_compact_banner(draw, size, referral_code, total_pnl, top_apy)
        
        # Add decorative elements
        _add_decorative_lines(draw, size)
        
        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)
        return buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Banner generation failed: {e}")
        return None


def _draw_main_banner(draw, size, referral_code, username, total_pnl, total_roi, top_apy, referral_count, total_commission):
    """Draw main banner layout (landscape/square)"""
    width, height = size
    padding = int(width * 0.05)
    
    # Logo / Brand
    font_brand = get_font(int(height * 0.08), bold=True)
    draw.text(
        (padding, padding),
        "MIMIC",
        font=font_brand,
        fill=COLORS['cyan']
    )
    
    # Tagline
    font_small = get_font(int(height * 0.035))
    draw.text(
        (padding, padding + int(height * 0.1)),
        "Copy Trading Platform",
        font=font_small,
        fill=COLORS['white_dim']
    )
    
    # Main stats section
    stats_y = int(height * 0.35)
    
    # PnL Display
    pnl_color = COLORS['green'] if total_pnl >= 0 else COLORS['red']
    pnl_sign = '+' if total_pnl >= 0 else ''
    font_pnl = get_font(int(height * 0.15), bold=True)
    draw.text(
        (padding, stats_y),
        f"{pnl_sign}${total_pnl:,.2f}",
        font=font_pnl,
        fill=pnl_color
    )
    
    # ROI Display
    roi_color = COLORS['green'] if total_roi >= 0 else COLORS['red']
    roi_sign = '+' if total_roi >= 0 else ''
    font_roi = get_font(int(height * 0.06), bold=True)
    draw.text(
        (padding, stats_y + int(height * 0.18)),
        f"ROI: {roi_sign}{total_roi:.1f}%",
        font=font_roi,
        fill=roi_color
    )
    
    # Top APY badge (if provided)
    if top_apy and top_apy > 0:
        badge_x = width - padding - int(width * 0.25)
        badge_y = int(height * 0.15)
        badge_width = int(width * 0.22)
        badge_height = int(height * 0.15)
        
        # Badge background
        draw.rectangle(
            [badge_x, badge_y, badge_x + badge_width, badge_y + badge_height],
            fill=(*COLORS['cyan'][:3], 30),
            outline=COLORS['cyan'],
            width=2
        )
        
        font_apy_label = get_font(int(height * 0.03))
        font_apy_value = get_font(int(height * 0.06), bold=True)
        
        draw.text(
            (badge_x + int(badge_width * 0.1), badge_y + int(badge_height * 0.15)),
            "TOP APY",
            font=font_apy_label,
            fill=COLORS['white_dim']
        )
        draw.text(
            (badge_x + int(badge_width * 0.1), badge_y + int(badge_height * 0.45)),
            f"{top_apy:.0f}%",
            font=font_apy_value,
            fill=COLORS['yellow']
        )
    
    # Referral Code (bottom)
    code_y = height - padding - int(height * 0.2)
    
    font_code_label = get_font(int(height * 0.035))
    font_code = get_font(int(height * 0.07), bold=True)
    
    draw.text(
        (padding, code_y),
        "JOIN WITH CODE:",
        font=font_code_label,
        fill=COLORS['white_dim']
    )
    draw.text(
        (padding, code_y + int(height * 0.05)),
        referral_code,
        font=font_code,
        fill=COLORS['cyan']
    )
    
    # Website URL
    font_url = get_font(int(height * 0.035))
    draw.text(
        (width - padding - int(width * 0.2), height - padding - int(height * 0.05)),
        "mimic.cash",
        font=font_url,
        fill=COLORS['cyan']
    )


def _draw_story_banner(draw, size, referral_code, username, total_pnl, total_roi, top_apy):
    """Draw vertical story format banner"""
    width, height = size
    padding = int(width * 0.08)
    
    # Logo at top
    font_brand = get_font(int(width * 0.12), bold=True)
    bbox = draw.textbbox((0, 0), "MIMIC", font=font_brand)
    text_width = bbox[2] - bbox[0]
    draw.text(
        ((width - text_width) // 2, int(height * 0.08)),
        "MIMIC",
        font=font_brand,
        fill=COLORS['cyan']
    )
    
    # Tagline
    font_tag = get_font(int(width * 0.04))
    bbox = draw.textbbox((0, 0), "COPY TRADING", font=font_tag)
    text_width = bbox[2] - bbox[0]
    draw.text(
        ((width - text_width) // 2, int(height * 0.14)),
        "COPY TRADING",
        font=font_tag,
        fill=COLORS['white_dim']
    )
    
    # Big PnL in center
    pnl_color = COLORS['green'] if total_pnl >= 0 else COLORS['red']
    pnl_sign = '+' if total_pnl >= 0 else ''
    font_pnl = get_font(int(width * 0.15), bold=True)
    pnl_text = f"{pnl_sign}${total_pnl:,.0f}"
    bbox = draw.textbbox((0, 0), pnl_text, font=font_pnl)
    text_width = bbox[2] - bbox[0]
    draw.text(
        ((width - text_width) // 2, int(height * 0.35)),
        pnl_text,
        font=font_pnl,
        fill=pnl_color
    )
    
    # ROI
    roi_color = COLORS['green'] if total_roi >= 0 else COLORS['red']
    roi_sign = '+' if total_roi >= 0 else ''
    font_roi = get_font(int(width * 0.08), bold=True)
    roi_text = f"ROI: {roi_sign}{total_roi:.1f}%"
    bbox = draw.textbbox((0, 0), roi_text, font=font_roi)
    text_width = bbox[2] - bbox[0]
    draw.text(
        ((width - text_width) // 2, int(height * 0.45)),
        roi_text,
        font=font_roi,
        fill=roi_color
    )
    
    # APY Badge
    if top_apy and top_apy > 0:
        font_apy = get_font(int(width * 0.06), bold=True)
        apy_text = f"UP TO {top_apy:.0f}% APY"
        bbox = draw.textbbox((0, 0), apy_text, font=font_apy)
        text_width = bbox[2] - bbox[0]
        draw.text(
            ((width - text_width) // 2, int(height * 0.55)),
            apy_text,
            font=font_apy,
            fill=COLORS['yellow']
        )
    
    # Referral Code (bottom)
    font_code_label = get_font(int(width * 0.045))
    font_code = get_font(int(width * 0.1), bold=True)
    
    label_text = "JOIN WITH CODE"
    bbox = draw.textbbox((0, 0), label_text, font=font_code_label)
    text_width = bbox[2] - bbox[0]
    draw.text(
        ((width - text_width) // 2, int(height * 0.75)),
        label_text,
        font=font_code_label,
        fill=COLORS['white_dim']
    )
    
    bbox = draw.textbbox((0, 0), referral_code, font=font_code)
    text_width = bbox[2] - bbox[0]
    draw.text(
        ((width - text_width) // 2, int(height * 0.80)),
        referral_code,
        font=font_code,
        fill=COLORS['cyan']
    )
    
    # URL at bottom
    font_url = get_font(int(width * 0.05))
    url_text = "mimic.cash"
    bbox = draw.textbbox((0, 0), url_text, font=font_url)
    text_width = bbox[2] - bbox[0]
    draw.text(
        ((width - text_width) // 2, int(height * 0.92)),
        url_text,
        font=font_url,
        fill=COLORS['cyan']
    )


def _draw_compact_banner(draw, size, referral_code, total_pnl, top_apy):
    """Draw compact banner (leaderboard/sidebar)"""
    width, height = size
    padding = int(min(width, height) * 0.1)
    
    is_leaderboard = width > height
    
    if is_leaderboard:
        # Horizontal layout
        # Logo
        font_brand = get_font(int(height * 0.4), bold=True)
        draw.text(
            (padding, (height - int(height * 0.4)) // 2),
            "MIMIC",
            font=font_brand,
            fill=COLORS['cyan']
        )
        
        # APY in middle
        if top_apy and top_apy > 0:
            font_apy = get_font(int(height * 0.35), bold=True)
            apy_text = f"{top_apy:.0f}% APY"
            draw.text(
                (int(width * 0.25), (height - int(height * 0.35)) // 2),
                apy_text,
                font=font_apy,
                fill=COLORS['yellow']
            )
        
        # Code on right
        font_code = get_font(int(height * 0.3), bold=True)
        bbox = draw.textbbox((0, 0), referral_code, font=font_code)
        text_width = bbox[2] - bbox[0]
        draw.text(
            (width - padding - text_width, (height - int(height * 0.3)) // 2),
            referral_code,
            font=font_code,
            fill=COLORS['green']
        )
    else:
        # Vertical layout (sidebar)
        # Logo
        font_brand = get_font(int(height * 0.1), bold=True)
        bbox = draw.textbbox((0, 0), "MIMIC", font=font_brand)
        text_width = bbox[2] - bbox[0]
        draw.text(
            ((width - text_width) // 2, padding),
            "MIMIC",
            font=font_brand,
            fill=COLORS['cyan']
        )
        
        # APY
        if top_apy and top_apy > 0:
            font_apy = get_font(int(height * 0.12), bold=True)
            apy_text = f"{top_apy:.0f}%"
            bbox = draw.textbbox((0, 0), apy_text, font=font_apy)
            text_width = bbox[2] - bbox[0]
            draw.text(
                ((width - text_width) // 2, int(height * 0.3)),
                apy_text,
                font=font_apy,
                fill=COLORS['yellow']
            )
            
            font_apy_label = get_font(int(height * 0.06))
            bbox = draw.textbbox((0, 0), "APY", font=font_apy_label)
            text_width = bbox[2] - bbox[0]
            draw.text(
                ((width - text_width) // 2, int(height * 0.45)),
                "APY",
                font=font_apy_label,
                fill=COLORS['white_dim']
            )
        
        # Code
        font_code_label = get_font(int(height * 0.05))
        font_code = get_font(int(height * 0.08), bold=True)
        
        bbox = draw.textbbox((0, 0), "CODE:", font=font_code_label)
        text_width = bbox[2] - bbox[0]
        draw.text(
            ((width - text_width) // 2, int(height * 0.7)),
            "CODE:",
            font=font_code_label,
            fill=COLORS['white_dim']
        )
        
        bbox = draw.textbbox((0, 0), referral_code, font=font_code)
        text_width = bbox[2] - bbox[0]
        draw.text(
            ((width - text_width) // 2, int(height * 0.78)),
            referral_code,
            font=font_code,
            fill=COLORS['green']
        )


def _add_decorative_lines(draw, size):
    """Add decorative grid/scan lines for cyberpunk effect"""
    width, height = size
    
    # Subtle horizontal scan lines
    for y in range(0, height, 4):
        if y % 8 == 0:
            draw.line([(0, y), (width, y)], fill=(255, 255, 255, 5), width=1)
    
    # Corner decorations
    corner_length = min(width, height) // 10
    line_color = (*COLORS['cyan'][:3], 80)
    
    # Top left corner
    draw.line([(0, corner_length), (0, 0), (corner_length, 0)], fill=line_color, width=1)
    # Bottom right corner  
    draw.line([(width - corner_length, height - 1), (width - 1, height - 1), (width - 1, height - corner_length)], fill=line_color, width=1)


def get_banner_types() -> dict:
    """Get available banner types with descriptions"""
    return {
        key: {
            'size': f"{config['size'][0]}x{config['size'][1]}",
            'description': config['description'],
        }
        for key, config in BANNER_CONFIGS.items()
    }


# ==================== UTILITY FUNCTIONS ====================

def get_platform_top_apy() -> float:
    """
    Calculate the platform's top APY based on recent performance.
    This is used in banners to show potential returns.
    """
    try:
        from models import db, TradeHistory, User
        from sqlalchemy import func
        from datetime import timedelta
        
        # Get average ROI from last 30 days for active traders
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        
        # Get sum of ROI for users with positive results
        result = db.session.query(
            func.sum(TradeHistory.roi)
        ).filter(
            TradeHistory.close_time >= thirty_days_ago,
            TradeHistory.roi > 0
        ).scalar()
        
        if result and result > 0:
            # Annualize the 30-day return
            monthly_return = min(result / 100, 0.5)  # Cap at 50% monthly
            apy = ((1 + monthly_return) ** 12 - 1) * 100
            return min(apy, 500)  # Cap at 500% APY
        
        return 120  # Default APY for display
        
    except Exception as e:
        logger.warning(f"Could not calculate top APY: {e}")
        return 120  # Default


def get_user_trading_stats(user_id: int) -> dict:
    """Get user's trading statistics for banner generation"""
    try:
        from models import db, TradeHistory, User
        from sqlalchemy import func
        
        user = User.query.get(user_id)
        if not user:
            return {'total_pnl': 0, 'total_roi': 0}
        
        # Get total PnL
        total_pnl = db.session.query(
            func.coalesce(func.sum(TradeHistory.pnl), 0.0)
        ).filter(TradeHistory.user_id == user_id).scalar() or 0
        
        # Get average ROI
        avg_roi = db.session.query(
            func.coalesce(func.avg(TradeHistory.roi), 0.0)
        ).filter(TradeHistory.user_id == user_id).scalar() or 0
        
        return {
            'total_pnl': float(total_pnl),
            'total_roi': float(avg_roi),
        }
        
    except Exception as e:
        logger.warning(f"Could not get user trading stats: {e}")
        return {'total_pnl': 0, 'total_roi': 0}
