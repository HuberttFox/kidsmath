#!/usr/bin/env bash
# 构建安卓 APK（TWA/Bubblewrap，联网版）。
# 前置：Node 18+、JDK 17、Android SDK（ANDROID_HOME）、@bubblewrap/cli。
# 用法：
#   1) 编辑 android/twa-manifest.json：host/iconUrl 改为你的域名（必须 HTTPS）
#   2) 生成签名：keytool -genkey -v -keystore android/android.keystore -alias kidsmath -keyalg RSA -keysize 2048 -validity 10000
#   3) bash scripts/build_android.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v npx >/dev/null; then echo "需要 Node/npx"; exit 1; fi
if [ -z "${ANDROID_HOME:-}" ] && [ -z "${ANDROID_SDK_ROOT:-}" ]; then
  echo "需要 Android SDK（设置 ANDROID_HOME）"; exit 1
fi

npx @bubblewrap/cli init --manifest=android/twa-manifest.json
npx @bubblewrap/cli build
echo "APK 输出：$(find app/build/outputs -name '*.apk' | head -1)"
