#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
[[ -f PKGBUILD ]] || { echo 'Corre na pasta packaging/aur.'; exit 1; }
pkgver="$(grep '^pkgver=' PKGBUILD | head -1 | awk -F= '{print $2}')"
_githubuser="$(grep '^_githubuser=' PKGBUILD | head -1 | awk -F= '{print $2}')"
_repo="$(grep '^_repo=' PKGBUILD | head -1 | awk -F= '{print $2}')"
URL="https://github.com/${_githubuser}/${_repo}/archive/refs/tags/v${pkgver}.tar.gz"
echo "A verificar: $URL"
curl -sSf -o /dev/null -L "$URL"
updpkgsums
makepkg --printsrcinfo >.SRCINFO
echo 'Pronto. Segue: ./enviar-para-aur.sh'
