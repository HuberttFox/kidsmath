# 部署

## 局域网分享（老师/家长）

```bash
mathgen serve --host 0.0.0.0 --port 8080
```
同一 Wi-Fi 下用 `http://<本机IP>:8080` 访问。

## 公网（简单方式）

任意有公网 IP 或内网穿透的服务器：

```bash
pip install mathgen
nohup mathgen serve --host 0.0.0.0 --port 8080 &
```
建议反向代理加 HTTPS（如 caddy：`caddy reverse-proxy --from 你的域名 --to localhost:8080`）。

## Docker

镜像已内置中文字体（Noto Sans SC 子集）与模板/静态文件，无需额外下载，开箱即用。

### 构建并启动（docker compose）

```bash
docker compose up -d --build
```

访问 `http://<服务器IP>:8080`。健康检查自动执行（`/healthz`），重启策略 `unless-stopped`。

### 只用 Dockerfile

```bash
docker build -t mathgen .
docker run -d --name mathgen -p 8080:8080 --restart unless-stopped mathgen
```

### 常用操作

```bash
docker compose logs -f mathgen   # 看日志
docker compose restart mathgen   # 重启
docker compose down              # 停止（容器删除，无数据落盘）
```

## 说明

- 无用户系统、无题库存储，纯出题工具；数据不落盘。
- 预览与下载共用 seed，保证题目一致。
- Docker 镜像运行非 root 用户（mathgen），多阶段构建（uv 锁版本，`--no-dev` 不带测试依赖）。
