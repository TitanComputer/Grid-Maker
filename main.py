import os
import sys
import json
from PIL import Image, ImageDraw, ImageTk
import customtkinter as ctk
from customtkinter import filedialog
import tkinter as tk
from tkinter import colorchooser, messagebox
import time
import threading
from idlelib.tooltip import Hovertip
import webbrowser
from math import floor

APP_VERSION = "1.0.0"
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
    "grid_cols": 200,
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

        self.update_idletasks()
        width = 500
        height = 750
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
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
            "grid_cols": ctk.IntVar(value=DEFAULT_CONFIG["grid_cols"]),
        }
        self.is_running = False
        self.stop_requested = False
        self.total_files = 0
        self.processing_thread = None

        # Load config to overwrite default variable values
        self.load_config()

        # --- UI Setup ---
        self.grid_columnconfigure(0, weight=1)
        self._create_widgets()

        # --- Lock Updater Control START ---
        self.lock_refresh_active = True
        if "IS_LOCK_CREATED" in globals() and IS_LOCK_CREATED:
            self.lock_thread = threading.Thread(target=self._lock_updater, daemon=True)
            self.lock_thread.start()
            print("Lock refresh started.")
        # --- Lock Updater Control END ---

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
            "grid_cols": self.settings["grid_cols"].get(),
        }

        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config_data, f, indent=4)
            print("Configuration saved successfully.")
        except Exception as e:
            print(f"Error saving configuration: {e}")

    # --- UI Creation and Layout Methods ---

    def _create_widgets(self):
        """Creates all UI widgets and initializes their grid layout."""

        # Main Frame for Padding/Spacing
        self.main_frame = ctk.CTkFrame(self)
        # FIX: Removed padx=20, pady=20 to eliminate the outer margin that was causing the content to be distanced from the window edges.
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)

        # ------------------------------
        # Row 0 & 1: Folder Selection
        # ------------------------------
        # Added padx=20 to the internal elements to create the desired margin within the frame
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

        # NEW: apply last saved folder if it exists
        if self.folder_path_var.get() != "":
            self.folder_entry.configure(state="normal")
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, self.folder_path_var.get())
            self.folder_entry.configure(state="readonly")

        self.browse_button = ctk.CTkButton(self.main_frame, text="Browse", command=self._browse_folder)
        self.browse_button.grid(row=1, column=1, padx=(5, 20), sticky="e")

        # Configure column weights for folder row
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=0)

        # ------------------------------
        # Row 2 & 3: Horizontal Padding Slider
        # ------------------------------
        ctk.CTkLabel(
            self.main_frame, text="2. Horizontal Padding (Left/Right Trim in px):", font=ctk.CTkFont(weight="bold")
        ).grid(row=2, column=0, columnspan=2, pady=(10, 5), sticky="w", padx=20)
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
        ).grid(row=4, column=0, columnspan=2, pady=(10, 5), sticky="w", padx=20)
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
            row=6, column=0, columnspan=2, pady=(10, 5), sticky="w", padx=20
        )
        self.zoom_slider = self._create_slider(
            frame=self.main_frame,
            row=7,
            key="zoom_factor",
            slider_var=self.settings["zoom_factor"],
            from_=0.1,
            to=4.0,
            format_spec="{:.1f}x",
            resolution=0.1,
        )

        # ------------------------------
        # Row 8 & 9: Color Picker
        # ------------------------------
        ctk.CTkLabel(self.main_frame, text="5. Grid Line Color:", font=ctk.CTkFont(weight="bold")).grid(
            row=8, column=0, columnspan=2, pady=(10, 5), sticky="w", padx=20
        )

        color_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        color_frame.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(0, 5), padx=20)  # Added padx=20

        color_frame.grid_columnconfigure(0, weight=1)

        self.color_button = ctk.CTkButton(color_frame, text="Select Color", command=self._pick_color)
        self.color_button.grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.color_display = ctk.CTkFrame(
            color_frame,
            width=50,
            height=20,
            fg_color=self.settings["grid_color"].get(),
            corner_radius=5,
            border_width=2,
            border_color="gray",
        )
        self.color_display.grid(row=0, column=1, sticky="e")
        # Update color display when variable changes
        self.settings["grid_color"].trace_add(
            "write", lambda *args: self.color_display.configure(fg_color=self.settings["grid_color"].get())
        )

        # ------------------------------
        # Row 10 & 11: Grid Row Count Slider
        # ------------------------------
        ctk.CTkLabel(
            self.main_frame, text="6. Grid Row Count (Horizontal Lines, 50-400):", font=ctk.CTkFont(weight="bold")
        ).grid(row=10, column=0, columnspan=2, pady=(10, 5), sticky="w", padx=20)
        self.rows_slider = self._create_slider(
            frame=self.main_frame,
            row=11,
            key="grid_rows",
            slider_var=self.settings["grid_rows"],
            from_=50,
            to=400,
            format_spec="{:.0f}",
        )

        # ------------------------------
        # Row 12 & 13: Grid Column Count Slider
        # ------------------------------
        ctk.CTkLabel(
            self.main_frame, text="7. Grid Column Count (Vertical Lines, 50-400):", font=ctk.CTkFont(weight="bold")
        ).grid(row=12, column=0, columnspan=2, pady=(10, 5), sticky="w", padx=20)
        self.cols_slider = self._create_slider(
            frame=self.main_frame,
            row=13,
            key="grid_cols",
            slider_var=self.settings["grid_cols"],
            from_=50,
            to=400,
            format_spec="{:.0f}",
        )

        # ------------------------------
        # Row 14 & 15: Progress Bar and Percentage Label
        # ------------------------------
        ctk.CTkLabel(self.main_frame, text="Progress:", font=ctk.CTkFont(weight="bold")).grid(
            row=14, column=0, columnspan=2, pady=(10, 5), sticky="w", padx=20
        )

        # New Frame for Progress Bar and Percentage Label
        progress_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        progress_frame.grid(row=15, column=0, columnspan=2, pady=(5, 10), sticky="ew", padx=20)
        progress_frame.grid_columnconfigure(0, weight=1)  # Progress bar takes most space
        progress_frame.grid_columnconfigure(1, weight=0)  # Percentage label is fixed width

        self.progress_bar = ctk.CTkProgressBar(progress_frame, orientation="horizontal", mode="determinate")
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.progress_bar.set(0)

        # Label to display the percentage
        self.progress_label = ctk.CTkLabel(progress_frame, textvariable=self.progress_text_var, width=50)
        self.progress_label.grid(row=0, column=1, sticky="e")

        # ------------------------------
        # Row 16: Start/Stop Button (Increased Size and Font)
        # ------------------------------
        self.start_button = ctk.CTkButton(
            self.main_frame,
            text="Start Process",
            command=self.toggle_process,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            height=50,  # Increased height
            font=ctk.CTkFont(size=20, weight="bold"),  # Larger font
        )
        self.start_button.grid(row=16, column=0, columnspan=2, pady=(10, 10), sticky="ew", padx=20)  # Added padx=20

        # ------------------------------
        # Row 17: Action Buttons (Donate/Preview/Reset - Fixed Height)
        # ------------------------------
        button_row_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        # Increased pady bottom from 10 to 30 for extra space at the bottom
        button_row_frame.grid(row=17, column=0, columnspan=2, pady=(10, 30), sticky="ew", padx=20)
        button_row_frame.grid_columnconfigure(0, weight=1)
        button_row_frame.grid_columnconfigure(1, weight=1)
        button_row_frame.grid_columnconfigure(2, weight=1)  # Added column for Reset Button

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
        self.donate_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        # Preview Button (Fixed height for size consistency)
        self.preview_button = ctk.CTkButton(
            button_row_frame,
            text="Preview Grid",
            state="disabled",
            font=BUTTON_FONT,
            height=BUTTON_HEIGHT,  # Fixed height
        )
        self.preview_button.grid(row=0, column=1, sticky="ew", padx=(5, 5))

        # Reset Button (Text is now English)
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
        self.reset_button.grid(row=0, column=2, sticky="ew", padx=(5, 0))

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
            number_of_steps=floor((to - from_) / resolution) if resolution else None,
        )
        slider.grid(row=0, column=0, sticky="ew")

        # Initial label update to set the correct value
        update_label(slider_var.get())
        return slider

    # --- Interaction and Process Control Methods ---

    def _browse_folder(self):
        """Opens a dialog to select the input folder and updates the path variable."""
        initial_dir = (
            self.folder_path_var.get()
            if os.path.isdir(self.folder_path_var.get())
            else os.path.expanduser("~/Documents")
        )

        folder_selected = filedialog.askdirectory(initialdir=initial_dir, title="Select Folder Containing Images")
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

    def _pick_color(self):
        """Opens a color chooser dialog and updates the grid color variable and display."""
        color_code = colorchooser.askcolor(title="Choose Grid Color", initialcolor=self.settings["grid_color"].get())

        if color_code and color_code[1] is not None:
            self.settings["grid_color"].set(color_code[1])

    def _reset_settings(self):
        """Resets all configuration settings to their default values, excluding the folder path, and updates UI labels."""

        # Keys that are connected to sliders and need label update
        slider_keys = ["h_padding", "v_padding", "zoom_factor", "grid_rows", "grid_cols"]

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

        # Reset Progress Bar and Label
        self.progress_bar.set(0)
        self.progress_text_var.set("0%")
        self.save_config()
        messagebox.showinfo(
            "Settings Reset", "All settings (except the folder path) have been reset to default values."
        )

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
        self.cols_slider.configure(state=state)

    def start_process(self):
        """
        Initializes and manages the grid processing operation on the selected folder.
        Runs in a separate thread.
        """
        self.is_running = True
        self.progress_bar.set(0)
        self.progress_text_var.set("0%")  # Reset text at start

        # Configure button for STOP state with new style parameters
        self.after(
            0,
            lambda: self.start_button.configure(
                text="Stop Process",
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
            self.after(0, lambda: messagebox.showinfo("Info", "No supported images found in the selected folder."))
            self._cleanup_process(success=False)
            return

        settings = {
            "h_padding": self.settings["h_padding"].get(),
            "v_padding": self.settings["v_padding"].get(),
            "zoom_factor": self.settings["zoom_factor"].get(),
            "grid_color": self.settings["grid_color"].get(),
            "grid_rows": self.settings["grid_rows"].get(),
            "grid_cols": self.settings["grid_cols"].get(),
        }

        for i, filename in enumerate(files):
            if self.stop_requested:
                self.after(0, lambda: messagebox.showinfo("Stopped", "Process manually stopped by user."))
                self._cleanup_process(success=False)
                return

            input_path = os.path.join(folder_path, filename)

            # --- FILENAME SANITIZATION FIX ---
            base_name, ext = os.path.splitext(filename)
            # Replace spaces and parentheses with underscores for file system compatibility
            safe_base_name = base_name.replace(" ", "_").replace("(", "").replace(")", "")
            # Ensure multiple underscores are not collapsed, as a simple replace is safer
            output_filename = f"grid_{safe_base_name}{ext}"
            output_path = os.path.join(output_dir, output_filename)
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
                    lambda: messagebox.showerror(
                        "Processing Error",
                        f"Error processing {filename}: {e}\n\nThis may be caused by special characters in the filename. Try renaming the file.",
                    ),
                )
                self._cleanup_process(success=False)
                return  # Exit process on critical error

        self._cleanup_process(success=True)

    def _cleanup_process(self, success):
        """Resets the UI state and flags after the process completes or is stopped."""
        self.is_running = False
        self.stop_requested = False

        # Configure button for START state with new style parameters
        self.after(
            0,
            lambda: self.start_button.configure(
                text="Start Process",
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
            # Show success message as requested
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Success",
                    f"All images processed successfully!\n\n{self.total_files} files were saved to:\n{os.path.normpath(os.path.join(self.folder_path_var.get(), 'output'))}",
                ),
            )
        else:
            # Ensure progress bar remains at current state or 0 if started and immediately stopped
            if self.progress_bar.get() < 1.0:
                current_progress = self.progress_bar.get()
                current_percentage = int(current_progress * 100)
                self.after(0, lambda: self.progress_text_var.set(f"{current_percentage}%"))
            else:
                # If success=False but progress is 1.0 (shouldn't happen usually, but for safety)
                self.after(0, lambda: self.progress_text_var.set("100%"))

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

        # 3. Draw Grid
        draw = ImageDraw.Draw(img)
        color = settings["grid_color"]

        # Grid settings
        rows = settings["grid_rows"]
        cols = settings["grid_cols"]

        # Calculate step size for lines
        row_step = height / rows
        col_step = width / cols

        # Draw Horizontal Lines (Rows)
        for i in range(1, rows):
            y = int(i * row_step)
            # Draw line from (0, y) to (width, y)
            draw.line([(0, y), (width, y)], fill=color, width=1)

        # Draw Vertical Lines (Columns)
        for i in range(1, cols):
            x = int(i * col_step)
            # Draw line from (x, 0) to (x, height)
            draw.line([(x, 0), (x, height)], fill=color, width=1)

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

        # Make modal
        top.grab_set()
        top.transient(self)

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
