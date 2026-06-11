#!/bin/bash
set -euo pipefail

VERSION="0.7.0"
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

python3 -m pip install -r requirements-dev.txt

ICONSET="$ROOT/build/PdfEditor.iconset"
rm -rf "$ICONSET" "$ROOT/dist/PdfEditor.app" "$ROOT/dist/PdfEditor-$VERSION-macOS.dmg"
mkdir -p "$ICONSET" "$ROOT/dist"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" assets/pdfeditor-512.png --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" assets/pdfeditor-512.png --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o assets/pdfeditor.icns

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "PdfEditor" \
  --icon "assets/pdfeditor.icns" \
  --osx-bundle-identifier "com.zouzoukobernard.pdfeditor" \
  --collect-all pymupdf \
  --add-data "ocr-data:ocr-data" \
  --add-data "assets:assets" \
  run.py

codesign --force --deep --sign - dist/PdfEditor.app
hdiutil create \
  -volname "PdfEditor" \
  -srcfolder dist/PdfEditor.app \
  -ov \
  -format UDZO \
  "dist/PdfEditor-$VERSION-macOS.dmg"

echo "DMG généré dans dist/PdfEditor-$VERSION-macOS.dmg"
