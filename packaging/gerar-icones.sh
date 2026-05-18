#!/usr/bin/env bash
# Gera PNG hicolor a partir do SVG (quadrado, sem faixas brancas).
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SVG="${RAIZ}/data/icons/hicolor/scalable/apps/agildocheats.svg"
OUT="${RAIZ}/data/icons/hicolor"

if ! command -v rsvg-convert >/dev/null 2>&1; then
  echo "Instala: sudo pacman -S librsvg"
  exit 1
fi

[[ -f "$SVG" ]] || { echo "SVG em falta: $SVG"; exit 1; }

for tam in 16 22 24 32 48 64 128 256; do
  dir="${OUT}/${tam}x${tam}/apps"
  mkdir -p "$dir"
  rsvg-convert -w "$tam" -h "$tam" -o "${dir}/agildocheats.png" "$SVG"
done

rsvg-convert -w 512 -h 512 -o "${RAIZ}/icone.png" "$SVG"
cp "${RAIZ}/icone.png" "${OUT}/scalable/apps/agildocheats.png"
echo "Ícones gerados em ${OUT} e icone.png"
