#!/bin/sh
set -e

: "${SSL_DOMAIN:?define SSL_DOMAIN}"
: "${SSL_IP:?define SSL_IP}"
: "${SSL_ORGANIZATION:=MyOrg}"
: "${SSL_COUNTRY:=AR}"

CERT_DIR="/etc/letsencrypt/live/$SSL_DOMAIN"
mkdir -p "$CERT_DIR"

if [ ! -f "$CERT_DIR/fullchain.pem" ] || [ ! -f "$CERT_DIR/privkey.pem" ]; then
  echo "🔐 Generando certificado autofirmado para $SSL_DOMAIN..."
  openssl req -x509 -nodes -days 3650 -newkey rsa:4096 \
    -keyout "$CERT_DIR/privkey.pem" \
    -out "$CERT_DIR/fullchain.pem" \
    -subj "/CN=$SSL_DOMAIN/O=$SSL_ORGANIZATION/C=$SSL_COUNTRY" \
    -addext "subjectAltName=DNS:$SSL_DOMAIN,IP:$SSL_IP"
  chmod 600 "$CERT_DIR/privkey.pem" "$CERT_DIR/fullchain.pem"
else
  echo "✅ Certificado ya existe"
fi

echo "⚙️  Renderizando configuración Nginx desde template..."
envsubst '${SSL_DOMAIN} ${SSL_IP} ${SSL_ORGANIZATION} ${SSL_COUNTRY} ${NGINX_PORT_HTTP} ${NGINX_PORT_HTTPS} ${WEB_UPSTREAM}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

echo "🚀 Iniciando Nginx..."
exec nginx -g "daemon off;"
