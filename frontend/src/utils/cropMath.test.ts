import {
  clampRect,
  createDefaultCrop,
  moveRect,
  resizeRectFromHandle,
  setCropDimension,
  rectToCropBox,
  cropBoxToRect,
  ASPECT_PRESETS,
} from './cropMath';

function assert(condition: boolean, msg?: string) {
  if (!condition) {
    throw new Error(msg || 'Assertion failed');
  }
}

function assertEqual<T>(actual: T, expected: T, msg?: string) {
  if (actual !== expected) {
    throw new Error(msg || `Expected ${expected}, but got ${actual}`);
  }
}

console.log('Running cropMath tests...');

// 1. clampRect
const clamped = clampRect({ x: -10, y: -20, width: 500, height: 600 }, 400, 300);
assertEqual(clamped.x, 0);
assertEqual(clamped.y, 0);
assertEqual(clamped.width, 400);
assertEqual(clamped.height, 300);

// 2. createDefaultCrop with ratio 1:1 (Square)
const squareCrop = createDefaultCrop(1000, 500, 1.0, 0.9);
assertEqual(squareCrop.width, squareCrop.height);
assertEqual(squareCrop.width, 450); // 500 * 0.9
assert(squareCrop.x >= 0 && squareCrop.x + squareCrop.width <= 1000);
assert(squareCrop.y >= 0 && squareCrop.y + squareCrop.height <= 500);

// 3. moveRect
const moved = moveRect({ x: 50, y: 50, width: 100, height: 100 }, 20, -10, 300, 300);
assertEqual(moved.x, 70);
assertEqual(moved.y, 40);

const clampedMove = moveRect({ x: 250, y: 250, width: 100, height: 100 }, 100, 100, 300, 300);
assertEqual(clampedMove.x, 200);
assertEqual(clampedMove.y, 200);

// 4. resizeRectFromHandle - free resize
const freeResizeSE = resizeRectFromHandle(
  { x: 100, y: 100, width: 100, height: 100 },
  'se',
  50,
  30,
  500,
  500,
  null
);
assertEqual(freeResizeSE.width, 150);
assertEqual(freeResizeSE.height, 130);

// 5. resizeRectFromHandle - locked aspect ratio (1:1)
const lockedResizeSE = resizeRectFromHandle(
  { x: 100, y: 100, width: 100, height: 100 },
  'se',
  50,
  30,
  500,
  500,
  1.0
);
assertEqual(lockedResizeSE.width, lockedResizeSE.height);

// 6. setCropDimension - manual width and height inputs with locked ratio
const dimUpdate = setCropDimension(
  { x: 50, y: 50, width: 100, height: 100 },
  'width',
  200,
  500,
  500,
  1.0
);
assertEqual(dimUpdate.width, 200);
assertEqual(dimUpdate.height, 200);

// 7. rectToCropBox & cropBoxToRect
const box = rectToCropBox({ x: 10, y: 20, width: 30, height: 40 });
assertEqual(box[0], 10);
assertEqual(box[1], 20);
assertEqual(box[2], 40);
assertEqual(box[3], 60);

const restored = cropBoxToRect(box);
assertEqual(restored.x, 10);
assertEqual(restored.y, 20);
assertEqual(restored.width, 30);
assertEqual(restored.height, 40);

// 8. Aspect presets
assertEqual(ASPECT_PRESETS.length, 6);

console.log('All cropMath tests passed successfully!');
