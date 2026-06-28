#!/bin/sh
set -e

: "${PORT:=80}"
: "${API_BASE_URL:=http://localhost:5000}"
: "${CACHE_VERSION:=prod}"

# Render templates with env vars (no envsubst dependency on alpine).
# login.html MUST be here too — it reads ${API_BASE_URL} for the cross-origin
# login POST; left unsubstituted it posts to the frontend origin and 405s.
for f in index.html login.html sw.js; do
    sed -e "s|\${API_BASE_URL}|${API_BASE_URL}|g" \
        -e "s|\${CACHE_VERSION}|${CACHE_VERSION}|g" \
        "/usr/share/nginx/html/${f}.tpl" > "/usr/share/nginx/html/${f}"
done

# Write nginx site config with the provided $PORT
cat > /etc/nginx/conf.d/default.conf <<EOF
server {
    listen ${PORT};
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location = /sw.js {
        add_header Cache-Control "no-cache";
        try_files \$uri =404;
    }
}
EOF

# Remove the default :80 server that ships with the image (it conflicts when PORT != 80)
rm -f /etc/nginx/conf.d/default.conf.bak
