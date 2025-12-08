import os
import subprocess
import sys
import json
import math
import time
import threading
import webbrowser
from PIL import Image, ImageDraw, ImageTk, ImageFont, ImageFilter
import tkinter as tk
from tkinter import colorchooser, messagebox
import customtkinter as ctk
from customtkinter import filedialog, CTkImage
from idlelib.tooltip import Hovertip

APP_VERSION = "2.7.0"
APP_NAME = "Grid Maker"
CONFIG_FILENAME = "config.json"

# Default configuration structure
DEFAULT_CONFIG = {
    "app_name": APP_NAME,
    "app_version": APP_VERSION,
    "folder_path": "",
    "h_padding": 0,
    "v_padding": 0,
    "zoom_factor": 1.0,
    "grid_color": "#000000",
    "grid_rows": 100,
    "show_grid_numbers": True,
    "grid_number_text_color": "#000000",
    "grid_number_bg_color": "#FFFFFF",
    "grid_enabled": True,
    "grid_thickness": 1,
    "grid_highlight_every": 0,
    "pixel_art_enabled": True,
    "pixel_art_scale": 8,
    "pixel_art_palette": "None",
    "pixel_art_dithering": "None",
    "pixel_art_sharpen": False,
    "sync_grid_to_pixels": True,
}

# Determine configuration directory based on OS
if sys.platform == "win32":
    CONFIG_DIR = os.path.join(os.getenv("LOCALAPPDATA", "/tmp"), APP_NAME)
else:
    CONFIG_DIR = os.path.join(os.getenv("HOME", "/tmp"), f".{APP_NAME}")

CONFIG_FILE = os.path.join(CONFIG_DIR, CONFIG_FILENAME)
os.makedirs(CONFIG_DIR, exist_ok=True)


# --- Single Instance Logic START with Timeout ---
APP_LOCK_DIR = os.path.join(os.getenv("LOCALAPPDATA", os.getenv("HOME", "/tmp")), APP_NAME)
LOCK_FILE = os.path.join(APP_LOCK_DIR, "app.lock")
LOCK_TIMEOUT_SECONDS = 60

os.makedirs(APP_LOCK_DIR, exist_ok=True)
IS_LOCK_CREATED = False

if os.path.exists(LOCK_FILE):
    try:
        lock_age = time.time() - os.path.getmtime(LOCK_FILE)

        if lock_age > LOCK_TIMEOUT_SECONDS:
            os.remove(LOCK_FILE)
            print(f"Removed stale lock file (Age: {int(lock_age)}s).")
        else:
            try:
                temp_root = tk.Tk()
                temp_root.withdraw()
                messagebox.showwarning(
                    f"{APP_NAME} v{APP_VERSION}",
                    f"{APP_NAME} is already running.\nOnly one instance is allowed.",
                )
                temp_root.destroy()
            except Exception:
                print("Application is already running.")

            sys.exit(0)

    except Exception as e:
        print(f"Error checking lock file: {e}. Exiting.")
        sys.exit(0)

try:
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    IS_LOCK_CREATED = True
except Exception as e:
    print(f"Could not create lock file: {e}")
    sys.exit(1)

# --- Single Instance Logic END with Timeout ---


class GridMaker(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")

        # Load assets safely (assuming 'assets' folder is alongside the script)
        # Using a resource path helper if needed, but for simplicity we rely on relative path here.
        temp_dir = os.path.dirname(__file__)
        try:
            self.iconpath = ImageTk.PhotoImage(file=self.resource_path(os.path.join(temp_dir, "assets", "icon.png")))
            heart_path = self.resource_path(os.path.join(temp_dir, "assets", "heart.png"))
            img = Image.open(heart_path)
            width_img, height_img = img.size
            # For CTk widgets (scaled, recommended)
            self.heart_image = ctk.CTkImage(
                light_image=Image.open(heart_path), dark_image=Image.open(heart_path), size=(width_img, height_img)
            )

            # For window icon (must be PhotoImage)
            self.heart_icon = ImageTk.PhotoImage(file=heart_path)
            self.wm_iconbitmap()
            self.iconphoto(False, self.iconpath)
        except Exception:
            # Fallback if assets are missing
            self.iconpath = None
            self.heart_image = None
            print("Warning: Could not load application icons.")

        self.center_window()
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- Variables ---
        self.folder_path_var = ctk.StringVar(value=DEFAULT_CONFIG["folder_path"])
        # Variable for displaying progress percentage
        self.progress_text_var = ctk.StringVar(value="0%")
        self.settings = {
            "h_padding": ctk.IntVar(value=DEFAULT_CONFIG["h_padding"]),
            "v_padding": ctk.IntVar(value=DEFAULT_CONFIG["v_padding"]),
            "zoom_factor": ctk.DoubleVar(value=DEFAULT_CONFIG["zoom_factor"]),
            "grid_color": ctk.StringVar(value=DEFAULT_CONFIG["grid_color"]),
            "grid_rows": ctk.IntVar(value=DEFAULT_CONFIG["grid_rows"]),
            "show_grid_numbers": ctk.BooleanVar(value=DEFAULT_CONFIG["show_grid_numbers"]),
            "grid_number_text_color": ctk.StringVar(value=DEFAULT_CONFIG["grid_number_text_color"]),
            "grid_number_bg_color": ctk.StringVar(value=DEFAULT_CONFIG["grid_number_bg_color"]),
            "grid_enabled": ctk.BooleanVar(value=DEFAULT_CONFIG["grid_enabled"]),
            "grid_thickness": ctk.IntVar(value=DEFAULT_CONFIG["grid_thickness"]),
            "grid_highlight_every": ctk.IntVar(value=DEFAULT_CONFIG["grid_highlight_every"]),
            "pixel_art_enabled": ctk.BooleanVar(value=DEFAULT_CONFIG["pixel_art_enabled"]),
            "pixel_art_scale": ctk.IntVar(value=DEFAULT_CONFIG["pixel_art_scale"]),
            "pixel_art_palette": ctk.StringVar(value=DEFAULT_CONFIG["pixel_art_palette"]),
            "pixel_art_dithering": ctk.StringVar(value=DEFAULT_CONFIG["pixel_art_dithering"]),
            "pixel_art_sharpen": ctk.BooleanVar(value=DEFAULT_CONFIG["pixel_art_sharpen"]),
            "sync_grid_to_pixels": ctk.BooleanVar(value=DEFAULT_CONFIG["sync_grid_to_pixels"]),
        }
        # cols no longer has its own slider → always same as rows
        self.settings["grid_cols"] = self.settings["grid_rows"]
        self.is_running = False
        self.stop_requested = False
        self.total_files = 0
        self.processing_thread = None

        # preview-only state
        self._preview_scale = 1.0
        self._preview_scale_min = 1.0
        self._preview_scale_max = 4.0
        self._preview_zoom_target = None  # "center" or "mouse" or None
        self._preview_before_abs = None  # (abs_x_before, abs_y_before)
        self._preview_before_bbox = None  # bbox before zoom
        self._preview_mouse_x = None  # last mouse pos on canvas (pixels)
        self._preview_mouse_y = None

        # Load config to overwrite default variable values
        self.load_config()

        # --- UI Setup ---
        self.grid_columnconfigure(0, weight=1)
        self._create_widgets()
        self._on_grid_toggle()
        self._update_preview_button_state()

        # --- Lock Updater Control START ---
        self.lock_refresh_active = True
        if "IS_LOCK_CREATED" in globals() and IS_LOCK_CREATED:
            self.lock_thread = threading.Thread(target=self._lock_updater, daemon=True)
            self.lock_thread.start()
            print("Lock refresh started.")
        # --- Lock Updater Control END ---

    def _update_preview_button_state(self):
        folder = self.folder_path_var.get()
        if not os.path.isdir(folder):
            self.preview_button.configure(state="disabled")
            return
        supported = (".png", ".jpg", ".jpeg", ".avif", ".webp")
        files = [
            f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(supported)
        ]
        if len(files) > 0:
            self.preview_button.configure(state="normal")
        else:
            self.preview_button.configure(state="disabled")

    def center_window(self):
        """
        Centers the main application window on the screen.

        This function calculates the appropriate x and y coordinates such that
        the window is positioned at the center of the user's screen. It sets the
        window's geometry using a fixed width and height.
        """
        self.update_idletasks()
        width = 500
        height = 890
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def resource_path(self, relative_path):
        """Get absolute path to resource, needed for PyInstaller."""
        temp_dir = os.path.dirname(__file__)
        return os.path.join(temp_dir, relative_path)

    # --- Config Management Methods ---

    def load_config(self):
        """Loads configuration from config.json or uses defaults."""
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                for key in DEFAULT_CONFIG:
                    if key in config:
                        # Update variables if key exists in settings dictionary
                        if key in self.settings:
                            self.settings[key].set(config[key])
                        # Special handling for folder_path (StringVar)
                        elif key == "folder_path":
                            self.folder_path_var.set(config["folder_path"])
                        elif key == "show_grid_numbers":
                            self.settings["show_grid_numbers"].set(config[key])

                print("Configuration loaded successfully.")
        except FileNotFoundError:
            print("Config file not found. Using default settings.")
            self._apply_default_config()
        except json.JSONDecodeError:
            print("Error decoding config file. Using default settings.")
            self._apply_default_config()
        except Exception as e:
            print(f"An unexpected error occurred during config loading: {e}. Using default settings.")
            self._apply_default_config()

    def _apply_default_config(self):
        """Applies values from DEFAULT_CONFIG to instance variables."""
        for key, value in DEFAULT_CONFIG.items():
            if key in self.settings:
                self.settings[key].set(value)
        self.folder_path_var.set(DEFAULT_CONFIG["folder_path"])

    def save_config(self):
        """Saves current application settings to config.json."""
        config_data = {
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "folder_path": self.folder_path_var.get(),
            "h_padding": self.settings["h_padding"].get(),
            "v_padding": self.settings["v_padding"].get(),
            "zoom_factor": self.settings["zoom_factor"].get(),
            "grid_color": self.settings["grid_color"].get(),
            "grid_rows": self.settings["grid_rows"].get(),
            "show_grid_numbers": self.settings["show_grid_numbers"].get(),
            "grid_number_text_color": self.settings["grid_number_text_color"].get(),
            "grid_number_bg_color": self.settings["grid_number_bg_color"].get(),
            "grid_enabled": self.settings["grid_enabled"].get(),
            "grid_thickness": self.settings["grid_thickness"].get(),
            "grid_highlight_every": self.settings["grid_highlight_every"].get(),
            "pixel_art_enabled": self.settings["pixel_art_enabled"].get(),
            "pixel_art_scale": self.settings["pixel_art_scale"].get(),
            "pixel_art_palette": self.settings["pixel_art_palette"].get(),
            "pixel_art_dithering": self.settings["pixel_art_dithering"].get(),
            "pixel_art_sharpen": self.settings["pixel_art_sharpen"].get(),
            "sync_grid_to_pixels": self.settings["sync_grid_to_pixels"].get(),
        }

        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config_data, f, indent=4)
            print("Configuration saved successfully.")
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def _draw_grid(self, img, rows, cols, color):
        """
        Draws a grid on the given PIL image object.
        Tries to keep cells square and covers the entire image.
        If rows or cols is zero, grid drawing is skipped.
        """

        width, height = img.size
        draw = ImageDraw.Draw(img)

        # grid thickness
        thickness = self.settings["grid_thickness"].get()

        # grid highlight
        highlight_every = self.settings["grid_highlight_every"].get()

        # base square size (try to keep cells square)
        cell_w = width / cols
        cell_h = height / rows
        cell_size = max(cell_w, cell_h)

        # how many cells needed to cover full image
        cols_needed = int(math.ceil(width / cell_size))
        rows_needed = int(math.ceil(height / cell_size))

        # draw horizontal lines (y)
        for r in range(rows_needed):
            y = r * cell_size
            line_thickness = thickness
            if highlight_every and r % highlight_every == 0:
                line_thickness += 1
            draw.line([(0, y), (width, y)], fill=color, width=line_thickness)

        # draw last horizontal line
        line_thickness = thickness
        if highlight_every and rows_needed % highlight_every == 0:
            line_thickness += 1
        draw.line([(0, height), (width, height)], fill=color, width=line_thickness)

        # draw vertical lines (x)
        for c in range(cols_needed):
            x = c * cell_size
            line_thickness = thickness
            if highlight_every and c % highlight_every == 0:
                line_thickness += 1
            draw.line([(x, 0), (x, height)], fill=color, width=line_thickness)

        # draw last vertical line
        line_thickness = thickness
        if highlight_every and cols_needed % highlight_every == 0:
            line_thickness += 1
        draw.line([(width, 0), (width, height)], fill=color, width=line_thickness)

        return img

    def _render_preview_image(self):
        """Render the currently selected image into the preview window using CTkImage."""
        if not (hasattr(self, "preview_files") and self.preview_files):
            return

        # ensure preview-only scale exists
        self._preview_scale = getattr(self, "_preview_scale", 1.0)

        img_path = self.preview_files[self.preview_index]

        try:
            img = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"Preview load error: {e}")
            return

        # Load settings
        h_pad = self.settings["h_padding"].get()
        v_pad = self.settings["v_padding"].get()
        zoom = self.settings["zoom_factor"].get()
        grid_color = self.settings["grid_color"].get()
        rows = self.settings["grid_rows"].get()
        cols = rows  # always square grid

        # Crop padding
        width, height = img.size
        if width > 2 * h_pad and height > 2 * v_pad:
            img = img.crop((h_pad, v_pad, width - h_pad, height - v_pad))

        # Apply zoom
        width, height = img.size
        new_width = int(width * zoom)
        new_height = int(height * zoom)
        if new_width > 0 and new_height > 0:
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Apply Pixel Art
        if self.settings["pixel_art_enabled"].get():
            img = self._apply_pixel_art(img)
            rows = self.settings["grid_rows"].get()
            cols = rows

        # --- Skip if grid disabled ---
        if self.settings.get("grid_enabled").get() and rows > 0:
            # Draw grid
            img = self._draw_grid(img, rows, cols, grid_color)
            # --- Apply grid numbers if enabled
            if self.settings["show_grid_numbers"].get():
                img = self._apply_grid_numbers(img)

        # Resize to fit preview window (apply preview-only scale)
        try:
            preview_width = self.preview_window.winfo_width()
            if preview_width < 50:
                preview_width = 600
        except:
            preview_width = 600

        # base fit-to-window size
        aspect_ratio = img.height / img.width
        base_width = preview_width
        base_height = int(base_width * aspect_ratio)

        # apply preview-only scale
        scale = getattr(self, "_preview_scale", 1.0)

        # clamp scale to reasonable bounds
        if scale < self._preview_scale_min:
            scale = self._preview_scale_min
            self._preview_scale = scale
        if scale > self._preview_scale_max:
            scale = self._preview_scale_max
            self._preview_scale = scale

        # compute target display size
        target_width = max(1, int(base_width * scale))
        target_height = max(1, int(base_height * scale))

        # optional: prevent zooming out smaller than fit-to-window (so image not tiny)
        if target_width < base_width or target_height < base_height:
            target_width = base_width
            target_height = base_height
            self._preview_scale = 1.0
            scale = 1.0

        final_img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        # Convert to CTkImage (fix HighDPI warning)
        ctk_img = CTkImage(light_image=final_img, dark_image=final_img, size=(target_width, target_height))

        self.last_render = img
        self.preview_image_label.configure(image=ctk_img)
        self.preview_image_label.image = ctk_img  # prevent garbage collection

        # update canvas scrollregion
        try:
            # run idle tasks to ensure widget sizes updated
            self.preview_frame.update_idletasks()
            # old bbox MAY be stored in self._preview_before_bbox (set before zoom)
            self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))
            # if a zoom action occurred, recenter accordingly
            if getattr(self, "_preview_zoom_target", None) is not None:
                before_bbox = getattr(self, "_preview_before_bbox", None)
                before_abs = getattr(self, "_preview_before_abs", None)
                # bbox after
                after_bbox = self.preview_canvas.bbox("all") or (0, 0, 1, 1)

                if before_bbox and before_abs:
                    bx1, by1, bx2, by2 = before_bbox
                    ax1, ay1, ax2, ay2 = after_bbox
                    old_w = max(1, bx2 - bx1)
                    old_h = max(1, by2 - by1)
                    new_w = max(1, ax2 - ax1)
                    new_h = max(1, ay2 - ay1)

                    abs_x_before, abs_y_before = before_abs

                    # compute relative fraction inside old content
                    rel_x = (abs_x_before - bx1) / old_w
                    rel_y = (abs_y_before - by1) / old_h
                    rel_x = min(max(rel_x, 0.0), 1.0)
                    rel_y = min(max(rel_y, 0.0), 1.0)

                    # compute new absolute coordinate in AFTER bbox corresponding to same relative point
                    abs_x_after = ax1 + rel_x * new_w
                    abs_y_after = ay1 + rel_y * new_h

                    # now compute target top-left so that that absolute point appears at the same canvas pixel
                    # get focal canvas pixel: if target was mouse, use stored mouse coords; else center
                    if (
                        self._preview_zoom_target == "mouse"
                        and self._preview_mouse_x is not None
                        and self._preview_mouse_y is not None
                    ):
                        focal_x = self._preview_mouse_x
                        focal_y = self._preview_mouse_y
                    else:
                        focal_x = self.preview_canvas.winfo_width() // 2
                        focal_y = self.preview_canvas.winfo_height() // 2

                    # desired top-left absolute after so that abs_x_after maps to focal_x:
                    desired_left = abs_x_after - focal_x
                    desired_top = abs_y_after - focal_y

                    # convert to fraction for xview_moveto/yview_moveto (0..1)
                    frac_x = desired_left / new_w
                    frac_y = desired_top / new_h
                    frac_x = min(max(frac_x, 0.0), 1.0)
                    frac_y = min(max(frac_y, 0.0), 1.0)

                    try:
                        self.preview_canvas.xview_moveto(frac_x)
                        self.preview_canvas.yview_moveto(frac_y)
                    except:
                        pass

                else:
                    # fallback: center
                    self._center_preview_on_canvas()

                # reset zoom-target state so normal renders won't recenter
                self._preview_zoom_target = None
                self._preview_before_bbox = None
                self._preview_before_abs = None
            else:
                # no zoom action — do nothing (keep current scroll as-is)
                pass

        except Exception:
            pass

    def _center_preview_on_canvas(self):
        try:
            self.preview_canvas.update_idletasks()

            x1, y1, x2, y2 = self.preview_canvas.bbox("all")
            content_w = x2 - x1
            content_h = y2 - y1

            canvas_w = self.preview_canvas.winfo_width()
            canvas_h = self.preview_canvas.winfo_height()

            # compute target scroll offsets
            if content_w > canvas_w:
                x_offset = (content_w - canvas_w) / 2
                self.preview_canvas.xview_moveto(x_offset / content_w)
            else:
                self.preview_canvas.xview_moveto(0)

            if content_h > canvas_h:
                y_offset = (content_h - canvas_h) / 2
                self.preview_canvas.yview_moveto(y_offset / content_h)
            else:
                self.preview_canvas.yview_moveto(0)

        except:
            pass

    def _reset_scrollbar(self):
        if hasattr(self, "preview_window") and self.preview_window.winfo_exists():
            self.preview_canvas.yview_moveto(0)
            self.preview_canvas.xview_moveto(0)

    def _preview_next(self):
        if self.preview_index < len(self.preview_files) - 1:
            self.preview_index += 1
            self._preview_scale = 1.0
            self._reset_scrollbar()
            self._render_preview_image()
            self._update_preview_nav_buttons()

    def _preview_prev(self):
        if self.preview_index > 0:
            self.preview_index -= 1
            self._preview_scale = 1.0
            self._reset_scrollbar()
            self._render_preview_image()
            self._update_preview_nav_buttons()

    def _preview_restyle(self):
        self._preview_scale = 1.0
        self._update_preview_nav_buttons()
        self._render_preview_image()
        self._reset_scrollbar()

    def _update_zoom_buttons(self):
        scale = getattr(self, "_preview_scale", 1.0)

        if scale <= self._preview_scale_min:
            self.zoom_out_btn.configure(state="disabled")
        else:
            self.zoom_out_btn.configure(state="normal")

        if scale >= self._preview_scale_max:
            self.zoom_in_btn.configure(state="disabled")
        else:
            self.zoom_in_btn.configure(state="normal")

    def _preview_zoom_in(self, target="center"):
        cur = self._preview_scale
        if cur >= self._preview_scale_max:
            return

        self._preview_scale = min(cur * 1.25, self._preview_scale_max)
        self._preview_zoom_target = target
        self._render_preview_image()
        self._update_zoom_buttons()

    def _preview_zoom_out(self, target="center"):
        cur = self._preview_scale
        if cur <= self._preview_scale_min:
            return

        self._preview_scale = max(cur / 1.25, self._preview_scale_min)
        self._preview_zoom_target = target
        self._render_preview_image()
        self._update_zoom_buttons()

    def _mousewheel_zoom(self, event):
        """
        Handle mouse-wheel zoom so the point under the cursor stays fixed.
        Stores 'before' bbox and absolute coords, sets zoom target to "mouse",
        updates preview scale and triggers a render (which will recenter).
        """
        canvas = self.preview_canvas

        # compute mouse position relative to canvas (client coords)
        try:
            # best: use pointer position to handle focus/label vs canvas differences
            cx = canvas.winfo_pointerx() - canvas.winfo_rootx()
            cy = canvas.winfo_pointery() - canvas.winfo_rooty()
        except Exception:
            # fallback: use event coords (might be relative to widget that raised event)
            cx = getattr(event, "x", 0)
            cy = getattr(event, "y", 0)

        # store bbox and absolute canvas coordinate of that point BEFORE changing scale
        try:
            before_bbox = canvas.bbox("all")
        except Exception:
            before_bbox = None

        # absolute coords in canvas space (works even when scrolled)
        try:
            abs_x_before = canvas.canvasx(cx)
            abs_y_before = canvas.canvasy(cy)
        except Exception:
            abs_x_before = cx
            abs_y_before = cy

        self._preview_before_bbox = before_bbox
        self._preview_before_abs = (abs_x_before, abs_y_before)
        self._preview_mouse_x = int(cx)
        self._preview_mouse_y = int(cy)
        self._preview_zoom_target = "mouse"

        # compute new scale
        cur = self._preview_scale

        if event.delta > 0:  # zoom in
            if cur >= self._preview_scale_max:
                return  # stop zoom
            new_scale = min(cur * 1.25, self._preview_scale_max)
        else:  # zoom out
            if cur <= self._preview_scale_min:
                return
            new_scale = max(cur / 1.25, self._preview_scale_min)

        self._preview_scale = new_scale
        self._render_preview_image()
        self._update_zoom_buttons()

    def _update_preview_nav_buttons(self):
        total = len(self.preview_files)

        # Disable "Previous" if at first image
        if self.preview_index <= 0:
            self.prev_btn.configure(state="disabled")
        else:
            self.prev_btn.configure(state="normal")

        # Disable "Next" if at last image
        if self.preview_index >= total - 1:
            self.next_btn.configure(state="disabled")
        else:
            self.next_btn.configure(state="normal")

        self._update_zoom_buttons()

    def get_unique_path(self, file_path: str) -> str:
        """
        Returns a unique file path by appending _01, _02, ... if needed.
        Example:
            test.png -> test.png
            (exists) -> test_01.png
            (exists) -> test_02.png
        """
        dir_name = os.path.dirname(file_path)
        base = os.path.basename(file_path)
        name, ext = os.path.splitext(base)

        # If the file does NOT already exist → return original
        if not os.path.exists(file_path):
            return file_path

        # Otherwise add counters
        counter = 1
        while True:
            new_name = f"{name}_{counter:02d}{ext}"
            new_path = os.path.join(dir_name, new_name)
            if not os.path.exists(new_path):
                return new_path
            counter += 1

    def _preview_save(self):
        """Save the currently previewed image with grid applied."""
        try:
            self.attributes("-disabled", True)
            self._render_preview_image()
            current_file = self.preview_files[self.preview_index]

            # ensure output folder
            output_folder = os.path.normpath(os.path.join(os.path.dirname(current_file), "output"))
            os.makedirs(output_folder, exist_ok=True)

            # build output name
            base = os.path.basename(current_file)
            name, ext = os.path.splitext(base)

            save_path = self.get_unique_path(os.path.join(output_folder, f"{name}_preview_grid{ext}"))

            # self.last_render holds the last rendered PIL image (from _render_preview_image)
            if hasattr(self, "last_render") and self.last_render is not None:

                base_name, ext = os.path.splitext(os.path.basename(save_path))
                save_format = "PNG"
                if ext.lower() in (".jpg", ".jpeg"):
                    save_format = "JPEG"

                if save_format == "JPEG":
                    self.last_render.save(save_path, format=save_format, quality=95)
                else:
                    self.last_render.save(save_path, format=save_format)

                result = messagebox.askyesno(
                    "Saved", f"Image saved successfully:\n\n{save_path}\n\nOpen the folder?", parent=self.preview_window
                )

                if result:
                    folder = os.path.dirname(save_path)
                    subprocess.Popen(f'explorer "{folder}"')
            else:
                messagebox.showerror("Error", "Rendered image not found.", parent=self.preview_window)

        except Exception as e:
            messagebox.showerror("Save Error", str(e), parent=self.preview_window)
        finally:
            self.attributes("-disabled", False)

    def _on_preview_mouse_move(self, event):
        try:
            # event.x/event.y are coordinates *inside the label widget*
            # convert to canvas coordinates by adding label widget's position on canvas
            # we can use canvasx/canvasy from the preview_canvas if label is placed at (0,0) inside preview_frame
            self._preview_mouse_x = event.x
            self._preview_mouse_y = event.y
        except:
            self._preview_mouse_x = None
            self._preview_mouse_y = None

    def _open_preview_window(self):
        """Opens a non-modal preview window positioned next to the main window."""
        # prevent duplicate preview window
        if hasattr(self, "preview_window") and self.preview_window.winfo_exists():
            try:
                self.preview_window.lift()
                self.preview_window.focus()
            except:
                pass
            return

        # --- Create preview window ---
        self.preview_window = ctk.CTkToplevel(self)
        top = self.preview_window
        top.withdraw()
        top.title("Preview")
        top.resizable(False, False)

        if self.iconpath:
            top.after(200, lambda: top.iconphoto(False, self.iconpath))

        # --- Get main window size and position ---
        self.update_idletasks()
        main_w = self.winfo_width()
        main_h = self.winfo_height()

        # --- Preview window size ---
        preview_w = 700
        preview_h = main_h

        # --- Get screen size ---
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        # --- Calculate top-left coordinates to center both windows together ---
        total_w = main_w + preview_w
        total_h = max(main_h, preview_h)

        center_x = (screen_w - total_w) // 2
        center_y = (screen_h - total_h) // 2

        # --- Set positions ---
        main_x = center_x
        main_y = center_y
        preview_x = main_x + main_w
        preview_y = main_y

        # --- Apply geometry ---
        self.geometry(f"{main_w}x{main_h}+{main_x}+{main_y}")
        top.geometry(f"{preview_w}x{preview_h}+{preview_x}+{preview_y}")

        # --- Call center_window when preview window is closed ---
        def on_preview_close():
            if hasattr(self, "center_window"):
                self.center_window()
                self.update_idletasks()
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", on_preview_close)

        # --- Scan folder ---
        folder = self.folder_path_var.get()
        supported = (".png", ".jpg", ".jpeg", ".avif", ".webp")
        self.preview_files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(supported)
        ]

        if not self.preview_files:
            messagebox.showwarning("Preview", "No supported images found.", parent=self.preview_window)
            top.destroy()
            return

        self.preview_index = 0
        self._preview_scale = 1.0

        # =============================================================
        #   SCROLLABLE CANVAS (vertical + horizontal) USING ONLY GRID
        # =============================================================
        top.grid_rowconfigure(0, weight=1)
        top.grid_columnconfigure(0, weight=1)

        container = ctk.CTkFrame(top)
        container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        # Canvas for image preview
        self.preview_canvas = tk.Canvas(container, background=self.cget("bg"), highlightthickness=0)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")

        # Scrollbars
        self.preview_v_scroll = tk.Scrollbar(container, orient="vertical", command=self.preview_canvas.yview)
        self.preview_v_scroll.grid(row=0, column=1, sticky="ns")

        self.preview_h_scroll = tk.Scrollbar(container, orient="horizontal", command=self.preview_canvas.xview)
        self.preview_h_scroll.grid(row=1, column=0, sticky="ew")

        # Attach scrollbars
        self.preview_canvas.configure(
            yscrollcommand=self.preview_v_scroll.set, xscrollcommand=self.preview_h_scroll.set
        )

        # Inner CTk frame inside canvas
        self.preview_frame = ctk.CTkFrame(self.preview_canvas, fg_color="transparent")
        self._preview_window_id = self.preview_canvas.create_window((0, 0), window=self.preview_frame, anchor="nw")

        # Update scrollregion when inner frame resizes
        def _update_region(event=None):
            self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

        self.preview_frame.bind("<Configure>", _update_region)

        # Image label inside preview_frame
        self.preview_image_label = ctk.CTkLabel(self.preview_frame, text="")
        self.preview_image_label.grid(row=0, column=0, pady=5)

        # =============================================================
        #   DRAG & DROP PANNING (SMART LOCK)
        # =============================================================

        def start_pan(event):
            self.preview_image_label.configure(cursor="fleur")

            # store starting mouse position
            self._pan_start_x = event.x_root
            self._pan_start_y = event.y_root

            self.preview_canvas.scan_mark(event.x_root, event.y_root)

        def move_pan(event):
            # Compute content and view sizes
            bbox = self.preview_canvas.bbox("all")
            if not bbox:
                return

            content_width = bbox[2] - bbox[0]
            content_height = bbox[3] - bbox[1]

            view_width = self.preview_canvas.winfo_width()
            view_height = self.preview_canvas.winfo_height()

            # Calculate target x
            if content_width > view_width:
                target_x = event.x_root
            else:
                target_x = self._pan_start_x

            # Calculate target y
            if content_height > view_height:
                target_y = event.y_root
            else:
                target_y = self._pan_start_y

            # Perform the drag
            self.preview_canvas.scan_dragto(target_x, target_y, gain=1)

        def stop_pan(event):
            self.preview_image_label.configure(cursor="hand2")

        # --- Bindings ---
        self.preview_image_label.bind("<Enter>", lambda e: self.preview_image_label.configure(cursor="hand2"))
        self.preview_image_label.bind("<Leave>", lambda e: self.preview_image_label.configure(cursor=""))

        self.preview_image_label.bind("<ButtonPress-1>", start_pan)
        self.preview_image_label.bind("<B1-Motion>", move_pan)
        self.preview_image_label.bind("<ButtonRelease-1>", stop_pan)

        # Mouse wheel zoom
        # store mouse pos relative to the *canvas* (not label) so we can compute canvasx/canvasy
        self.preview_canvas.bind("<Motion>", lambda e: self._on_preview_mouse_move(e))
        # mouse wheel bindings (windows/mac/linux)
        self.preview_image_label.bind("<MouseWheel>", self._mousewheel_zoom)
        self.preview_image_label.bind("<Button-4>", lambda e: self._mousewheel_zoom(e))  # linux up
        self.preview_image_label.bind("<Button-5>", lambda e: self._mousewheel_zoom(e))  # linux down

        # =============================================================
        #   BUTTON ROW (GRID, BIG FONT, BOLD)
        # =============================================================
        buttons_frame = ctk.CTkFrame(top)
        buttons_frame.grid(row=1, column=0, sticky="ew", pady=10)
        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=1)
        buttons_frame.grid_columnconfigure(2, weight=1)
        buttons_frame.grid_columnconfigure(3, weight=1)
        buttons_frame.grid_columnconfigure(4, weight=1)
        buttons_frame.grid_columnconfigure(5, weight=1)

        btn_font = ctk.CTkFont(size=16, weight="bold")

        # Previous button
        self.prev_btn = ctk.CTkButton(
            buttons_frame, text="Previous", width=120, height=40, font=btn_font, command=self._preview_prev
        )
        self.prev_btn.grid(row=0, column=0, padx=10, pady=10)

        # Re-Style button
        self.restyle_btn = ctk.CTkButton(
            buttons_frame, text="Re-Style", width=120, height=40, font=btn_font, command=self._preview_restyle
        )
        self.restyle_btn.grid(row=0, column=1, padx=10, pady=10)

        # Zoom Out button
        self.zoom_out_btn = ctk.CTkButton(
            buttons_frame,
            text="Zoom -",
            width=120,
            height=40,
            font=btn_font,
            command=lambda: self._preview_zoom_out(target="center"),
        )
        self.zoom_out_btn.grid(row=0, column=2, padx=10, pady=10)

        # Save button
        self.save_btn = ctk.CTkButton(
            buttons_frame, text="Save", width=120, height=40, font=btn_font, command=self._preview_save
        )
        self.save_btn.grid(row=0, column=3, padx=10, pady=10)

        # Zoom In button
        self.zoom_in_btn = ctk.CTkButton(
            buttons_frame,
            text="Zoom +",
            width=120,
            height=40,
            font=btn_font,
            command=lambda: self._preview_zoom_in(target="center"),
        )
        self.zoom_in_btn.grid(row=0, column=4, padx=10, pady=10)

        # Next button
        self.next_btn = ctk.CTkButton(
            buttons_frame, text="Next", width=120, height=40, font=btn_font, command=self._preview_next
        )
        self.next_btn.grid(row=0, column=5, padx=10, pady=10)

        # --- First render ---
        top.after(250, self._render_preview_image)
        self._update_preview_nav_buttons()

        # --- Start periodic file check (Polling) ---
        self._file_check_job = self.after(5000, self._check_for_new_files)

        top.after(200, top.deiconify)

    def _restyle_checker(self):
        # --- Call _render_preview_image if preview window is open ---
        if hasattr(self, "preview_window") and self.preview_window.winfo_exists():
            self._render_preview_image()

        try:
            pw = self.preview_window

            # if minimized → restore
            if pw.state() == "iconic":
                pw.state("normal")

            self.after(
                0,
                lambda: [
                    # bring to front
                    pw.lift(),
                    pw.focus_force(),
                    self.focus(),
                ],
            )

        except:
            pass

    def _update_grid_controls(self, small_w, small_h):
        """Calculates and updates grid cell count based on pixel art dimensions and updates UI controls."""
        if not self.settings["sync_grid_to_pixels"].get():
            # Only run if sync is enabled
            return

        # Calculate grid count:
        # Since the grid must be square (rows=cols), we select the max of the small dimensions
        # to ensure the grid covers the entire pixelated area without creating non-square cells.
        new_grid_count = max(small_w, small_h)

        # Clamp the result
        MIN_CELLS = 0
        MAX_CELLS = 400
        new_grid_count = max(MIN_CELLS, min(MAX_CELLS, int(new_grid_count)))

        # Update setting, slider, and label
        current_value = self.settings["grid_rows"].get()
        if current_value != new_grid_count:
            self.settings["grid_rows"].set(new_grid_count)
            # The slider is disabled when sync is on, but we still update its value
            self.rows_slider.set(new_grid_count)

            # Update label text using the pre-defined function
            fmt = getattr(self, "grid_rows_format")
            lbl = getattr(self, "grid_rows_label")
            lbl.configure(text=fmt.format(new_grid_count))

    def _on_pixler_toggle(self):
        """Disables/enables all pixel-related UI when toggle is switched, and handles grid sync logic."""
        enabled = self.settings["pixel_art_enabled"].get()
        state = "normal" if enabled else "disabled"
        grid_enabled = self.settings["grid_enabled"].get()

        # Pixel Size Slider
        self.pixel_scale_slider.configure(state=state)

        # Palette OptionMenu
        self.pixel_palette_option.configure(state=state)

        # Dithering OptionMenu
        self.pixel_dither_option.configure(state=state)

        # Sharpen Toggle
        self.pixel_sharpen_toggle.configure(state=state)

        # Sync to pixels toggle logic
        if enabled:
            # If Pixler is ON: If Grid is also ON, set sync toggle to ON and enable it
            if grid_enabled:
                self.settings["sync_grid_to_pixels"].set(True)
                self.sync_grid_toggle.configure(state="normal")
            else:
                # Pixler is ON but Grid is OFF: sync toggle must remain OFF and disabled
                self.settings["sync_grid_to_pixels"].set(False)
                self.sync_grid_toggle.configure(state="disabled")
        else:
            # If Pixler is OFF: Sync toggle must be OFF and disabled (regardless of grid status)
            self.settings["sync_grid_to_pixels"].set(False)
            self.sync_grid_toggle.configure(state="disabled")

        # Update Grid Slider state based on new sync toggle status
        self._on_sync_grid_toggle()

        # Restyle preview
        self._restyle_checker()

    def _on_sync_grid_toggle(self):
        """Enables/disables grid rows slider based on sync-to-pixels toggle and updates grid count."""
        sync_enabled = self.settings["sync_grid_to_pixels"].get()
        grid_enabled = self.settings["grid_enabled"].get()

        # Check if the grid itself is enabled before changing state
        if grid_enabled and sync_enabled:
            # Sync is active and Grid is on: Disable manual grid controls
            self.rows_slider.configure(state="disabled")
            self.minus_btn.configure(state="disabled")
            self.plus_btn.configure(state="disabled")
        elif grid_enabled and not sync_enabled:
            # Sync is inactive and Grid is on: Enable manual grid controls
            self.rows_slider.configure(state="normal")
            self.minus_btn.configure(state="normal")
            self.plus_btn.configure(state="normal")
        else:
            # Grid is off: Keep controls disabled
            self.rows_slider.configure(state="disabled")
            self.minus_btn.configure(state="disabled")
            self.plus_btn.configure(state="disabled")

        # Restyle preview
        self._restyle_checker()

    def _on_grid_toggle(self):
        """Disables/enables all grid-related UI when toggle is switched."""
        enabled = self.settings["grid_enabled"].get()

        state = "normal" if enabled else "disabled"

        # Buttons
        self.color_button.configure(state=state)
        # self.color_display is a CTkFrame, can't set state
        # We can optionally gray it out
        self.color_display.configure(fg_color=self.settings["grid_color"].get() if enabled else "#d3d3d3")

        # Grid number options
        self.grid_number_toggle.configure(state=state)
        self.num_text_color_button.configure(state=state)
        self.num_text_color_display.configure(
            fg_color=self.settings["grid_number_text_color"].get() if enabled else "#d3d3d3"
        )
        self.num_bg_color_button.configure(state=state)
        self.num_bg_color_display.configure(
            fg_color=self.settings["grid_number_bg_color"].get() if enabled else "#d3d3d3"
        )

        # Grid thickness slider
        self.grid_thickness_slider.configure(state=state)

        # Enable/disable highlight radio buttons
        for rbtn in self.grid_highlight_rbtns:
            rbtn.configure(state=state)

        # Sync to pixels toggle logic
        if enabled:
            # If Grid is ON, sync toggle state depends on Pixel Art state
            pixler_enabled = self.settings["pixel_art_enabled"].get()
            sync_toggle_state = "normal" if pixler_enabled else "disabled"
            # If Grid is ON and Pixler is ON, set sync to True automatically
            if pixler_enabled:
                self.settings["sync_grid_to_pixels"].set(True)
            else:
                # If Grid is ON and Pixler is OFF, set sync to False automatically (per requirement: shouldn't be able to turn on sync if pixler is off)
                self.settings["sync_grid_to_pixels"].set(False)

        else:
            # If Grid is OFF, sync toggle must be OFF and disabled
            sync_toggle_state = "disabled"
            self.settings["sync_grid_to_pixels"].set(False)

        self.sync_grid_toggle.configure(state=sync_toggle_state)

        # Grid rows slider and buttons state should be controlled by _on_sync_grid_toggle when grid is ON
        # If Grid is OFF, they are disabled regardless.
        if enabled:
            # Call _on_sync_grid_toggle to set the correct state for rows slider and buttons
            self._on_sync_grid_toggle()
        else:
            # If Grid is OFF, explicitly disable them
            self.rows_slider.configure(state="disabled")
            self.minus_btn.configure(state="disabled")
            self.plus_btn.configure(state="disabled")

        # Restyle preview
        self._restyle_checker()

    def _apply_pixel_art(self, img):
        scale = max(1, int(self.settings["pixel_art_scale"].get()))
        palette = str(self.settings["pixel_art_palette"].get()).lower()
        dith = str(self.settings["pixel_art_dithering"].get()).lower()
        sharpen = bool(self.settings["pixel_art_sharpen"].get())

        orig_width, orig_height = img.size

        # compute target small dimensions
        small_w = max(1, orig_width // scale)
        small_h = max(1, orig_height // scale)

        # compute target (cropped) full-size dimensions that are exact multiples of scale
        target_w = small_w * scale
        target_h = small_h * scale

        # if original isn't divisible by scale, crop centered to make it divisible
        if target_w != orig_width or target_h != orig_height:
            left = (orig_width - target_w) // 2
            top = (orig_height - target_h) // 2
            right = left + target_w
            bottom = top + target_h
            img = img.crop((left, top, right, bottom))

        width, height = img.size  # now width==target_w, height==target_h

        print(width // scale, height // scale)

        # Update grid count based on pixel art dimensions
        if self.settings["sync_grid_to_pixels"].get():
            # Calculate and update the grid controls based on the pixel art dimensions
            self._update_grid_controls(small_w, small_h)

        # create small (downscaled) image in RGB for predictable behavior
        small = img.convert("RGB").resize((small_w, small_h), Image.NEAREST)

        target_colors = 256
        if palette != "none":
            if palette == "game boy":
                target_colors = 4
            else:
                try:
                    target_colors = int(palette)
                except Exception:
                    target_colors = 16

        # Step 1: Generate the Palette Image (Base)
        if palette != "none":
            base_palette_img = small.quantize(
                colors=target_colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
            )
        else:
            base_palette_img = None

        # Step 2: Apply Dithering based on mode
        if dith == "ordered":
            # Create the pattern using Web Palette
            temp_ordered = small.convert("P", dither=Image.ORDERED)

            if base_palette_img:
                # FIX: Convert 'P' back to 'RGB' before re-quantizing to the custom palette
                temp_rgb = temp_ordered.convert("RGB")
                # Map the patterned pixels to the custom palette (dither=0 to preserve the pattern)
                small_p = temp_rgb.quantize(palette=base_palette_img, dither=Image.Dither.NONE)
            else:
                small_p = temp_ordered

        elif dith == "floyd":
            if base_palette_img:
                small_p = small.quantize(palette=base_palette_img, dither=Image.Dither.FLOYDSTEINBERG)
            else:
                small_p = small.convert("P", dither=Image.Dither.FLOYDSTEINBERG, palette=Image.Palette.ADAPTIVE)

        else:
            # No Dithering
            if base_palette_img:
                small_p = base_palette_img
            else:
                small_p = small

        # ---------- Upscale ----------
        result = small_p.resize((width, height), Image.NEAREST)

        if result.mode != "RGB":
            result = result.convert("RGB")

        if sharpen:
            result = result.filter(ImageFilter.SHARPEN)

        return result

    # --- UI Creation and Layout Methods ---
    def _create_widgets(self):
        """Creates all UI widgets and initializes their grid layout."""

        # Main Frame for Padding/Spacing
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)

        # ------------------------------
        # Row 0 & 1: Folder Selection
        # ------------------------------
        ctk.CTkLabel(
            self.main_frame,
            text="1. Select Input Folder (Must Contain PNG, JPG, AVIF, WEBP):",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, columnspan=2, pady=(10, 5), sticky="w", padx=20)

        self.folder_entry = ctk.CTkEntry(
            self.main_frame,
            width=350,
            placeholder_text="Select a folder containing supported image formats",
        )
        self.folder_entry.configure(state="readonly")
        self.folder_entry.grid(row=1, column=0, padx=(20, 5), sticky="ew")

        if self.folder_path_var.get() != "":
            self.folder_entry.configure(state="normal")
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, self.folder_path_var.get())
            self.folder_entry.configure(state="readonly")

        self.browse_button = ctk.CTkButton(
            self.main_frame, text="Browse", command=self._browse_folder, font=ctk.CTkFont(weight="bold"), width=90
        )
        self.browse_button.grid(row=1, column=1, padx=(5, 20), sticky="e")

        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=0)

        # ------------------------------
        # Row 2 & 3: Horizontal Padding Slider
        # ------------------------------
        ctk.CTkLabel(
            self.main_frame, text="2. Horizontal Padding (Left/Right Trim in px):", font=ctk.CTkFont(weight="bold")
        ).grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky="w", padx=20)
        self.h_padding_slider = self._create_slider(
            frame=self.main_frame,
            row=3,
            key="h_padding",
            slider_var=self.settings["h_padding"],
            from_=0,
            to=100,
            format_spec="{:.0f} px",
        )

        # ------------------------------
        # Row 4 & 5: Vertical Padding Slider
        # ------------------------------
        ctk.CTkLabel(
            self.main_frame, text="3. Vertical Padding (Top/Bottom Trim in px):", font=ctk.CTkFont(weight="bold")
        ).grid(row=4, column=0, columnspan=2, pady=0, sticky="w", padx=20)
        self.v_padding_slider = self._create_slider(
            frame=self.main_frame,
            row=5,
            key="v_padding",
            slider_var=self.settings["v_padding"],
            from_=0,
            to=100,
            format_spec="{:.0f} px",
        )

        # ------------------------------
        # Row 6 & 7: Zoom Slider
        # ------------------------------
        ctk.CTkLabel(self.main_frame, text="4. Zoom/Resize Factor:", font=ctk.CTkFont(weight="bold")).grid(
            row=6, column=0, columnspan=2, pady=0, sticky="w", padx=20
        )
        self.zoom_slider = self._create_slider(
            frame=self.main_frame,
            row=7,
            key="zoom_factor",
            slider_var=self.settings["zoom_factor"],
            from_=0.1,
            to=10.0,
            format_spec="{:.1f}x",
            resolution=0.1,
        )

        # ============================================================
        # 5. Pixel Art Settings (Rows 8, 9, 10)
        # ============================================================

        # ------------------------------
        # Row 8: Title + Enable Pixel Art Toggle
        # ------------------------------
        row8_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row8_frame.grid(row=8, column=0, columnspan=2, sticky="ew", padx=20, pady=2)

        # Title
        ctk.CTkLabel(row8_frame, text="5. Pixel Art Settings:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w"
        )

        # Enable Pixel Art
        pixel_toggle_frame = ctk.CTkFrame(row8_frame, fg_color="transparent")
        pixel_toggle_frame.grid(row=0, column=1, padx=(179, 0))

        ctk.CTkLabel(pixel_toggle_frame, text="Enable Pixel Art", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(0, 10)
        )

        self.pixel_art_toggle = ctk.CTkSwitch(
            pixel_toggle_frame,
            text="",
            variable=self.settings["pixel_art_enabled"],
            onvalue=True,
            offvalue=False,
            command=self._on_pixler_toggle,
        )
        self.pixel_art_toggle.grid(row=0, column=1)

        # ------------------------------
        # Row 9: Pixel Size Slider
        # ------------------------------
        pixel_slider_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        pixel_slider_frame.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(0, 5), padx=20)

        # Configure columns: 0=Label, 1=Slider+Value
        pixel_slider_frame.grid_columnconfigure(0, weight=0)
        pixel_slider_frame.grid_columnconfigure(1, weight=1)

        # Title Label
        ctk.CTkLabel(pixel_slider_frame, text="Pixel Size (Scale):", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )

        # Slider
        self.pixel_scale_slider = self._create_slider(
            frame=pixel_slider_frame,
            row=0,
            key="pixel_art_scale",
            slider_var=self.settings["pixel_art_scale"],
            from_=2,
            to=50,
            format_spec="{:.0f}",
            resolution=1,
        )

        # Place slider + value frame in column 1
        slider_and_value_frame = self.pixel_scale_slider.master
        slider_and_value_frame.grid_configure(row=0, column=1, sticky="ew", padx=(0, 0), pady=(0, 0))

        # ------------------------------
        # Row 10: Palette + Dithering + Sharpen Toggle
        # ------------------------------
        row10_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row10_frame.grid(row=10, column=0, columnspan=2, sticky="ew", padx=20, pady=(10, 10))

        # Configure columns: 0=Palette, 1=Dithering, 2=spacer, 3=Sharpen
        row10_frame.grid_columnconfigure(0, weight=1)
        row10_frame.grid_columnconfigure(1, weight=1)
        row10_frame.grid_columnconfigure(2, weight=1)

        # Palette
        ctk.CTkLabel(row10_frame, text="Palette:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.pixel_palette_option = ctk.CTkOptionMenu(
            row10_frame,
            variable=self.settings["pixel_art_palette"],
            values=["None", "16", "32", "64", "Game Boy"],
            command=lambda v: self._restyle_checker(),
        )
        self.pixel_palette_option.grid(row=0, column=0, sticky="e", padx=(50, 15))  # Adjust spacing as needed

        # Dithering
        ctk.CTkLabel(row10_frame, text="Dithering:").grid(row=0, column=1, sticky="w", padx=(0, 10))
        self.pixel_dither_option = ctk.CTkOptionMenu(
            row10_frame,
            variable=self.settings["pixel_art_dithering"],
            values=["None", "Floyd", "Ordered"],
            command=lambda v: self._restyle_checker(),
        )
        self.pixel_dither_option.grid(row=0, column=1, sticky="e", padx=(60, 10))  # Adjust spacing

        # Sharpen Toggle (always right)
        sharpen_frame = ctk.CTkFrame(row10_frame, fg_color="transparent")
        sharpen_frame.grid(row=0, column=2, sticky="e", padx=(10, 8))

        ctk.CTkLabel(sharpen_frame, text="Sharpen", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=(0, 10))

        self.pixel_sharpen_toggle = ctk.CTkSwitch(
            sharpen_frame,
            text="",
            variable=self.settings["pixel_art_sharpen"],
            onvalue=True,
            offvalue=False,
            command=self._restyle_checker,
        )
        self.pixel_sharpen_toggle.grid(row=0, column=1)

        # ------------------------------
        # Row 11 : Grid Toggle
        # ------------------------------
        ctk.CTkLabel(self.main_frame, text="6. Grid Line Settings:", font=ctk.CTkFont(weight="bold")).grid(
            row=11, column=0, columnspan=2, pady=5, sticky="w", padx=20
        )

        # Toggle frame on the right side of the label
        grid_toggle_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        grid_toggle_frame.grid(row=11, column=0, columnspan=2, padx=(340, 0), pady=(10, 5))

        disable_toggle_label = ctk.CTkLabel(grid_toggle_frame, text="Enable Grid", font=ctk.CTkFont(weight="bold"))
        disable_toggle_label.grid(row=0, column=0, padx=(0, 10), sticky="e")

        self.grid_disable_toggle = ctk.CTkSwitch(
            grid_toggle_frame,
            text="",
            variable=self.settings["grid_enabled"],
            onvalue=True,
            offvalue=False,
            command=self._on_grid_toggle,
        )
        self.grid_disable_toggle.grid(row=0, column=1, sticky="e")

        # ------------------------------
        # Row 12: Grid Line Thickness
        # ------------------------------
        thickness_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        thickness_frame.grid(row=12, column=0, columnspan=2, sticky="ew", pady=(0, 5), padx=20)

        thickness_frame.grid_columnconfigure(0, weight=0)  # Title Label
        thickness_frame.grid_columnconfigure(1, weight=1)  # Slider + Value Frame

        ctk.CTkLabel(thickness_frame, text="Grid Line Thickness:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )

        self.grid_thickness_slider = self._create_slider(
            frame=thickness_frame,
            row=0,
            key="grid_thickness",
            slider_var=self.settings["grid_thickness"],
            from_=1,
            to=10,
            format_spec="{:.0f}",
            resolution=1,
        )

        slider_and_value_frame = self.grid_thickness_slider.master

        slider_and_value_frame.grid_configure(
            row=0,
            column=1,
            columnspan=1,
            sticky="ew",
            padx=(0, 0),
            pady=(0, 0),
        )

        # ------------------------------
        # Row 13: Highlight Grid Lines Every N Lines
        # ------------------------------
        highlight_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        highlight_frame.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(0, 5), padx=20)
        highlight_frame.grid_columnconfigure(0, weight=1)  # label
        highlight_frame.grid_columnconfigure(1, weight=0)  # buttons container

        # Label on the left
        ctk.CTkLabel(highlight_frame, text="Highlight Grid Every X Lines:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w"
        )

        # Buttons container
        buttons_frame = ctk.CTkFrame(highlight_frame, fg_color="transparent")
        buttons_frame.grid(row=0, column=0, sticky="e", padx=(0, 100))
        buttons_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.grid_highlight_rbtns = []

        for i, val in enumerate([0, 5, 10]):
            rbtn = ctk.CTkRadioButton(
                buttons_frame,
                text=str(val) if val != 0 else "Off",
                variable=self.settings["grid_highlight_every"],
                value=val,
                width=15,
                height=15,
                font=ctk.CTkFont(weight="bold"),
                command=self._restyle_checker,  # call restyle on change
            )
            rbtn.grid(row=0, column=i, padx=10)
            self.grid_highlight_rbtns.append(rbtn)

        # ------------------------------
        # Row 14 : Grid Line Color
        # ------------------------------
        color_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        color_frame.grid(row=14, column=0, columnspan=2, sticky="ew", pady=(5, 5), padx=20)
        color_frame.grid_columnconfigure(0, weight=0)
        color_frame.grid_columnconfigure(1, weight=0)
        color_frame.grid_columnconfigure(2, weight=1)

        self.color_button = ctk.CTkButton(
            color_frame,
            text="Grid Line Color",
            width=110,
            font=ctk.CTkFont(weight="bold"),
            command=lambda: self._pick_color("line"),
        )
        self.color_button.grid(row=0, column=0, sticky="w")

        self.color_display = ctk.CTkFrame(
            color_frame,
            width=40,
            height=20,
            fg_color=self.settings["grid_color"].get(),
            corner_radius=5,
            border_width=2,
            border_color="gray",
        )

        self.color_display.grid(row=0, column=1, padx=10, sticky="e")

        # ------------------------------
        # Row 15: Grid Numbering Colors Title
        # ------------------------------
        # Grid Numbering Title
        ctk.CTkLabel(
            self.main_frame,
            text="7. Grid Numbering Settings:",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=15, column=0, columnspan=2, pady=(15, 5), sticky="w", padx=20)

        # Toggle frame
        toggle_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        toggle_frame.grid(row=15, column=0, columnspan=2, padx=(225, 0), pady=(15, 5))

        toggle_label = ctk.CTkLabel(toggle_frame, text="Show Grid Numbers (Step = 10)", font=ctk.CTkFont(weight="bold"))
        toggle_label.grid(row=0, column=0, padx=(0, 10), sticky="e")

        self.grid_number_toggle = ctk.CTkSwitch(
            toggle_frame,
            text="",
            variable=self.settings["show_grid_numbers"],
            onvalue=True,
            offvalue=False,
            command=self._restyle_checker,
        )
        self.grid_number_toggle.grid(row=0, column=1, sticky="e")

        # ------------------------------
        # Row 16: Grid Numbering Colors (Text + Background)
        # ------------------------------
        gridnum_color_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        gridnum_color_frame.grid(row=16, column=0, columnspan=2, sticky="ew", padx=20, pady=(5, 10))
        gridnum_color_frame.grid_columnconfigure(0, weight=0)
        gridnum_color_frame.grid_columnconfigure(1, weight=0)
        gridnum_color_frame.grid_columnconfigure(2, weight=0)
        gridnum_color_frame.grid_columnconfigure(3, weight=1)

        # ---- Text Color Button ----
        self.num_text_color_button = ctk.CTkButton(
            gridnum_color_frame,
            text="Numbers Text Color",
            width=140,
            command=lambda: self._pick_color("text"),
            font=ctk.CTkFont(weight="bold"),
        )
        self.num_text_color_button.grid(row=0, column=0, sticky="w")

        self.num_text_color_display = ctk.CTkFrame(
            gridnum_color_frame,
            width=40,
            height=20,
            fg_color=self.settings["grid_number_text_color"].get(),
            corner_radius=5,
            border_width=2,
            border_color="gray",
        )
        self.num_text_color_display.grid(row=0, column=1, padx=(10, 20), sticky="w")

        # ---- Background Color Button ----
        self.num_bg_color_button = ctk.CTkButton(
            gridnum_color_frame,
            text="Numbers Background Color",
            width=140,
            command=lambda: self._pick_color("bg"),
            font=ctk.CTkFont(weight="bold"),
        )
        self.num_bg_color_button.grid(row=0, column=2, sticky="w")

        self.num_bg_color_display = ctk.CTkFrame(
            gridnum_color_frame,
            width=40,
            height=20,
            fg_color=self.settings["grid_number_bg_color"].get(),
            corner_radius=5,
            border_width=2,
            border_color="gray",
        )
        self.num_bg_color_display.grid(row=0, column=3, padx=(10, 0), sticky="w")

        # ------------------------------
        # Row 17 & 18: Grid Cell Count Slider
        # ------------------------------

        ctk.CTkLabel(
            self.main_frame,
            text="8. Grid Cell Count (Square Grid, 0-400):",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=17, column=0, columnspan=2, sticky="w", padx=20)

        # Toggle frame on the right side of the label
        sync_grid_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        sync_grid_frame.grid(row=17, column=0, columnspan=2, padx=(298, 0))

        sync_grid_toggle_label = ctk.CTkLabel(
            sync_grid_frame, text="Sync Grid to Pixels", font=ctk.CTkFont(weight="bold")
        )
        sync_grid_toggle_label.grid(row=0, column=0, padx=(0, 10), sticky="e")

        self.sync_grid_toggle = ctk.CTkSwitch(
            sync_grid_frame,
            text="",
            variable=self.settings["sync_grid_to_pixels"],
            onvalue=True,
            offvalue=False,
            command=self._on_sync_grid_toggle,
        )
        self.sync_grid_toggle.grid(row=0, column=1, sticky="e")

        grid_cells_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        grid_cells_frame.grid(row=18, column=0, columnspan=2, sticky="ew", padx=20, pady=(10, 5))
        grid_cells_frame.grid_columnconfigure(1, weight=1)

        MIN_CELLS = 0
        MAX_CELLS = 400
        STEP = 1

        def clamp(val):
            return max(MIN_CELLS, min(MAX_CELLS, int(val)))

        def update_grid_rows_label(value):
            try:
                numeric = float(value)
                fmt = getattr(self, "grid_rows_format")
                lbl = getattr(self, "grid_rows_label")
                lbl.configure(text=fmt.format(numeric))
            except:
                pass

        def on_slider_change(value):
            v = clamp(float(value))
            self.settings["grid_rows"].set(v)
            update_grid_rows_label(v)

        def change_by(delta):
            cur = self.settings["grid_rows"].get()
            new = clamp(cur + delta)
            self.settings["grid_rows"].set(new)
            self.rows_slider.set(new)
            update_grid_rows_label(new)
            self._restyle_checker()

        self.minus_btn = ctk.CTkButton(
            grid_cells_frame,
            text="-",
            width=40,
            height=32,
            font=ctk.CTkFont(size=18, weight="bold"),
            command=lambda: change_by(-STEP),
        )
        self.minus_btn.grid(row=0, column=0, padx=(0, 8))

        self.rows_slider = ctk.CTkSlider(
            grid_cells_frame,
            from_=MIN_CELLS,
            to=MAX_CELLS,
            variable=self.settings["grid_rows"],
            command=on_slider_change,
            number_of_steps=MAX_CELLS - MIN_CELLS,
        )
        self.rows_slider.grid(row=0, column=1, sticky="ew")
        self.rows_slider.bind("<ButtonRelease-1>", self.on_release)

        self.plus_btn = ctk.CTkButton(
            grid_cells_frame,
            text="+",
            width=40,
            height=32,
            font=ctk.CTkFont(size=18, weight="bold"),
            command=lambda: change_by(STEP),
        )
        self.plus_btn.grid(row=0, column=2, padx=(8, 0))

        self.grid_rows_label = ctk.CTkLabel(grid_cells_frame, text="", width=60)
        self.grid_rows_label.grid(row=0, column=3, padx=(10, 0))
        self.grid_rows_format = "{:.0f}"

        # Initial sync
        update_grid_rows_label(self.settings["grid_rows"].get())

        # ------------------------------
        # Row 19 & 20: Progress Bar and Percentage Label
        # ------------------------------
        ctk.CTkLabel(self.main_frame, text="Progress:", font=ctk.CTkFont(weight="bold")).grid(
            row=19, column=0, columnspan=2, pady=(10, 0), sticky="w", padx=20
        )

        # New Frame for Progress Bar and Percentage Label
        progress_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        progress_frame.grid(row=20, column=0, columnspan=2, pady=(0, 10), sticky="ew", padx=20)
        progress_frame.grid_columnconfigure(0, weight=1)  # Progress bar takes most space
        progress_frame.grid_columnconfigure(1, weight=0)  # Percentage label is fixed width

        self.progress_bar = ctk.CTkProgressBar(progress_frame, orientation="horizontal", mode="determinate")
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.progress_bar.set(0)

        # Label to display the percentage
        self.progress_label = ctk.CTkLabel(progress_frame, textvariable=self.progress_text_var, width=50)
        self.progress_label.grid(row=0, column=1, sticky="e")

        # ------------------------------
        # Row 21: Start/Stop Button (Increased Size and Font)
        # ------------------------------
        self.start_button = ctk.CTkButton(
            self.main_frame,
            text="Start Batch Process",
            command=self.toggle_process,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            height=50,  # Increased height
            font=ctk.CTkFont(size=20, weight="bold"),  # Larger font
        )
        self.start_button.grid(row=21, column=0, columnspan=2, pady=(5, 5), sticky="ew", padx=20)

        # ------------------------------
        # Row 22: Action Buttons (Donate/Preview/Reset - Fixed Height)
        # ------------------------------
        button_row_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        button_row_frame.grid(row=22, column=0, columnspan=2, pady=(10, 15), sticky="ew", padx=20)
        button_row_frame.grid_columnconfigure(0, weight=1)
        button_row_frame.grid_columnconfigure(1, weight=1)
        button_row_frame.grid_columnconfigure(2, weight=1)

        BUTTON_HEIGHT = 40  # Fixed height to ensure all buttons are visually the same size
        BUTTON_FONT = ctk.CTkFont(size=16, weight="bold")

        # Donate Button (Vibrant Gold color selected for better contrast with red heart)
        self.donate_button = ctk.CTkButton(
            button_row_frame,
            text="Donate",
            image=self.heart_image,
            compound="right",
            fg_color="#FFD700",  # Vibrant Gold
            hover_color="#FFC400",  # Slightly darker gold on hover
            text_color="#000000",  # Black text for contrast on gold background
            font=BUTTON_FONT,
            height=BUTTON_HEIGHT,  # Fixed height
            command=self.donate,
        )
        self.donate_button.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        # Preview Button (Fixed height for size consistency)
        self.preview_button = ctk.CTkButton(
            button_row_frame,
            text="Preview Grid",
            font=BUTTON_FONT,
            height=BUTTON_HEIGHT,  # Fixed height
        )
        self.preview_button.configure(command=self._open_preview_window)
        self.preview_button.grid(row=0, column=1, sticky="ew", padx=(10, 10))

        # Reset Button
        self.reset_button = ctk.CTkButton(
            button_row_frame,
            text="Reset Settings",
            fg_color="#A9A9A9",  # Dark Gray
            hover_color="#808080",  # Gray
            text_color="#000000",
            font=BUTTON_FONT,
            height=BUTTON_HEIGHT,  # Fixed height
            command=self._reset_settings,
        )
        self.reset_button.grid(row=0, column=2, sticky="ew", padx=(10, 0))

    # --- Bind mouse release to call _restyle_checker ---
    def on_release(self, event):
        self._restyle_checker()

    def _create_slider(self, frame, row, key, slider_var, from_, to, format_spec, resolution=1):
        """
        Creates a slider and its associated label in the specified frame and row.
        Attaches the value_label to the instance using the 'key' for easy access.

        :param frame: The parent CTkFrame.
        :param row: The grid row number.
        :param key: Key name (e.g., 'h_padding') to store the label reference on self.
        :param slider_var: The CTkIntVar or CTkDoubleVar controlling the slider value.
        :param from_: The minimum value for the slider.
        :param to: The maximum value for the slider.
        :param format_spec: Python format specifier for displaying the value (e.g., "{:.0f} px").
        :param resolution: The step size for the slider.
        :return: The created CTkSlider instance.
        """
        slider_frame = ctk.CTkFrame(frame, fg_color="transparent")
        # Added padx=20 to ensure slider group alignment
        slider_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 5))
        slider_frame.grid_columnconfigure(0, weight=1)
        slider_frame.grid_columnconfigure(1, weight=0)

        # Initial label text is placeholder, will be updated by update_label
        value_label = ctk.CTkLabel(slider_frame, text="", width=80)
        value_label.grid(row=0, column=1, padx=(10, 0))

        # Store label and its format specifier on the instance for external updates (e.g., reset)
        setattr(self, f"{key}_label", value_label)
        setattr(self, f"{key}_format", format_spec)

        def update_label(value):
            """Updates the display label based on the slider value."""
            try:
                numeric_value = float(value)
                # Use the format specifier stored in the instance
                value_label.configure(text=getattr(self, f"{key}_format").format(numeric_value))
            except ValueError:
                value_label.configure(text=str(value))

        slider = ctk.CTkSlider(
            slider_frame,
            from_=from_,
            to=to,
            variable=slider_var,
            command=update_label,
            number_of_steps=math.floor((to - from_) / resolution) if resolution else None,
        )
        slider.grid(row=0, column=0, sticky="ew")

        slider.bind("<ButtonRelease-1>", self.on_release)

        # Initial label update to set the correct value
        update_label(slider_var.get())
        return slider

    # --- Interaction and Process Control Methods ---
    def _check_for_new_files(self):
        """Scans the current folder for file changes (addition or deletion) and updates the preview list."""
        if not (hasattr(self, "preview_window") and self.preview_window.winfo_exists()):
            # Stop polling if the preview window is closed
            if hasattr(self, "_file_check_job"):
                self.after_cancel(self._file_check_job)
                del self._file_check_job
            return

        folder = self.folder_path_var.get()
        supported = (".png", ".jpg", ".jpeg", ".avif", ".webp")

        # 1. Generate the list of current files in the folder
        new_preview_files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(supported)
        ]

        # 2. Get the currently displayed file
        current_file = self.preview_files[self.preview_index] if self.preview_files else None

        # 3. Check for any change (count change or content change)
        current_files_set = set(self.preview_files)
        new_files_set = set(new_preview_files)

        # Check if the list of files has changed
        if current_files_set != new_files_set:

            # Update the internal list
            self.preview_files = new_preview_files
            new_count = len(self.preview_files)

            # 4. Handle the index change and re-render only if the displayed file is affected

            # Check if the previously displayed file still exists in the new list
            if current_file and current_file in self.preview_files:
                # The current file exists, find its new index
                new_index = self.preview_files.index(current_file)

                # Check if the file's position (index) has changed
                if new_index != self.preview_index:
                    self.preview_index = new_index
                    self._render_preview_image()  # Re-render if index changed (should not happen if files are added/deleted at the end)

            elif new_count > 0:
                # The previously displayed file was deleted, or we had no files and now we do.
                # Adjust index to the nearest valid one and re-render.
                self.preview_index = min(self.preview_index, new_count - 1)
                self.preview_index = max(0, self.preview_index)
                self._render_preview_image()

            else:
                # All files deleted
                self.preview_index = 0
                # Close the window or display a message (depending on your preference)
                self.preview_window.destroy()
                if hasattr(self, "_file_check_job"):
                    self.after_cancel(self._file_check_job)
                    del self._file_check_job
                self._update_preview_button_state()
                return

            # Update navigation buttons state (critical after file changes)
            self._update_preview_nav_buttons()

        # 5. Schedule the next check
        self._file_check_job = self.after(
            5000, self._check_for_new_files
        )  # Check every 5 seconds  # Check every 5 seconds

    def _browse_folder(self):
        """Opens a dialog to select the input folder and updates the path variable."""
        initial_dir = (
            self.folder_path_var.get()
            if os.path.isdir(self.folder_path_var.get())
            else os.path.expanduser("~/Documents")
        )

        if hasattr(self, "preview_window") and self.preview_window.winfo_exists():
            self.preview_window.attributes("-disabled", True)

        folder_selected = filedialog.askdirectory(initialdir=initial_dir, title="Select Folder Containing Images")
        self._enable_preview_window()

        if folder_selected:
            # update the variable used elsewhere in code
            self.folder_path_var.set(folder_selected)
            # update visible entry text so placeholder is replaced
            try:
                self.folder_entry.configure(state="normal")
                self.folder_entry.delete(0, "end")
                self.folder_entry.insert(0, folder_selected)
                # make it readonly so user doesn't accidentally edit
                self.folder_entry.configure(state="readonly")
            except Exception:
                # fallback: if CTkEntry API differs, just set the variable
                pass

        # --- Update preview if window exists ---
        if hasattr(self, "preview_window") and self.preview_window.winfo_exists():
            # Re-scan the new folder
            folder = self.folder_path_var.get()
            supported = (".png", ".jpg", ".jpeg", ".avif", ".webp")
            self.preview_files = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(supported)
            ]

            if not self.preview_files:
                self.preview_window.destroy()
                self.center_window()
                self._update_preview_button_state()
                messagebox.showwarning("Preview", "No supported images found.")
                # If preview window closes, cancel the job
                if hasattr(self, "_file_check_job"):
                    self.after_cancel(self._file_check_job)
                    del self._file_check_job
                return

            # Reset index and re-render first image
            self.preview_index = 0
            self._preview_scale = 1.0
            self._update_preview_nav_buttons()
            self._reset_scrollbar()
            self._restyle_checker()

        self._update_preview_button_state()

    def _pick_color(self, mode):
        """Opens a color chooser dialog and updates the grid color variable and display."""

        if hasattr(self, "preview_window") and self.preview_window.winfo_exists():
            self.preview_window.attributes("-disabled", True)

        if mode == "text":
            initial = self.settings["grid_number_text_color"].get()
            color_code = colorchooser.askcolor(title="Choose Numbers Text Color", initialcolor=initial)

            if color_code and color_code[1]:
                new_color = color_code[1]
                self.settings["grid_number_text_color"].set(new_color)
                self.num_text_color_display.configure(fg_color=new_color)

        elif mode == "bg":
            initial = self.settings["grid_number_bg_color"].get()
            color_code = colorchooser.askcolor(title="Choose Numbers Background Color", initialcolor=initial)

            if color_code and color_code[1]:
                new_color = color_code[1]
                self.settings["grid_number_bg_color"].set(new_color)
                self.num_bg_color_display.configure(fg_color=new_color)

        elif mode == "line":
            initial = self.settings["grid_color"].get()
            color_code = colorchooser.askcolor(title="Choose Grid Color", initialcolor=initial)

            if color_code and color_code[1] is not None:
                new_color = color_code[1]
                self.settings["grid_color"].set(new_color)
                self.color_display.configure(fg_color=new_color)

        self._enable_preview_window()
        self._restyle_checker()

    def _reset_settings(self):
        """Resets all configuration settings to their default values, excluding the folder path, and updates UI labels."""

        self.attributes("-disabled", True)
        if hasattr(self, "preview_window") and self.preview_window.winfo_exists():
            self.preview_window.attributes("-disabled", True)

        # Keys that are connected to sliders and need label update
        slider_keys = [
            "h_padding",
            "v_padding",
            "zoom_factor",
            "grid_rows",
            "grid_cols",
            "pixel_art_scale",
            "grid_thickness",
        ]

        for key, value in DEFAULT_CONFIG.items():
            # Only reset settings stored in self.settings (sliders, color, etc.)
            if key in self.settings:
                self.settings[key].set(value)

                # Manually update slider label if it is one of the slider controls
                if key in slider_keys:
                    label = getattr(self, f"{key}_label")
                    format_spec = getattr(self, f"{key}_format")

                    try:
                        numeric_value = float(value)
                        label.configure(text=format_spec.format(numeric_value))
                    except ValueError:
                        label.configure(text=str(value))

        # Manually trigger color display update
        self.color_display.configure(fg_color=self.settings["grid_color"].get())
        self.num_text_color_display.configure(fg_color=self.settings["grid_number_text_color"].get())
        self.num_bg_color_display.configure(fg_color=self.settings["grid_number_bg_color"].get())

        # Reset grid highlight every
        self.settings["grid_highlight_every"].set(DEFAULT_CONFIG["grid_highlight_every"])

        # Reset grid toggle
        self.grid_disable_toggle.configure(state="normal" if self.settings["grid_enabled"].get() else "disabled")
        self._on_grid_toggle()  # ensure UI is consistent

        # Reset pixel toggle
        self._on_pixler_toggle()  # ensure UI is consistent

        # Reset sync grid toggle
        self.sync_grid_toggle.configure(state="normal" if self.settings["sync_grid_to_pixels"].get() else "disabled")
        self._on_sync_grid_toggle()  # ensure UI is consistent

        # preview scale (display-only)
        self._preview_scale = 1.0

        # Reset Progress Bar and Label
        self.progress_bar.set(0)
        self.progress_text_var.set("0%")
        self.save_config()
        self._reset_scrollbar()
        self._restyle_checker()

        messagebox.showinfo(
            "Settings Reset", "All settings (except the folder path) have been reset to default values."
        )

        self.attributes("-disabled", False)
        if hasattr(self, "preview_window") and self.preview_window.winfo_exists():
            self.preview_window.attributes("-disabled", False)
            self._update_preview_nav_buttons()

    def toggle_process(self):
        """
        Switches the application state between 'Start' and 'Stop'.
        Starts the processing thread or stops the running process.
        """
        if self.is_running:
            # Running -> Request Stop
            confirm = messagebox.askyesno(
                title="Stop Process", message="A process is currently running. Do you want to stop it?"
            )
            if confirm:
                self.stop_requested = True
        else:
            # Not running -> Start
            folder_path = self.folder_path_var.get()
            if not os.path.isdir(folder_path):
                messagebox.showerror("Error", "Selected path is not a valid directory.")
                return

            # Save current settings before starting
            self.save_config()
            self.stop_requested = False

            # Start process in a new thread
            self.processing_thread = threading.Thread(target=self.start_process, daemon=True)
            self.processing_thread.start()

    def _set_ui_state(self, state="normal"):
        """
        Enables or disables all interactive UI elements based on the running state.

        :param state: 'normal' to enable, 'disabled' to disable.
        """
        # Buttons
        self.browse_button.configure(state=state)
        self.color_button.configure(state=state)
        self.donate_button.configure(state=state)
        self.preview_button.configure(state=state)
        self.reset_button.configure(state=state)

        # Sliders
        self.h_padding_slider.configure(state=state)
        self.v_padding_slider.configure(state=state)
        self.zoom_slider.configure(state=state)
        self.rows_slider.configure(state=state)

    def start_process(self):
        """
        Initializes and manages the grid processing operation on the selected folder.
        Runs in a separate thread.
        """
        self.is_running = True
        self.progress_bar.set(0)
        self.progress_text_var.set("0%")  # Reset text at start

        if hasattr(self, "preview_window") and self.preview_window.winfo_exists():
            self.preview_window.attributes("-disabled", True)

        # Configure button for STOP state with new style parameters
        self.after(
            0,
            lambda: self.start_button.configure(
                text="Stop Batch Process",
                fg_color="red",
                hover_color="darkred",
                height=50,
                font=ctk.CTkFont(size=20, weight="bold"),
            ),
        )

        self.after(0, lambda: self._set_ui_state("disabled"))

        folder_path = self.folder_path_var.get()
        output_dir = os.path.normpath(os.path.join(folder_path, "output"))
        os.makedirs(output_dir, exist_ok=True)

        # Supported image formats
        supported_formats = (".png", ".jpg", ".jpeg", ".avif", ".webp")

        files = [
            f
            for f in os.listdir(folder_path)
            if os.path.isfile(os.path.join(folder_path, f)) and f.lower().endswith(supported_formats)
        ]

        self.total_files = len(files)
        if self.total_files == 0:
            self.after(
                0,
                lambda: [
                    messagebox.showinfo("Info", "No supported images found in the selected folder."),
                    self._enable_preview_window(),
                ],
            )
            self._cleanup_process(success=False)
            self._update_preview_button_state()
            return

        settings = {
            "h_padding": self.settings["h_padding"].get(),
            "v_padding": self.settings["v_padding"].get(),
            "zoom_factor": self.settings["zoom_factor"].get(),
            "grid_color": self.settings["grid_color"].get(),
            "grid_rows": self.settings["grid_rows"].get(),
            "grid_cols": self.settings["grid_rows"].get(),
            "show_grid_numbers": self.settings["show_grid_numbers"].get(),
        }

        for i, filename in enumerate(files):
            if self.stop_requested:
                self.after(
                    0,
                    lambda: [
                        messagebox.showinfo("Stopped", "Process manually stopped by user."),
                        self._enable_preview_window(),
                    ],
                )
                self._cleanup_process(success=False)
                return

            input_path = os.path.join(folder_path, filename)

            # --- FILENAME SANITIZATION FIX ---
            base_name, ext = os.path.splitext(filename)
            # Replace spaces and parentheses with underscores for file system compatibility
            safe_base_name = base_name.replace(" ", "_").replace("(", "").replace(")", "")
            # Ensure multiple underscores are not collapsed, as a simple replace is safer
            output_filename = f"grid_{safe_base_name}{ext}"
            output_path = self.get_unique_path(os.path.join(output_dir, output_filename))
            # --- FILENAME SANITIZATION FIX END ---

            try:
                self._process_image(input_path, output_path, settings)

                # Update progress bar and percentage label on the main thread
                progress_value = (i + 1) / self.total_files
                percentage = int(progress_value * 100)
                self.after(
                    0, lambda: [self.progress_bar.set(progress_value), self.progress_text_var.set(f"{percentage}%")]
                )

            except Exception as e:
                # Log the error with the problematic filename
                print(f"Error processing {filename}: {e}")
                self.after(
                    0,
                    lambda: [
                        messagebox.showerror(
                            "Processing Error",
                            f"Error processing {filename}: {e}\n\nThis may be caused by special characters in the filename. Try renaming the file.",
                        ),
                        self._enable_preview_window(),
                    ],
                )
                self._cleanup_process(success=False)
                return  # Exit process on critical error

        self._cleanup_process(success=True)

    def _enable_preview_window(self):
        if hasattr(self, "preview_window") and self.preview_window.winfo_exists():
            self.preview_window.attributes("-disabled", False)

    def _cleanup_process(self, success):
        """Resets the UI state and flags after the process completes or is stopped."""
        self.is_running = False
        self.stop_requested = False

        # Configure button for START state with new style parameters
        self.after(
            0,
            lambda: self.start_button.configure(
                text="Start Batch Process",
                fg_color="#3B82F6",
                hover_color="#2563EB",
                state="normal",
                height=50,
                font=ctk.CTkFont(size=20, weight="bold"),
            ),
        )

        self.after(0, lambda: self._set_ui_state("normal"))

        if success:
            # Ensure progress bar reaches 1.0 and label says 100%
            self.after(0, lambda: [self.progress_bar.set(1.0), self.progress_text_var.set("100%")])

            def show_success_and_option():
                output_folder = os.path.normpath(os.path.join(self.folder_path_var.get(), "output"))

                result = messagebox.askyesno(
                    "Success",
                    f"All images processed successfully!\n\n"
                    f"{self.total_files} files were saved to:\n{output_folder}\n\n"
                    f"Open the folder?",
                    parent=self,
                )

                if result:
                    subprocess.Popen(f'explorer "{output_folder}"')

                self._enable_preview_window()

            self.after(0, show_success_and_option)

        else:
            # Ensure progress bar remains at current state or 0 if started and immediately stopped
            if self.progress_bar.get() < 1.0:
                current_progress = self.progress_bar.get()
                current_percentage = int(current_progress * 100)
                self.after(0, lambda: self.progress_text_var.set(f"{current_percentage}%"))
            else:
                # If success=False but progress is 1.0 (shouldn't happen usually, but for safety)
                self.after(0, lambda: self.progress_text_var.set("100%"))

    def _apply_grid_numbers(self, img):
        """Applies grid numbers to the image."""
        text_color = self.settings["grid_number_text_color"].get()
        bg_color = self.settings["grid_number_bg_color"].get()

        img = img.convert("RGB")
        width, height = img.size

        rows_setting = self.settings["grid_rows"].get()

        if height >= width:
            rows = rows_setting
            cols = round(rows * (width / height))
        else:
            cols = rows_setting
            rows = round(cols * (height / width))

        try:
            font_size = max(14, min(width, height) // 40)
            font = ImageFont.truetype("arial.ttf", font_size)
            bold_font = ImageFont.truetype("arialbd.ttf", font_size)
        except:
            font = None
            bold_font = None
            font_size = 14

        base_margin = int(max(min(width, height) * 0.07, font_size * 2.5))
        margin_left = base_margin
        margin_top = base_margin

        new_width = width + margin_left
        new_height = height + margin_top

        new_img = Image.new("RGB", (new_width, new_height), bg_color)

        new_img.paste(img, (margin_left, margin_top))
        draw = ImageDraw.Draw(new_img)

        row_step = height / rows
        col_step = width / cols

        def text_size(draw_obj, text, font_obj):
            bbox = draw_obj.textbbox((0, 0), text, font=font_obj)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]

        # Row numbers every 10 rows
        for i in range(rows + 1):
            if i % 10 != 0:
                continue  # skip all non-10-step rows

            num = i // 10  # numbering logic

            y = round(i * row_step) + margin_top
            text = str(num)

            is_bold = (num == 0) or (num % 5 == 0)
            f = bold_font if is_bold else font

            w, h = text_size(draw, text, f)
            draw.text(
                (margin_left - w - max(5, font_size // 2), y - h),
                text,
                fill=text_color,
                font=f,
            )

        # Column numbers every 10 columns
        for i in range(cols + 1):
            if i % 10 != 0:
                continue  # skip all non-10-step columns

            num = i // 10

            x = round(i * col_step) + margin_left
            text = str(num)

            is_bold = (num == 0) or (num % 5 == 0)
            f = bold_font if is_bold else font

            w, h = text_size(draw, text, f)
            draw.text(
                (x - w // 2, margin_top - h - max(5, font_size // 2) - 5),
                text,
                fill=text_color,
                font=f,
            )

        return new_img

    def _process_image(self, input_path, output_path, settings):
        """
        Applies padding removal, resizing, and grid overlay to a single image.

        :param input_path: Full path to the input image file.
        :param output_path: Full path to save the processed image.
        :param settings: Dictionary containing all grid processing parameters.
        """
        img = Image.open(input_path).convert("RGB")
        width, height = img.size

        # 1. Padding Removal (Trim)
        h_pad = settings["h_padding"]  # Left/Right trim amount
        v_pad = settings["v_padding"]  # Top/Bottom trim amount

        # Calculate the new crop box
        # left = h_pad, top = v_pad, right = width - h_pad, bottom = height - v_pad
        if width > 2 * h_pad and height > 2 * v_pad:
            img = img.crop((h_pad, v_pad, width - h_pad, height - v_pad))
        # Recalculate size after crop
        width, height = img.size

        # 2. Resize (Zoom)
        zoom = settings["zoom_factor"]
        new_width = int(width * zoom)
        new_height = int(height * zoom)

        if new_width > 0 and new_height > 0:
            # Use BICUBIC for good quality resizing
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)  # Changed to LANCZOS for better quality
        # Recalculate size after resize
        width, height = img.size

        # Grid settings
        grid_color = settings["grid_color"]
        rows = settings["grid_rows"]
        cols = rows  # enforce square grid

        # Apply Pixel Art
        if self.settings["pixel_art_enabled"].get():
            img = self._apply_pixel_art(img)
            rows = self.settings["grid_rows"].get()
            cols = rows

        # --- Skip if grid disabled ---
        if self.settings.get("grid_enabled").get() and rows > 0:
            # 3. Draw grid
            img = self._draw_grid(img, rows, cols, grid_color)
            # --- Apply grid numbers if enabled
            if self.settings["show_grid_numbers"].get():
                img = self._apply_grid_numbers(img)

        # 4. Save Output
        base_name, ext = os.path.splitext(os.path.basename(output_path))
        save_format = "PNG"
        if ext.lower() in (".jpg", ".jpeg"):
            save_format = "JPEG"

        # Use quality setting for JPEG to ensure good output size/quality balance
        if save_format == "JPEG":
            img.save(output_path, format=save_format, quality=95)
        else:
            img.save(output_path, format=save_format)

    # --- Utility Methods ---

    def _lock_updater(self):
        """
        Periodically updates the lock file timestamp to keep the lock fresh.
        Runs in a separate thread.
        """
        global IS_LOCK_CREATED
        if not IS_LOCK_CREATED:
            return

        while self.lock_refresh_active:
            try:
                os.utime(LOCK_FILE, None)
                # print("Lock refreshed.")
            except Exception as e:
                print(f"Error refreshing lock: {e}")
                break

            time.sleep(LOCK_TIMEOUT_SECONDS / 2)

        print("Lock refresh stopped.")

    def donate(self):
        """Opens a donation window with options to support the project."""
        top = ctk.CTkToplevel(self)
        top.title("Donate ❤")
        top.resizable(False, False)
        self.attributes("-disabled", True)
        if hasattr(self, "preview_window") and self.preview_window.winfo_exists():
            self.preview_window.attributes("-disabled", True)

        def top_on_close():
            self.attributes("-disabled", False)
            self._enable_preview_window()
            top.destroy()
            self.lift()
            self.focus()

        top.protocol("WM_DELETE_WINDOW", top_on_close)
        top.withdraw()

        # Set icon safely for CTk
        if self.heart_icon:
            top.after(250, lambda: top.iconphoto(False, self.heart_icon))

        # Center the window
        width = 500
        height = 300
        x = (top.winfo_screenwidth() // 2) - (width // 2)
        y = (top.winfo_screenheight() // 2) - (height // 2)
        top.geometry(f"{width}x{height}+{x}+{y}")

        # Configure grid for Toplevel
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=0)

        # ==== Layout starts ====

        # Donate image (clickable)
        try:
            image_path = self.resource_path(os.path.join("assets", "donate.png"))
            img = Image.open(image_path)
            width_img, height_img = img.size
            donate_img = ctk.CTkImage(
                light_image=Image.open(image_path), dark_image=Image.open(image_path), size=(width_img, height_img)
            )
            donate_button = ctk.CTkLabel(top, image=donate_img, text="", cursor="hand2")
            donate_button.grid(row=0, column=0, columnspan=2, pady=(30, 20))
        except Exception:
            donate_button = ctk.CTkLabel(top, text="Support the Developer!", font=("Segoe UI", 16, "bold"))
            donate_button.grid(row=0, column=0, columnspan=2, pady=(30, 20))

        def open_link(event=None):
            webbrowser.open_new("http://www.coffeete.ir/Titan")

        donate_button.bind("<Button-1>", open_link)

        # USDT Label
        usdt_label = ctk.CTkLabel(top, text="USDT (Tether) – TRC20 Wallet Address :", font=("Segoe UI", 14, "bold"))
        usdt_label.grid(row=1, column=0, columnspan=2, pady=(30, 5), sticky="w", padx=20)

        # Entry field (readonly)
        wallet_address = "TGoKk5zD3BMSGbmzHnD19m9YLpH5ZP8nQe"
        wallet_entry = ctk.CTkEntry(top, width=300)
        wallet_entry.insert(0, wallet_address)
        wallet_entry.configure(state="readonly")
        wallet_entry.grid(row=2, column=0, padx=(20, 10), pady=5, sticky="ew")

        # Copy button
        copy_btn = ctk.CTkButton(top, text="Copy", width=80)
        copy_btn.grid(row=2, column=1, padx=(0, 20), pady=5, sticky="w")

        tooltip = None

        def copy_wallet():
            nonlocal tooltip
            self.clipboard_clear()
            self.clipboard_append(wallet_address)
            self.update()

            # Remove old tooltip if exists
            if tooltip:
                tooltip.hidetip()
                tooltip = None

            tooltip = Hovertip(copy_btn, "Copied to clipboard!")
            tooltip.showtip()

            # Hide after 2 seconds
            def hide_tip():
                if tooltip:
                    tooltip.hidetip()

            top.after(2000, hide_tip)

        copy_btn.configure(command=copy_wallet)

        top.after(200, top.deiconify)

    def on_close(self):
        """
        Handles application shutdown, cleans up the lock file, saves config,
        and checks if a process is running before exiting.
        """
        # Save settings on exit
        self.save_config()

        if self.is_running:
            confirm = messagebox.askyesno(
                title="Application Running",
                message="The image processing is currently running. Closing the application will stop the process. Do you want to close?",
            )
            if not confirm:
                return  # Don't close if user says no

            # If confirmed, request stop and allow the thread to stop naturally
            self.stop_requested = True
            # Give a small moment for the thread to register the stop signal
            if self.processing_thread and self.processing_thread.is_alive():
                self.processing_thread.join(0.2)

        # --- Single Instance Cleanup START ---
        global IS_LOCK_CREATED
        if "IS_LOCK_CREATED" in globals() and IS_LOCK_CREATED:
            self.lock_refresh_active = False
            try:
                if self.lock_thread.is_alive():
                    self.lock_thread.join(0.5)
                os.remove(LOCK_FILE)
            except Exception as e:
                print(f"Could not remove lock file: {e}")
        # --- Single Instance Cleanup END ---

        self.destroy()


if __name__ == "__main__":
    app = GridMaker()
    app.mainloop()
