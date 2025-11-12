import os
from PIL import Image, ImageDraw, ImageTk
import customtkinter as ctk
from customtkinter import filedialog
import os
from tkinter import messagebox
import threading
from idlelib.tooltip import Hovertip
import webbrowser


APP_VERSION = "1.0.0"


class GridMaker(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Grid Maker v{APP_VERSION}")
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

    def resource_path(self, relative_path):
        temp_dir = os.path.dirname(__file__)
        return os.path.join(temp_dir, relative_path)

    def start_process_threaded(self):
        threading.Thread(target=self.start_process, daemon=True).start()

    def start_process(self):
        pass

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

        # set icon safely for CTk
        top.iconphoto(False, self.iconpath)
        top.wm_iconbitmap()

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


if __name__ == "__main__":
    app = GridMaker()
    ctk.CTkButton(app, text="Donate", command=app.donate).pack(pady=40)
    app.mainloop()
