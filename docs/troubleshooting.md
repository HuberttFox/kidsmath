# 排障

常见问题按「现象 → 原因 → 解决」记录。部署相关（Docker、反向代理、备份）见 [deployment.md](deployment.md)，环境搭建见 [development.md](development.md)。

## PWA 更新不生效

**现象**：改了静态资源/页面，浏览器仍是旧 UI，刷新也看不到新版。

**原因**：Service Worker 缓存优先。`static/sw.js` 的 `activate` 阶段会删除旧版本缓存，但新版本部署后，用户**首次访问仍可能命中旧缓存页**（旧 SW 控制的页面直接走缓存）；新 SW 的 `install` 完成并 `skipWaiting()` 后才会接管。

**解决**：

- 确认已 bump `sw.js` 顶部的 `const CACHE = 'kidsmath-v<N>'` 版本号（改静态资源或缓存策略时必须 bump，否则新内容永远不落盘）。
- 用户侧：刷新一次，或等下一轮 `install` 后新版本自动接管（`clients.claim()` 生效）。
- 验证时在浏览器 DevTools → Application → Service Workers 里勾选 "Update on reload"。

## PDF 缺中文字形

**现象**：生成的中文 PDF 某些字变方块/空框，或提示字体缺失。

**原因**：`output/fonts.py` 的回退链为 **包内 Noto 子集 → 系统字体 → CID 兜底**：

1. `assets/font/NotoSansSC-Regular.ttf`（打包子集，字符集 = 应用题模板 + 常用 UI 字，由 `scripts/download_font.py` 生成）；
2. 系统字体（Noto CJK / 文泉驿 / 微软雅黑 / 宋体 / 苹方 / 华文黑体，按路径探测）；
3. `UnicodeCIDFont("STSong-Light")` 兜底。

打包子集若缺字且系统无 CJK 字体，则回退到 CID 字形（外观与 TTF 略有差异）；全部系统字体缺失时靠 CID 仍可输出，但个别冷僻字形可能缺。

**解决**：联网环境重跑 `uv run python scripts/download_font.py` 重新子集化（覆盖 topics 全部非 ASCII 字符，`tests/test_fonts.py` 有回归断言）；离线环境在宿主机安装任一系统 CJK 字体（如 Noto Sans CJK、文泉驿）。

## 浏览器音频自动播放策略

**现象**：番茄钟/计时到点不响铃，或后台标签页提示音延迟；切回前台才响。

**原因**：

- 浏览器自动播放策略：`AudioContext` 需在**用户首次点击**（开始按钮等手势）后才解除 suspended 状态。`audio.js` 的 `playChime()` 用 WebAudio 振荡器，未点击时 `ctx.resume()` 无效，静默降级。
- 后台标签页 JS 定时器被浏览器节流，`playChime` 触发时机可能推迟到回前台。

**解决**：

- 先点击页面上的「开始」再等提示音；这是浏览器策略，非代码 bug。
- 页面有兜底：到点时计时显示加 `body.time-up` 类，标题色闪烁（`timeflash` 动画），`member_timer.html` 还会在授权后发系统 Notification。

## Docker /data 卷权限

**现象**：`docker compose run` 备份/恢复时写宿主机目录失败（Permission denied），或卷内文件属主异常。

**原因**：镜像以非 root 的 `mathgen` 用户运行，无法保证可写宿主机当前目录；宿主机目录通常归宿主用户所有。

**解决**：归档容器用 `--user root` 运行，把备份写到挂载的宿主目录：

```bash
docker compose stop mathgen
docker compose run --rm --no-deps --user root -v "$PWD:/backup" --entrypoint sh mathgen \
  -c 'tar czf /backup/mathgen-data-$(date +%F).tar.gz -C /data .'
docker compose start mathgen
```

生成的 tar 在宿主机上归 root 所有（属预期备份产物）。完整备份/恢复命令见 [deployment.md](deployment.md)。

## KIDSMATH_DB 自定义路径

**现象**：设置 `KIDSMATH_DB` 指向不存在的深层路径，启动报找不到数据库。

**原因**：`db.py` 的 `_resolve_path()` 会自动 `Path(p).parent.mkdir(parents=True, exist_ok=True)`——**父目录会自动创建**，不会因目录不存在而失败。

**解决**：若仍报错，检查路径本身是否不可写（权限、只读挂载、drvfs 网络盘拒绝创建）。权限不足时 `sqlite3.connect` 抛 `PermissionError`/`OperationalError`，按错误信息修权限或换路径。

## drvfs/网络盘 SQLite 挂起

**现象**：数据库在 WSL drvfs（`/mnt/c/...`）或网络盘上时，读写偶发长时间挂起。

**原因**：`db.py` 明确**不用 WAL 模式**——WAL 的共享内存（`-wal`/`-shm` 文件）在 drvfs/网络盘上会挂起（见 `get_conn()` 注释）。代码走默认 journal 模式并设 `PRAGMA busy_timeout=5000`。

**解决**：把数据库放本地盘（`data/kidsmath.db` 默认路径）；不要手工 `PRAGMA journal_mode=WAL`。若团队共享库，用 Docker 卷（本地）或 SQLite 备份导出而非直接共享文件。

## 局域网 PWA 不显示安装入口

**现象**：`http://<IP>:8080` 访问时，浏览器地址栏没有「安装应用」入口。

**原因**：浏览器要求 **https 或 localhost** 才提供 PWA 安装入口；局域网裸 HTTP 属浏览器限制。

**解决**：功能不受影响——页面仍可正常使用，仅缺少安装按钮。要安装到桌面，用 localhost 访问，或反代加 HTTPS（见 [deployment.md](deployment.md)）。

## 常见 pytest 问题

**现象 1**：跑 `tests/test_ui_playwright.py` 全部跳过（`SKIPPED`）。

**原因**：未安装 playwright 包或未装浏览器，`pytest.importorskip("playwright.sync_api")` 优雅跳过。

**解决**：`uv run playwright install chromium` 后重跑（首次需下载）。

**现象 2**：测试把开发/生产数据库写坏，或测试间数据互相污染。

**原因**：未遵守测试隔离——`tests/conftest.py` 的 autouse fixture 为每个测试独立临时 SQLite（`db.configure(tmp_path / "test.db")`），并 `db.configure(None)` 重置单例。直接连默认 `data/kidsmath.db` 的测试会污染真实数据。

**解决**：测试里通过 `db.configure()` 或依赖 fixture，勿触碰默认 `data/kidsmath.db`；本机跑过真实服务后要清库，删该文件（服务停止时）再启动即可。

## 相关文档

- [deployment.md](deployment.md) — 部署、反向代理、备份/恢复
- [development.md](development.md) — 环境与测试
