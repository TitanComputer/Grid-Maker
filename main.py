import os
import sys
from PIL import Image, ImageDraw, ImageTk
import customtkinter as ctk
from customtkinter import filedialog
import tkinter as tk
import time
from tkinter import messagebox
import threading
from idlelib.tooltip import Hovertip
import webbrowser


APP_VERSION = "1.0.0"
APP_NAME = "Grid Maker"

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
        self.iconpath = ImageTk.PhotoImage(file=self.resource_path(os.path.join("assets", "icon.png")))
        self.wm_iconbitmap()
        self.iconphoto(False, self.iconpath)
        self.heart_image = ImageTk.PhotoImage(file=self.resource_path(os.path.join("assets", "heart.png")))
        self.update_idletasks()
        width = 500
        height = 500
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- Lock Updater Control START ---
        self.lock_refresh_active = True
        if "IS_LOCK_CREATED" in globals() and IS_LOCK_CREATED:
            self.lock_thread = threading.Thread(target=self._lock_updater, daemon=True)
            self.lock_thread.start()
            print("Lock refresh started.")
        # --- Lock Updater Control END ---

    def resource_path(self, relative_path):
        temp_dir = os.path.dirname(__file__)
        return os.path.join(temp_dir, relative_path)

    def start_process_threaded(self):
        threading.Thread(target=self.start_process, daemon=True).start()

    def start_process(self):
        pass

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
                print("Lock refreshed.")
            except Exception as e:
                print(f"Error refreshing lock: {e}")
                break

            time.sleep(LOCK_TIMEOUT_SECONDS / 2)

        print("Lock refresh stopped.")

    def donate(self):
        """
        Opens a donation window with options to support the project.

        This method creates a top-level window allowing users to make a donation.
        The window includes a clickable donation image, a label for a USDT (Tether)
        wallet address, a read-only entry field displaying the wallet address, and
        a 'Copy' button to copy the wallet address to the clipboard. The donation
        image opens a link when clicked, and the window is centered on the screen
        with a fixed size.

        The method also ensures the window behaves modally and provides feedback
        via a tooltip when the wallet address is copied.
        """

        top = ctk.CTkToplevel(self)
        top.title("Donate ❤")
        top.resizable(False, False)
        top.withdraw()

        # set icon safely for CTk
        top.after(250, lambda: top.iconphoto(False, self.heart_image))

        # Center the window
        width = 500
        height = 300
        x = (top.winfo_screenwidth() // 2) - (width // 2)
        y = (top.winfo_screenheight() // 2) - (height // 2)
        top.geometry(f"{width}x{height}+{x}+{y}")

        # Make modal
        top.grab_set()
        top.transient(self)

        # ==== Layout starts ====

        # Donate image (clickable)
        image_path = self.resource_path(os.path.join("assets", "donate.png"))
        img = Image.open(image_path)
        width, height = img.size
        donate_img = ctk.CTkImage(
            light_image=Image.open(image_path), dark_image=Image.open(image_path), size=(width, height)
        )
        donate_button = ctk.CTkLabel(top, image=donate_img, text="", cursor="hand2")
        donate_button.grid(row=0, column=0, columnspan=2, pady=(30, 20))

        def open_link(event):
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

        # Make the first column expand
        top.grid_columnconfigure(0, weight=1)
        top.after(200, top.deiconify)

    def on_close(self):

        # --- Single Instance Cleanup START ---
        global IS_LOCK_CREATED
        if "IS_LOCK_CREATED" in globals() and IS_LOCK_CREATED:
            self.lock_refresh_active = False
            try:
                os.remove(LOCK_FILE)
            except Exception as e:
                print(f"Could not remove lock file: {e}")
        # --- Single Instance Cleanup END ---

        self.destroy()


if __name__ == "__main__":
    app = GridMaker()
    app.mainloop()
