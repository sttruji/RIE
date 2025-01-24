import rawpy
import numpy as np
import cv2
import exifread
from ClassMetaData import MetadataDialog

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
    QDialog, QLineEdit, QGridLayout
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage


def read_exif_metadata(filename):
    """Use exifread to parse available EXIF tags from the file."""
    metadata = {}
    try:
        with open(filename, "rb") as f:
            tags = exifread.process_file(f, details=False)
        for tag in tags:
            metadata[str(tag)] = str(tags[tag])
    except Exception as e:
        print(f"Error reading EXIF metadata: {e}")
    return metadata

def parse_camera_lens_exif(exif_dict):
    """
    Attempt to extract camera/lens info from EXIF for lensfun lookup.
    We look for keys like 'Image Make', 'Image Model', 'EXIF LensModel',
    'EXIF FocalLength', 'EXIF FNumber'.
    """
    camera_make = exif_dict.get('Image Make', '')
    camera_model = exif_dict.get('Image Model', '')
    lens_model = exif_dict.get('EXIF LensModel', '')
    # Some RAWs might store focal length/f-number differently:
    focal_str = exif_dict.get('EXIF FocalLength', '50')   # fallback to 50
    fnumber_str = exif_dict.get('EXIF FNumber', '2.8')    # fallback

    # Convert strings like '56.0 mm' or '56' to numeric
    try:
        focal_length = float(focal_str.split()[0])
    except:
        focal_length = 50.0
    try:
        f_number = float(fnumber_str)
    except:
        f_number = 2.8

    # We'll return a dictionary with the relevant data
    return {
        'camera_make': camera_make.strip(),
        'camera_model': camera_model.strip(),
        'lens_model': lens_model.strip(),
        'focal_length': focal_length,
        'f_number': f_number
    }

def apply_adjustments(img_float, exposure, saturation, vibrance):
    """
    Apply exposure, saturation, vibrance to a float32 RGB image in [0..1].
    Returns a new float32 image in [0..1].
    """
    # 1) Exposure
    exposure_mult = 2.0 ** exposure  # e.g. exposure=-1 => 0.5, +1 => 2.0
    img_float = img_float * exposure_mult
    img_float = np.clip(img_float, 0.0, 1.0)

    # 2) Convert to HSV and apply saturation/vibrance
    img_bgr = cv2.cvtColor(img_float, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # saturation
    s = np.clip(s + (s * saturation), 0.0, 1.0)
    # vibrance
    s = np.clip(s + (s * vibrance * (1.0 - s)), 0.0, 1.0)

    hsv = cv2.merge([h, s, v])
    img_bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_rgb = np.clip(img_rgb, 0.0, 1.0)

    return img_rgb


class RawEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RAW Editor - with Preview & Lens Correction")
        self.resize(1280, 720)

        # Main widget + layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(10,10,10,10)
        main_layout.setSpacing(10)
        main_widget.setLayout(main_layout)

        # LEFT layout: image preview + filename
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)
        main_layout.addLayout(left_layout)

        # Preview label (fixed 960x540 for a 16:9 box, for example)
        self.preview_label = QLabel("No image loaded.")
        self.preview_label.setStyleSheet("background-color: #222;")
        self.preview_label.setFixedSize(960, 540)
        self.preview_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.preview_label)

        # Filename label
        self.filename_label = QLabel("")
        self.filename_label.setStyleSheet("color: white; font-style: italic;")
        left_layout.addWidget(self.filename_label)

        # RIGHT layout: sliders & buttons
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(10)
        main_layout.addLayout(controls_layout)

        # Exposure
        exposure_box = QHBoxLayout()
        self.exposure_slider = QSlider(Qt.Horizontal)
        self.exposure_slider.setRange(-100, 100)  # -1.0 to +1.0 in increments of .01
        self.exposure_slider.setValue(0)
        self.exposure_slider.valueChanged.connect(self.on_exposure_changed)
        exposure_box.addWidget(QLabel("Exposure"))
        exposure_box.addWidget(self.exposure_slider)
        # Label to show numeric value
        self.exposure_value_label = QLabel("0.00")
        exposure_box.addWidget(self.exposure_value_label)
        controls_layout.addLayout(exposure_box)

        # Saturation
        sat_box = QHBoxLayout()
        self.saturation_slider = QSlider(Qt.Horizontal)
        self.saturation_slider.setRange(-100, 100)
        self.saturation_slider.setValue(0)
        self.saturation_slider.valueChanged.connect(self.on_saturation_changed)
        sat_box.addWidget(QLabel("Saturation"))
        sat_box.addWidget(self.saturation_slider)
        self.saturation_value_label = QLabel("0.00")
        sat_box.addWidget(self.saturation_value_label)
        controls_layout.addLayout(sat_box)

        # Vibrance
        vib_box = QHBoxLayout()
        self.vibrance_slider = QSlider(Qt.Horizontal)
        self.vibrance_slider.setRange(-100, 100)
        self.vibrance_slider.setValue(0)
        self.vibrance_slider.valueChanged.connect(self.on_vibrance_changed)
        vib_box.addWidget(QLabel("Vibrance"))
        vib_box.addWidget(self.vibrance_slider)
        self.vibrance_value_label = QLabel("0.00")
        vib_box.addWidget(self.vibrance_value_label)
        controls_layout.addLayout(vib_box)

        # Buttons
        load_button = QPushButton("Load RAW (.ARW)")
        load_button.clicked.connect(self.load_raw)
        controls_layout.addWidget(load_button)

        export_button = QPushButton("Export as JPEG")
        export_button.clicked.connect(self.export_as_jpeg)
        controls_layout.addWidget(export_button)

        meta_button = QPushButton("View Metadata")
        meta_button.clicked.connect(self.show_metadata)
        controls_layout.addWidget(meta_button)

        controls_layout.addStretch()

        # --- INTERNAL VARS ---
        self.full_image = None          # full-resolution float32 RGB [0..1]
        self.preview_image = None       # smaller float32 RGB for real-time slider updates
        self.preview_scale = 0.25       # 25% scale for preview (adjust as needed)
        self.metadata_dict = {}
        self.camera_info = {}
        self.current_filename = None

        # Keep track if lens correction applied
        self.lens_correction_applied = False

        # Timers / signals to handle slider release
        # We'll only re-generate the full-res image once the user stops adjusting
        self.slider_update_timer = QTimer()
        self.slider_update_timer.setSingleShot(True)
        self.slider_update_timer.setInterval(300)  # 300ms after last change
        self.slider_update_timer.timeout.connect(self.process_full_res)

        # Connect sliderReleased signals to finalize
        self.exposure_slider.sliderReleased.connect(self.on_slider_released)
        self.saturation_slider.sliderReleased.connect(self.on_slider_released)
        self.vibrance_slider.sliderReleased.connect(self.on_slider_released)


    ### ------------------------
    ###       SLOT METHODS
    ### ------------------------

    def load_raw(self):
        """Open a file dialog to load a RAW file and decode it."""
        file_dialog = QFileDialog()
        filename, _ = file_dialog.getOpenFileName(
            self, "Open RAW File", "",
            "RAW Files (*.arw *.dng *.nef *.cr2 *.rw2 *.raf *.orf *.srw)"
        )
        if filename:
            try:
                with rawpy.imread(filename) as raw:
                    # Get full-res in float32 [0..1]
                    rgb8 = raw.postprocess()
                    self.full_image = rgb8.astype(np.float32) / 255.0

                # Create a smaller preview image (e.g., 25% size)
                h, w, c = self.full_image.shape
                preview_w = int(w * self.preview_scale)
                preview_h = int(h * self.preview_scale)
                self.preview_image = cv2.resize(
                    self.full_image, (preview_w, preview_h),
                    interpolation=cv2.INTER_AREA
                )

                # Read metadata
                self.metadata_dict = read_exif_metadata(filename)
                self.camera_info = parse_camera_lens_exif(self.metadata_dict)
                self.current_filename = filename
                self.filename_label.setText(f"Loaded: {filename}")

                # Reset sliders
                self.exposure_slider.setValue(0)
                self.saturation_slider.setValue(0)
                self.vibrance_slider.setValue(0)
                self.lens_correction_applied = False

                self.update_preview()  # show initial preview
            except Exception as e:
                print(f"Error loading RAW: {e}")


    def export_as_jpeg(self):
        """Save the current full-resolution edited image as a JPEG."""
        if self.full_image is None:
            return
        # Make sure we do a final process on the full image so the user’s latest slider settings are applied
        self.process_full_res()

        file_dialog = QFileDialog()
        save_path, _ = file_dialog.getSaveFileName(self, "Save as JPEG", "", "JPEG Files (*.jpg *.jpeg)")
        if save_path:
            # Convert from float32 [0..1] to 8-bit BGR
            final_bgr = (self.full_image * 255.0).clip(0, 255).astype(np.uint8)
            final_bgr = cv2.cvtColor(final_bgr, cv2.COLOR_RGB2BGR)
            cv2.imwrite(save_path, final_bgr)
            print(f"Exported: {save_path}")

    def show_metadata(self):
        """Open a dialog showing metadata in a table."""
        if not self.metadata_dict:
            return
        dialog = MetadataDialog(self.metadata_dict, self)
        dialog.exec_()

    def on_exposure_changed(self, value):
        # value is in [-100..100], meaning [-1..1] stops
        exposure_stops = value / 100.0
        self.exposure_value_label.setText(f"{exposure_stops:.2f}")
        self.update_preview()

    def on_saturation_changed(self, value):
        sat = value / 100.0
        self.saturation_value_label.setText(f"{sat:.2f}")
        self.update_preview()

    def on_vibrance_changed(self, value):
        vib = value / 100.0
        self.vibrance_value_label.setText(f"{vib:.2f}")
        self.update_preview()

    def on_slider_released(self):
        """
        Called when the user stops moving a slider. We'll wait 300ms
        and then update the full-res image. This avoids heavy computations
        if the user quickly moves multiple sliders.
        """
        self.slider_update_timer.start()

    ### ------------------------
    ###     IMAGE PROCESSING
    ### ------------------------

    def update_preview(self):
        """
        Apply current slider settings to self.preview_image and show it.
        (This is for quick feedback.)
        """
        if self.preview_image is None:
            return

        # Sliders
        exposure_val = self.exposure_slider.value() / 100.0
        sat_val = self.saturation_slider.value() / 100.0
        vib_val = self.vibrance_slider.value() / 100.0

        # Copy the preview
        preview_copy = self.preview_image.copy()
        # Apply adjustments
        adjusted = apply_adjustments(preview_copy, exposure_val, sat_val, vib_val)
        # Convert to 8-bit for display
        display_8u = (adjusted * 255.0).clip(0,255).astype(np.uint8)

        h, w, c = display_8u.shape
        bytes_per_line = c * w
        qimage = QImage(display_8u.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage)

        # Scale to fit the label (if you want to keep aspect ratio, you can do that).
        # But since our label is exactly the preview size, we can just set it directly:
        self.preview_label.setPixmap(pixmap)

    def process_full_res(self):
        """
        Apply slider settings to the *full-resolution* image (heavy operation).
        Called after sliderRelease or on export, so we do it less frequently.
        """
        if self.full_image is None:
            return

        # Sliders
        exposure_val = self.exposure_slider.value() / 100.0
        sat_val = self.saturation_slider.value() / 100.0
        vib_val = self.vibrance_slider.value() / 100.0

        # Apply adjustments
        full_copy = self.full_image.copy()
        adjusted_full = apply_adjustments(full_copy, exposure_val, sat_val, vib_val)

        self.full_image = adjusted_full

        # If lens correction was toggled AFTER we loaded, and user wants it
        # we could re-apply lens correction here. But in this example, we only
        # apply lens correction once (when the user clicks the button).
        # If you want to re-run lens correction each time, you'd do:
        # if self.lens_correction_applied:
        #     self.full_image = lensfun_correct(self.full_image, self.camera_info)

        print("Full-res image updated with current slider settings.")