import sys
import shutil
from pathlib import Path
from sqlalchemy.orm import Session
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QSplitter, QLabel, QTableWidget,
    QTableWidgetItem, QFileDialog, QHBoxLayout, QMessageBox, QVBoxLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget

from CleanerBase import APPLICATION
from cleaner_app import CleanerApp
# --- replace with your actual model ---
# from mymodels import FileModel, engine

def get_db_paths(session: Session) -> set[str]:
    # return {row[0] for row in session.query(FileModel.path)}
    return {"/tmp/test.jpg", "/tmp/missing.mp4"}


def get_all_files(root: str) -> set[str]:
    return {str(p) for p in Path(root).rglob("*") if p.is_file()}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cleaner_app = CleanerApp(restore=True)
        if not self.cleaner_app.input_folder:
            self.cleaner_app.input_folder = Path().home()
        if not self.cleaner_app.output_folder:
            self.cleaner_app.output_folder = self.cleaner_app.input_folder

        self.setWindowTitle(APPLICATION)

        container = QWidget()
        layout = QVBoxLayout(container)

        # Top button row
        button_row = QHBoxLayout()

        self.scan_btn = QPushButton("Run Scan")
        self.scan_btn.clicked.connect(self.run_scan)
        button_row.addWidget(self.scan_btn)

        self.pick_root_btn = QPushButton("Choose Root Folder")
        self.pick_root_btn.clicked.connect(self.choose_root)
        button_row.addWidget(self.pick_root_btn)

        self.import_btn = QPushButton("Import Directory")
        self.import_btn.clicked.connect(self.import_directory)
        button_row.addWidget(self.import_btn)

        layout.addLayout(button_row)

        # Splitter: table left | preview right
        splitter = QSplitter(Qt.Horizontal)

        self.config_row = QHBoxLayout()
        self.input_btn = QPushButton("new")
        # self.input_btn.clicked.connect(self.input_btn)
        self.config_row.addWidget(self.input_btn)
        layout.addLayout(self.config_row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Path", "Status"])
        self.table.cellClicked.connect(self.preview_file)
        splitter.addWidget(self.table)

        self.preview_container = QWidget()
        preview_layout = QVBoxLayout(self.preview_container)

        self.image_label = QLabel("No preview")
        self.image_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.image_label)

        self.video_widget = QVideoWidget()
        preview_layout.addWidget(self.video_widget)

        self.player = QMediaPlayer()
        self.player.setVideoOutput(self.video_widget)

        splitter.addWidget(self.preview_container)
        splitter.setSizes([400, 400])

        layout.addWidget(splitter)

        self.setCentralWidget(container)

        self.root_folder = str(Path.home())

    def choose_root(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose blah blah Folder", str(self.cleaner_app.output_folder))
        if folder:
            self.root_folder = folder

    def run_scan(self):
        session = None  # Session(engine) in real code
        db_paths = get_db_paths(session)
        fs_paths = get_all_files(self.root_folder)

        only_in_db = db_paths - fs_paths
        only_on_disk = fs_paths - db_paths

        results = []
        results.extend([(p, "DB only") for p in only_in_db])
        results.extend([(p, "Disk only") for p in only_on_disk])

        self.table.setRowCount(len(results))
        for row, (path, status) in enumerate(results):
            self.table.setItem(row, 0, QTableWidgetItem(path))
            self.table.setItem(row, 1, QTableWidgetItem(status))

    def preview_file(self, row, col):
        path_item = self.table.item(row, 0)
        if not path_item:
            return
        path = path_item.text()

        if any(path.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".bmp", ".gif"]):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.player.stop()
                self.video_widget.hide()
                self.image_label.show()
                self.image_label.setPixmap(pixmap.scaled(400, 400, Qt.KeepAspectRatio))
        elif any(path.lower().endswith(ext) for ext in [".mp4", ".avi", ".mkv"]):
            self.image_label.hide()
            self.video_widget.show()
            self.player.setSource(path)
            self.player.play()
        else:
            self.image_label.setText("No preview available")
            self.image_label.show()
            self.video_widget.hide()

    def import_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose Directory to Import")
        if not folder:
            return

        import_paths = get_all_files(folder)
        base_paths = get_all_files(self.root_folder)

        unique_files = import_paths - base_paths
        moved = 0

        for f in unique_files:
            try:
                dest = Path(self.root_folder) / Path(f).name
                shutil.move(f, dest)
                moved += 1
            except Exception as e:
                QMessageBox.warning(self, "Import Error", f"Failed to import {f}:\n{e}")

        QMessageBox.information(self, "Import Complete", f"Imported {moved} unique files into {self.root_folder}")
        self.run_scan()  # refresh table after import


if __name__ == "__main__":
    app = QApplication(sys.argv)   # create the Qt application
    win = MainWindow()              # make your window
    win.resize(900, 600)            # optional, set initial size
    win.show()                      # show the window
    sys.exit(app.exec())            # run the event loop until quit
