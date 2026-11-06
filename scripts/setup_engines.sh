#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TESSDATA_DIR="data/raw/models/tessdata"
KRAKEN_DIR="data/raw/models/kraken"
CALAMARI_DIR="data/raw/models/calamari/fraktur_historical"
BIN_DIR="data/raw/models/bin"

TESSDATA_FILE="$TESSDATA_DIR/deu_latf.traineddata"
KRAKEN_MODEL="$KRAKEN_DIR/german_kurrent.mlmodel"
CALAMARI_VENV=".venv-calamari"
CALAMARI_LINK="$BIN_DIR/calamari-predict"
CALAMARI_LINK_TARGET="../../../../$CALAMARI_VENV/bin/calamari-predict"

TESSDATA_URL="https://github.com/tesseract-ocr/tessdata_best/raw/main/deu_latf.traineddata"
KRAKEN_MODEL_URL="https://zenodo.org/records/11673242/files/rec_bohemica.mlmodel?download=1"
CALAMARI_MODEL_URL="https://github.com/Calamari-OCR/calamari_models/releases/download/2.2/fraktur_historical.tar.gz"

TESSDATA_SHA256="429b8c33d37e1a4823a2bb082a644ff13e252f735b7945e08a518d22ddcc459e"
KRAKEN_MODEL_SHA256="c16da6b363e9046c7eb6da957bb7a7c9a295c74bf5e9defa8893ef7eb638a8a6"
CALAMARI_ARCHIVE_SHA256="49ac046b40fa3c97fdd973055caa2f2b2332010bd08f0bccb2aaa599c4730111"
# sha256 over the sorted per-file sha256 list of the installed model dir — covers the
# actual checkpoint weights, not just the JSON metadata.
CALAMARI_DIR_DIGEST="15b1db073bf1a44e1e9719e9ce4b81eb8e584c92a5064c65da7f4e6b3b13bc55"

TESSERACT_STATUS="MISSING"
TESSERACT_FIX="brew install tesseract && bash scripts/setup_engines.sh"
KRAKEN_STATUS="MISSING"
KRAKEN_FIX="uv sync --group engines && bash scripts/setup_engines.sh"
CALAMARI_STATUS="MISSING"
CALAMARI_FIX="bash scripts/setup_engines.sh"

failures=0

log() {
  printf '%s\n' "$*"
}

fatal() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

sha256() {
  if have sha256sum; then
    sha256sum "$1" | awk '{print $1}'
  elif have shasum; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    fatal "need sha256sum or shasum to verify model hashes"
  fi
}

verify_sha256() {
  local file="$1"
  local expected="$2"
  local actual

  [[ -f "$file" ]] || fatal "expected file missing after setup: $file"
  actual="$(sha256 "$file")"
  [[ "$actual" == "$expected" ]] || fatal "$file sha256 mismatch: expected $expected, got $actual"
}

download_if_missing() {
  local url="$1"
  local output="$2"

  if [[ -f "$output" ]]; then
    log "present: $output"
    return 0
  fi

  have curl || fatal "curl not found; install curl and retry"
  log "downloading: $output"
  curl -fL --retry 3 --retry-delay 2 -o "$output" "$url" || fatal "download failed: $url"
}

setup_tesseract() {
  mkdir -p "$TESSDATA_DIR"
  download_if_missing "$TESSDATA_URL" "$TESSDATA_FILE"
  verify_sha256 "$TESSDATA_FILE" "$TESSDATA_SHA256"

  if ! have tesseract; then
    log "missing: tesseract binary (install with: brew install tesseract)"
    failures=$((failures + 1))
    return 0
  fi

  if tesseract --list-langs --tessdata-dir "$TESSDATA_DIR" 2>/dev/null | awk 'NR > 1 {print}' | grep -qx 'deu_latf'; then
    TESSERACT_STATUS="OK"
    TESSERACT_FIX="-"
  else
    log "missing: tesseract cannot load deu_latf from $TESSDATA_DIR"
    failures=$((failures + 1))
  fi
}

setup_kraken() {
  mkdir -p "$KRAKEN_DIR"
  download_if_missing "$KRAKEN_MODEL_URL" "$KRAKEN_MODEL"
  verify_sha256 "$KRAKEN_MODEL" "$KRAKEN_MODEL_SHA256"

  if ! have uv; then
    log "missing: uv binary (install uv, then run: uv sync --group engines)"
    failures=$((failures + 1))
    return 0
  fi

  log "syncing uv dependency group: engines"
  if ! uv sync --group engines; then
    log "missing: uv sync --group engines failed"
    failures=$((failures + 1))
    return 0
  fi

  if uv run kraken --version >/dev/null 2>&1; then
    KRAKEN_STATUS="OK"
    KRAKEN_FIX="-"
  else
    log "missing: uv run kraken --version failed"
    failures=$((failures + 1))
  fi
}

calamari_dir_digest() {
  # Digest over every installed file (sorted), so the checkpoint WEIGHTS are pinned,
  # not just the JSON metadata next to them.
  local tool
  if have sha256sum; then tool="sha256sum"; else tool="shasum -a 256"; fi
  (cd "$CALAMARI_DIR" && find . -type f | LC_ALL=C sort | xargs $tool | $tool | awk '{print $1}')
}

verify_calamari_dir() {
  local actual
  actual="$(calamari_dir_digest)"
  [[ "$actual" == "$CALAMARI_DIR_DIGEST" ]] || fatal \
    "$CALAMARI_DIR content digest mismatch: expected $CALAMARI_DIR_DIGEST, got $actual (move the dir aside and rerun to reinstall)"
}

setup_calamari_model() {
  if [[ -e "$CALAMARI_DIR/0.ckpt" ]]; then
    log "present: $CALAMARI_DIR"
    verify_calamari_dir
    return 0
  fi

  have curl || fatal "curl not found; install curl and retry"
  have tar || fatal "tar not found; install tar and retry"

  local tmpdir
  tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/calamari-model.XXXXXX")" || fatal "failed to create temp dir"
  trap 'rm -rf "$tmpdir"; trap - RETURN' RETURN

  log "downloading: $CALAMARI_DIR"
  curl -fL --retry 3 --retry-delay 2 -o "$tmpdir/fraktur_historical.tar.gz" "$CALAMARI_MODEL_URL" || fatal "download failed: $CALAMARI_MODEL_URL"
  verify_sha256 "$tmpdir/fraktur_historical.tar.gz" "$CALAMARI_ARCHIVE_SHA256"
  tar -xzf "$tmpdir/fraktur_historical.tar.gz" -C "$tmpdir" || fatal "failed to extract Calamari model archive"
  [[ -d "$tmpdir/fraktur_historical" ]] || fatal "Calamari archive did not contain fraktur_historical/"

  mkdir -p "$(dirname "$CALAMARI_DIR")"
  if [[ -e "$CALAMARI_DIR" ]]; then
    fatal "$CALAMARI_DIR exists but is incomplete; move it aside and rerun"
  fi
  mv "$tmpdir/fraktur_historical" "$CALAMARI_DIR" || fatal "failed to install Calamari model"
  verify_calamari_dir
}

setup_calamari_venv() {
  if ! have uv; then
    log "missing: uv binary (install uv, then rerun setup)"
    failures=$((failures + 1))
    return 0
  fi

  if [[ ! -x "$CALAMARI_VENV/bin/python" ]]; then
    log "creating: $CALAMARI_VENV"
    if ! uv venv --python 3.11 "$CALAMARI_VENV"; then
      log "missing: failed to create $CALAMARI_VENV with Python 3.11"
      failures=$((failures + 1))
      return 0
    fi
  fi

  if ! calamari_version_ok "$CALAMARI_VENV/bin/calamari-predict"; then
    log "installing: calamari-ocr==2.3.1 into $CALAMARI_VENV"
    if ! uv pip install --python "$CALAMARI_VENV/bin/python" 'calamari-ocr==2.3.1'; then
      log "missing: failed to install calamari-ocr==2.3.1 into $CALAMARI_VENV"
      failures=$((failures + 1))
      return 0
    fi
  fi

  if ! calamari_version_ok "$CALAMARI_VENV/bin/calamari-predict"; then
    log "missing: $CALAMARI_VENV/bin/calamari-predict does not run"
    failures=$((failures + 1))
    return 0
  fi
}

setup_calamari_symlink() {
  mkdir -p "$BIN_DIR"
  if [[ -e "$CALAMARI_LINK" && ! -L "$CALAMARI_LINK" ]]; then
    fatal "$CALAMARI_LINK exists and is not a symlink; refusing to replace it"
  fi
  ln -sfn "$CALAMARI_LINK_TARGET" "$CALAMARI_LINK" || fatal "failed to update $CALAMARI_LINK"
}

calamari_version_ok() {
  local binary="$1"
  local output

  [[ -x "$binary" ]] || return 1
  output="$("$binary" --version 2>&1 || true)"
  [[ "$output" == *"calamari-predict v2.3.1"* ]]
}

setup_calamari() {
  setup_calamari_model
  setup_calamari_venv
  setup_calamari_symlink

  if calamari_version_ok "$CALAMARI_LINK"; then
    CALAMARI_STATUS="OK"
    CALAMARI_FIX="-"
  else
    log "missing: $CALAMARI_LINK does not resolve to a runnable calamari-predict"
    failures=$((failures + 1))
  fi
}

print_status_table() {
  printf '\n%-20s %-8s %s\n' "engine" "status" "fix"
  printf '%-20s %-8s %s\n' "------" "------" "---"
  printf '%-20s %-8s %s\n' "tesseract_fraktur" "$TESSERACT_STATUS" "$TESSERACT_FIX"
  printf '%-20s %-8s %s\n' "kraken_kurrent" "$KRAKEN_STATUS" "$KRAKEN_FIX"
  printf '%-20s %-8s %s\n' "calamari_fraktur" "$CALAMARI_STATUS" "$CALAMARI_FIX"
}

setup_tesseract
setup_kraken
setup_calamari
print_status_table

if (( failures > 0 )); then
  exit 1
fi
