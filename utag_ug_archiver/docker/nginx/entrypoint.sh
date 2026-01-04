#!/bin/sh
set -e

: "${NGINX_SERVER_NAME:=localhost}"
: "${WEB_SERVICE_HOST:=web}"
: "${WEB_SERVICE_PORT:=8000}"

CERT_DIR="/etc/letsencrypt/live/${NGINX_SERVER_NAME}"
CERT_FILE="${CERT_DIR}/fullchain.pem"
KEY_FILE="${CERT_DIR}/privkey.pem"
OPTIONS_FILE="/etc/letsencrypt/options-ssl-nginx.conf"

mkdir -p "${CERT_DIR}"
mkdir -p /var/www/certbot

if [ ! -f "${CERT_FILE}" ] || [ ! -f "${KEY_FILE}" ]; then
    echo "[nginx-proxy] Generating fallback self-signed certificate for ${NGINX_SERVER_NAME}"
    openssl req -x509 -nodes -newkey rsa:2048 -days 10 \
        -keyout "${KEY_FILE}" \
        -out "${CERT_FILE}" \
        -subj "/CN=${NGINX_SERVER_NAME}" >/dev/null 2>&1
fi

if [ ! -f "${OPTIONS_FILE}" ]; then
    cat <<'EOF' > "${OPTIONS_FILE}"
ssl_session_cache shared:le_nginx_SSL:10m;
ssl_session_timeout 1d;
ssl_session_tickets off;

ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers off;

ssl_ciphers ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
EOF
fi

envsubst '${NGINX_SERVER_NAME} ${WEB_SERVICE_HOST} ${WEB_SERVICE_PORT}' \
    < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

exec "$@"
