# RetinaDetachNet

**Automated TUNEL and Nuclei Quantification for Retinal Detachment Analysis**

A deep learning-based tool for quantifying apoptotic cells (TUNEL+) and nuclei density in retinal detachment immunohistochemistry images using StarDist segmentation and U-Net-based ONL (Outer Nuclear Layer) segmentation.

---

## Features

- **Deep Learning Segmentation**: Uses StarDist (pretrained `2D_versatile_fluo` model) for accurate cell segmentation
- **U-Net ONL Detection**: Automatically identifies the Outer Nuclear Layer region using a trained U-Net model
- **Dual-Channel Analysis**: Processes paired Nuclei (DAPI) and TUNEL fluorescence images
- **Configurable Parameters**: Adjust thresholds, area filters, and overlap criteria via GUI
- **Comprehensive Output**: Generates visualizations and quantitative CSV results
- **Cross-Platform**: Works on macOS, Linux, and Windows

---

## Quick Start (5 minutes)

### Step 1: Install Miniconda (one time)

Download and install Miniconda from: https://docs.conda.io/en/latest/miniconda.html

### Step 2: Clone and Install RetinaDetachNet (one time)

**macOS/Linux:**
```bash
git clone https://github.com/kostasbaroutis/RetinaDetachNet.git
cd RetinaDetachNet
./install.sh
```

**Windows:**
```bash
git clone https://github.com/kostasbaroutis/RetinaDetachNet.git
cd RetinaDetachNet
install.bat
```

### Step 3: Run the Program

```bash
conda activate retinadetachnet
python RetinaDetachNet.py
```

A window will open. Select your Nuclei and TUNEL folders and click "Run Analysis".

### Updating to Latest Version

```bash
cd RetinaDetachNet
git pull
```

---

## Input Requirements

### Image Format
- **Format**: TIFF (.tif) files
- **Bit depth**: 16-bit recommended
- **Channels**: Single-channel fluorescence images

### File Organization
Place your images in two separate folders:

```
your_data/
├── Nuclei/          # DAPI/nuclei channel images
│   ├── 1.tif
│   ├── 2.tif
│   └── ...
└── TUNEL/           # TUNEL channel images
    ├── 1.tif        # Must match nuclei filenames
    ├── 2.tif
    └── ...
```

**Important**: Nuclei and TUNEL files are matched by filename. `Nuclei/1.tif` pairs with `TUNEL/1.tif`.

---

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Pixels per µm | 3.1 | Microscope calibration for spatial measurements |
| Min Area (µm²) | 10 | Minimum TUNEL cell size filter |
| Max Area (µm²) | 60 | Maximum TUNEL cell size filter |
| StarDist Thresh (Nuclei) | 0.01 | Nuclei detection sensitivity |
| StarDist Thresh (TUNEL) | 0.5 | TUNEL detection sensitivity |
| TUNEL Filter Overlap Thresh | 0.6 | Minimum overlap with intensity threshold |

---

## Output

Results are saved in the parent directory of your input folders:

```
your_data/
├── Nuclei/
├── TUNEL/
├── visualizations/           # QC images for each sample
│   ├── 1_01_original_nuclei.png
│   ├── 1_01b_onl_unet_mask.png
│   ├── 1_02_original_tunel.png
│   ├── 1_03_segmented_tunel_candidates.png
│   ├── 1_04_threshold_binary.png
│   ├── 1_05_filtered_tunel_positive.png
│   ├── 1_06_segmented_nuclei.png
│   └── 1_combined_2x3_pipeline.png
└── Results/
    └── analysis_summary.csv   # Quantitative metrics
```

### CSV Output Columns

| Column | Description |
|--------|-------------|
| File | Image filename |
| TUNEL_Filtered | Count of TUNEL+ cells after filtering |
| TUNEL_per_mm2 | TUNEL density per mm² |
| Nuclei | Total nuclei count in ONL |
| Area(um2) | ONL area in µm² |
| Density | Nuclei density per mm² |

---

## System Requirements

- **Python**: 3.10 recommended
- **RAM**: 8 GB minimum, 16 GB recommended
- **GPU**: Optional (CUDA for NVIDIA, MPS for Apple Silicon)
- **Storage**: ~200 MB for installation

---

## Troubleshooting

### "Model configuration not found"
Ensure the `models/` folder contains `config.json` and `model_weights.pth`. Try `git pull` to update.

### "No files processed"
Check that:
1. Nuclei and TUNEL filenames match exactly
2. Files have `.tif` extension
3. Images contain valid data (not empty)

### Slow processing
- Processing uses GPU acceleration when available (CUDA/MPS)
- First run downloads StarDist model (~50 MB)
- Large images take longer; consider downsizing if needed

---

## Citation

If you use RetinaDetachNet in your research, please cite:

```
[Citation pending publication]
```

---

## License

[License information to be added]

---

## Support

For issues and questions, please open an issue on GitHub:
https://github.com/kostasbaroutis/RetinaDetachNet/issues
