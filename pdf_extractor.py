# ==============================================================================
# SECTION 1: IMPORTS AND DEPENDENCY CHECKS
# This section handles importing standard library modules and external dependencies.
# It implements a fallback mechanism so that the application will launch and run
# (possibly in a basic GUI mode) even if external UI packages are missing.
# ==============================================================================

import os
import sys
import io
from tkinter import filedialog, messagebox

# --- PDF Processing Library Check ---
# pypdf is used for extracting, merging, and compressing PDF files.
try:
    from pypdf import PdfReader, PdfWriter
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    PdfReader, PdfWriter = None, None

# --- Image Processing Library Check ---
# Pillow (PIL) is required for compressing and re-encoding images inside the PDF.
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

# --- Modern GUI Framework Check ---
# customtkinter is used to build a beautiful, modern theme-supported GUI.
# If it is missing, we fallback to standard Tkinter (tkinter.ttk).
try:
    import customtkinter as ctk
    USE_CUSTOM_TK = True
except ImportError:
    import tkinter as tk
    from tkinter import ttk
    USE_CUSTOM_TK = False


# ==============================================================================
# SECTION 2: CORE PDF COMPRESSION & EXTRACTION ENGINE
# This function handles the actual PDF logic: reading the source file, extracting
# the specified page range, applying lossless compression, and progressively
# applying lossy image quality compression if the output exceeds 5MB.
# ==============================================================================

def extract_and_compress_pdf(pdf_path, start_page, end_page, save_path):
    """
    Extracts a page range from a PDF, compresses it, and saves it.
    Attempts to keep the file size under 5MB by reducing image quality if needed.
    
    Parameters:
        pdf_path (str): Path to the source PDF file.
        start_page (int): The starting page of the range (1-indexed).
        end_page (int): The ending page of the range (1-indexed).
        save_path (str): The file path where the output PDF will be saved.
        
    Returns:
        float: The final size of the saved PDF in Megabytes (MB).
    """
    if not PYPDF_AVAILABLE:
        raise RuntimeError("pypdf library is not installed.")
        
    # Read the input document and initialize the output writer
    reader = PdfReader(pdf_path)
    writer = PdfWriter()

    # Copy the selected page range from the reader into the writer.
    # Note: pypdf uses 0-indexed page numbers, while users input 1-indexed numbers.
    for page_num in range(start_page - 1, end_page):
        writer.add_page(reader.pages[page_num])

    # --- Phase 1: Lossless Stream Compression ---
    # We apply zlib deflate compression to the page text streams (level 9 = max compression).
    for page in writer.pages:
        page.compress_content_streams(level=9)
        
    # --- Phase 2: Duplicate Object Deduplication ---
    # Merge identical objects (like fonts or repeating logos/backgrounds) to avoid duplicates.
    writer.compress_identical_objects()

    # --- Phase 3: File Size Verification ---
    # Write the current PDF structure into a memory buffer to check its file size.
    buffer = io.BytesIO()
    writer.write(buffer)
    size_in_mb = len(buffer.getvalue()) / (1024 * 1024)

    # --- Phase 4: Progressive Lossy Image Compression ---
    # If the file exceeds 5MB and Pillow is available, we progressively compress images.
    # We step through lower JPEG qualities (75%, 50%, 25%, 10%) until the size drops under 5MB.
    if size_in_mb > 5.0 and PILLOW_AVAILABLE:
        qualities = [75, 50, 25, 10]
        for q in qualities:
            # Load the current compressed version from memory
            temp_reader = PdfReader(io.BytesIO(buffer.getvalue()))
            new_writer = PdfWriter()
            
            # Rebuild the PDF, compressing images along the way
            for page in temp_reader.pages:
                new_page = new_writer.add_page(page)
                try:
                    # Iterate over all images embedded on the current page
                    for img in new_page.images:
                        try:
                            # Retrieve the image as a PIL Image object
                            pil_img = img.image
                            if pil_img:
                                # Replace the original image with a lower-quality version
                                img.replace(pil_img, quality=q)
                        except Exception:
                            # Skip if a specific image cannot be processed (e.g. monochrome mask)
                            pass
                except Exception:
                    pass
                # Apply stream compression on the newly written pages
                new_page.compress_content_streams(level=9)
                
            # Deduplicate resources again
            new_writer.compress_identical_objects()
            
            # Re-verify the size of the compressed PDF
            temp_buf = io.BytesIO()
            new_writer.write(temp_buf)
            temp_size = len(temp_buf.getvalue()) / (1024 * 1024)
            
            # Update working buffer and size trackers
            buffer = temp_buf
            size_in_mb = temp_size
            
            # If we successfully brought the file size under 5MB, we stop compressing
            if size_in_mb <= 5.0:
                break

    # --- Phase 5: Save Output ---
    # Write the compressed buffer to the actual file path on the disk
    with open(save_path, "wb") as output_pdf:
        output_pdf.write(buffer.getvalue())
        
    return size_in_mb


# ==============================================================================
# SECTION 3: MODERN CUSTOMTKINTER USER INTERFACE CLASS
# This class defines the modern-themed desktop application using CustomTkinter,
# including layout creation, callbacks for picking files, splitting, and error
# validations.
# ==============================================================================

if USE_CUSTOM_TK:
    # Set the UI theme style (system default dark/light mode integration)
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    class PDFExtractorApp(ctk.CTk):
        def __init__(self):
            super().__init__()

            # Configure window properties
            self.title("Modern PDF Page Extractor & Splitter")
            self.geometry("600x430")
            self.resizable(False, False)

            # Define internal state variables
            self.pdf_path = None
            self.total_pages = 0

            # Render UI components
            self.setup_ui()

        def setup_ui(self):
            # Header Title Label
            self.title_label = ctk.CTkLabel(
                self, 
                text="PDF Extractor & Splitter", 
                font=ctk.CTkFont(size=24, weight="bold")
            )
            self.title_label.pack(pady=(25, 15))

            # --- File Selection Section ---
            self.file_frame = ctk.CTkFrame(self)
            self.file_frame.pack(pady=10, padx=40, fill="x")

            self.select_btn = ctk.CTkButton(
                self.file_frame, 
                text="Choose PDF File", 
                command=self.choose_file,
                width=150
            )
            self.select_btn.pack(pady=15, side="left", padx=(15, 10))

            self.file_label = ctk.CTkLabel(
                self.file_frame, 
                text="No file selected", 
                text_color="gray",
                anchor="w",
                justify="left"
            )
            self.file_label.pack(pady=15, side="left", fill="x", expand=True, padx=(0, 15))

            # --- Document Information Section ---
            self.info_frame = ctk.CTkFrame(self)
            self.info_frame.pack(pady=10, padx=40, fill="x")
            
            self.pages_label = ctk.CTkLabel(
                self.info_frame,
                text="Total Pages: -",
                font=ctk.CTkFont(size=14, weight="bold")
            )
            self.pages_label.pack(pady=10)

            # --- Inputs Section (Start Page, End Page, and Parts fields side-by-side) ---
            self.options_frame = ctk.CTkFrame(self)
            self.options_frame.pack(pady=15, padx=40, fill="x")
            self.options_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

            # Start Page Field
            self.start_label = ctk.CTkLabel(self.options_frame, text="Start Page:")
            self.start_label.grid(row=0, column=0, padx=(15, 5), pady=15, sticky="e")
            self.start_entry = ctk.CTkEntry(self.options_frame, width=60, state="disabled")
            self.start_entry.grid(row=0, column=1, padx=(5, 15), pady=15, sticky="w")

            # End Page Field
            self.end_label = ctk.CTkLabel(self.options_frame, text="End Page:")
            self.end_label.grid(row=0, column=2, padx=(15, 5), pady=15, sticky="e")
            self.end_entry = ctk.CTkEntry(self.options_frame, width=60, state="disabled")
            self.end_entry.grid(row=0, column=3, padx=(5, 15), pady=15, sticky="w")

            # Parts Field
            self.parts_label = ctk.CTkLabel(self.options_frame, text="Parts:")
            self.parts_label.grid(row=0, column=4, padx=(15, 5), pady=15, sticky="e")
            self.parts_entry = ctk.CTkEntry(self.options_frame, width=60, state="disabled")
            self.parts_entry.grid(row=0, column=5, padx=(5, 15), pady=15, sticky="w")

            # --- Execution Frame ---
            self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.action_frame.pack(pady=(10, 5), padx=40, fill="x")

            self.export_btn = ctk.CTkButton(
                self.action_frame,
                text="Export / Process PDF",
                command=self.export_pdf,
                state="disabled",
                font=ctk.CTkFont(size=14, weight="bold"),
                height=40
            )
            self.export_btn.pack(fill="x")

            # --- Status Bar ---
            self.status_label = ctk.CTkLabel(
                self, 
                text="Ready", 
                text_color="gray",
                font=ctk.CTkFont(size=12)
            )
            self.status_label.pack(side="bottom", pady=10)

        def choose_file(self):
            """
            Opens a file dialog to choose a PDF file, parses total pages,
            and initializes GUI text fields with default values.
            """
            if not PYPDF_AVAILABLE:
                messagebox.showerror("Error", "pypdf library is not installed. Please run 'pip install pypdf' to enable PDF processing.")
                return

            file_path = filedialog.askopenfilename(
                title="Select a PDF File",
                filetypes=[("PDF Files", "*.pdf")]
            )
            if not file_path:
                return

            try:
                self.pdf_path = file_path
                filename = os.path.basename(file_path)
                self.file_label.configure(text=filename, text_color=["black", "white"])

                # Read and evaluate the loaded PDF
                reader = PdfReader(file_path)
                self.total_pages = len(reader.pages)

                self.pages_label.configure(text=f"Total Pages: {self.total_pages}")

                # Enable entry inputs and insert default page parameters
                self.start_entry.configure(state="normal")
                self.end_entry.configure(state="normal")
                self.parts_entry.configure(state="normal")

                self.start_entry.delete(0, "end")
                self.start_entry.insert(0, "1")

                self.end_entry.delete(0, "end")
                self.end_entry.insert(0, str(self.total_pages))

                self.parts_entry.delete(0, "end")
                self.parts_entry.insert(0, "1")

                self.export_btn.configure(state="normal")
                self.status_label.configure(text="PDF loaded successfully.", text_color="green")

            except Exception as e:
                self.status_label.configure(text="Failed to read PDF file.", text_color="red")
                messagebox.showerror("Error", f"Failed to read PDF file:\n{str(e)}")

        def export_pdf(self):
            """
            Validates range and parts inputs, opens save file dialogs,
            runs the extraction & compression pipeline, and alerts results.
            """
            if not self.pdf_path:
                return

            # --- Validation Phase ---
            try:
                start_val = self.start_entry.get().strip()
                end_val = self.end_entry.get().strip()
                parts_val = self.parts_entry.get().strip()

                if not start_val or not end_val or not parts_val:
                    raise ValueError("All fields must be filled.")

                start_page = int(start_val)
                end_page = int(end_val)
                num_parts = int(parts_val)

                if start_page < 1:
                    raise ValueError("Start page must be 1 or greater.")
                if end_page > self.total_pages:
                    raise ValueError(f"End page cannot exceed total pages ({self.total_pages}).")
                if start_page > end_page:
                    raise ValueError("Start page must be less than or equal to End page.")
                if num_parts < 1:
                    raise ValueError("Number of parts must be 1 or greater.")

                range_pages = end_page - start_page + 1
                if num_parts > range_pages:
                    raise ValueError(f"Number of parts ({num_parts}) cannot exceed pages in selected range ({range_pages}).")

            except ValueError as e:
                messagebox.showerror("Invalid Input", str(e))
                return

            # --- Mode 1: Single File Export (Parts = 1) ---
            if num_parts == 1:
                save_path = filedialog.asksaveasfilename(
                    title="Export PDF As",
                    defaultextension=".pdf",
                    filetypes=[("PDF Files", "*.pdf")],
                    initialfile=f"extracted_{start_page}_to_{end_page}.pdf"
                )
                if not save_path:
                    return

                self.status_label.configure(text="Exporting & Compressing...", text_color="orange")
                self.update_idletasks()

                try:
                    final_size = extract_and_compress_pdf(self.pdf_path, start_page, end_page, save_path)

                    if final_size > 5.0:
                        self.status_label.configure(text=f"Exported: {final_size:.2f} MB (Exceeds 5MB)", text_color="orange")
                        messagebox.showwarning(
                            "Export Warning",
                            f"Successfully exported pages {start_page} to {end_page} to:\n{save_path}\n\n"
                            f"Warning: The file size is {final_size:.2f} MB, which exceeds the 5MB limit. "
                            f"We compressed it as much as possible, but it could not be reduced further."
                        )
                    else:
                        self.status_label.configure(text=f"Export completed! ({final_size:.2f} MB)", text_color="green")
                        messagebox.showinfo(
                            "Success",
                            f"Successfully exported pages {start_page} to {end_page} to:\n{save_path}\n\n"
                            f"Final file size: {final_size:.2f} MB (Compressed)"
                        )

                except Exception as e:
                    self.status_label.configure(text="Export failed.", text_color="red")
                    messagebox.showerror("Error", f"Failed to export PDF:\n{str(e)}")

            # --- Mode 2: Multi-Part Split Export (Parts > 1) ---
            else:
                save_path = filedialog.asksaveasfilename(
                    title="Choose Base Name for Split Files",
                    defaultextension=".pdf",
                    filetypes=[("PDF Files", "*.pdf")],
                    initialfile=f"split_range_{start_page}_to_{end_page}.pdf"
                )
                if not save_path:
                    return

                self.status_label.configure(text="Splitting & Compressing...", text_color="orange")
                self.update_idletasks()

                try:
                    # Calculate equal pages split offsets within the range
                    ranges = []
                    k, m = divmod(range_pages, num_parts)
                    curr_start = start_page
                    for i in range(num_parts):
                        curr_end = curr_start + k + (1 if i < m else 0) - 1
                        ranges.append((curr_start, curr_end))
                        curr_start = curr_end + 1

                    # Extract file path prefix/suffix info
                    base, ext = os.path.splitext(save_path)
                    if not ext:
                        ext = ".pdf"

                    exported_files = []
                    exceeded_limit = False
                    
                    # Run the extraction & compression on each calculated page block
                    for idx, (s, e) in enumerate(ranges):
                        part_path = f"{base}_part{idx+1}{ext}"
                        self.status_label.configure(text=f"Exporting part {idx+1}/{num_parts}...")
                        self.update_idletasks()
                        
                        part_size = extract_and_compress_pdf(self.pdf_path, s, e, part_path)
                        exported_files.append((part_path, part_size))
                        if part_size > 5.0:
                            exceeded_limit = True

                    # Prepare summary overview alert
                    summary_msg = f"Successfully split pages {start_page} to {end_page} into {num_parts} parts:\n\n"
                    for p_path, p_size in exported_files:
                        p_name = os.path.basename(p_path)
                        summary_msg += f"- {p_name}: {p_size:.2f} MB\n"

                    if exceeded_limit:
                        self.status_label.configure(text="Completed (Some parts exceed 5MB)", text_color="orange")
                        messagebox.showwarning(
                            "Split Warning",
                            summary_msg + "\nWarning: Some parts exceed the 5MB limit. We compressed them as much as possible, but they could not be reduced further."
                        )
                    else:
                        self.status_label.configure(text="Completed successfully!", text_color="green")
                        messagebox.showinfo(
                            "Success",
                            summary_msg + "\nAll parts are under the 5MB limit (Compressed)."
                        )

                except Exception as e:
                    self.status_label.configure(text="Split failed.", text_color="red")
                    messagebox.showerror("Error", f"Failed to split PDF:\n{str(e)}")


# ==============================================================================
# SECTION 4: STANDARD TKINTER FALLBACK USER INTERFACE CLASS
# This class defines the standard styled Tkinter GUI in case CustomTkinter
# fails to import. It has identical logic, layout, inputs, and validation checks.
# ==============================================================================

else:
    class PDFExtractorApp(tk.Tk):
        def __init__(self):
            super().__init__()

            # Configure window properties
            self.title("PDF Page Extractor & Splitter")
            self.geometry("600x430")
            self.resizable(False, False)

            # Apply styling elements using Tkinter's TTK styled theme system
            self.style = ttk.Style()
            self.style.theme_use("clam")

            # Soft background theme colors to make it look premium
            bg_color = "#f0f2f5"
            self.configure(bg=bg_color)
            
            # Label, button, and frame configurations
            self.style.configure(".", background=bg_color, font=("Segoe UI", 10))
            self.style.configure("TLabel", background=bg_color, foreground="#333333")
            self.style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), foreground="#1a1a1a")
            self.style.configure("Info.TLabel", font=("Segoe UI", 11, "bold"), foreground="#2b2b2b")
            self.style.configure("TButton", font=("Segoe UI", 10), padding=6)
            self.style.configure("Action.TButton", font=("Segoe UI", 11, "bold"), padding=10)
            self.style.configure("TFrame", background=bg_color)

            # Define internal state variables
            self.pdf_path = None
            self.total_pages = 0

            # Render UI components
            self.setup_ui()

        def setup_ui(self):
            # Header Title Label
            self.title_label = ttk.Label(
                self, 
                text="PDF Extractor & Splitter", 
                style="Header.TLabel"
            )
            self.title_label.pack(pady=(25, 15))

            # --- File Selection Section ---
            self.file_frame = ttk.Frame(self)
            self.file_frame.pack(pady=10, padx=40, fill="x")

            self.select_btn = ttk.Button(
                self.file_frame, 
                text="Choose PDF File", 
                command=self.choose_file,
                width=18
            )
            self.select_btn.pack(pady=15, side="left", padx=(15, 10))

            self.file_label = ttk.Label(
                self.file_frame, 
                text="No file selected",
                foreground="gray",
                anchor="w"
            )
            self.file_label.pack(pady=15, side="left", fill="x", expand=True, padx=(0, 15))

            # --- Document Information Section ---
            self.info_frame = ttk.Frame(self)
            self.info_frame.pack(pady=10, padx=40, fill="x")
            
            self.pages_label = ttk.Label(
                self.info_frame,
                text="Total Pages: -",
                style="Info.TLabel",
                anchor="center"
            )
            self.pages_label.pack(pady=10)

            # --- Inputs Section (Start Page, End Page, and Parts fields side-by-side) ---
            self.options_frame = ttk.Frame(self)
            self.options_frame.pack(pady=15, padx=40, fill="x")
            self.options_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

            # Start Page Field
            self.start_label = ttk.Label(self.options_frame, text="Start Page:")
            self.start_label.grid(row=0, column=0, padx=(15, 5), pady=15, sticky="e")
            self.start_entry = ttk.Entry(self.options_frame, width=8, state="disabled")
            self.start_entry.grid(row=0, column=1, padx=(5, 15), pady=15, sticky="w")

            # End Page Field
            self.end_label = ttk.Label(self.options_frame, text="End Page:")
            self.end_label.grid(row=0, column=2, padx=(15, 5), pady=15, sticky="e")
            self.end_entry = ttk.Entry(self.options_frame, width=8, state="disabled")
            self.end_entry.grid(row=0, column=3, padx=(5, 15), pady=15, sticky="w")

            # Parts Field
            self.parts_label = ttk.Label(self.options_frame, text="Parts:")
            self.parts_label.grid(row=0, column=4, padx=(15, 5), pady=15, sticky="e")
            self.parts_entry = ttk.Entry(self.options_frame, width=8, state="disabled")
            self.parts_entry.grid(row=0, column=5, padx=(5, 15), pady=15, sticky="w")

            # --- Execution Frame ---
            self.action_frame = ttk.Frame(self)
            self.action_frame.pack(pady=(10, 5), padx=40, fill="x")

            self.export_btn = ttk.Button(
                self.action_frame,
                text="Export / Process PDF",
                command=self.export_pdf,
                state="disabled",
                style="Action.TButton"
            )
            self.export_btn.pack(fill="x")

            # --- Status Bar ---
            self.status_label = ttk.Label(
                self, 
                text="Ready", 
                foreground="gray",
                font=("Segoe UI", 9)
            )
            self.status_label.pack(side="bottom", pady=10)

        def choose_file(self):
            """
            Opens a file dialog to choose a PDF file, parses total pages,
            and initializes GUI text fields with default values.
            """
            if not PYPDF_AVAILABLE:
                messagebox.showerror("Error", "pypdf library is not installed. Please run 'pip install pypdf' to enable PDF processing.")
                return

            file_path = filedialog.askopenfilename(
                title="Select a PDF File",
                filetypes=[("PDF Files", "*.pdf")]
            )
            if not file_path:
                return

            try:
                self.pdf_path = file_path
                filename = os.path.basename(file_path)
                self.file_label.configure(text=filename, foreground="black")

                # Read and evaluate the loaded PDF
                reader = PdfReader(file_path)
                self.total_pages = len(reader.pages)

                self.pages_label.configure(text=f"Total Pages: {self.total_pages}")

                # Enable entry inputs and insert default page parameters
                self.start_entry.configure(state="normal")
                self.end_entry.configure(state="normal")
                self.parts_entry.configure(state="normal")

                self.start_entry.delete(0, "end")
                self.start_entry.insert(0, "1")

                self.end_entry.delete(0, "end")
                self.end_entry.insert(0, str(self.total_pages))

                self.parts_entry.delete(0, "end")
                self.parts_entry.insert(0, "1")

                self.export_btn.configure(state="normal")
                self.status_label.configure(text="PDF loaded successfully.", foreground="green")

            except Exception as e:
                self.status_label.configure(text="Failed to read PDF file.", foreground="red")
                messagebox.showerror("Error", f"Failed to read PDF file:\n{str(e)}")

        def export_pdf(self):
            """
            Validates range and parts inputs, opens save file dialogs,
            runs the extraction & compression pipeline, and alerts results.
            """
            if not self.pdf_path:
                return

            # --- Validation Phase ---
            try:
                start_val = self.start_entry.get().strip()
                end_val = self.end_entry.get().strip()
                parts_val = self.parts_entry.get().strip()

                if not start_val or not end_val or not parts_val:
                    raise ValueError("All fields must be filled.")

                start_page = int(start_val)
                end_page = int(end_val)
                num_parts = int(parts_val)

                if start_page < 1:
                    raise ValueError("Start page must be 1 or greater.")
                if end_page > self.total_pages:
                    raise ValueError(f"End page cannot exceed total pages ({self.total_pages}).")
                if start_page > end_page:
                    raise ValueError("Start page must be less than or equal to End page.")
                if num_parts < 1:
                    raise ValueError("Number of parts must be 1 or greater.")

                range_pages = end_page - start_page + 1
                if num_parts > range_pages:
                    raise ValueError(f"Number of parts ({num_parts}) cannot exceed pages in selected range ({range_pages}).")

            except ValueError as e:
                messagebox.showerror("Invalid Input", str(e))
                return

            # --- Mode 1: Single File Export (Parts = 1) ---
            if num_parts == 1:
                save_path = filedialog.asksaveasfilename(
                    title="Export PDF As",
                    defaultextension=".pdf",
                    filetypes=[("PDF Files", "*.pdf")],
                    initialfile=f"extracted_{start_page}_to_{end_page}.pdf"
                )
                if not save_path:
                    return

                self.status_label.configure(text="Exporting & Compressing...", foreground="orange")
                self.update_idletasks()

                try:
                    final_size = extract_and_compress_pdf(self.pdf_path, start_page, end_page, save_path)

                    if final_size > 5.0:
                        self.status_label.configure(text=f"Exported: {final_size:.2f} MB (Exceeds 5MB)", foreground="orange")
                        messagebox.showwarning(
                            "Export Warning",
                            f"Successfully exported pages {start_page} to {end_page} to:\n{save_path}\n\n"
                            f"Warning: The file size is {final_size:.2f} MB, which exceeds the 5MB limit. "
                            f"We compressed it as much as possible, but it could not be reduced further."
                        )
                    else:
                        self.status_label.configure(text=f"Export completed! ({final_size:.2f} MB)", foreground="green")
                        messagebox.showinfo(
                            "Success",
                            f"Successfully exported pages {start_page} to {end_page} to:\n{save_path}\n\n"
                            f"Final file size: {final_size:.2f} MB (Compressed)"
                        )

                except Exception as e:
                    self.status_label.configure(text="Export failed.", foreground="red")
                    messagebox.showerror("Error", f"Failed to export PDF:\n{str(e)}")

            # --- Mode 2: Multi-Part Split Export (Parts > 1) ---
            else:
                save_path = filedialog.asksaveasfilename(
                    title="Choose Base Name for Split Files",
                    defaultextension=".pdf",
                    filetypes=[("PDF Files", "*.pdf")],
                    initialfile=f"split_range_{start_page}_to_{end_page}.pdf"
                )
                if not save_path:
                    return

                self.status_label.configure(text="Splitting & Compressing...", foreground="orange")
                self.update_idletasks()

                try:
                    # Calculate equal pages split offsets within the range
                    ranges = []
                    k, m = divmod(range_pages, num_parts)
                    curr_start = start_page
                    for i in range(num_parts):
                        curr_end = curr_start + k + (1 if i < m else 0) - 1
                        ranges.append((curr_start, curr_end))
                        curr_start = curr_end + 1

                    # Extract file path prefix/suffix info
                    base, ext = os.path.splitext(save_path)
                    if not ext:
                        ext = ".pdf"

                    exported_files = []
                    exceeded_limit = False
                    
                    # Run the extraction & compression on each calculated page block
                    for idx, (s, e) in enumerate(ranges):
                        part_path = f"{base}_part{idx+1}{ext}"
                        self.status_label.configure(text=f"Exporting part {idx+1}/{num_parts}...")
                        self.update_idletasks()
                        
                        part_size = extract_and_compress_pdf(self.pdf_path, s, e, part_path)
                        exported_files.append((part_path, part_size))
                        if part_size > 5.0:
                            exceeded_limit = True

                    # Prepare summary overview alert
                    summary_msg = f"Successfully split pages {start_page} to {end_page} into {num_parts} parts:\n\n"
                    for p_path, p_size in exported_files:
                        p_name = os.path.basename(p_path)
                        summary_msg += f"- {p_name}: {p_size:.2f} MB\n"

                    if exceeded_limit:
                        self.status_label.configure(text="Completed (Some parts exceed 5MB)", foreground="orange")
                        messagebox.showwarning(
                            "Split Warning",
                            summary_msg + "\nWarning: Some parts exceed the 5MB limit. We compressed them as much as possible, but they could not be reduced further."
                        )
                    else:
                        self.status_label.configure(text="Completed successfully!", foreground="green")
                        messagebox.showinfo(
                            "Success",
                            summary_msg + "\nAll parts are under the 5MB limit (Compressed)."
                        )

                except Exception as e:
                    self.status_label.configure(text="Split failed.", foreground="red")
                    messagebox.showerror("Error", f"Failed to split PDF:\n{str(e)}")


# ==============================================================================
# SECTION 5: APP ENTRY POINT
# Checks if this script is executed directly, and boots the main program loop.
# ==============================================================================

if __name__ == "__main__":
    app = PDFExtractorApp()
    app.mainloop()
