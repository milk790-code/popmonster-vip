# agentmemory 後端容器（部署到 Railway）
# 把本機 npm 套件 @agentmemory/agentmemory 包成可上線的 REST 服務。
#
# 重要事實（已在 v0.9.22 驗證）：
#  - REST 在 :3111；bundled iii-config.yaml 預設 host=127.0.0.1（僅 loopback）。
#    要對外提供，下面用 sed 把 host 改成 0.0.0.0。
#  - 記憶資料落在工作目錄下的 ./data/（state_store.db + stream_store）。
#    => WORKDIR=/app，volume 掛在 /app/data 才能持久化。
#  - REST 預設「無驗證」（原設計假設 localhost）。對外暴露務必加保護，
#    見同目錄 README.md 的「安全」段（Railway 私網 / proxy + token）。
FROM node:22-slim

ENV AGENTMEMORY_HOME=/app/.agentmemory \
    NODE_ENV=production

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @agentmemory/agentmemory@0.9.22

# 讓 REST 監聽所有介面（預設只綁 127.0.0.1，容器外連不到）
RUN CFG="$(npm root -g)/@agentmemory/agentmemory/dist/iii-config.yaml" \
    && sed -i 's/host: 127.0.0.1/host: 0.0.0.0/g' "$CFG"

# 記憶資料目錄（Railway volume 掛載點）
RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 3111

# Railway 會注入 $PORT；agentmemory 用 --port 覆寫 REST 埠。
# 預設指令即啟動 worker + iii-engine。
CMD ["sh", "-c", "agentmemory --port ${PORT:-3111}"]
