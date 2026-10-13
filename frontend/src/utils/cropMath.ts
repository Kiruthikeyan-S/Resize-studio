/**
 * Pure crop geometry and dimension calculation utilities for Ratio Studio.
 * Operates in original-image pixel space with strict bounds clamping.
 */

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type HandleType = 'nw' | 'ne' | 'se' | 'sw' | 'n' | 's' | 'e' | 'w';

export type AspectPresetKey = 'free' | '1:1' | '4:5' | '3:4' | '16:9' | '5:4';

export interface AspectPreset {
  key: AspectPresetKey;
  label: string;
  ratio: number | null; // width / height, null for free crop
}

export const ASPECT_PRESETS: AspectPreset[] = [
  { key: 'free', label: 'Free Crop', ratio: null },
  { key: '1:1', label: 'Square (1:1)', ratio: 1.0 },
  { key: '4:5', label: 'Portrait (4:5)', ratio: 4 / 5 },
  { key: '3:4', label: 'Portrait (3:4)', ratio: 3 / 4 },
  { key: '16:9', label: 'Landscape (16:9)', ratio: 16 / 9 },
  { key: '5:4', label: 'Landscape (5:4)', ratio: 5 / 4 },
];

/**
 * Clamps a crop rectangle to stay strictly within [0, 0, imageW, imageH].
 * Ensures width and height are integers >= minSize.
 */
export function clampRect(rect: Rect, imageW: number, imageH: number, minSize = 20): Rect {
  const safeMin = Math.max(10, Math.min(minSize, Math.floor(Math.min(imageW, imageH) / 2)));
  let width = Math.round(rect.width);
  let height = Math.round(rect.height);

  width = Math.max(safeMin, Math.min(imageW, width));
  height = Math.max(safeMin, Math.min(imageH, height));

  let x = Math.round(rect.x);
  let y = Math.round(rect.y);

  x = Math.max(0, Math.min(imageW - width, x));
  y = Math.max(0, Math.min(imageH - height, y));

  return { x, y, width, height };
}

/**
 * Creates a default centered crop box.
 * If ratio is specified, calculates the largest centered rectangle with that aspect ratio.
 */
export function createDefaultCrop(
  imageW: number,
  imageH: number,
  ratio: number | null = null,
  coverage = 0.9
): Rect {
  const baseW = imageW * coverage;
  const baseH = imageH * coverage;

  if (!ratio || ratio <= 0) {
    const width = Math.round(baseW);
    const height = Math.round(baseH);
    const x = Math.round((imageW - width) / 2);
    const y = Math.round((imageH - height) / 2);
    return clampRect({ x, y, width, height }, imageW, imageH);
  }

  let width: number;
  let height: number;

  if (baseW / baseH > ratio) {
    height = baseH;
    width = height * ratio;
  } else {
    width = baseW;
    height = width / ratio;
  }

  // Ensure it fits inside full image
  if (width > imageW) {
    width = imageW;
    height = width / ratio;
  }
  if (height > imageH) {
    height = imageH;
    width = height * ratio;
  }

  const roundedW = Math.round(width);
  const roundedH = Math.round(height);
  const x = Math.round((imageW - roundedW) / 2);
  const y = Math.round((imageH - roundedH) / 2);

  return clampRect({ x, y, width: roundedW, height: roundedH }, imageW, imageH);
}

/**
 * Moves a rectangle by delta dx, dy and clamps within image bounds.
 */
export function moveRect(
  rect: Rect,
  dx: number,
  dy: number,
  imageW: number,
  imageH: number
): Rect {
  return clampRect(
    {
      x: rect.x + dx,
      y: rect.y + dy,
      width: rect.width,
      height: rect.height,
    },
    imageW,
    imageH
  );
}

/**
 * Resizes a rectangle using corner/edge handle movements.
 * If lockedRatio is provided, respects the aspect ratio constraint.
 */
export function resizeRectFromHandle(
  origin: Rect,
  handle: HandleType,
  dx: number,
  dy: number,
  imageW: number,
  imageH: number,
  lockedRatio: number | null = null,
  minSize = 20
): Rect {
  const safeMin = Math.max(10, Math.min(minSize, Math.floor(Math.min(imageW, imageH) / 2)));

  // Current corners
  let left = origin.x;
  let top = origin.y;
  let right = origin.x + origin.width;
  let bottom = origin.y + origin.height;

  // Free resize when aspect ratio is not locked
  if (!lockedRatio || lockedRatio <= 0) {
    switch (handle) {
      case 'se':
        right = Math.max(left + safeMin, Math.min(imageW, origin.x + origin.width + dx));
        bottom = Math.max(top + safeMin, Math.min(imageH, origin.y + origin.height + dy));
        break;
      case 'sw':
        left = Math.max(0, Math.min(right - safeMin, origin.x + dx));
        bottom = Math.max(top + safeMin, Math.min(imageH, origin.y + origin.height + dy));
        break;
      case 'ne':
        right = Math.max(left + safeMin, Math.min(imageW, origin.x + origin.width + dx));
        top = Math.max(0, Math.min(bottom - safeMin, origin.y + dy));
        break;
      case 'nw':
        left = Math.max(0, Math.min(right - safeMin, origin.x + dx));
        top = Math.max(0, Math.min(bottom - safeMin, origin.y + dy));
        break;
      case 'e':
        right = Math.max(left + safeMin, Math.min(imageW, origin.x + origin.width + dx));
        break;
      case 'w':
        left = Math.max(0, Math.min(right - safeMin, origin.x + dx));
        break;
      case 's':
        bottom = Math.max(top + safeMin, Math.min(imageH, origin.y + origin.height + dy));
        break;
      case 'n':
        top = Math.max(0, Math.min(bottom - safeMin, origin.y + dy));
        break;
    }

    return clampRect(
      {
        x: Math.round(left),
        y: Math.round(top),
        width: Math.round(right - left),
        height: Math.round(bottom - top),
      },
      imageW,
      imageH,
      minSize
    );
  }

  // Aspect ratio is locked: width / height = lockedRatio
  const ratio = lockedRatio;

  if (handle === 'se') {
    // Anchor: top-left (left, top)
    const rawW = origin.width + dx;
    let newW = Math.max(safeMin, Math.min(imageW - left, rawW));
    let newH = newW / ratio;

    if (top + newH > imageH) {
      newH = imageH - top;
      newW = newH * ratio;
    }
    if (newW < safeMin || newH < safeMin) {
      newW = Math.max(safeMin, safeMin * ratio);
      newH = newW / ratio;
    }
    return {
      x: Math.round(left),
      y: Math.round(top),
      width: Math.round(newW),
      height: Math.round(newH),
    };
  }

  if (handle === 'sw') {
    // Anchor: top-right (right, top)
    const rawW = origin.width - dx;
    let newW = Math.max(safeMin, Math.min(right, rawW));
    let newH = newW / ratio;

    if (top + newH > imageH) {
      newH = imageH - top;
      newW = newH * ratio;
    }
    if (newW < safeMin || newH < safeMin) {
      newW = Math.max(safeMin, safeMin * ratio);
      newH = newW / ratio;
    }
    return {
      x: Math.round(right - newW),
      y: Math.round(top),
      width: Math.round(newW),
      height: Math.round(newH),
    };
  }

  if (handle === 'ne') {
    // Anchor: bottom-left (left, bottom)
    const rawW = origin.width + dx;
    let newW = Math.max(safeMin, Math.min(imageW - left, rawW));
    let newH = newW / ratio;

    if (bottom - newH < 0) {
      newH = bottom;
      newW = newH * ratio;
    }
    if (newW < safeMin || newH < safeMin) {
      newW = Math.max(safeMin, safeMin * ratio);
      newH = newW / ratio;
    }
    return {
      x: Math.round(left),
      y: Math.round(bottom - newH),
      width: Math.round(newW),
      height: Math.round(newH),
    };
  }

  if (handle === 'nw') {
    // Anchor: bottom-right (right, bottom)
    const rawW = origin.width - dx;
    let newW = Math.max(safeMin, Math.min(right, rawW));
    let newH = newW / ratio;

    if (bottom - newH < 0) {
      newH = bottom;
      newW = newH * ratio;
    }
    if (newW < safeMin || newH < safeMin) {
      newW = Math.max(safeMin, safeMin * ratio);
      newH = newW / ratio;
    }
    return {
      x: Math.round(right - newW),
      y: Math.round(bottom - newH),
      width: Math.round(newW),
      height: Math.round(newH),
    };
  }

  // Edge handles with locked ratio: adjust the other dimension proportionally
  if (handle === 'e' || handle === 'w') {
    const rawW = handle === 'e' ? origin.width + dx : origin.width - dx;
    const maxAllowedW = handle === 'e' ? imageW - left : right;
    let newW = Math.max(safeMin, Math.min(maxAllowedW, rawW));
    let newH = newW / ratio;

    if (newH > imageH) {
      newH = imageH;
      newW = newH * ratio;
    }

    // Keep vertical position centered around origin center
    const centerY = origin.y + origin.height / 2;
    let newY = centerY - newH / 2;
    if (newY < 0) newY = 0;
    if (newY + newH > imageH) newY = imageH - newH;

    const newX = handle === 'e' ? left : right - newW;

    return clampRect(
      {
        x: Math.round(newX),
        y: Math.round(newY),
        width: Math.round(newW),
        height: Math.round(newH),
      },
      imageW,
      imageH,
      minSize
    );
  }

  if (handle === 's' || handle === 'n') {
    const rawH = handle === 's' ? origin.height + dy : origin.height - dy;
    const maxAllowedH = handle === 's' ? imageH - top : bottom;
    let newH = Math.max(safeMin, Math.min(maxAllowedH, rawH));
    let newW = newH * ratio;

    if (newW > imageW) {
      newW = imageW;
      newH = newW / ratio;
    }

    // Keep horizontal position centered around origin center
    const centerX = origin.x + origin.width / 2;
    let newX = centerX - newW / 2;
    if (newX < 0) newX = 0;
    if (newX + newW > imageW) newX = imageW - newW;

    const newY = handle === 's' ? top : bottom - newH;

    return clampRect(
      {
        x: Math.round(newX),
        y: Math.round(newY),
        width: Math.round(newW),
        height: Math.round(newH),
      },
      imageW,
      imageH,
      minSize
    );
  }

  return origin;
}

/**
 * Updates a dimension (width or height) manually entered by the user.
 */
export function setCropDimension(
  current: Rect,
  dimension: 'width' | 'height',
  value: number,
  imageW: number,
  imageH: number,
  lockedRatio: number | null = null,
  minSize = 20
): Rect {
  if (isNaN(value) || value <= 0) return current;

  const safeMin = Math.max(10, Math.min(minSize, Math.floor(Math.min(imageW, imageH) / 2)));

  if (!lockedRatio || lockedRatio <= 0) {
    if (dimension === 'width') {
      const w = Math.max(safeMin, Math.min(imageW, Math.round(value)));
      let x = current.x;
      if (x + w > imageW) x = imageW - w;
      return clampRect({ x, y: current.y, width: w, height: current.height }, imageW, imageH, minSize);
    } else {
      const h = Math.max(safeMin, Math.min(imageH, Math.round(value)));
      let y = current.y;
      if (y + h > imageH) y = imageH - h;
      return clampRect({ x: current.x, y, width: current.width, height: h }, imageW, imageH, minSize);
    }
  }

  // Locked ratio
  const ratio = lockedRatio;
  if (dimension === 'width') {
    let w = Math.max(safeMin, Math.min(imageW, Math.round(value)));
    let h = Math.round(w / ratio);
    if (h > imageH) {
      h = imageH;
      w = Math.round(h * ratio);
    }
    let x = current.x;
    let y = current.y;
    if (x + w > imageW) x = imageW - w;
    if (y + h > imageH) y = imageH - h;
    return clampRect({ x, y, width: w, height: h }, imageW, imageH, minSize);
  } else {
    let h = Math.max(safeMin, Math.min(imageH, Math.round(value)));
    let w = Math.round(h * ratio);
    if (w > imageW) {
      w = imageW;
      h = Math.round(w / ratio);
    }
    let x = current.x;
    let y = current.y;
    if (x + w > imageW) x = imageW - w;
    if (y + h > imageH) y = imageH - h;
    return clampRect({ x, y, width: w, height: h }, imageW, imageH, minSize);
  }
}

/**
 * Converts Rect to 4-tuple [left, top, right, bottom]
 */
export function rectToCropBox(rect: Rect): [number, number, number, number] {
  return [
    Math.round(rect.x),
    Math.round(rect.y),
    Math.round(rect.x + rect.width),
    Math.round(rect.y + rect.height),
  ];
}

/**
 * Converts 4-tuple [left, top, right, bottom] to Rect
 */
export function cropBoxToRect(box: [number, number, number, number]): Rect {
  return {
    x: box[0],
    y: box[1],
    width: Math.max(10, box[2] - box[0]),
    height: Math.max(10, box[3] - box[1]),
  };
}
