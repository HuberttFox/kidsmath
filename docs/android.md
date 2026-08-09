# 安卓 App（TWA 联网版）

用 Google 官方 TWA（Trusted Web Activity）方案把 kidsmath 网页包装为安卓 App：WebView 加载线上 HTTPS 服务，家长从桌面图标直接打开。

PWA 与 TWA 使用两份独立配置：`src/mathgen/static/manifest.webmanifest` 是浏览器安装 PWA 的 manifest；`android/twa-manifest.json` 是 Bubblewrap 构建 TWA 的配置。TWA 的 `startUrl` 为 `/?app=1`，PWA 的 `start_url` 保持 `/`。

## 前置条件

1. kidsmath 服务已部署到 **HTTPS 域名**（TWA 强制 https；见 docs/deployment.md）
2. Node 18+、JDK 17、Android SDK（`ANDROID_HOME`）
3. `npx @bubblewrap/cli`（首次运行自动安装）

## 构建 APK

```bash
# 1) 修改 android/twa-manifest.json，见下方配置说明
# 2) 生成签名 keystore（只需一次）
keytool -genkey -v -keystore android/android.keystore -alias kidsmath \
  -keyalg RSA -keysize 2048 -validity 10000
# 3) 构建
bash scripts/build_android.sh
```

输出 `app-release.apk` 于 Bubblewrap 生成的项目 `app/build/outputs/`。

## TWA 配置

编辑 `android/twa-manifest.json` 时：

- `host`：已部署 HTTPS 服务的域名，不含协议和路径。
- `iconUrl`、`maskableIconUrl`：该 HTTPS 域名上的应用图标 URL；当前均指向 512px maskable PNG。
- `startUrl`：保持 `/?app=1`，使 TWA 从应用模式入口启动。
- `signingKey.path`、`signingKey.alias`：分别对应 `android/` 目录下的 keystore 文件和创建 keystore 时使用的别名；妥善备份该密钥，后续更新必须使用同一密钥。

## 发布 APK（GitHub Releases）

```bash
gh release create v1.0.0 app-release.apk --title "kidsmath v1.0.0" --notes "安卓安装包"
```

产品页的「安装为应用」链接已直接指向项目的 GitHub Releases 页面；上传 APK 后即可从该链接下载。

## Google Play 二期清单

- 开发者账号：https://play.google.com/console （一次性 $25）
- 隐私政策页面（域名下托管）
- 上传 **AAB**（`bubblewrap build --aab` 或 Android Studio 生成）替代 APK
- 应用信息：图标（512 PNG 已有）、截图、内容分级问卷
- 审核周期 1-7 天

## 其他

- 图标：`scripts/generate_icons.py`（Pillow）生成 192/512 + maskable PNG，manifest 已引用
- PWA manifest 与 TWA 配置分别维护；桌面浏览器的「安装应用」继续使用 PWA manifest。
- App 模式：`?app=1` 仅将站点 logo 的链接从 `/product` 改为 `/`；顶部产品页导航仍保留且可访问。
