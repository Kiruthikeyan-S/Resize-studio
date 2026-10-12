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
}

export interface ConvertSettings {
  image_id: string;
  mode: 'smart_crop' | 'safe_fit' | 'manual_crop';
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
  outputs: RatioOutput[];
}

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

  getDownloadUrl(imageId: string, safeKey: string, mode?: string): string {
    const q = mode ? `?mode=${encodeURIComponent(mode)}` : '';
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

  getFullPreviewUrl(imageId: string, safeKey: string, version: number = 1, mode?: string): string {
    const modeParam = mode ? `&mode=${encodeURIComponent(mode)}` : '';
    return `${API_BASE}/preview-full/${imageId}/${safeKey}?v=${version}${modeParam}`;
  },
};
