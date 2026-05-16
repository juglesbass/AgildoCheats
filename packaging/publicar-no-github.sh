#!/usr/bin/env bash
# Publica em https://github.com/juglesbass/AgildoCheats
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo 'Não é um repositório git. Corre: git init -b main && git remote add origin …'
  exit 1
fi
if [[ -z "$(git config user.email 2>/dev/null)" ]]; then
  git config user.email 'agomesdasilva99@gmail.com'
  git config user.name 'Agildo Gomes da Silva'
fi
VERSAO="$(tr -d '[:space:]' < version.txt)"
TAG="v${VERSAO}"
echo "A enviar main…"
git push -u origin main
if git rev-parse -q "refs/tags/${TAG}" >/dev/null 2>&1; then
  git push origin "${TAG}" || true
else
  git tag -a "${TAG}" -m "Release ${VERSAO}"
  git push origin "${TAG}"
fi
echo "https://github.com/juglesbass/AgildoCheats/releases/tag/${TAG}"
