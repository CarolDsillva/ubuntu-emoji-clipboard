#!/usr/bin/env bash
# Builds dist/clipboard-picker_<version>_all.deb (needs dpkg-deb, i.e. Debian/Ubuntu).
#   packaging/build-deb.sh            version from the latest git tag
#   packaging/build-deb.sh 1.2.0      explicit version (a leading "v" is dropped)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG=clipboard-picker
APP_ID=io.github.ClipboardPicker
APP_DIR=/usr/share/$PKG
VERSION="${1:-$(git -C "$ROOT" describe --tags --abbrev=0 2>/dev/null || echo 0.0.0)}"
VERSION="${VERSION#v}"
OUT="$ROOT/dist"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
chmod 755 "$STAGE"  # mktemp makes it 0700, which would become the package root's mode
umask 022

install -Dm644 "$ROOT/clipboard_picker.py" "$STAGE$APP_DIR/clipboard_picker.py"
install -Dm644 "$ROOT/emoji_data.py"       "$STAGE$APP_DIR/emoji_data.py"
mkdir -p "$STAGE/usr/bin"
sed "s|@APP_DIR@|$APP_DIR|g" "$ROOT/packaging/clipboard-picker" > "$STAGE/usr/bin/$PKG"
chmod 755 "$STAGE/usr/bin/$PKG"
install -Dm644 "$ROOT/packaging/$APP_ID.desktop" "$STAGE/usr/share/applications/$APP_ID.desktop"
install -Dm644 "$ROOT/packaging/clipboard-picker-autostart.desktop" "$STAGE/etc/xdg/autostart/$PKG.desktop"
install -Dm644 "$ROOT/packaging/$APP_ID.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
install -Dm644 "$ROOT/LICENSE" "$STAGE/usr/share/doc/$PKG/copyright"
MAINTAINER="Carol Dsilva <109918630+CarolDsillva@users.noreply.github.com>"
cat <<EOF | gzip -9n > "$STAGE/usr/share/doc/$PKG/changelog.gz"
$PKG ($VERSION) stable; urgency=low

  * Release $VERSION. Full notes:
    https://github.com/CarolDsillva/ubuntu-emoji-clipboard/releases

 -- $MAINTAINER  $(date -R)
EOF
chmod 644 "$STAGE/usr/share/doc/$PKG/changelog.gz"

SIZE_KB="$(du -sk "$STAGE" | cut -f1)"
mkdir -p "$STAGE/DEBIAN"
echo "/etc/xdg/autostart/$PKG.desktop" > "$STAGE/DEBIAN/conffiles"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-gi, gir1.2-gtk-3.0
Recommends: xdotool, fonts-noto-color-emoji
Installed-Size: $SIZE_KB
Maintainer: $MAINTAINER
Homepage: https://github.com/CarolDsillva/ubuntu-emoji-clipboard
Description: Windows-style Win+. emoji and clipboard history picker
 Press Super+. to open a popup with two tabs: searchable emoji and a
 history of copied text with pinning. It runs in the background from
 login and binds the shortcut for each user the first time it starts.
EOF

mkdir -p "$OUT"
DEB="$OUT/${PKG}_${VERSION}_all.deb"
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "$DEB" >/dev/null
echo "Built $DEB"
