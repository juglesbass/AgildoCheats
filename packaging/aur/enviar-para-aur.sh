#!/usr/bin/env bash
set -euo pipefail
FONTES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$(grep -m1 '^pkgname=' "${FONTES}/PKGBUILD" | cut -d= -f2 | awk '{print $1}')"
cd "$FONTES"
grep -qE 'sha256sums=\([^)]*SKIP' PKGBUILD && { echo 'Corre ./prepare-for-aur.sh'; exit 1; }
if [[ -z "$(git config user.email 2>/dev/null)" ]]; then
  git config user.email 'agomesdasilva99@gmail.com'
  git config user.name 'Agildo Gomes da Silva'
fi
makepkg --printsrcinfo >.SRCINFO
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
git -c init.defaultBranch=master clone "ssh://aur@aur.archlinux.org/${PKG}.git" "${WORKDIR}/repo"
cd "${WORKDIR}/repo"
git config user.email 'agomesdasilva99@gmail.com'
git config user.name 'Agildo Gomes da Silva'
cp "${FONTES}/PKGBUILD" "${FONTES}/.SRCINFO" "${FONTES}/agildocheats.install" \
   "${FONTES}/agildocheats.desktop" "${FONTES}/LICENSE" .
git add PKGBUILD .SRCINFO agildocheats.install agildocheats.desktop LICENSE
pkgver="$(grep ^pkgver= PKGBUILD | awk -F= '{print $2}')"
pkgrel="$(grep ^pkgrel= PKGBUILD | awk -F= '{print $2}')"
if git rev-parse -q HEAD >/dev/null; then
  git commit -m "Atualizar para ${pkgver}-${pkgrel}"
else
  git commit -m "Publicação inicial ${pkgver}-${pkgrel}"
fi
git push origin master
echo "https://aur.archlinux.org/packages/${PKG}"
