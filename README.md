# Grid Maker

Grid Maker is a desktop tool for batch-processing images and generating customizable grid overlays.  
It supports PNG, JPG, JPEG, AVIF, and WEBP formats, and allows trimming, zooming, recoloring, and grid configuration with precision.  
It also includes an advanced **Pixel Art mode**, which can downscale images into pixel-sized blocks, apply color palettes (16/32/64/Game Boy), use optional dithering filters, and then upscale them cleanly.  
This mode is especially useful for converting photos or patterns into simplified pixel-art templates and can automatically sync the grid size with the pixel dimensions for perfectly aligned results.
The built-in Preview Window lets you inspect each image with the exact final settings before exporting.

This tool is commonly used for creating **knitting, crochet, and cross-stitch patterns**, where accurately gridded images are required for pattern design.

Built with Python, CustomTkinter, and Pillow, the tool provides a modern UI, live preview system, and full control over grid settings.

---

## ✨ Features

### 🔧 Image Processing
- Trim horizontal and vertical padding  
- Resize images using a zoom factor (0.1× – 10×)  
- Apply customizable grid lines with adjustable:
  - Row/Column count
  - Grid thickness
  - Grid color  
  - Grid highlight
- High-quality rendering using LANCZOS resampling

### 🎨 Pixel Art details
- Pixel Size (scale): downscale factor. Image gets reduced to (orig/scale) then upscaled with nearest-neighbor.
- Palette options: None, 16, 32, 64, Game Boy (4 colors).
- Dithering: None | Floyd (Floyd–Steinberg) | Ordered.
- If "Sync grid to pixels" is enabled, the grid rows/cols are set automatically to match the pixel-art dimensions.

### 📁 Batch Processing
- Automatically processes all supported images in the selected folder  
- Supported formats:
  - **PNG**, **JPG**, **JPEG**, **AVIF**, **WEBP**
- Saves outputs into an automatically created `output` folder  
- Progress bar with real-time percentage  
- Detects and safely handles filenames with special characters  

### 👁️ Live Preview Window
- Non-modal preview window positioned beside the main window  
- Displays the final rendering exactly as it will be saved  
- Vertical + horizontal scrollbars for large images  
- Mouse wheel zoom preserves the point under the cursor (mouse-centered zoom).  
- Mouse drag pan allows for quick navigation (panning is limited to the preview window).
- Navigation and action buttons:
  - **Previous**
  - **Next**
  - **Re-Style**
  - **Zoom In/Out**
  - **Save**
- Automatically prevents opening multiple preview windows  

### 🖥️ User Interface
- Modern dark-themed UI built with CustomTkinter  
- Larger bold button controls  
- Real-time slider updates  
- Settings automatically saved in a JSON config  
- Reset button restores settings (folder selection remains unchanged)

### 🔒 Single Instance Protection
- Prevents running multiple app instances using a lock file  
- Automatically recovers from stale locks after 60 seconds 

### 🐞 Troubleshooting
- If the app says "already running": the lock file may exist. The app removes stale locks older than 60s automatically, or manually delete the lock file in the app data folder.
- AVIF files not loading: install `pillow-avif-plugin`.
- If preview shows "No supported images found": ensure filenames end with .png/.jpg/.jpeg/.avif/.webp (case-insensitive) and folder path is correct.
- If output filenames collide, the app will append _01, _02, ... (safe behavior).

---

## 🚀 Usage Guide

### 1. Select Input Folder
Choose a folder containing supported image formats.  
An `output` directory will be created automatically inside the same folder.

### 2. Adjust Grid and Image Settings
- Padding trim  
- Zoom factor  
- Pixel art mode
- Grid thickness
- Grid color  
- Grid rows/columns  

All settings update in real-time.

### 3. Preview (Optional)
Click **Preview Grid** to:
- View images with the applied pixel art and grid  
- Navigate between images  
- Save the preview result manually  

### 4. Start Processing
Click **Start Process**.  
All processed images will be saved into `/output/`.  

A message box will show:
- Number of processed files  
- Output folder path  
- Ask to open the output folder

---

## 🧵 Use Cases

Grid Maker is especially useful for:

- **Knitting pattern creation**  
- **Crochet charts**  
- **Cross-stitch design**  
- **Pixel-art and sprite planning**  
- **Embroidery pattern guides**  
- **Scientific / educational grid overlays**  

---

## 🖼️ Screenshots

<img width="1205" height="922" alt="Untitled5" src="https://github.com/user-attachments/assets/c1c48e80-55ac-4dbc-aa50-34ff7fe91584" />


## 📥 Download

You can download the latest compiled `.exe` version from the [Releases](https://github.com/TitanComputer/Grid-Maker/releases/latest) section.  
No need to install Python — just download and run.

## ⚙️ Usage

If you're using the Python script:
```bash
python main.py
```
Or, run the Grid-Maker.exe file directly if you downloaded the compiled version.

---

## 📦 Dependencies

- Python 3.11 or newer
- `CustomTkinter`
- Recommended: Create a virtual environment

Standard libraries only (os, re, etc.)

If you're modifying and running the script directly and use additional packages (like requests or tkinter), install them via:
```bash
pip install -r requirements.txt
```

## 📁 Project Structure

```bash
grid_maker/
│
├── main.py                     # Main application entry point
├── README.md                   # Project documentation
├── assets/
│   ├── icon.png                # Project icon
│   ├── icon.ico                # Project icon for Windows
│   ├── heart.png               # Heart Logo
│   └── donate.png              # Donate Picture
└── requirements.txt            # Python dependencies
```
---

## 🎨 Icon Credit
The application icon used in this project is sourced from [Flaticon](https://www.flaticon.com/free-icon/pixels_923035).

**Pixels icon** created by [Freepik](https://www.flaticon.com/authors/freepik) – [Flaticon](https://www.flaticon.com/)

## 🛠 Compiled with Nuitka and UPX
The executable was built using [`Nuitka`](https://nuitka.net/) and [`UPX`](https://github.com/upx/upx) for better performance and compactness, built automatically via GitHub Actions.

You can build the standalone executable using the following command:

```bash
.\venv\Scripts\python.exe -m nuitka --jobs=4 --enable-plugin=upx --upx-binary="YOUR PATH\upx.exe" --enable-plugin=multiprocessing --lto=yes --enable-plugin=tk-inter --windows-console-mode=disable --follow-imports --windows-icon-from-ico="assets/icon.png" --include-data-dir=assets=assets --include-package=pillow_avif --python-flag=no_site,no_asserts,no_docstrings,static_hashes --onefile --onefile-no-compression --standalone --msvc=latest --assume-yes-for-downloads --output-filename=Grid-Maker main.py
```

## 🚀 CI/CD

The GitHub Actions workflow builds the binary on every release and attaches it as an artifact.

---

## 🤝 Contributing
Pull requests are welcome.
If you have suggestions for improvements or new features, feel free to open an issue.

## ☕ Support
If you find this project useful and would like to support its development, consider donating:

<a href="http://www.coffeete.ir/Titan"><img width="500" height="140" alt="buymeacoffee" src="https://github.com/user-attachments/assets/8ddccb3e-2afc-4fd9-a782-89464ec7dead" /></a>

## 💰 USDT (Tether) – TRC20 Wallet Address:

```bash
TGoKk5zD3BMSGbmzHnD19m9YLpH5ZP8nQe
```
Thanks a lot for your support! 🙏
