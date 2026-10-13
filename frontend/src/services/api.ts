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
  ratio_safe_key: string;
  ratio_name: string;
  size_key: 'large' | 'medium' | 'small';
  size_label: string;
  width: number;
  height: number;
  file_name: string;
  file_size: number;
}

export interface RatioOutput {
  ratio_key: string;
  safe_key: string;
  legacy_key?: string;
  name: string;
  width: number;
  height: number;
  orientation: string;
  file_name: string;
  file_size: number;
  version: number;
  preview_url: string;
  download_url: string;
  source_url: string;
  source_width: number;
  source_height: number;
  crop_box: [number, number, number, number];
  mode: string;
  edges_trimmed?: boolean;
  fit_info?: FitInfo;
  fallback_reason?: string;
  variants?: OutputVariant[];
}

export interface ConvertSettings {
  image_id: string;
  mode: 'direct_stretch' | 'smart_crop' | 'ai_expand' | 'safe_fit' | 'manual_crop';
  bg_color_hex: string;
  is_transparent: boolean;
  export_format: 'jpeg' | 'png' | 'webp';
  quality: number;
  sharpen: boolean;
  denoise: boolean;
  custom_crops?: Record<string, [number, number, number, number]>;
}

export interface ConvertResponse {
  image_id: string;
  original_filename: string;
  export_format: string;
  mode: string;
  revision?: number;
  outputs: RatioOutput[];
}

export const SIZE_KEYS = ['large', 'medium', 'small'] as const;
export type SizeKey = (typeof SIZE_KEYS)[number];

/** Fixed export sizes per ratio (must match backend SIZE_PRESETS). */
export const RATIO_SIZE_TABLE: {
  safe_key: string;
  name: string;
  sizes: Record<SizeKey, [number, number]>;
}[] = [
  { safe_key: 'square_1x1', name: 'Square (1:1)', sizes: { large: [2048, 2048], medium: [1080, 1080], small: [512, 512] } },
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

const API_BASE = (import.meta.env.VITE_API_BASE as string) || '/api';

export const api = {
  async uploadImage(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post<UploadResponse>(`${API_BASE}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  async uploadMultipleImages(files: File[]): Promise<UploadResponse[]> {
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    const response = await axios.post<UploadResponse[]>(`${API_BASE}/upload-multiple`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  async convertImage(settings: ConvertSettings): Promise<ConvertResponse> {
    const response = await axios.post<ConvertResponse>(`${API_BASE}/convert`, settings);
    return response.data;
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
    return response.data;
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
    return response.data;
  },

  async updateOriginalFraming(
    imageId: string,
    cropBox: [number, number, number, number]
  ): Promise<UploadResponse> {
    const response = await axios.post<UploadResponse>(`${API_BASE}/update-original`, {
      image_id: imageId,
      crop_box: cropBox,
    });
    return response.data;
  },

  async resetOriginalFraming(imageId: string): Promise<UploadResponse> {
    const response = await axios.post<UploadResponse>(`${API_BASE}/reset-original/${imageId}`);
    return response.data;
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

  getDownloadUrl(imageId: string, safeKey: string, mode?: string, size?: string): string {
    const params = new URLSearchParams();
    if (mode) params.set('mode', mode);
    if (size) params.set('size', size);
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

  getPreviewUrl(imageId: string, safeKey: string, version: number = 1, mode?: string, size?: string): string {
    const params = new URLSearchParams();
    params.set('v', version.toString());
    if (mode) params.set('mode', mode);
    if (size) params.set('size', size);
    return `${API_BASE}/preview/${imageId}/${safeKey}?${params.toString()}`;
  },

  getFullPreviewUrl(imageId: string, safeKey: string, version: number = 1, mode?: string, size?: string): string {
    const params = new URLSearchParams();
    params.set('v', version.toString());
    if (mode) params.set('mode', mode);
    if (size) params.set('size', size);
    return `${API_BASE}/preview-full/${imageId}/${safeKey}?${params.toString()}`;
  },
};
