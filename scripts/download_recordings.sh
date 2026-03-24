#!/bin/bash
# ============================================================
# Download recordings for ENF AutoResearch
# ============================================================
#
# Source: Slovenian anti-corruption wiretapping recordings
# Published at: https://www.anti-corruption2026.com/
# Hosted on Google Drive for reproducibility.
#
# Requirements: gdown (pip install gdown)
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/../data/recordings"
mkdir -p "$DATA_DIR"

# Google Drive folder
DRIVE_FOLDER_URL="https://drive.google.com/drive/folders/1lqLFe7YW5FE60DKVG5ZGy3jPzXHy0EfV"
DRIVE_FOLDER_ID="1lqLFe7YW5FE60DKVG5ZGy3jPzXHy0EfV"

echo "============================================================"
echo "ENF AutoResearch — Download Recordings"
echo "============================================================"
echo ""
echo "Source: ${DRIVE_FOLDER_URL}"
echo "Target: ${DATA_DIR}"
echo ""

# Check for gdown
if ! command -v gdown &> /dev/null; then
    echo "Installing gdown..."
    pip install gdown
fi

# Method 1: Download entire folder (preferred)
echo "Downloading all recordings from Google Drive folder..."
gdown --folder "$DRIVE_FOLDER_ID" -O "$DATA_DIR" --remaining-ok 2>/dev/null

# Method 2: If folder download fails, try individual files
if [ $? -ne 0 ] || [ "$(ls -1 "$DATA_DIR"/*.wav 2>/dev/null | wc -l)" -lt 14 ]; then
    echo ""
    echo "Folder download incomplete. Trying individual files..."
    echo ""

    declare -A FILES=(
        ["DP01_paravan_geni.wav"]="1Z8AdhwI0K97syZEhi7ctiuEtMeLE6rum"
        ["JO01_oberstar_dars_influence.wav"]="1wRDhom6RsRX11M7OBOGVZAam-lAXiuUS"
        ["JO02_oberstar_dars_contracts.wav"]="1lQfun8-aXMqrfiRffHzbrG48tqvNeU19"
        ["JO03_oberstar_deep_state.wav"]="1EsH5HvnM6VrA-tblBCOdsLywL0mUmHRF"
        ["NZK01_zidar_klemencic_p1.wav"]="15oaqILlICB2lsGTKhUQe0OSAM9SldqRU"
        ["NZK02_zidar_klemencic_p2.wav"]="11icn7ImyUxBv84eEnoE-9LLOR-OXplD3"
        ["RH01_hodej_sdh.wav"]="1ecPUxhKGL07RspB5-pAv-29lq3enAY7Q"
        ["RH02_hodej_coercion.wav"]="1tKnvhH2i9EYZC0-q_okFQ7coLl2wQa35"
        ["SP01_svarc_pipan_lobbying.wav"]="149QhkxzeDeWQ2xAjbsaU7NGrVTSWoh6G"
        ["SP02_svarc_pipan_geni.wav"]="15Dkj3rYcP7M84eHcdc34gKrePSfvC1G2"
        ["SP03_svarc_pipan_deepstate.wav"]="10LPTEzuND4znrqe1JGGISKPDyQLEXbjK"
        ["TV01_vukmanovic_geni.wav"]="1XIl5gR6DJtngx3oNgzUpkUwNws-PhhVR"
        ["VV01_vukovic_vonta.wav"]="1yLxqKBFWt3dz62R4eO81Lj2ixN6H8SDY"
        ["VV02_vukovic_helbl.wav"]="1TkWr8JhE4QdXkKSlKctDwMOGzbfe-oud"
    )

    for fname in "${!FILES[@]}"; do
        fid="${FILES[$fname]}"
        outpath="$DATA_DIR/$fname"
        if [ -f "$outpath" ]; then
            echo "  SKIP (exists): $fname"
        else
            echo "  Downloading: $fname..."
            gdown "https://drive.google.com/uc?id=$fid" -O "$outpath"
        fi
    done
fi

echo ""
echo "============================================================"
echo "Downloaded recordings:"
echo "============================================================"
count=0
for f in "$DATA_DIR"/*.wav; do
    if [ -f "$f" ]; then
        size=$(du -h "$f" | cut -f1)
        echo "  $(basename "$f") ($size)"
        count=$((count + 1))
    fi
done

echo ""
echo "Total: $count recordings"
du -sh "$DATA_DIR" 2>/dev/null

echo ""
echo "Next: run 'uv run python prepare.py' to validate data"
