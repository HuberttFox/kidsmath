# 安卓 App（TWA 联网版）

用 Google 官方 TWA（Trusted Web Activity）方案把 kidsmath 网页包装为安卓 App：WebView 加载线上 HTTPS 服务，家长从桌面图标直接打开，**产品页在 App 内隐藏**（`/?app=1` 隐藏导航产品入口）。

## 前置条件

1. kidsmath 服务已部署到 **HTTPS 域名**（TWA 强制 https；见 docs/deploy.md）
2. Node 18+、JDK 17、Android SDK（`ANDROID_HOME`）
3. `npx @bubblewrap/cli`（首次运行自动安装）

## 构建 APK

```bash
# 1) 修改 android/twa-manifest.json：host / iconUrl 换成你的域名
# 2) 生成签名 keystore（只需一次）
keytool -genkey -v -keystore android/android.keystore -alias kidsmath \
  -keyalg RSA -keysize 2048 -validity 10000
# 3) 构建
bash scripts/build_android.sh
```

输出 `app-release.apk` 于 Bubblewrap 生成的项目 `app/build/outputs/`。

## 发布 APK（GitHub Releases）

```bash
gh release create v1.0.0 app-release.apk --title "kidsmath v1.0.0" --notes "安卓安装包"
```

产品页"安装为应用"区可加下载链接（占位）。

## Google Play 二期清单

- 开发者账号：https://play.google.com/console （一次性 $25）
- 隐私政策页面（域名下托管）
- 上传 **AAB**（`bubblewrap build --aab` 或 Android Studio 生成）替代 APK
- 应用信息：图标（512 PNG 已有）、截图、内容分级问卷
- 审核周期 1-7 天

## 其他

- 图标：`scripts/generate_icons.py`（Pillow）生成 192/512 + maskable PNG，manifest 已引用
- PWA 与 TWA 共用同一 manifest；桌面浏览器"安装应用"仍可用
- App 内产品页隐藏：`?app=1` 查询参数（base.html 条件渲染产品 nav）
