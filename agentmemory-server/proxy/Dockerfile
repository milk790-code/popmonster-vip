# agentmemory auth proxy（Caddy + Bearer token）
# Build/run 為 Railway 一個獨立 service（與 agentmemory service 同專案、Private Network）。
FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile

# Railway 注入 $PORT；Caddy 讀 {$PORT:8080}
EXPOSE 8080

CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
