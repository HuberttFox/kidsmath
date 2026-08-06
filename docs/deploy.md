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

## 说明

- 无用户系统、无题库存储，纯出题工具；数据不落盘。
- 预览与下载共用 seed，保证题目一致。
