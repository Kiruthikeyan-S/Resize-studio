# Ratio Studio — Professional Multi-Ratio Image Converter

**Ratio Studio** is a modern, high-performance web application designed to automatically convert single source images into five standardized commercial aspect ratios without stretching, distortion, or artificial hallucinations.

It features two primary processing options:
- **Option A — Full-Frame Photo**: Fills each target canvas with prominent subject framing, adaptive edge margins, and saliency-guided subject centering.
- **Option B — Entire Image Visible (Safe Fit)**: Preserves 100% of the original image on a clean, solid studio background without any content trimmed or blurred duplicate effects.

---

## 📸 Five Predefined Target Ratios

Every output is generated with mathematical precision according to standard production specifications:

| Ratio | Dimensions | Orientation | Framing Style | Resampling |
|---|---|---|---|---|
| **Square (1:1)** | `2048 × 2048` px | Square | Full-frame, subject centered | Pillow LANCZOS |
| **Portrait (4:5)** | `1600 × 2000` px | Portrait | Full-frame prominent framing | Pillow LANCZOS |
| **Portrait (3:4)** | `1536 × 2048` px | Portrait | Full-frame prominent framing | Pillow LANCZOS |
| **Landscape (16:9)** | `2560 × 1440` px | Landscape | Full-frame panoramic view | Pillow LANCZOS |
| **Landscape (5:4)** | `2000 × 1600` px | Landscape | Full-frame balanced proportions | Pillow LANCZOS |

---

## ⚡ Core Features & Capabilities

- **Two Clear Processing Options**:
  1. **Full-Frame Photo (Default)**: Multi-cue subject-aware Smart Crop combining spectral saliency, Canny edge detection, and morphological bounding contours. Anchors directly on the main subject (vehicles, products, portraits) to maximize subject prominence while preserving accurate proportions. If extreme aspect ratio shift (e.g. wide vehicle into narrow portrait 4:5 or 3:4) would clip vehicle wheels or bumpers, the engine automatically falls back to Safe Fit to safeguard the complete subject.
  2. **Entire Image Visible (Safe Fit)**: Preserves 100% of the image on a clean solid studio background (Pure White, Light Gray, Dark Slate, Pitch Black, or custom hex color).
- **Lossless Master Upload Caching**:
  - Uploaded files are preserved byte-for-byte unchanged (`raw.*`).
  - A normalized working master copy (`working.png`) is created with EXIF orientation corrected, eliminating repeated lossy JPEG recompression artifacts.
  - Full chroma 4:4:4 subsampling is preserved for high-quality JPEG exports.
- **Interactive Adjust Framing Tool**:
  - Live visual crop overlay with rule-of-thirds grid guides.
  - Strict aspect ratio preservation that prevents distortion and stretching.
  - Bounds and ratio validation with HTTP 422 error rejection.
- **Individual Image Replacement & Source Isolation**:
  - Upload a custom replacement source for any individual ratio without altering the other four outputs.
  - Independent source URLs (`/api/ratio-source/...`) ensure the crop editor always edits the active source image.
- **High-Fidelity Preview & Downloads**:
  - Lightweight WebP thumbnails for fast preview cards with stable revision tags (`?v=...`) for deterministic caching.
  - Dedicated full-resolution modal preview endpoint (`/api/preview-full/...`).
  - Individual high-resolution file downloads (`image_square_1x1.jpg`, etc.).
  - Complete package ZIP download (`ratio-studio-images.zip`) with `manifest.json`.
- **Optional Intelligence & Enhancement**:
  - Optional Groq Vision API analysis (`/api/analyze/{image_id}`) providing subject classification and crop risk analysis with graceful fallback.
  - Optional super-resolution and edge enhancement service.
- **Security & Validation**:
  - Streaming byte-level file size enforcement (max 20 MB).
  - Decompression bomb protection (`MAX_IMAGE_PIXELS = 64,000,000`).
  - Strict hexadecimal session ID validation preventing directory traversal.

---

## 🛠️ Technology Stack

### Frontend
- **React 19** with **TypeScript**
- **Vite 8**
- **Tailwind CSS v4** with a clean, minimal **Light Theme**
- **Lucide React** for lightweight icons
- **Axios** with API proxying

### Backend
- **Python 3.11+**
- **FastAPI**
- **Pillow** (LANCZOS resampling, EXIF transpose, sRGB profile management)
- **OpenCV** (2D Discrete Fourier Transform spectral saliency, bilateral filtering)
- **Groq Python SDK** (Optional vision analysis)
- **Uvicorn** ASGI server

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
│   │   ├── crop_engine.py       # Subject-aware smart crop, Safe Fit, ratio validation
│   │   ├── quality_manager.py   # EXIF correction, sRGB, alpha transparency, sharpen, denoise
│   │   ├── image_processor.py   # Lossless cache, isolated sources, versioned previews
│   │   ├── groq_vision.py       # Optional Groq Vision analysis service
│   │   ├── image_enhancer.py    # Optional super-resolution & enhancement service
│   │   └── zip_generator.py     # ZIP packager and manifest.json generator
│   └── tests/
│       ├── conftest.py          # Pytest path configuration
│       ├── test_upload.py       # Upload format, corruption, size, path traversal tests
│       ├── test_ratios.py       # Dimensions, crop math, replacement, groq fallback tests
│       └── test_download.py     # Download routes, ZIP integrity, session cleanup tests
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx             # Clean branding header
│   │   │   ├── ImageUploader.tsx      # Drag-and-drop file uploader
│   │   │   ├── OriginalPreview.tsx    # Source image metadata & preview
│   │   │   ├── ConversionSettings.tsx # Option A / B, format, and quality controls
│   │   │   ├── RatioCard.tsx          # Card with ratio preview, adjust crop, and replace
│   │   │   ├── PreviewGrid.tsx        # Responsive output grid
│   │   │   ├── CropEditor.tsx         # Interactive framing adjustment modal
│   │   │   ├── PreviewModal.tsx       # Full-resolution inspection modal
│   │   │   └── DownloadAll.tsx        # One-click ZIP download package
│   │   ├── services/
│   │   │   └── api.ts                 # Axios API client and TypeScript interfaces
│   │   ├── App.tsx                    # Main application component
│   │   └── index.css                  # Light theme CSS tokens
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.11+**
- **Node.js 18+** and **npm**

### 2. Backend Setup
```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Start the backend API server:
```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation will be available at `http://127.0.0.1:8000/docs`.

### 3. Frontend Setup
```powershell
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 🧪 Automated Testing

### Backend Tests (20 Automated Tests)
Run the full regression test suite:
```powershell
cd backend
python -m pytest -v
```

### Frontend Production Build
Run the TypeScript and Vite build verification:
```powershell
cd frontend
npm run build
```

---

## 📄 License
MIT License.
