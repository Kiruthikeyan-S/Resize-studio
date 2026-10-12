import React, { useState, useRef } from 'react';
import type { DragEvent, ChangeEvent } from 'react';
import { Upload, AlertCircle, Loader2 } from 'lucide-react';
import type { UploadResponse } from '../services/api';
import { api } from '../services/api';

interface ImageUploaderProps {
  onUploadSuccess: (data: UploadResponse[]) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
}

export const ImageUploader: React.FC<ImageUploaderProps> = ({
  onUploadSuccess,
  isLoading,
  setIsLoading,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = async (filesList: FileList | File[]) => {
    setErrorMessage(null);
    setUploadStatus(null);

    const validFiles: File[] = [];
    const validExtensions = ['image/jpeg', 'image/png', 'image/webp'];

    for (let i = 0; i < filesList.length; i++) {
      const file = filesList[i];
      if (!validExtensions.includes(file.type) && !/\.(jpg|jpeg|png|webp)$/i.test(file.name)) {
        continue;
      }
      if (file.size > 20 * 1024 * 1024) {
        continue;
      }
      validFiles.push(file);
    }

    if (validFiles.length === 0) {
      setErrorMessage('No valid JPEG, PNG, or WebP images found (max 20 MB per file).');
      return;
    }

    try {
      setIsLoading(true);
      setUploadStatus(validFiles.length > 1 ? `Uploading ${validFiles.length} images...` : 'Uploading image...');
      
      if (validFiles.length === 1) {
        const single = await api.uploadImage(validFiles[0]);
        onUploadSuccess([single]);
      } else {
        const batch = await api.uploadMultipleImages(validFiles);
        onUploadSuccess(batch);
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to upload image(s).';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
      setUploadStatus(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const onDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const onFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files);
    }
  };

  return (
    <div className="w-full">
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => !isLoading && fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center transition-all cursor-pointer flex flex-col items-center justify-center group shadow-xs ${
          isDragOver
            ? 'border-violet-500 bg-violet-50/60 shadow-md shadow-violet-100'
            : 'border-slate-300 bg-white hover:border-violet-500 hover:bg-slate-50/50'
        } ${isLoading ? 'pointer-events-none opacity-60' : ''}`}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={onFileSelect}
          accept="image/jpeg,image/png,image/webp"
          multiple
          className="hidden"
        />

        <div className="w-16 h-16 rounded-2xl bg-violet-50 group-hover:bg-violet-100 border border-violet-100 flex items-center justify-center mb-4 transition-colors">
          {isLoading ? (
            <Loader2 className="w-8 h-8 text-violet-600 animate-spin" />
          ) : (
            <Upload className="w-8 h-8 text-violet-600 group-hover:scale-110 transition-transform" />
          )}
        </div>

        <h3 className="text-lg font-semibold text-slate-900 mb-1">
          {uploadStatus || 'Upload your image(s)'}
        </h3>
        <p className="text-sm text-slate-500 max-w-md mb-4">
          Drag & drop single or multiple files here, or{' '}
          <span className="text-violet-600 font-medium underline underline-offset-2">browse files</span>
        </p>

        <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-slate-500">
          <span className="px-2.5 py-1 rounded-md bg-violet-50 text-violet-700 font-medium border border-violet-200">
            Multiple Upload Supported
          </span>
          <span className="px-2.5 py-1 rounded-md bg-slate-100 border border-slate-200">JPEG, PNG, WebP</span>
          <span className="px-2.5 py-1 rounded-md bg-slate-100 border border-slate-200">Up to 20 MB each</span>
          <span className="px-2.5 py-1 rounded-md bg-slate-100 border border-slate-200">Batch Processing</span>
        </div>
      </div>

      {errorMessage && (
        <div className="mt-3 flex items-center gap-2 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
};
