import axios from 'axios';

export interface UploadResponse {
  image_id: string;
  original_filename: string;
  width: number;
  height: number;
  raw_width?: number;
  raw_height?: number;
  file_size: number;
  format: string;
  mode: string;
  original_url: string;
  raw_url?: string;
  version?: number;
  is_low_res?: boolean;
  is_cropped_master?: boolean;
  master_crop_box?: [number, number, number, number] | null;
}

export interface FitInfo {
  has_subject_box: boolean;
  fits_completely: boolean;
  clipped_horizontal: boolean;
  clipped_vertical: boolean;
  message: string;
}

export interface OutputVariant {
  selection_id: string;
  legacy_selection_id?: string;
  method?: 'standard' | 'groq' | 'ai';
  ratio_safe_key: string;
  ratio_name: string;
  size_key: 'large' | 'medium' | 'small';
  size_label: string;
  width: number;
  height: number;
  file_name: string;
  file_size: number;
  status?: string;
}

export interface RatioOutput {
  ratio_key: string;
  safe_key: string;
  legacy_key?: string;
  method?: 'standard' | 'groq' | 'ai';
  name: string;
  width: number;
  height: number;
  orientation: string;
  file_name: string;
  file_size: number;
  file_path?: string;
  version: number;
  preview_url: string;
  download_url: string;
  source_url: string;
  source_width: number;
  source_height: number;
  crop_box: [number, number, number, number];
  mode: string;
  status?: 'ready' | 'unavailable' | 'failed' | 'fallback';
  provider?: string;
  error_message?: string;
  edges_trimmed?: boolean;
  fit_info?: FitInfo;
  fallback_reason?: string;
  is_generative_ai?: boolean;
  enhancement_status?: string;
  enhancement_provider?: string;
  foreground_mode?: 'auto' | 'original' | 'enhanced';
  foreground_fidelity?: string;
  foreground_description?: string;
  variants?: OutputVariant[];
}

export interface ComparisonRow {
  safe_key: string;
  ratio_key: string;
  name: string;
  width: number;
  height: number;
  orientation: string;
  standard: RatioOutput;
  groq?: RatioOutput;
  ai: RatioOutput;
  preferred_method: 'standard' | 'groq' | 'ai';
}

export interface ConvertSettings {
  image_id: string;
  mode: 'direct_stretch' | 'comparison' | 'smart_crop' | 'ai_expand' | 'safe_fit' | 'manual_crop';
  standard_fit?: 'stretch' | 'contain' | 'cover';
  bg_color_hex: string;
  is_transparent: boolean;
  export_format: 'jpeg' | 'png' | 'webp';
  quality: number;
  sharpen: boolean;
  denoise: boolean;
  allow_opencv_fallback?: boolean;
  prompt_hint?: string;
  custom_crops?: Record<string, [number, number, number, number]>;
  foreground_mode?: 'auto' | 'original' | 'enhanced';
  enhance_foreground?: boolean;
  sr_scale?: number;
}

export interface ConvertComparisonSettings {
  image_id: string;
  export_format: 'jpeg' | 'png' | 'webp';
  quality: number;
  bg_color_hex: string;
  is_transparent: boolean;
  sharpen: boolean;
  denoise: boolean;
  allow_opencv_fallback?: boolean;
  prompt_hint?: string;
  standard_fit?: 'stretch' | 'contain' | 'cover';
  foreground_mode?: 'auto' | 'original' | 'enhanced';
  enhance_foreground?: boolean;
  sr_scale?: number;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ConvertComparisonResponse {
  image_id: string;
  original_filename: string;
  export_format: string;
  revision: number;
  ai_status: 'ready' | 'unavailable' | 'failed' | 'fallback';
  ai_provider?: string;
  ai_message?: string;
  ai_is_generative?: boolean;
  groq_status?: 'ready' | 'unavailable' | 'failed' | 'fallback';
  groq_provider?: string;
  groq_message?: string;
  enhancement_status?: string;
  enhancement_provider?: string;
  foreground_mode?: 'auto' | 'original' | 'enhanced';
  foreground_fidelity?: string;
  rows: ComparisonRow[];
  outputs: RatioOutput[];
  token_usage?: TokenUsage;
}

export interface ConvertResponse {
  image_id: string;
  original_filename: string;
  export_format: string;
  mode: string;
  revision?: number;
  outputs: RatioOutput[];
  rows?: ComparisonRow[];
  ai_status?: string;
  token_usage?: TokenUsage;
}

export const SIZE_KEYS = ['large', 'medium', 'small'] as const;
export type SizeKey = (typeof SIZE_KEYS)[number];

/** Fixed export sizes per ratio (must match backend SIZE_PRESETS). */
export const RATIO_SIZE_TABLE: {
  safe_key: string;
  name: string;
  sizes: Record<SizeKey, [number, number]>;
}[] = [
  { safe_key: 'square_1x1', name: 'Square (1:1)', sizes: { large: [2048, 2048], medium: [1024, 1024], small: [512, 512] } },
  { safe_key: 'portrait_4x5', name: 'Portrait (4:5)', sizes: { large: [1600, 2000], medium: [1080, 1350], small: [800, 1000] } },
  { safe_key: 'portrait_3x4', name: 'Portrait (3:4)', sizes: { large: [1536, 2048], medium: [1080, 1440], small: [768, 1024] } },
  { safe_key: 'landscape_16x9', name: 'Landscape (16:9)', sizes: { large: [2560, 1440], medium: [1920, 1080], small: [1280, 720] } },
  { safe_key: 'landscape_5x4', name: 'Landscape (5:4)', sizes: { large: [2000, 1600], medium: [1350, 1080], small: [1000, 800] } },
];

export interface GroqAnalysisResponse {
  enabled: boolean;
  available?: boolean;
  message?: string;
  analysis?: {
    category: string;
    description: string;
    approximate_center_x: number;
    approximate_center_y: number;
    approximate_bbox?: [number, number, number, number];
    aspect_sensitivity: string;
    recommended_mode: string;
    risk_notes?: string;
  };
}

const envApiBase =
  (import.meta.env.VITE_API_BASE as string) ||
  (import.meta.env.VITE_API_BASE_URL as string) ||
  (import.meta.env.VITE_API_URL as string);

export const API_BASE =
  envApiBase ||
  (typeof window !== 'undefined' &&
   window.location.hostname !== 'localhost' &&
   window.location.hostname !== '127.0.0.1' &&
   !window.location.hostname.endsWith('.localhost')
    ? 'https://racemath.site/api'
    : '/api');

export function resolveUrl(url: string | undefined): string {
  if (!url) return '';
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('blob:') || url.startsWith('data:')) {
    return url;
  }
  if (API_BASE.startsWith('http://') || API_BASE.startsWith('https://')) {
    const baseHost = API_BASE.replace(/\/api\/?$/, '');
    const cleanPath = url.startsWith('/') ? url : `/${url}`;
    return `${baseHost}${cleanPath}`;
  }
  return url;
}

function normalizeUploadResponse(data: UploadResponse): UploadResponse {
  return {
    ...data,
    original_url: resolveUrl(data.original_url),
    raw_url: data.raw_url ? resolveUrl(data.raw_url) : undefined,
  };
}

function normalizeRatioOutput(out: RatioOutput): RatioOutput {
  return {
    ...out,
    preview_url: resolveUrl(out.preview_url),
    download_url: resolveUrl(out.download_url),
    source_url: resolveUrl(out.source_url),
  };
}

export const api = {
  async uploadImage(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post<UploadResponse>(`${API_BASE}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return normalizeUploadResponse(response.data);
  },

  async uploadMultipleImages(files: File[]): Promise<UploadResponse[]> {
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    const response = await axios.post<UploadResponse[]>(`${API_BASE}/upload-multiple`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data.map(normalizeUploadResponse);
  },

  async convertImage(settings: ConvertSettings): Promise<ConvertResponse> {
    const response = await axios.post<ConvertResponse>(`${API_BASE}/convert`, settings);
    const data = response.data;
    if (data.outputs) {
      data.outputs = data.outputs.map(normalizeRatioOutput);
    }
    return data;
  },

  async convertComparison(settings: ConvertComparisonSettings): Promise<ConvertComparisonResponse> {
    const response = await axios.post<ConvertComparisonResponse>(`${API_BASE}/convert-comparison`, settings);
    const data = response.data;
    if (data.rows) {
      data.rows = data.rows.map((row) => ({
        ...row,
        standard: normalizeRatioOutput(row.standard),
        groq: row.groq ? normalizeRatioOutput(row.groq) : undefined,
        ai: normalizeRatioOutput(row.ai),
      }));
    }
    return data;
  },

  async replaceRatio(
    ratio: string,
    imageId: string,
    file?: File,
    mode?: string,
    cropCoords?: [number, number, number, number]
  ): Promise<RatioOutput> {
    const formData = new FormData();
    formData.append('image_id', imageId);
    if (file) {
      formData.append('file', file);
    }
    if (mode) {
      formData.append('mode', mode);
    }
    if (cropCoords) {
      formData.append('crop_coords', JSON.stringify(cropCoords));
    }
    const response = await axios.post<RatioOutput>(
      `${API_BASE}/replace/${ratio}`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return normalizeRatioOutput(response.data);
  },

  async adjustCrop(
    imageId: string,
    ratio: string,
    cropBox: [number, number, number, number]
  ): Promise<RatioOutput> {
    const response = await axios.post<RatioOutput>(`${API_BASE}/adjust-crop`, {
      image_id: imageId,
      ratio,
      crop_box: cropBox,
    });
    return normalizeRatioOutput(response.data);
  },

  async updateOriginalFraming(
    imageId: string,
    cropBox: [number, number, number, number]
  ): Promise<UploadResponse> {
    const response = await axios.post<UploadResponse>(`${API_BASE}/update-original`, {
      image_id: imageId,
      crop_box: cropBox,
    });
    return normalizeUploadResponse(response.data);
  },

  async resetOriginalFraming(imageId: string): Promise<UploadResponse> {
    const response = await axios.post<UploadResponse>(`${API_BASE}/reset-original/${imageId}`);
    return normalizeUploadResponse(response.data);
  },

  async deleteSession(imageId: string): Promise<void> {
    await axios.delete(`${API_BASE}/images/${imageId}`);
  },

  /** POST selected '<ratio>:<size>' ids; returns the ZIP blob built from the latest generation. */
  async downloadSelectedZip(
    imageId: string,
    selections: string[],
    revision?: number
  ): Promise<Blob> {
    try {
      const response = await axios.post(
        `${API_BASE}/download-selected`,
        { image_id: imageId, selections, revision },
        { responseType: 'blob' }
      );
      return response.data as Blob;
    } catch (err: any) {
      // With responseType 'blob', JSON error bodies arrive as a Blob; extract the server message.
      const data = err?.response?.data;
      let detail: string | undefined;
      if (data instanceof Blob) {
        try {
          detail = JSON.parse(await data.text())?.detail;
        } catch {
          detail = undefined;
        }
      }
      throw new Error(detail || err?.message || 'Failed to create ZIP.');
    }
  },

  getDownloadUrl(imageId: string, safeKey: string, mode?: string, size?: string, method?: string): string {
    const params = new URLSearchParams();
    if (size) params.set('size', size);
    if (method) params.set('method', method);
    if (mode && !method) params.set('mode', mode);
    const q = params.toString() ? `?${params.toString()}` : '';
    return `${API_BASE}/download/${imageId}/${safeKey}${q}`;
  },

  getDownloadAllUrl(imageId: string, mode?: string): string {
    const q = mode ? `?mode=${encodeURIComponent(mode)}` : '';
    return `${API_BASE}/download-all/${imageId}${q}`;
  },

  getDownloadBatchUrl(imageIds: string[], mode?: string): string {
    const modeParam = mode ? `&mode=${encodeURIComponent(mode)}` : '';
    return `${API_BASE}/download-batch?image_ids=${imageIds.join(',')}${modeParam}`;
  },

  getPreviewUrl(imageId: string, safeKey: string, version: number = 1, mode?: string, size?: string, method?: string): string {
    const params = new URLSearchParams();
    params.set('v', version.toString());
    if (mode) params.set('mode', mode);
    if (size) params.set('size', size);
    if (method) params.set('method', method);
    return `${API_BASE}/preview/${imageId}/${safeKey}?${params.toString()}`;
  },

  getFullPreviewUrl(imageId: string, safeKey: string, version: number = 1, mode?: string, size?: string, method?: string): string {
    const params = new URLSearchParams();
    params.set('v', version.toString());
    if (mode) params.set('mode', mode);
    if (size) params.set('size', size);
    if (method) params.set('method', method);
    return `${API_BASE}/preview-full/${imageId}/${safeKey}?${params.toString()}`;
  },
};
