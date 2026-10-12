# Ratio Studio — Smart Image Aspect Ratio Converter

**Ratio Studio** is a modern, high-performance web application designed to automatically convert single source images into five standardized aspect ratios without stretching or distortion.

It is built strictly using **classical digital signal processing and traditional image-processing techniques** (Fourier Transform spectral saliency, PIL LANCZOS resampling, bilateral filtering, and unsharp masking). **No AI, machine learning, generative models, or paid external APIs are used.**

---

## 📸 Five Predefined Target Ratios

Every output is generated with mathematical precision according to standard production specifications:

| Ratio | Dimensions | Orientation | Standard Target | Resampling |
|---|---|---|---|---|
| **Square (1:1)** | `2048 × 2048` px | Square | Profile pictures, Instagram posts, product tiles | Pillow LANCZOS |
| **Portrait (4:5)** | `1600 × 2000` px | Portrait | Instagram & Facebook feeds | Pillow LANCZOS |
| **Portrait (3:4)** | `1536 × 2048` px | Portrait | Tablets, editorial, print banners | Pillow LANCZOS |
| **Landscape (16:9)** | `2560 × 1440` px | Landscape | YouTube thumbnails, displays, web banners | Pillow LANCZOS |
| **Ratio (5:4)** | `2000 × 1600` px | Landscape | Medium format photography, art prints | Pillow LANCZOS |

---

## ⚡ Core Features & Capabilities

- **3 Deterministic Processing Modes**:
  1. **Smart Crop**: Classical Spectral Residual Saliency (`cv2.dft` + log magnitude spectrum analysis) automatically detects the visual center of interest and anchors the crop window around subjects/focal points.
  2. **Fit / Contain**: Preserves 100% of the image without cropping a single pixel. Supports smooth blurred background expansion or solid background fill.
  3. **Center Crop**: Traditional center-anchored framing preserving maximum frame area.
- **Interactive Re-adjust Crop Tool**: Fine-tune horizontal and vertical crop offsets with real-time visual rule-of-thirds grid overlay.
- **Individual Image Replacement**: Upload a custom replacement source image for any individual ratio without altering the other four outputs.
- **Quality & Format Management**:
  - EXIF orientation auto-transposition (`ImageOps.exif_transpose`).
  - Strict sRGB color profile compliance.
  - RGBA transparency handling with automatic background composition for JPEG.
  - Optional subtle edge-preserving bilateral denoising.
  - Optional subtle unsharp mask sharpening (zero halos).
- **Download Pipeline**:
  - Individual high-resolution file downloads (`image_1x1.jpg`, `image_16x9.jpg`, etc.).
  - One-click ZIP download (`ratio-studio-images.zip`) containing all 5 images plus a detailed `manifest.json`.
- **Security & Reliability**:
  - Deep file signature and header validation (verifying true byte content, not just extensions).
  - Decompression bomb protection (`MAX_IMAGE_PIXELS = 64,000,000`).
  - Path traversal protection with sanitization and safe server-generated IDs.
  - Automatic expiration and cleanup of temporary sessions.

---

## 🛠️ Technology Stack

### Frontend
- **React 19** with **TypeScript**
- **Vite 8**
- **Tailwind CSS v4** with custom modern dark theme (`#09090B`, `#111114`, `#18181B`, `#8B5CF6`)
- **Lucide React** for lightweight icons
- **Axios** with Vite API proxy configuration

### Backend
- **Python 3.11+** (compatible with 3.11 – 3.14+)
- **FastAPI**
- **Pillow 10+** (LANCZOS resampling, EXIF transpose, unsharp masking)
- **OpenCV 4.8+ / 5.0+** (2D Discrete Fourier Transform spectral saliency, bilateral denoising)
- **Python zipfile** (ZIP streaming and manifest packaging)
- **Uvicorn** for ASGI server

---

## 📂 Project Structure

```
Rezise/
├── backend/
│   ├── main.py                  # FastAPI application entrypoint & lifespan
│   ├── requirements.txt         # Backend Python dependencies
│   ├── routes/
│   │   ├── upload.py            # POST /api/upload & GET /api/original/{image_id}
│   │   ├── convert.py           # POST /api/convert, /api/replace/{ratio}, /api/adjust-crop
│   │   └── download.py          # GET /api/download, /api/download-all, /api/preview
│   ├── services/
│   │   ├── validator.py         # File validation, size limits, decompression bomb prevention
│   │   ├── crop_engine.py       # Ratio math, OpenCV spectral saliency, Fit & Center crop
│   │   ├── quality_manager.py   # EXIF correction, sRGB, alpha transparency, sharpen, denoise
│   │   ├── image_processor.py   # Pipeline coordinator, thumbnail generation, session storage
│   │   └── zip_generator.py     # ZIP packager and manifest.json generator
│   ├── storage/
│   │   ├── original/            # Temporary storage for uploaded originals
│   │   └── generated/           # Temporary storage for generated outputs & thumbs
│   └── tests/
│       ├── conftest.py          # Pytest path configuration
│       ├── test_upload.py       # Upload format, corruption, size, path traversal tests
│       ├── test_ratios.py       # Dimensions, stretching prevention, transparency, replace tests
│       └── test_download.py     # Download routes, ZIP integrity, session cleanup tests
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx             # Top navigation & application branding
│   │   │   ├── ImageUploader.tsx      # Drag-and-drop file uploader
│   │   │   ├── OriginalPreview.tsx    # Source image metadata & preview
│   │   │   ├── ConversionSettings.tsx # Mode, format, quality, and processing toggles
│   │   │   ├── RatioCard.tsx          # Card with aspect-ratio container, actions & preview
│   │   │   ├── PreviewGrid.tsx        # 5-card responsive output grid
│   │   │   ├── CropEditor.tsx         # Interactive crop adjustment modal
│   │   │   └── DownloadAll.tsx        # ZIP download banner
│   │   ├── services/
│   │   │   └── api.ts                 # Axios API client & TypeScript interfaces
│   │   ├── App.tsx                    # Main state machine and layout
│   │   ├── index.css                  # Tailwind styles and dark theme palette
│   │   └── main.tsx                   # React root entry
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

---

## 🚀 Getting Started (Windows / Local Execution)

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### 2. Backend Setup
From the project root:

```powershell
# Navigate to backend directory
cd backend

# Install dependencies (if not already installed globally)
pip install -r requirements.txt

# Start the FastAPI backend server on port 8000
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

The API will be available at `http://127.0.0.1:8000`. You can also explore the interactive Swagger documentation at `http://127.0.0.1:8000/docs`.

### 3. Frontend Setup
In a new terminal window:

```powershell
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

The frontend will start at `http://localhost:5173`. Open it in your web browser.

---

## 🧪 Running Automated Tests

A comprehensive pytest test suite is included in `backend/tests/`:

```powershell
# Run all tests with verbose output
python -m pytest backend/tests -v
```

### Verified Test Cases:
- Exact dimensions generated for all 5 aspect ratios.
- Non-stretching guarantee for wide and tall images.
- Valid crop boundaries clamped inside source dimensions.
- Proper handling of transparent RGBA PNGs (both PNG and JPEG export).
- Fit/Contain mode with background blur and canvas filling.
- Isolated ratio replacement without side-effects on other 4 ratios.
- Upload security: rejection of corrupted files, empty files, and path traversal strings.
- Individual download headers and attachment filenames.
- ZIP archive generation containing all 5 images + valid `manifest.json`.
- Session deletion and cleanup.
