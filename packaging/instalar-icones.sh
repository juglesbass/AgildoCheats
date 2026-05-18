#!/usr/bin/env bash
# Instala ícones no sistema (bash — não precisa de loop fish).
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

"${RAIZ}/packaging/gerar-icones.sh"

for tam in 16 22 24 32 48 64 128 256; do
  install -Dm644 "data/icons/hicolor/${tam}x${tam}/apps/agildocheats.png" \
    "/usr/share/icons/hicolor/${tam}x${tam}/apps/agildocheats.png"
done
install -Dm644 icone.png /usr/share/pixmaps/agildocheats.png
install -Dm644 data/icons/hicolor/scalable/apps/agildocheats.svg \
  /usr/share/icons/hicolor/scalable/apps/agildocheats.svg

gtk-update-icon-cache -f -t /usr/share/icons/hicolor
echo "Pronto. Corre: kbuildsycoca6 --noincremental"
