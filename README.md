# Ratio Studio — Professional Multi-Ratio Image Converter

**Ratio Studio** is a modern, high-performance web application designed to automatically convert single source images into five standardized commercial aspect ratios without stretching, distortion, or artificial hallucinations.

It features two primary comparison methods:
- **Method A — Standard Resize**: Pure mathematical Pillow LANCZOS direct stretch, preserving 100% of approved pixels with zero AI alteration.
- **Method B — AI Enhanced Resize**: Cloudflare Workers AI inpainting background outpainting combined with Groq Vision scene analysis, plus **CNN-based Real-ESRGAN Super-Resolution** and protected foreground compositing.

---

## 📸 Five Commercial Target Ratios

Every output is generated with mathematical precision according to standard production specifications:

| Ratio | Dimensions | Orientation | Method A (Standard) | Method B (AI Enhanced) |
|---|---|---|---|---|
| **Square (1:1)** | 2048 × 2048 px | Square | Direct stretch (LANCZOS) | AI Outpainted background + Protected foreground |
| **Portrait (4:5)** | 1600 × 2000 px | Portrait | Direct stretch (LANCZOS) | AI Outpainted background + Protected foreground |
| **Portrait (3:4)** | 1536 × 2048 px | Portrait | Direct stretch (LANCZOS) | AI Outpainted background + Protected foreground |
| **Landscape (16:9)** | 2560 × 1440 px | Landscape | Direct stretch (LANCZOS) | AI Outpainted background + Protected foreground |
| **Landscape (5:4)** | 2000 × 1600 px | Landscape | Direct stretch (LANCZOS) | AI Outpainted background + Protected foreground |

---

## ⚡ Core Features & Capabilities

- **Method A & Method B Side-by-Side Comparison**:
  - Interactive comparison view for all 5 aspect ratios.
  - Independent selection per ratio: select Standard or AI for any ratio, or use presets (Select All Standard, Select All AI, Best Mix).
  - Selected ZIP export (/api/download-selected) delivering exact selected variants and master manifest.json.

- **CNN Super-Resolution (Real-ESRGAN)**:
  - Deep Convolutional Neural Network (**RRDBNet** with 23 Residual-in-Residual Dense Blocks and 4x scale factor).
  - Pure PyTorch implementation with singleton caching and memory-efficient tiled inference.
  - Automatic download and caching of official pretrained weights (RealESRGAN_x4plus.pth).
  - **Foreground Mode Choice**:
    - Original (100%): Preserves 100% of approved pixels without alteration (pixel_identical).
    - Real-ESRGAN: Reconstructs edges, textures, and clarity via CNN inference (i_enhanced_detail).
  - Master enhancement caching: generated once per approved master and reused across all ratios and sizes.

- **Scene-Aware AI Background Outpainting**:
  - Cloudflare Workers AI inpainting (@cf/runwayml/stable-diffusion-v1-5-inpainting).
  - Groq Vision analyzes environment and scene lighting/composition for natural prompt generation.
  - Cosine-feathered protected foreground compositing preventing seam artifacts and subject alteration.
  - Graceful fallback to Studio texture synthesis with honest status reporting.

- **Non-Destructive Original-Image-First Workflow**:
  - Uploaded files are preserved byte-for-byte unchanged (
aw.*).
  - Working master copy (working.png) is created with EXIF orientation corrected.
  - Full cropping and pan/zoom adjustment before generation.
  - Revert to raw at any time.

---

## 🛠️ Technology Stack

### Frontend
- **React 19** with **TypeScript**
- **Vite 8**
- **Tailwind CSS v4** with a clean light theme
- **Lucide React** icons
- **Axios** with API proxying

### Backend
- **Python 3.11+**
- **FastAPI**
- **PyTorch 2.0+** (Real-ESRGAN RRDBNet CNN inference)
- **Pillow** (LANCZOS resampling, sRGB color space, EXIF orientation)
- **OpenCV** (Pre-diffusion feathering, background synthesis)
- **Cloudflare Workers AI** & **Groq Vision SDK**
- **Uvicorn** ASGI server

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.11+**
- **Node.js 18+** and **npm**

### 2. Quick Launch
Run the launcher script from the root directory:
`powershell
./run.bat
`
Or start each service manually:

**Backend**:
`powershell
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
`
API Docs available at: http://127.0.0.1:8000/docs

**Frontend**:
`powershell
cd frontend
npm run dev
`
Open http://localhost:5173 in your browser.

---

## 🧪 Automated Testing

Full test suite with **60 automated tests** covering dimensions, CNN super-resolution, immutability, fallback handling, and downloads:
`powershell
pytest backend/tests -v
`

---

## 📄 License
MIT License.
