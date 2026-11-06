#!/usr/bin/env bash
# The OCR programs of the integration tests, on a GitHub runner, from the .deb files in DIR (the
# job's cache) without the network, else from the Ubuntu archive within time limits.
#
#   ocr-packages.sh key            the cache's key: the runner image and this script
#   ocr-packages.sh install DIR    install them, from DIR when it holds them
#   ocr-packages.sh download DIR   only fetch their .deb files into DIR (to fill the cache)
#
# The files fit the runner image they were fetched on (the packages it has, their versions), so
# the key names it; a new image (about weekly) fetches them again.
#
# apt has no limit of its own: on 06.11.2026 it waited three times for a mirror that had stopped
# answering, until the job's limit (15 minutes) cancelled it, without its log. Here every
# connection may stand still for 20 seconds, every attempt takes at most LIMIT, and the log is
# shown when the last of ATTEMPTS fails. A mirror can also trickle, which no timeout of apt's
# notices (the same day, Azure's sent 2 of 66 MB a minute): the attempts after the first go to
# Ubuntu's own archive instead of the runner's mirror.
set -euo pipefail

PACKAGES=(
  ghostscript pngquant qpdf tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng unpaper
  libharfbuzz-subset0 libpango-1.0-0 libpangoft2-1.0-0
)
ATTEMPTS=3
LIMIT=60s  # a fetch from a mirror that answers takes 10 to 30 seconds

mode=${1:?key, install or download}
if [ "$mode" = key ]; then
  echo "ocr-debs-${ImageOS:?}-${ImageVersion:?}-$(sha256sum "$0" | cut -c1-16)"
  exit 0
fi
dir=${2:?the directory of the .deb files}
mkdir -p "$dir/partial"
sudo=()
[ "$(id -u)" = 0 ] || sudo=(sudo)
export DEBIAN_FRONTEND=noninteractive

apt_options=(
  -q -o Acquire::Retries=2 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20
  -o APT::Update::Error-Mode=any -o DPkg::Lock::Timeout=60
  -o Dir::Cache::archives="$dir" -o APT::Keep-Downloaded-Packages=true
)
# Only the Ubuntu archive: the runner's other sources (Microsoft, Docker, ...) add nothing here.
if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then
  parts=$(mktemp -d)
  cp /etc/apt/sources.list.d/ubuntu.sources "$parts/"
  apt_options+=(-o Dir::Etc::SourceList=/dev/null -o Dir::Etc::SourceParts="$parts")
fi

log=$(mktemp)
attempt() {
  "${sudo[@]}" timeout "$LIMIT" apt-get "${apt_options[@]}" update \
    && "${sudo[@]}" timeout "$LIMIT" apt-get "${apt_options[@]}" install --fix-broken \
      --no-install-recommends -y "$@" "${PACKAGES[@]}"
}
other_mirror() {
  [ -n "${parts:-}" ] || return 0
  sed -i -E 's#^URIs:[[:space:]]*mirror\+file:.*#URIs: http://archive.ubuntu.com/ubuntu/#' \
    "$parts/ubuntu.sources"
}
from_archive() {  # $@: further options of the install (--download-only)
  for number in $(seq "$ATTEMPTS"); do
    if [ "$number" -gt 1 ]; then
      other_mirror
    fi
    attempt "$@" >>"$log" 2>&1 && return 0
    code=$?  # 124: the attempt took longer than LIMIT
    echo "attempt $number of $ATTEMPTS failed (code $code)" | tee -a "$log" >&2
  done
  cat "$log" >&2
  return 1
}

# The trigger of man-db rebuilds the index of the manual pages: slow, and nobody reads them.
"${sudo[@]}" rm -f /var/lib/man-db/auto-update

case $mode in
download)
  from_archive --download-only
  # Only the files, readable by the runner's user that saves the cache (apt's lock is root's).
  "${sudo[@]}" rm -rf "$dir/lock" "$dir/partial"
  "${sudo[@]}" chown -R "$(id -u):$(id -g)" "$dir"
  echo "fetched $(find "$dir" -maxdepth 1 -name '*.deb' | wc -l) packages from the archive"
  ;;
install)
  start=$SECONDS
  if compgen -G "$dir/*.deb" >/dev/null && "${sudo[@]}" dpkg -i "$dir"/*.deb >"$log" 2>&1; then
    echo "installed from the cache in $((SECONDS - start)) s"
  else
    [ -s "$log" ] && { echo "the cache did not install:" >&2; cat "$log" >&2; : >"$log"; }
    from_archive
    echo "installed from the archive in $((SECONDS - start)) s"
  fi
  ;;
*)
  echo "unknown mode: $mode" >&2
  exit 2
  ;;
esac
