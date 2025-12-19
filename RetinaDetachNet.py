#!/usr/bin/env python
# coding: utf-8
"""
RetinaDetachNet - Automated TUNEL and Nuclei Quantification for Retinal Detachment Analysis

A deep learning-based tool for quantifying apoptotic cells (TUNEL+) and nuclei density
in retinal detachment immunohistochemistry images using StarDist segmentation and
U-Net-based ONL segmentation.

Version: 1.0.0

Distribution: Standalone Python GUI Application
Repository: https://github.com/kbaroutis/RetinaDetachNet
"""

# Suppress TensorFlow and StarDist warnings/popups
import os
os.environ['STARDIST_DISABLE_TF_LOG'] = '1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import glob
import json
import tifffile as tiff
import numpy as np
import pandas as pd
import threading
from scipy.ndimage import label, distance_transform_edt
from skimage.filters import threshold_otsu
from skimage.measure import regionprops
from skimage.restoration import rolling_ball
from skimage.transform import resize
from stardist.models import StarDist2D
from csbdeep.utils import normalize
from skimage.segmentation import find_boundaries
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import customtkinter as ctk
from tkinter import filedialog, messagebox

import torch
import segmentation_models_pytorch as smp

__version__ = "1.0.0"
__app_name__ = "RetinaDetachNet"

# ONL U-Net Model Path - Relative to script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ONL_MODEL_DIR = os.path.join(SCRIPT_DIR, "models")
ONL_THRESHOLD = 0.5  # Optimal threshold based on training validation metrics
ROLLING_BALL_RADIUS_UM = 6.5  # Rolling ball radius in micrometers for background subtraction


def load_onl_model(model_dir, device):
    """Load trained U-Net model for ONL segmentation."""
    config_path = os.path.join(model_dir, 'config.json')

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Model configuration not found at {config_path}\n"
            f"Please ensure the 'models' folder contains config.json and model_weights.pth"
        )

    with open(config_path, 'r') as f:
        config = json.load(f)

    model = smp.Unet(
        encoder_name=config['encoder'],
        encoder_weights=None,
        in_channels=3,
        classes=config['num_classes'],
    )

    weights_path = os.path.join(model_dir, 'model_weights.pth')
    best_model_path = os.path.join(model_dir, 'best_model.pth')

    if os.path.exists(weights_path):
        state_dict = torch.load(weights_path, map_location=device, weights_only=True)
        model.load_state_dict(state_dict)
    elif os.path.exists(best_model_path):
        checkpoint = torch.load(best_model_path, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint['model_state_dict'])
    else:
        raise FileNotFoundError(
            f"No model weights found in {model_dir}\n"
            f"Please ensure the 'models' folder contains model_weights.pth"
        )

    model = model.to(device)
    model.eval()
    return model, config


def normalize_percentile(image, pmin=0.1, pmax=95.0):
    """Percentile-based normalization matching training preprocessing."""
    mi = np.percentile(image, pmin)
    ma = np.percentile(image, pmax)
    if ma - mi < 1e-6:
        return np.zeros_like(image, dtype=np.float32)
    normalized = (image - mi) / (ma - mi)
    return np.clip(normalized, 0, 1).astype(np.float32)


def predict_onl(model, image, config, device, threshold=0.5):
    """
    Predict ONL segmentation mask using U-Net model.

    Args:
        model: Trained U-Net model
        image: Input nuclei/DAPI image as numpy array
        config: Model configuration dict
        device: torch device
        threshold: Probability threshold for binary mask

    Returns:
        pred: Binary predicted mask (0=background, 1=ONL)
        prob: Probability map (0-1)
    """
    img_size = config['img_size']
    original_shape = image.shape[:2]

    # Handle multi-channel images
    if len(image.shape) == 3:
        channel_means = [image[:, :, i].mean() for i in range(image.shape[2])]
        best_channel = np.argmax(channel_means)
        image = image[:, :, best_channel]
    image = image.astype(np.float32)

    # Resize to model input size
    image_resized = resize(image, (img_size, img_size), order=1, preserve_range=True, anti_aliasing=True)

    # Apply percentile normalization (matches training)
    image_resized = normalize_percentile(image_resized, pmin=0.1, pmax=95.0)

    # Stack to 3 channels (ResNet encoder expects 3 channels)
    image_3ch = np.stack([image_resized, image_resized, image_resized], axis=-1)

    # Convert to tensor: (H, W, C) -> (1, C, H, W)
    image_tensor = torch.from_numpy(image_3ch).permute(2, 0, 1).unsqueeze(0).float().to(device)

    # Predict
    with torch.no_grad():
        output = model(image_tensor)
        prob = torch.sigmoid(output).squeeze().cpu().numpy()
        pred = (prob > threshold).astype(np.uint8)

    # Resize back to original size
    pred_original = resize(pred, original_shape, order=0, preserve_range=True, anti_aliasing=False).astype(np.uint8)
    prob_original = resize(prob, original_shape, order=1, preserve_range=True, anti_aliasing=True)

    return pred_original, prob_original


def get_torch_device():
    """Get the best available torch device."""
    if torch.backends.mps.is_available():
        return torch.device('mps')
    elif torch.cuda.is_available():
        return torch.device('cuda')
    else:
        return torch.device('cpu')


# — Appearance —
ctk.set_appearance_mode("System")  # "Dark" or "Light"
ctk.set_default_color_theme("dark-blue")


class RetinaDetachNetApp(ctk.CTk):
    """
    Main application class for RetinaDetachNet.

    Provides a GUI for automated TUNEL and nuclei quantification
    in retinal detachment immunohistochemistry images.
    """

    def __init__(self):
        super().__init__()
        self.title(f"{__app_name__} - Retinal Detachment Analysis")
        self.geometry("600x600")
        self.resizable(True, True)
        self.eval('tk::PlaceWindow . center')

        # Cancellation flag & thread ref
        self.cancel_event = threading.Event()
        self.analysis_thread = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Input variables
        self.nuclei_dir_var = ctk.StringVar(value="Select nuclei directory")
        self.tunel_dir_var = ctk.StringVar(value="Select TUNEL directory")
        self.pixels_per_um_var = ctk.DoubleVar(value=3.1)
        self.min_area_um2_var = ctk.DoubleVar(value=10)
        self.max_area_um2_var = ctk.DoubleVar(value=60)
        self.prob_thresh_nuc = ctk.DoubleVar(value=0.01)
        self.prob_thresh_tun = ctk.DoubleVar(value=0.5)
        self.overlap_thresh_var = ctk.DoubleVar(value=0.6)

        # Layout
        main_frame = ctk.CTkFrame(self, corner_radius=12)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title label
        title_label = ctk.CTkLabel(main_frame, text=__app_name__,
                                   font=("Arial", 20, "bold"))
        title_label.pack(pady=(0, 10))

        frm = ctk.CTkFrame(main_frame, corner_radius=8)
        frm.pack(fill="x", padx=10, pady=10)

        def make_row(label_text, widget, row):
            ctk.CTkLabel(frm, text=label_text, font=("Arial", 12))\
                .grid(row=row, column=0, sticky="w", padx=5, pady=8)
            widget.grid(row=row, column=1, sticky="ew", padx=5, pady=8)

        # Nuclei Dir
        nuc_entry = ctk.CTkEntry(frm, textvariable=self.nuclei_dir_var, width=400)
        make_row("Nuclei Directory:", nuc_entry, 0)
        ctk.CTkButton(frm, text="Browse", width=80,
                      command=lambda: self.nuclei_dir_var.set(filedialog.askdirectory()))\
            .grid(row=0, column=2, padx=5)

        # TUNEL Dir
        tun_entry = ctk.CTkEntry(frm, textvariable=self.tunel_dir_var, width=400)
        make_row("TUNEL Directory:", tun_entry, 1)
        ctk.CTkButton(frm, text="Browse", width=80,
                      command=lambda: self.tunel_dir_var.set(filedialog.askdirectory()))\
            .grid(row=1, column=2, padx=5)

        # Pixels per µm
        ppum = ctk.CTkEntry(frm, textvariable=self.pixels_per_um_var, width=100)
        make_row("Pixels per µm:", ppum, 2)

        # Min area
        mina = ctk.CTkEntry(frm, textvariable=self.min_area_um2_var, width=100)
        make_row("Min Area (µm²):", mina, 3)

        # Max area
        maxa = ctk.CTkEntry(frm, textvariable=self.max_area_um2_var, width=100)
        make_row("Max Area (µm²):", maxa, 4)

        # StarDist thresholds
        pn = ctk.CTkEntry(frm, textvariable=self.prob_thresh_nuc, width=100)
        make_row("StarDist Thresh (Nuclei):", pn, 5)

        pt = ctk.CTkEntry(frm, textvariable=self.prob_thresh_tun, width=100)
        make_row("StarDist Thresh (TUNEL):", pt, 6)

        # Overlap threshold for TUNEL filter
        ot = ctk.CTkEntry(frm, textvariable=self.overlap_thresh_var, width=100)
        make_row("TUNEL Filter Overlap Thresh:", ot, 7)

        frm.grid_columnconfigure(1, weight=1)

        # Progress UI (hidden until run)
        self.prog = ctk.CTkFrame(main_frame, corner_radius=8)
        self.prog_label = ctk.CTkLabel(self.prog, text="Preparing...", font=("Arial", 12))
        self.prog_label.pack(pady=(10, 5))
        self.prog_bar = ctk.CTkProgressBar(self.prog, width=500, mode="determinate")
        self.prog_bar.pack(pady=(0, 5), padx=10)
        self.finish_label = ctk.CTkLabel(self.prog, text="", font=("Arial", 12))
        self.finish_label.pack(pady=(5, 0))
        self.cancel_btn = ctk.CTkButton(self.prog, text="Cancel", width=120, command=self.cancel)
        self.cancel_btn.pack(pady=(0, 10))

        # Run button
        self.submit_btn = ctk.CTkButton(main_frame, text="Run Analysis", command=self.submit,
                                        width=200, height=40, font=("Arial", 14))
        self.submit_btn.pack(pady=(0, 20))

    def on_close(self):
        self.cancel_event.set()
        if self.analysis_thread and self.analysis_thread.is_alive():
            self.wait_for_thread_completion()
        else:
            self.destroy()

    def cancel(self):
        self.cancel_event.set()
        if self.analysis_thread and self.analysis_thread.is_alive():
            self.prog_label.configure(text="Cancelling...")
            self.submit_btn.configure(state="disabled")
            self.after(100, lambda: self.wait_for_thread_completion(canceled=True))
        else:
            messagebox.showinfo("Cancelled", "Analysis cancelled.")
            self.destroy()

    def wait_for_thread_completion(self, canceled=False):
        if self.analysis_thread and self.analysis_thread.is_alive():
            self.after(100, lambda: self.wait_for_thread_completion(canceled))
        else:
            if canceled:
                messagebox.showinfo("Cancelled", "Analysis cancelled.\nWindow will close.")
            self.destroy()

    def submit(self):
        # Validate inputs
        if not os.path.isdir(self.nuclei_dir_var.get()) or not os.path.isdir(self.tunel_dir_var.get()):
            messagebox.showerror("Error", "One or more directories are invalid.")
            return
        if self.pixels_per_um_var.get() <= 0:
            messagebox.showerror("Error", "Pixels per µm must be positive.")
            return
        if self.min_area_um2_var.get() <= 0 or self.max_area_um2_var.get() <= 0:
            messagebox.showerror("Error", "Area thresholds must be positive.")
            return
        if self.max_area_um2_var.get() < self.min_area_um2_var.get():
            messagebox.showerror("Error", "Max area must be >= min area.")
            return
        if self.overlap_thresh_var.get() < 0 or self.overlap_thresh_var.get() > 1:
            messagebox.showerror("Error", "Overlap threshold must be between 0 and 1.")
            return

        self.cancel_event.clear()
        self.prog_label.configure(text="Preparing...")
        self.prog_bar.set(0)
        self.finish_label.configure(text="")
        self.cancel_btn.pack(pady=(0, 10))
        self.prog.pack(fill="x", padx=10, pady=20)
        self.submit_btn.configure(state="disabled")
        self.update()

        self.analysis_thread = threading.Thread(target=self.worker, daemon=False)
        self.analysis_thread.start()

    def worker(self):
        try:
            um2_px = (1 / self.pixels_per_um_var.get()) ** 2
            rolling_ball_radius_px = max(1, round(ROLLING_BALL_RADIUS_UM * self.pixels_per_um_var.get()))
            nuc_files = sorted(glob.glob(os.path.join(self.nuclei_dir_var.get(), '*.tif')))
            tun_files = sorted(glob.glob(os.path.join(self.tunel_dir_var.get(), '*.tif')))

            # Load StarDist model
            stardist_model = StarDist2D.from_pretrained('2D_versatile_fluo')

            # Load ONL U-Net model
            torch_device = get_torch_device()
            onl_model, onl_config = load_onl_model(ONL_MODEL_DIR, torch_device)

            # Determine output base directory as parent of nuclei/tunel directories
            nuclei_parent = os.path.dirname(os.path.abspath(self.nuclei_dir_var.get()))
            tunel_parent = os.path.dirname(os.path.abspath(self.tunel_dir_var.get()))

            # Use nuclei parent as default
            if nuclei_parent == tunel_parent:
                OUTPUT_BASE_DIR = nuclei_parent
            else:
                OUTPUT_BASE_DIR = nuclei_parent

            # Create output directories
            out_viz = os.path.join(OUTPUT_BASE_DIR, 'visualizations')
            out_results = os.path.join(OUTPUT_BASE_DIR, 'Results')
            for d in (out_viz, out_results):
                os.makedirs(d, exist_ok=True)

            results = []
            num_files = len(nuc_files)
            self.after(0, lambda: self.prog_bar.set(0))
            overlap_thresh = self.overlap_thresh_var.get()

            for i, nf in enumerate(nuc_files):
                if self.cancel_event.is_set():
                    return

                self.after(0, lambda i=i: self.prog_label.configure(text=f"Processing {i+1}/{num_files}..."))

                # Extract base filename without extension
                nuc_basename = os.path.basename(nf)
                fid = os.path.splitext(nuc_basename)[0]

                # Find matching TUNEL file with the same name
                tf = os.path.join(self.tunel_dir_var.get(), f"{fid}.tif")

                # Skip if matching TUNEL file doesn't exist
                if not os.path.exists(tf):
                    continue

                # Nuclei ROI & ONL mask using U-Net
                img = tiff.imread(nf).astype(np.float32)

                # Predict ONL mask using U-Net model
                onl_mask, onl_prob = predict_onl(onl_model, img, onl_config, torch_device, ONL_THRESHOLD)

                # Use the full U-Net mask as ROI (no connected component filtering)
                roi = onl_mask.astype(bool)
                area_um2 = np.sum(roi) * um2_px

                if area_um2 == 0:
                    continue

                # Process nuclei
                bg2 = rolling_ball(img, radius=rolling_ball_radius_px)
                sub2 = np.clip(img - bg2, 0, None)
                m2 = np.zeros_like(sub2)
                m2[roi] = sub2[roi]

                # Normalize nuclei using default percentile normalization
                nrm2 = normalize(m2, 1, 99.8, axis=(0, 1))

                # StarDist nuclei segmentation
                lbl_n2, _ = stardist_model.predict_instances(nrm2, prob_thresh=self.prob_thresh_nuc.get())

                # Count all nuclei (no area filter)
                unique_nuc = np.unique(lbl_n2)
                unique_nuc = unique_nuc[unique_nuc > 0]
                total_n = len(unique_nuc)
                density = total_n / area_um2 * 1e6 if area_um2 > 0 else np.nan

                # TUNEL processing
                timg = tiff.imread(tf).astype(np.float32)
                bg = rolling_ball(timg, radius=rolling_ball_radius_px)
                sub = np.clip(timg - bg, 0, None)
                sub_m = np.zeros_like(sub)
                sub_m[roi] = sub[roi]

                # Normalize TUNEL using default percentile normalization
                norm = normalize(sub_m, 1, 99.8, axis=(0, 1))

                # StarDist TUNEL segmentation (candidates)
                lbl_t, _ = stardist_model.predict_instances(norm, prob_thresh=self.prob_thresh_tun.get())

                # Get candidate TUNEL IDs with area filter
                candidate_tunel_ids = []
                unique_tun = np.unique(lbl_t)
                unique_tun = unique_tun[unique_tun > 0]

                for tun_id in unique_tun:
                    tun_mask = lbl_t == tun_id
                    tun_area_px = np.sum(tun_mask)
                    tun_area_um2 = tun_area_px * um2_px
                    if self.min_area_um2_var.get() <= tun_area_um2 <= self.max_area_um2_var.get():
                        candidate_tunel_ids.append(tun_id)

                # Compute thresholded binary for combo filter (Global Otsu)
                thresh_val = threshold_otsu(norm)
                tunel_binary = norm > thresh_val

                # Filter for combo: keep if overlap fraction >= overlap_thresh
                kept_tunel_ids = []
                for tun_id in candidate_tunel_ids:
                    tun_mask = lbl_t == tun_id
                    tun_area_px = np.sum(tun_mask)
                    intersect_area = np.sum(tun_mask & tunel_binary)
                    overlap_fraction = intersect_area / tun_area_px if tun_area_px > 0 else 0
                    if overlap_fraction >= overlap_thresh:
                        kept_tunel_ids.append(tun_id)

                # Count filtered TUNEL cells
                tunel_filtered = len(kept_tunel_ids)

                # Visualizations - individual images
                plt.figure(figsize=(10, 10))
                plt.imshow(m2, cmap='gray')
                plt.title('Original Nuclei')
                plt.axis('off')
                plt.savefig(os.path.join(out_viz, f"{fid}_01_original_nuclei.png"), bbox_inches='tight')
                plt.close()

                # ONL U-Net Mask visualization with overlay
                plt.figure(figsize=(10, 10))
                plt.imshow(img, cmap='gray')
                onl_overlay = np.zeros((*onl_mask.shape, 4))
                onl_overlay[onl_mask == 1] = [1, 0, 0, 0.4]  # Red with alpha
                plt.imshow(onl_overlay)
                plt.title('ONL Segmentation (U-Net)')
                plt.axis('off')
                plt.savefig(os.path.join(out_viz, f"{fid}_01b_onl_unet_mask.png"), bbox_inches='tight')
                plt.close()

                plt.figure(figsize=(10, 10))
                plt.imshow(sub_m, cmap='gray')
                plt.title('Original TUNEL')
                plt.axis('off')
                plt.savefig(os.path.join(out_viz, f"{fid}_02_original_tunel.png"), bbox_inches='tight')
                plt.close()

                tun_bound = find_boundaries(lbl_t, mode='outer')
                tun_overlay = sub_m.copy()
                tun_overlay[tun_bound] = np.max(sub_m)

                plt.figure(figsize=(10, 10))
                plt.imshow(tun_overlay, cmap='gray')
                plt.title('StarDist TUNEL Candidates')
                plt.axis('off')
                plt.savefig(os.path.join(out_viz, f"{fid}_03_segmented_tunel_candidates.png"), bbox_inches='tight')
                plt.close()

                binary_overlay = np.zeros_like(sub_m)
                binary_overlay[tunel_binary] = np.max(sub_m)

                plt.figure(figsize=(10, 10))
                plt.imshow(binary_overlay, cmap='gray')
                plt.title('Threshold Binary Mask')
                plt.axis('off')
                plt.savefig(os.path.join(out_viz, f"{fid}_04_threshold_binary.png"), bbox_inches='tight')
                plt.close()

                filtered_lbl_t = np.zeros_like(lbl_t)
                for kt_id in kept_tunel_ids:
                    filtered_lbl_t[lbl_t == kt_id] = kt_id

                filt_bound = find_boundaries(filtered_lbl_t, mode='outer')
                filt_overlay = sub_m.copy()
                filt_overlay[filt_bound] = np.max(sub_m)

                plt.figure(figsize=(10, 10))
                plt.imshow(filt_overlay, cmap='gray')
                plt.title('Filtered TUNEL+ (Post-Threshold)')
                plt.axis('off')
                plt.savefig(os.path.join(out_viz, f"{fid}_05_filtered_tunel_positive.png"), bbox_inches='tight')
                plt.close()

                # Nuclei overlay visualization
                nuc_bound = find_boundaries(lbl_n2, mode='outer')
                nuc_overlay = m2.copy()
                nuc_overlay[nuc_bound] = np.max(m2)

                plt.figure(figsize=(10, 10))
                plt.imshow(nuc_overlay, cmap='gray')
                plt.title('Segmented Nuclei')
                plt.axis('off')
                plt.savefig(os.path.join(out_viz, f"{fid}_06_segmented_nuclei.png"), bbox_inches='tight')
                plt.close()

                # Combined 2x3 panel with ONL mask
                fig, axs = plt.subplots(2, 3, figsize=(30, 20))
                axs = axs.flatten()

                # Create ONL overlay image for panel
                onl_display = img.copy()
                onl_display_rgba = np.stack([img/img.max(), img/img.max(), img/img.max(), np.ones_like(img)], axis=-1)
                onl_display_rgba[onl_mask == 1, 0] = 1.0  # Add red tint
                onl_display_rgba[onl_mask == 1, 1] *= 0.5
                onl_display_rgba[onl_mask == 1, 2] *= 0.5

                images = [
                    (m2, 'Original Nuclei', 'gray'),
                    (onl_display_rgba, 'ONL Segmentation (U-Net)', None),
                    (nuc_overlay, 'Segmented Nuclei', 'gray'),
                    (sub_m, 'Original TUNEL', 'gray'),
                    (filt_overlay, 'Filtered TUNEL+ (Post-Threshold)', 'gray'),
                    (binary_overlay, 'Threshold Binary Mask', 'gray')
                ]

                for idx, (img_data, title, cmap) in enumerate(images):
                    if cmap:
                        axs[idx].imshow(img_data, cmap=cmap)
                    else:
                        axs[idx].imshow(img_data)
                    axs[idx].set_title(title, fontsize=14)
                    axs[idx].axis('off')

                plt.tight_layout()
                plt.savefig(os.path.join(out_viz, f"{fid}_combined_2x3_pipeline.png"), bbox_inches='tight')
                plt.close()

                pct_tunel = tunel_filtered / area_um2 * 1e6 if area_um2 > 0 else np.nan
                results.append({
                    "File": fid,
                    "TUNEL_Filtered": tunel_filtered,
                    "TUNEL_per_mm2": pct_tunel,
                    "Nuclei": total_n,
                    "Area(um2)": area_um2,
                    "Density": density
                })

                self.after(0, lambda i=i: self.prog_bar.set((i + 1) / num_files))

            # Wrap-up
            if self.cancel_event.is_set():
                return

            if results:
                df = pd.DataFrame(results)
                # Sort by numeric file order
                df['File_Numeric'] = pd.to_numeric(df['File'], errors='coerce')
                df = df.sort_values('File_Numeric')
                df = df.drop('File_Numeric', axis=1)
                # Round all numeric columns to 2 decimal places
                numeric_columns = df.select_dtypes(include=[np.number]).columns
                df[numeric_columns] = df[numeric_columns].round(2)
                df.to_csv(os.path.join(out_results, 'analysis_summary.csv'), index=False)
                self.after(0, lambda: messagebox.showinfo("Completed", f"Done! Saved results to:\n{out_results}"))
            else:
                self.after(0, lambda: messagebox.showinfo("Completed", "No files processed."))

            self.after(0, lambda: self.prog_label.configure(text="Analysis Complete"))
            self.after(0, lambda: self.finish_label.configure(text="Finished"))
            self.after(0, lambda: self.cancel_btn.pack_forget())
            self.after(0, lambda: self.submit_btn.configure(state="normal"))

        except Exception as e:
            error_message = str(e)
            self.after(0, lambda: messagebox.showerror("Error", f"Analysis failed: {error_message}"))
            self.after(0, lambda: self.prog_label.configure(text="Error Occurred"))
            self.after(0, lambda: self.cancel_btn.pack_forget())
            self.after(0, lambda: self.submit_btn.configure(state="normal"))


def main():
    """Entry point for RetinaDetachNet application."""
    app = RetinaDetachNetApp()
    app.mainloop()


if __name__ == "__main__":
    main()
