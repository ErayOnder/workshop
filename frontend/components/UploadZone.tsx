"use client";

import { useRef, useState, DragEvent, ChangeEvent } from "react";
import { Upload, ImageIcon } from "lucide-react";

interface Props {
  file: File | null;
  onChange: (file: File) => void;
  disabled?: boolean;
}

export default function UploadZone({ file, onChange, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const preview = file ? URL.createObjectURL(file) : null;

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && dropped.type.startsWith("image/")) onChange(dropped);
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const chosen = e.target.files?.[0];
    if (chosen) onChange(chosen);
  }

  return (
    <div
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={[
        "upload-zone",
        dragging ? "upload-zone--drag" : "",
        disabled ? "upload-zone--disabled" : "",
        file ? "upload-zone--filled" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={handleChange}
        disabled={disabled}
      />

      {preview ? (
        <div className="upload-preview">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={preview} alt="Ring preview" className="upload-preview__img" />
          <div className="upload-preview__overlay">
            <ImageIcon size={16} />
            <span>{file?.name}</span>
          </div>
        </div>
      ) : (
        <div className="upload-empty">
          <Upload className="upload-empty__icon" size={28} strokeWidth={1.5} />
          <p className="upload-empty__title">Drop your ring image here</p>
          <p className="upload-empty__hint">or click to browse — JPEG, PNG, WebP</p>
        </div>
      )}
    </div>
  );
}
