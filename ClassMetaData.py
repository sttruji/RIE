from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
    QDialog, QLineEdit, QGridLayout
)


class MetadataDialog(QDialog):
    """A simple dialog that shows metadata in a table."""
    def __init__(self, metadata_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Metadata")

        # Create a table
        grid = QGridLayout()
        self.setLayout(grid)

        row = 0
        for key, val in metadata_dict.items():
            label_key = QLabel(str(key))
            label_val = QLabel(str(val))
            grid.addWidget(label_key, row, 0)
            grid.addWidget(label_val, row, 1)
            row += 1

        self.resize(600, 400)