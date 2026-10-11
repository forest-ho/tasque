# Android アプリのビルド

Android版はKivyで動作し、SQLiteデータは端末のアプリ専用領域に保存します。既存の `quest_app.db` はAPKに含めず、Androidで初回起動したときに新しいDBを作成します。Web版とAndroid版のデータは共有されません。

現在の設定では、アプリ名は「たすくえ」、最低対応バージョンは Android 9（API 28）、ビルド対象 API は 31、NDK は 25b です。ネットワークアクセスに `INTERNET` と `ACCESS_NETWORK_STATE` 権限を使用します。

## ビルド環境

LinuxまたはWSL2上のLinux環境を使用してください。Ubuntuでは、先にビルドツールとKivyのLinux依存ライブラリを用意します。

```bash
sudo apt update
sudo apt install -y build-essential git zip unzip openjdk-17-jdk python3-dev python3-pip autoconf libtool pkg-config zlib1g-dev libncurses-dev libffi-dev libssl-dev libltdl-dev libgl-dev libmtdev-dev libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
pip install -r requirements-android.txt
buildozer -v android debug
```

初回のビルドではAndroid SDK/NDKなどがダウンロードされます。生成されたAPKは `bin/` に出力されます。Android端末へUSBデバッグでインストールする場合は次を実行します。

```bash
buildozer android debug deploy run
```

Web版はこれまで通り `streamlit run app.py` で起動できます。

## Web版のデータ分離

Web版はブラウザーにランダムな識別Cookieを保存し、その値ごとに `web_data/` 内のSQLiteデータベースを使います。同じブラウザープロファイルではデータが継続し、別のブラウザーや端末からは別データになります。Cookieを削除すると新しいデータ領域が作られ、以前のデータには戻れません。ログイン機能や端末間のデータ引き継ぎはありません。この方式は認証ではなく、共有端末では同じブラウザープロファイルを使う人が同じデータを見られます。

従来の `quest_app.db` のデータはWeb版のユーザー領域へ引き継がれません。公開運用ではHTTPSを使用し、`web_data/` をGitへ登録せず、すべてのアプリインスタンスから利用できる永続ストレージに保存してください。ブラウザーのCookieを共有・コピーした場合は同じデータ領域を使うため、共有端末ではCookieを共有しないでください。
