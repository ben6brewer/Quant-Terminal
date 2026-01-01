"""Editable Table Base - Reusable base class for editable QTableWidgets.

This base class provides common infrastructure for editable tables:
- Widget wrapping pattern with container
- Position tracking for reverse widget lookup
- Theme-aware styling
- Inner widget access utilities
"""

from abc import abstractmethod
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from app.core.theme_manager import ThemeManager
from app.services.theme_stylesheet_service import ThemeStylesheetService


class EditableTableBase(QTableWidget):
    """
    Base class for editable QTableWidgets with themed cell widgets.

    Provides:
    - Widget wrapping in containers with themed backgrounds
    - Position tracking (row/col stored on widgets for O(1) lookup)
    - Theme application infrastructure
    - Inner widget access utilities

    Subclasses should:
    - Implement _get_editable_columns() to define which columns have widgets
    - Call _setup_base_table() in their __init__
    - Connect to theme_manager.theme_changed for theme updates
    """

    def __init__(
        self,
        theme_manager: ThemeManager,
        columns: List[str],
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize EditableTableBase.

        Args:
            theme_manager: Theme manager for styling
            columns: List of column header labels
            parent: Parent widget
        """
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._columns = columns
        self._highlight_editable = True

    # -------------------------------------------------------------------------
    # Abstract Methods - Must be implemented by subclasses
    # -------------------------------------------------------------------------

    @abstractmethod
    def _get_editable_columns(self) -> List[int]:
        """
        Return list of column indices that have editable widgets.

        Returns:
            List of column indices (e.g., [0, 1, 3, 4, 5, 6])
        """
        pass

    # -------------------------------------------------------------------------
    # Base Setup
    # -------------------------------------------------------------------------

    def _setup_base_table(self) -> None:
        """
        Set up basic table structure.
        Call this from subclass __init__.
        """
        self.setColumnCount(len(self._columns))
        self.setHorizontalHeaderLabels(self._columns)

        # Set header alignment
        header = self.horizontalHeader()
        for col in range(len(self._columns)):
            item = self.horizontalHeaderItem(col)
            if item:
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Fixed row heights
        v_header = self.verticalHeader()
        v_header.setVisible(True)
        v_header.setDefaultSectionSize(48)

        # Selection and display
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)

        # Scroll settings
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
        self.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)

        # Disable built-in sorting (for manual control)
        self.setSortingEnabled(False)

    def _set_corner_label(self, text: str) -> None:
        """
        Set text for the table corner button.

        Args:
            text: Label text
        """
        corner_button = self.findChild(QAbstractButton)
        if corner_button:
            corner_button.setText(text)
            corner_button.setEnabled(False)

    # -------------------------------------------------------------------------
    # Widget Wrapping
    # -------------------------------------------------------------------------

    def _wrap_widget_in_cell(self, widget: QWidget) -> QWidget:
        """
        Wrap a widget in a container with themed background.

        Args:
            widget: The widget to wrap

        Returns:
            Container widget with the widget inside
        """
        bg_color = self._get_cell_background_color()

        container = QWidget()
        container.setAutoFillBackground(True)
        container.setStyleSheet(f"QWidget {{ background-color: {bg_color}; }}")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(widget)

        # Store reference to inner widget
        container.setProperty("_inner_widget", widget)

        return container

    def _set_editable_cell_widget(
        self,
        row: int,
        col: int,
        widget: QWidget,
    ) -> None:
        """
        Set a widget in a cell with proper background coloring.

        Sets both a QTableWidgetItem with background color AND the cell widget.

        Args:
            row: Row index
            col: Column index
            widget: Widget to place in cell
        """
        bg_color = self._get_cell_background_color()

        # Create table item with background
        item = QTableWidgetItem()
        if self._highlight_editable and bg_color != "transparent":
            item.setBackground(QBrush(QColor(bg_color)))
        self.setItem(row, col, item)

        # Wrap and set widget
        container = self._wrap_widget_in_cell(widget)
        self.setCellWidget(row, col, container)

    def _get_inner_widget(self, row: int, col: int) -> Optional[QWidget]:
        """
        Get the inner widget from a cell (unwraps container).

        Args:
            row: Row index
            col: Column index

        Returns:
            Inner widget or None
        """
        cell_widget = self.cellWidget(row, col)
        if cell_widget is None:
            return None

        inner = cell_widget.property("_inner_widget")
        if inner is not None:
            return inner

        return cell_widget

    # -------------------------------------------------------------------------
    # Widget Position Tracking
    # -------------------------------------------------------------------------

    def _set_widget_position(self, widget: QWidget, row: int, col: int) -> None:
        """
        Store row/col position on widget for O(1) lookup.

        Args:
            widget: Widget to tag
            row: Row index
            col: Column index
        """
        widget.setProperty("_table_row", row)
        widget.setProperty("_table_col", col)

    def _find_row_for_widget(self, widget: QWidget) -> Optional[int]:
        """
        Find row index for a widget using stored property.

        Args:
            widget: Widget to find

        Returns:
            Row index or None
        """
        row = widget.property("_table_row")
        return row if row is not None else None

    def _find_cell_for_widget(self, widget: QWidget) -> Tuple[Optional[int], Optional[int]]:
        """
        Find (row, col) for a widget using stored properties.

        Args:
            widget: Widget to find

        Returns:
            (row, col) tuple or (None, None)
        """
        row = widget.property("_table_row")
        col = widget.property("_table_col")
        if row is not None and col is not None:
            return (row, col)
        return (None, None)

    def _update_row_positions(self, start_row: int) -> None:
        """
        Update stored row positions for all widgets from start_row onwards.

        Called after row insertion/deletion to keep positions in sync.

        Args:
            start_row: First row to update
        """
        editable_cols = self._get_editable_columns()
        for row in range(start_row, self.rowCount()):
            for col in editable_cols:
                inner_widget = self._get_inner_widget(row, col)
                if inner_widget:
                    inner_widget.setProperty("_table_row", row)

    # -------------------------------------------------------------------------
    # Theme Support
    # -------------------------------------------------------------------------

    def _get_cell_background_color(self) -> str:
        """
        Get themed background color for editable cells.

        Returns:
            Color string or "transparent"
        """
        if not self._highlight_editable:
            return "transparent"

        theme = self.theme_manager.current_theme
        colors = ThemeStylesheetService.get_colors(theme)
        return colors["accent"]

    def _get_widget_stylesheet(self) -> str:
        """Get themed stylesheet for line edit widgets."""
        theme = self.theme_manager.current_theme
        return ThemeStylesheetService.get_line_edit_stylesheet(
            theme, highlighted=self._highlight_editable
        )

    def _get_combo_stylesheet(self) -> str:
        """Get themed stylesheet for combo box widgets."""
        theme = self.theme_manager.current_theme
        return ThemeStylesheetService.get_combobox_stylesheet(
            theme, highlighted=self._highlight_editable
        )

    def _apply_base_theme(self) -> None:
        """
        Apply base theme styling to table and widgets.
        Call this from subclass _apply_theme().
        """
        theme = self.theme_manager.current_theme

        # Table stylesheet
        stylesheet = ThemeStylesheetService.get_table_stylesheet(theme)
        self.setStyleSheet(stylesheet)

        # Widget styles
        widget_stylesheet = self._get_widget_stylesheet()
        combo_stylesheet = self._get_combo_stylesheet()
        bg_color = self._get_cell_background_color()

        editable_cols = self._get_editable_columns()

        for row in range(self.rowCount()):
            for col in editable_cols:
                container = self.cellWidget(row, col)
                if container:
                    # Update container background
                    container.setStyleSheet(
                        f"QWidget {{ background-color: {bg_color}; }}"
                    )

                    # Update cell item background
                    item = self.item(row, col)
                    if item:
                        if self._highlight_editable and bg_color != "transparent":
                            item.setBackground(QBrush(QColor(bg_color)))
                        else:
                            item.setBackground(QBrush())

                    # Update inner widget style
                    inner = container.property("_inner_widget")
                    if inner:
                        if isinstance(inner, QComboBox):
                            inner.setStyleSheet(combo_stylesheet)
                        elif isinstance(inner, QLineEdit):
                            inner.setStyleSheet(widget_stylesheet)

    def set_highlight_editable(self, enabled: bool) -> None:
        """
        Enable or disable editable field highlighting.

        Args:
            enabled: True to show colored backgrounds on editable fields
        """
        if self._highlight_editable == enabled:
            return
        self._highlight_editable = enabled
        self._apply_base_theme()

    # -------------------------------------------------------------------------
    # Read-Only Cell Creation
    # -------------------------------------------------------------------------

    def _create_readonly_cell(
        self,
        row: int,
        col: int,
        text: str = "--",
    ) -> QTableWidgetItem:
        """
        Create a read-only cell item.

        Args:
            row: Row index
            col: Column index
            text: Initial text

        Returns:
            The created QTableWidgetItem
        """
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, col, item)
        return item
