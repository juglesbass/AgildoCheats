#!/usr/bin/env bash
# Publica GitHub (main + etiqueta) e depois AUR.
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSAO="$(tr -d '[:space:]' < "${RAIZ}/version.txt")"
TAG="v${VERSAO}"

echo "=== 1/3 GitHub (${TAG}) ==="
"${RAIZ}/packaging/publicar-no-github.sh"

echo ""
echo "=== 2/3 AUR (checksums) ==="
cd "${RAIZ}/packaging/aur"
./prepare-for-aur.sh

echo ""
echo "=== 3/3 AUR (push) ==="
./enviar-para-aur.sh

echo ""
echo "Pronto. Instala com: paru -Syu agildocheats"
