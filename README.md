# Roast Log

個人用のコーヒー豆焙煎記録Webアプリです。SQLite、画像アップロード、CaddyによるHTTPSリバースプロキシをDocker Composeでまとめて起動します。

## 起動

```powershell
Copy-Item .env.example .env
# .env の APP_DOMAIN と ADMIN_PASSWORD を編集
docker compose up -d --build
```

`APP_DOMAIN` のDNS A/AAAAレコードは、起動先VMへ向けてください。Caddyが80/443を受け、証明書を自動取得します。

ローカルDocker Desktopで確認する場合は、`https://localhost` または `https://127.0.0.1` を開きます。ローカル証明書の警告が出る場合があります。

## 構成

- `app`: Python標準ライブラリのみで動くWebアプリ。外部には直接公開しません。
- `caddy`: HTTPS終端と `app:3000` へのリバースプロキシ。
- `roast_data`: SQLite DB。
- `roast_uploads`: 焙煎写真、ロースター写真。
- `caddy_data`: Caddy証明書データ。

## 管理

設定画面、マスタ編集、ロースター管理、バックアップ復元は管理パスワードで保護されます。

初期パスワードは `.env` の `ADMIN_PASSWORD` です。初回DB作成後にアプリ内で変更できます。

## ローカル確認

Dockerなしで確認する場合:

```powershell
python app/server.py
```

PythonがPATHにない環境では、利用可能なPython実行ファイルで `app/server.py` を起動してください。既定URLは `http://127.0.0.1:3000` です。
