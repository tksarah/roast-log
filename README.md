# Roast Log

コーヒー豆の焙煎記録アプリです。公開トップのLPと、Basic認証付きの管理画面を同居させています。SQLite、画像アップロード、CaddyによるHTTPSリバースプロキシをDocker Composeでまとめて起動します。

## 起動

```powershell
Copy-Item .env.example .env
# .env の APP_DOMAIN / ADMIN_USER / ADMIN_PASSWORD_HASH を編集
docker compose up -d --build
```

`ADMIN_PASSWORD_HASH` には Caddy のハッシュを設定してください。生成例:

```powershell
docker run --rm caddy:2-alpine caddy hash-password --plaintext "strong-password"
```

`APP_DOMAIN` のDNS A/AAAAレコードは、起動先VMへ向けてください。Caddyが80/443を受け、証明書を自動取得します。

ローカルDocker Desktopで確認する場合は、`https://localhost` または `https://127.0.0.1` を開きます。ローカル証明書の警告が出る場合があります。

公開ページは `/`、管理画面は `/admin/` です。`/admin/` と管理APIは Basic認証が必要です。

## 構成

- `app`: Python標準ライブラリのみで動くWebアプリ。外部には直接公開しません。
- `caddy`: HTTPS終端、`app:3000` へのリバースプロキシ、`/admin/` と管理APIへの Basic認証。
- `roast_data`: SQLite DB。
- `roast_uploads`: 焙煎写真、ロースター写真。
- `caddy_data`: Caddy証明書データ。

## 管理

管理画面は `/admin/` 配下にあり、Caddy の Basic認証で保護します。

- `/`: 公開LP。公開フラグを付けた焙煎記録だけを表示します。
- `/admin/`: 焙煎記録の管理SPA。Dashboard、Records、New Roast、Settings、Backup を含みます。
- 公開LPに載せる文面は、管理画面の焙煎記録フォームから `公開LPに掲載する` と `公開用メモ` を設定します。

## ローカル確認

Dockerなしで確認する場合:

```powershell
python app/server.py
```

PythonがPATHにない環境では、利用可能なPython実行ファイルで `app/server.py` を起動してください。既定URLは `http://127.0.0.1:3000` です。

このモードでは Caddy を経由しないため Basic認証はかかりません。認証を含めて確認する場合は Docker Compose を使ってください。
