import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import os

import dir_diff  # <-- main moduel with the functions

#Get current directory
pwd = os.path.dirname(__file__)

#########################################
# GUI Application
#########################################

class DirDiffGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Dir Diff Tool")
        self.root.geometry("600x420")

        self.progress_queue = queue.Queue()

        # ------------- Directory selection -------------
        row = ttk.Frame(root)
        row.pack(fill="x", padx=10, pady=20)
        row.columnconfigure(1, weight=1)

        ttk.Label(row, text="Source Directory:").grid(row=0, column=0, sticky="w")
        self.src_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.src_var).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(row, text="Browse", command=self.browse_source).grid(row=0, column=2, sticky="e")

        # ------------- Manifest selection -------------
        row = ttk.Frame(root)
        row.pack(fill="x", padx=10, pady=10)
        row.columnconfigure(1, weight=1)

        ttk.Label(row, text="Old Manifest File:").grid(row=0, column=0, sticky="w")
        self.manifest_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.manifest_var).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(row, text="Browse", command=self.browse_manifest).grid(row=0, column=2, sticky="e")

        # ------------- Output directory -------------
        row = ttk.Frame(root)
        row.pack(fill="x", padx=10, pady=20)
        row.columnconfigure(1, weight=1)

        ttk.Label(row, text="Output Directory:").grid(row=0, column=0, sticky="w")
        self.output_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.output_var).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(row, text="Browse", command=self.browse_output).grid(row=0, column=2, sticky="e")

        # ------------- Save new manifest -------------
        row = ttk.Frame(root)
        row.pack(fill="x", padx=10, pady=10)
        row.columnconfigure(1, weight=1)

        ttk.Label(row, text="Save New Manifest As:").grid(row=0, column=0, sticky="w")
        self.save_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.save_var).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(row, text="Browse", command=self.browse_save_manifest).grid(row=0, column=2, sticky="e")

        # ------------- Buttons -------------
        ttk.Button(root, text="Build Manifest Only", command=self.run_build_manifest).pack(pady=8)
        ttk.Button(root, text="Extract Differential", command=self.run_extract_diff).pack(pady=4)

        # ------------- Progress Bar -------------
        ttk.Label(root, text="Progress:").pack(anchor="w", padx=10)
        self.progress = ttk.Progressbar(root, length=550, mode='determinate')
        self.progress.pack(padx=10, pady=10)

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(root, textvariable=self.status_var).pack()

        self.root.after(100, self.process_progress_queue)

    ###########################################################
    # File Browsers
    ###########################################################
    def browse_source(self):
        path = filedialog.askdirectory(initialdir=pwd)
        if path:
            self.src_var.set(path)

    def browse_manifest(self):
        path = filedialog.askopenfilename(initialdir=pwd,filetypes=[("JSON files", "*.json")])
        if path:
            self.manifest_var.set(path)

    def browse_output(self):
        path = filedialog.askdirectory(initialdir=pwd)
        if path:
            self.output_var.set(path)

    def browse_save_manifest(self):
        path = filedialog.asksaveasfilename(initialdir=pwd,defaultextension=".json")
        if path:
            self.save_var.set(path)

    ###########################################################
    # Worker Thread Wrappers
    ###########################################################
    def run_build_manifest(self):
        if not self.src_var.get():
            messagebox.showerror("Error", "Select a source directory.")
            return
        if not self.save_var.get():
            messagebox.showerror("Error", "Set save path for new manifest")
            return

        threading.Thread(target=self.worker_build_manifest, daemon=True).start()

    def run_extract_diff(self):
        if not self.src_var.get() or not self.manifest_var.get():
            messagebox.showerror("Error", "Select source directory and old manifest file.")
            return
        if not self.output_var.get():
            question = messagebox.askyesno("Output", "Output not defined. Use defualt 'extracted' directory?")
            if question:
                self.output_var.set(os.path.join(os.path.dirname(__file__), "extracted"))
            else:
                return
        if not self.save_var.get():
            question = messagebox.askokcancel("Save New Manifest", "Save file for new manifest not defined. Manifest for the current source directory will not be saved. Continue?")
            if not question:
                return
                
        threading.Thread(target=self.worker_extract_diff, daemon=True).start()

    ###########################################################
    # Actual Worker Logic (runs in background threads)
    ###########################################################
    def worker_build_manifest(self):
        self.set_status("Building manifest...")
        try:
            dir_diff.generate_manifest(
                self.src_var.get(),
                save_new_manifest=self.save_var.get() or None,
                progress_queue=self.progress_queue
            )
            self.set_status("Manifest built successfully.")
        except Exception as e:
            self.set_status("Error")
            messagebox.showerror("Error", str(e))

    def worker_extract_diff(self):
        self.set_status("Extracting differential...")
        try:
            dir_diff.extract_differential(
                self.src_var.get(),
                self.manifest_var.get(),
                output_dir=self.output_var.get() or None,
                save_new_manifest=self.save_var.get() or None,
                progress_queue=self.progress_queue

            )
            self.set_status("Done.")
        except Exception as e:
            self.set_status("Error")
            messagebox.showerror("Error", str(e))

    ###########################################################
    # Progress Bar Queue Handler
    ###########################################################
    def process_progress_queue(self):
        """Reads progress updates sent from worker threads."""
        try:
            while True:
                progress, total = self.progress_queue.get_nowait()
                self.progress["maximum"] = total
                self.progress["value"] = progress
        except queue.Empty:
            pass

        self.root.after(100, self.process_progress_queue)

    def set_status(self, text):
        self.status_var.set(text)


###########################################################
# Run GUI
###########################################################

if __name__ == "__main__":
    root = tk.Tk()
    app = DirDiffGUI(root)
    root.mainloop()
