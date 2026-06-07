# AGENTS.md

## プロジェクト概要

Roast Log は、コーヒー豆の焙煎記録を管理し、公開LPに一部の記録を表示するWebアプリです。管理画面では焙煎記録、写真、ロースター、選択肢、味覚軸、バックアップを扱います。公開ページでは `is_public=1` の焙煎記録だけを表示します。

このリポジトリは、小さく自己完結した構成を重視しています。Python標準ライブラリ、SQLite、Vanilla HTML/CSS/JavaScript、Docker Compose、Caddyで構成され、追加依存は原則として増やしません。

## エージェント一覧

| エージェント | 主な役割 | 主な入出力 |
| --- | --- | --- |
| Product Steward | プロダクト目的、画面導線、公開/管理の境界を保つ | 入力: ユーザー要望、現行UI。出力: 仕様、受け入れ条件、優先度 |
| Backend/API Agent | `app/server.py` のAPI、DB、アップロード、バックアップを保守 | 入力: API仕様、DB変更要件。出力: Python実装、マイグレーション、APIレスポンス |
| Admin Frontend Agent | `static/admin.html`、`static/app.js`、`static/styles.css` の管理SPAを保守 | 入力: 管理業務フロー、APIレスポンス。出力: 管理画面UI、フォーム、状態管理 |
| Public LP Agent | `static/index.html`、`static/public.js`、`static/landing.css`、`assets/` の公開LPを保守 | 入力: ブランド/LP要件、公開API。出力: 公開画面、レスポンシブUI、画像利用 |
| Data/Backup Agent | SQLiteスキーマ、シード、バックアップ/復元の整合性を守る | 入力: データ要件、既存DB。出力: 安全なスキーマ変更、復元検証 |
| QA/Release Agent | ローカル起動、Docker起動、API/UI/バックアップの検証を行う | 入力: 変更差分、テスト観点。出力: 検証結果、再現手順、残リスク |
| Ops/Security Agent | Caddy、Basic認証、環境変数、公開範囲を管理 | 入力: デプロイ要件、`.env`。出力: Caddy/Docker設定、運用注意点 |

## 各エージェントの役割

- Product Steward は、実装に入る前に「公開LPに出すもの」「管理画面だけで扱うもの」「データを壊してはいけないもの」を明確にします。
- Backend/API Agent は、Python標準ライブラリの範囲でAPI、DB、ファイル保存、バックアップを実装します。
- Admin Frontend Agent は、管理者が焙煎記録を迷わず作成・編集・公開設定できる状態を保ちます。
- Public LP Agent は、公開された焙煎記録だけを、ブランドの雰囲気とレスポンシブ品質を保って表示します。
- Data/Backup Agent は、SQLite、uploads、ZIPバックアップの互換性と復元安全性を守ります。
- QA/Release Agent は、変更後に起動、主要画面、API、データ操作、レスポンシブ表示を確認します。
- Ops/Security Agent は、Caddy、Docker、Basic認証、環境変数、公開パスの安全性を確認します。

## 技術スタック

- Backend: Python 3.12、標準ライブラリのみ
  - `http.server.ThreadingHTTPServer`
  - `sqlite3`
  - `cgi.FieldStorage` による multipart upload
  - `zipfile` によるバックアップ/復元
- Frontend: Vanilla HTML/CSS/JavaScript
  - 公開LP: `static/index.html`、`static/public.js`、`static/landing.css`
  - 管理SPA: `static/admin.html`、`static/app.js`、`static/styles.css`
- Database: SQLite
- Runtime/Deploy: Docker Compose
- Reverse Proxy/Auth: Caddy 2
- Assets: PNG画像を `assets/` に配置

## ディレクトリ構造

```text
.
├── app/
│   └── server.py          # HTTPサーバー、API、DB、アップロード、バックアップ
├── assets/
│   ├── favicon.png
│   ├── hero.png           # 公開LPヒーロー画像
│   ├── icon.png
│   ├── roast-level.png
│   └── sample-lp.png
├── static/
│   ├── admin.html         # 管理SPAのHTML
│   ├── app.js             # 管理SPAの状態管理/API/UI
│   ├── index.html         # 公開LPのHTML
│   ├── landing.css        # 公開LPのCSS
│   ├── public.js          # 公開LPのデータ取得/描画
│   └── styles.css         # 管理SPAのCSS
├── Caddyfile              # HTTPS、Basic認証、reverse_proxy
├── Dockerfile
├── docker-compose.yml
├── README.md
└── AGENTS.md
```

実行時には `data/` と `uploads/` が作成されます。これらは永続データで、Git管理対象にしません。

## 入出力の形式

### Backend/API

- JSON APIは `Content-Type: application/json; charset=utf-8` を返します。
- エラーは `{ "error": "message" }` の形式で返します。
- アップロードAPIは `multipart/form-data` を受け取り、保存後に公開パスを返します。
- 主なAPI:
  - `GET /api/public/journal`: 公開LP用。公開済み焙煎記録と公開統計を返す。
  - `GET /api/bootstrap`: 管理画面初期データ。選択肢、ロースター、味覚軸、統計、今日の日付を返す。
  - `GET /api/records`: 管理画面一覧。検索、絞り込み、ソートを受ける。
  - `GET/PUT/DELETE /api/records/{id}`: 焙煎記録の取得、更新、削除。
  - `POST /api/records`: 焙煎記録の作成。
  - `POST /api/records/{id}/duplicate`: 記録複製。
  - `POST /api/records/{id}/photos`: 焙煎写真追加。
  - `POST/PUT /api/roasters`, `/api/options`, `/api/flavor-axes`: 管理マスタ更新。
  - `GET /api/backup/export`: DBとuploadsをZIP出力。
  - `POST /api/backup/import`: ZIPからDBとuploadsを復元。

### Frontend

- 管理画面は `state` オブジェクトを中心に、API結果をDOMへ描画します。
- 公開LPは `/api/public/journal` を取得し、データがない場合は `fallbackRecords` を表示します。
- HTML生成時は `escapeHtml` / `escapeAttr` を使い、ユーザー入力を直接HTMLへ差し込まないでください。

## 守るべき制約

- Pythonバックエンドは標準ライブラリのみを基本とします。外部依存を追加する場合は、必要性、Dockerfile、運用影響を明記してください。
- 管理APIと `/admin/` はCaddyのBasic認証で守ります。アプリ単体起動時は認証がかからない前提です。
- 公開LPには `is_public=1` の記録だけを出してください。
- `.env`、`data/`、`uploads/`、SQLite DB、秘密情報はGitに追加しないでください。
- DB変更は `init_db()` と `migrate_schema()` の整合性を保ってください。既存データを壊す破壊的変更は避けます。
- バックアップ復元は実データを置き換えるため、UIでは確認を挟み、コードではZIPパス検証を維持してください。
- アップロードファイルは画像拡張子のみを許可し、保存先は `uploads/records` と `uploads/roasters` に限定します。
- 既存の未コミット変更を勝手に戻さないでください。
- 公開LPのビジュアル変更では、`assets/hero.png` や既存画像を活かし、モバイルで文字やボタンが重ならないように確認してください。

## 使用するツール

- コード探索: `rg`, `rg --files`
- 編集: `apply_patch`
- ローカル起動:
  - Dockerあり: `docker compose up -d --build`
  - Dockerなし: `python app/server.py`
  - PythonがPATHにない場合は、利用可能なPython実行ファイルで `app/server.py` を起動する
- API確認: `curl`
- UI確認: ブラウザ、または利用可能ならPlaywright/Chrome headless
- Docker/Caddy確認: `docker compose logs`, `docker compose ps`
- Git確認: `git status --short`, `git diff`

## 他エージェントとの連携方法

- Product Steward が目的、公開範囲、受け入れ条件を整理します。
- Backend/API Agent がAPIやDBの変更点を先に明確にし、入出力形式をAdmin Frontend AgentとPublic LP Agentへ共有します。
- Admin Frontend Agent と Public LP Agent は、既存APIを優先して使います。API変更が必要な場合はBackend/API Agentへ戻します。
- Data/Backup Agent は、スキーマ変更、アップロード保存、バックアップ復元に関わる変更をレビューします。
- Ops/Security Agent は、Caddyの認証対象パスとDocker環境変数の変更を確認します。
- QA/Release Agent は、最後に公開LP、管理SPA、API、バックアップ、Docker起動の観点で検証します。
- 複数エージェントが同時に作業する場合は、担当ファイルを分け、同じファイルを編集する前に差分を確認してください。

## コーディング規約

### Python

- `app/server.py` は単一ファイル構成を維持します。大きな責務分離が必要になるまで、局所的な関数追加で対応してください。
- SQLはパラメータバインドを使い、ユーザー入力をSQL文字列に直接埋め込まないでください。
- レスポンスは `self.json()` を使い、HTTPエラーは `HttpError` を使って扱います。
- 数値入力は `to_number()` のように空値を `None` に正規化します。
- ファイルパス処理は `Path` を使い、バックアップ展開では `backup_member_path()` の検証を維持します。

### JavaScript

- Vanilla JSで実装し、ビルド工程を追加しないでください。
- 共有状態は既存の `state` オブジェクトに寄せます。
- API呼び出しは管理画面では `api()`、公開LPでは `fetchPublicJournal()` の既存方針に合わせます。
- DOMへ文字列を出す場合は `escapeHtml()` / `escapeAttr()` を使います。
- 既存の関数名、ビューID、フォームname属性、APIフィールド名を不用意に変えないでください。

### CSS/HTML

- 公開LPは `landing.css`、管理SPAは `styles.css` に分けます。
- 既存のCSS変数、カード半径、紙/コーヒー系の配色に合わせます。
- レスポンシブでは `@media (max-width: 1180px)`, `760px`, `480px` 付近の既存方針を優先します。
- アクセシビリティ用の見出しやラベルを残し、画像だけで意味が失われないようにします。

## エラー修正方針

- まず再現条件を特定し、関連するAPI、DOM、DB、アップロードファイルのどこで壊れているかを切り分けます。
- 500系エラーは `app/server.py` の該当ルート、DBクエリ、ファイルパス、JSON/multipart処理を確認します。
- 公開LPで表示が空の場合は、`/api/public/journal`、`is_public`、`public_summary`、写真URLを確認します。
- 管理画面で保存できない場合は、フォームname、`RECORD_FIELDS`、`saveRecord()`、`save_record()` の対応を確認します。
- 画像が出ない場合は、`/uploads/` または `/assets/` のパス、`mediaVersion`、保存先の相対パスを確認します。
- バックアップ/復元の不具合は、ZIP構造、`manifest.json`、`database.sqlite`、`uploads/` の安全な展開を確認します。
- 修正は最小範囲で行い、ユーザーの既存変更を戻さないでください。

## テスト方針

自動テストは現在ありません。変更時は少なくとも以下を手動または軽量スクリプトで確認してください。

- 起動確認:
  - `python app/server.py` で `http://127.0.0.1:3000/` が開く。
  - Docker確認が必要な変更では `docker compose up -d --build` が通る。
- 公開LP:
  - `/` が表示される。
  - `/api/public/journal` がJSONを返す。
  - 公開済み記録だけが表示される。
  - データがない場合にfallback表示が崩れない。
  - デスクトップ/モバイルでヒーロー、カード、フッターが重ならない。
- 管理SPA:
  - `/admin/` が表示される。
  - Dashboard、Records、New Roast、Settings、Backup の各ビューに移動できる。
  - 焙煎記録の作成、編集、複製、削除ができる。
  - 写真アップロード後に表示される。
  - ロースター、選択肢、味覚軸を追加/更新できる。
- データ/バックアップ:
  - SQLite DBが作成され、シードが投入される。
  - バックアップZIPをexportできる。
  - importは検証済みZIPだけを受け付ける。
- セキュリティ/運用:
  - Docker/Caddy経由では `/admin/` と管理APIにBasic認証がかかる。
  - `/api/public/journal` は公開APIとして認証対象外でよい。

## ローカル環境の前提

- 開発者はWindows/PowerShell環境を想定しています。
- Docker Desktopがある場合はDocker Composeで本番に近い構成を確認できます。
- DockerなしでもPython単体で起動できますが、この場合CaddyのBasic認証はかかりません。
- `.env` は `.env.example` から作成し、`APP_DOMAIN`、`ADMIN_USER`、`ADMIN_PASSWORD_HASH` を設定します。
- `ADMIN_PASSWORD_HASH` は Caddy の `caddy hash-password` で生成します。
- ローカルデータは `data/`、アップロード画像は `uploads/` に保存されます。

## 今後の開発で一貫性を保つ判断基準

- 小さく自己完結した構成を優先し、ビルド工程や依存関係を増やす前に既存の標準ライブラリ/Vanilla JSで解けるか確認します。
- 管理画面の利便性と公開LPの見栄えを分けて考え、公開LPには公開許可された情報だけを出します。
- データ永続性を最優先します。DB、uploads、backup/importに触る変更は、見た目変更より慎重に扱います。
- APIフィールド名、フォームname、DBカラム名の対応を崩さないようにします。
- ユーザー入力は常にエスケープし、SQLは常にパラメータ化します。
- デザイン変更は既存のコーヒー/紙質感の世界観に合わせ、モバイルでの読みやすさを必ず確認します。
- 既存の未コミット差分はユーザーまたは別作業の成果として扱い、依頼範囲外では変更しません。
