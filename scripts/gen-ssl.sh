#!/bin/sh
# Самоподписанный сертификат. Для админки по IP лучше пользоваться HTTP :80.
# Телефонам нужен HTTPS с именем из PUBLIC_BASE_URL.
set -e
DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../nginx/ssl" && pwd)"
mkdir -p "$DIR"
HOST="${1:-ntdc.example.com}"
if [ -f "$DIR/ntdc.crt" ] && [ -f "$DIR/ntdc.key" ]; then
  echo "Certificates already exist in $DIR"
  exit 0
fi
SAN="DNS:${HOST},DNS:localhost,IP:127.0.0.1"
shift || true
for extra in "$@"; do
  case "$extra" in
    *[a-zA-Z]*) SAN="${SAN},DNS:${extra}" ;;
    *) SAN="${SAN},IP:${extra}" ;;
  esac
done
openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout "$DIR/ntdc.key" \
  -out "$DIR/ntdc.crt" \
  -subj "/CN=$HOST" \
  -addext "subjectAltName=${SAN}"
chmod 600 "$DIR/ntdc.key"
echo "Wrote $DIR/ntdc.crt and $DIR/ntdc.key for $HOST ($SAN)"
