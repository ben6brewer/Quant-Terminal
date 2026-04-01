"""Minimal PySide6 widget create/destroy cycle test.

Tests whether shiboken6 has a heap corruption bug when rapidly
creating and destroying QWidget trees.

Run with:
    MallocScribble=1 .venv/bin/python test_widget_cycle.py

Expected: either crashes (shiboken6 bug) or runs 1000 cycles (app bug).
"""
import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QStackedWidget, QStackedLayout,
    QPushButton, QLabel, QCheckBox, QRadioButton, QGraphicsView,
    QTableView,
)
from PySide6.QtCore import QTimer

app = QApplication(sys.argv)
stack = QStackedWidget()
stack.resize(800, 600)
stack.show()

cycle = [0]


def create_module_widget():
    """Create a widget tree similar to a Quant Terminal module."""
    container = QWidget()
    container_layout = QStackedLayout(container)
    container_layout.setStackingMode(QStackedLayout.StackAll)

    module = QWidget()
    layout = QVBoxLayout(module)
    layout.addWidget(QPushButton("Button 1"))
    layout.addWidget(QPushButton("Button 2"))
    layout.addWidget(QLabel("Label"))
    layout.addWidget(QCheckBox("Check"))
    layout.addWidget(QRadioButton("Radio"))
    layout.addWidget(QGraphicsView())
    layout.addWidget(QTableView())
    container_layout.addWidget(module)

    overlay = QWidget()
    overlay_layout = QVBoxLayout(overlay)
    overlay_layout.addWidget(QPushButton("Home"))
    container_layout.addWidget(overlay)

    return container


def cycle_once():
    # Remove and destroy current (mimics _destroy_module_container)
    if stack.count() > 0:
        old = stack.widget(0)
        stack.removeWidget(old)
        old.hide()
        old.setParent(None)
        old.deleteLater()

    # Create new (mimics open_module with factory)
    new_widget = create_module_widget()
    stack.addWidget(new_widget)
    stack.setCurrentWidget(new_widget)

    cycle[0] += 1
    if cycle[0] % 50 == 0:
        print(f"Cycle {cycle[0]} OK")

    if cycle[0] >= 1000:
        print("PASSED: 1000 cycles without crash")
        app.quit()


timer = QTimer()
timer.timeout.connect(cycle_once)
timer.start(0)

sys.exit(app.exec())
