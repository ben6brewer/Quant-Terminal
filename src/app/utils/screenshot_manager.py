from __future__ import annotations

from pathlib import Path
from typing import Optional
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Qt, QRect


class ScreenshotManager:
    """
    Manages module screenshots for tile display.
    Generates placeholder images if screenshots don't exist.
    """

    _SCREENSHOT_DIR = Path.home() / ".quant_terminal" / "screenshots"

    # Section-based color palette for placeholders
    _SECTION_COLORS = {
        "Charting": "#1e88e5",      # Blue
        "Portfolio": "#43a047",     # Green
        "Market Data": "#fb8c00",   # Orange
        "Analysis": "#8e24aa",      # Purple
        "Settings": "#546e7a",      # Gray
    }

    @staticmethod
    def get_screenshot_path(module_id: str) -> Path:
        """Get the path to a module's screenshot."""
        return ScreenshotManager._SCREENSHOT_DIR / f"{module_id}.png"

    @staticmethod
    def has_screenshot(module_id: str) -> bool:
        """Check if a screenshot exists for the module."""
        return ScreenshotManager.get_screenshot_path(module_id).exists()

    @staticmethod
    def get_default_screenshot() -> QPixmap:
        """Get a generic default screenshot placeholder."""
        pixmap = QPixmap(280, 200)
        pixmap.fill(QColor("#2d2d2d"))

        painter = QPainter(pixmap)
        painter.setPen(QColor("#cccccc"))
        painter.setFont(QFont("Arial", 14))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "No Preview")
        painter.end()

        return pixmap

    @staticmethod
    def generate_placeholder(module_id: str, label: str, emoji: str, section: str = "Settings") -> QPixmap:
        """
        Generate a colored placeholder image with emoji and label.

        Args:
            module_id: The module's unique ID
            label: Display label (e.g., "Charts", "Portfolio")
            emoji: Emoji icon (e.g., "📊", "💼")
            section: Section name for color selection

        Returns:
            QPixmap with generated placeholder
        """
        # Create pixmap
        pixmap = QPixmap(280, 200)

        # Get color for section (default to Settings gray if not found)
        color = ScreenshotManager._SECTION_COLORS.get(section, "#546e7a")
        pixmap.fill(QColor(color))

        # Draw overlay with darker gradient effect
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw semi-transparent overlay for depth
        overlay = QColor(0, 0, 0, 80)
        painter.fillRect(pixmap.rect(), overlay)

        # Draw emoji at top center
        emoji_font = QFont("Segoe UI Emoji", 48)
        painter.setFont(emoji_font)
        painter.setPen(QColor("#ffffff"))
        emoji_rect = QRect(0, 40, 280, 60)
        painter.drawText(emoji_rect, Qt.AlignCenter, emoji)

        # Draw label below emoji
        label_font = QFont("Arial", 16, QFont.Bold)
        painter.setFont(label_font)
        label_rect = QRect(0, 120, 280, 30)
        painter.drawText(label_rect, Qt.AlignCenter, label)

        # Draw "Preview Coming Soon" text
        hint_font = QFont("Arial", 10)
        painter.setFont(hint_font)
        painter.setPen(QColor("#cccccc"))
        hint_rect = QRect(0, 155, 280, 20)
        painter.drawText(hint_rect, Qt.AlignCenter, "Preview Coming Soon")

        painter.end()

        return pixmap

    @staticmethod
    def load_or_generate(module_id: str, label: str, emoji: str, section: str = "Settings") -> QPixmap:
        """
        Load screenshot from disk if it exists, otherwise generate placeholder.

        Args:
            module_id: The module's unique ID
            label: Display label for placeholder generation
            emoji: Emoji icon for placeholder generation
            section: Section name for color selection

        Returns:
            QPixmap with screenshot or placeholder
        """
        if ScreenshotManager.has_screenshot(module_id):
            # Load existing screenshot
            path = ScreenshotManager.get_screenshot_path(module_id)
            return QPixmap(str(path))
        else:
            # Generate placeholder
            return ScreenshotManager.generate_placeholder(module_id, label, emoji, section)

    @staticmethod
    def save_screenshot(module_id: str, pixmap: QPixmap) -> bool:
        """
        Save a screenshot to disk (for future use when capturing real screenshots).

        Args:
            module_id: The module's unique ID
            pixmap: The screenshot image

        Returns:
            True if saved successfully, False otherwise
        """
        # Ensure directory exists
        ScreenshotManager._SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        # Save pixmap
        path = ScreenshotManager.get_screenshot_path(module_id)
        return pixmap.save(str(path), "PNG")
