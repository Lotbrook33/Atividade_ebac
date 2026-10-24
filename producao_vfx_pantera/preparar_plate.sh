#!/usr/bin/env bash
# Gera o plate 1080x1920 a partir da foto original (1206x2622 com barras pretas).
# Área útil da foto: x 0–1205, y 237–2378 (já em 9:16); recorta 1 px para dentro para evitar
# a borda de compressão JPEG e escala para 1080x1920.
set -euo pipefail
FOTO="${1:?uso: preparar_plate.sh foto.jpg [saida.png]}"
SAIDA="${2:-plate_final_1080x1920.png}"
ffmpeg -v error -y -i "$FOTO" -vf "crop=1204:2140:1:238,scale=1080:1920:flags=lanczos,format=rgb24" "$SAIDA"
echo "$SAIDA"
