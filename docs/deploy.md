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
# 数据卷必须手动挂载：/data/kidsmath.db（含用户/历史/保存配置）
docker run -d --name mathgen -p 8080:8080 --restart unless-stopped \
  -v mathgen-data:/data -e KIDSMATH_DB=/data/kidsmath.db mathgen
```

### 常用操作

```bash
docker compose logs -f mathgen   # 看日志
docker compose restart mathgen   # 重启
docker compose down              # 停止（容器删除，数据保留在 mathgen-data 卷）
```

## PWA 安装

- 浏览器「安装应用」仅在 **https** 或 **localhost** 下可用；局域网用 `http://<IP>:8080` 访问时不显示安装入口，属浏览器限制，功能不受影响。
- nginx/caddy 反代时确认静态资源响应头：
  - `Content-Type: application/manifest+json` 用于 `/static/manifest.webmanifest`（缺失时部分浏览器仍可解析，但建议配全）；
  - `Cache-Control: no-cache` 或短 TTL 用于 `/static/sw.js`，避免旧 SW 长期驻留；
  - 其余静态资源（HTML/CSS/JS）建议 `Cache-Control: max-age=31536000, immutable` + SW 内部版本化刷新。
- Service worker 离线缓存 app shell 与 `/product`；`/user/*`、`/login`、`/api/*`、`/generate`、`/download.*` **一律走网络**（认证与会话状态必须实时）。

## 说明

- 用户系统：账号密码登录（pbkdf2 哈希）、会话 cookie、历史与保存配置存 SQLite（`KIDSMATH_DB` 环境变量指定路径，默认 `data/kidsmath.db`）。
- 局域网/裸 HTTP 部署时自动禁用 Secure cookie（HTTPS 下启用）。
- 预览与下载共用 seed，保证题目一致。
- Docker 镜像运行非 root 用户（mathgen），多阶段构建（uv 锁版本，`--no-dev` 不带测试依赖）。
