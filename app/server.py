from __future__ import annotations

import cgi
import datetime as dt
import json
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import tempfile
import urllib.parse
import zipfile
from contextlib import contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
ASSETS_DIR = ROOT / "assets"
DB_PATH = Path(os.environ.get("DB_PATH", ROOT / "data" / "roast-log.sqlite3"))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", ROOT / "uploads"))
RECORD_UPLOAD_DIR = UPLOAD_DIR / "records"
ROASTER_UPLOAD_DIR = UPLOAD_DIR / "roasters"
APP_PORT = int(os.environ.get("APP_PORT", "3000"))
PUBLIC_PAGE = STATIC_DIR / "index.html"
ADMIN_PAGE = STATIC_DIR / "admin.html"


DEFAULT_NAMES = [
    "ブルーマウンテン",
    "ハイマウンテン",
    "ジャマイカ",
    "クリスタルマウンテン",
    "グアテマラアンティグア",
    "コロンビアスプレモ",
    "モカハラー",
    "モカマタリ",
    "キリマンジャロ",
    "トラジャ",
    "カロシ",
    "ガヨマウンテン",
    "マンデリン",
    "ハワイコナ",
]

DEFAULT_ROASTERS = ["Gene Cafe", "weroast"]
DEFAULT_PROCESSING = ["ナチュラル", "ウォッシュド", "ハニー", "パルプドナチュラル", "スマトラ式"]
DEFAULT_RATINGS = [
    ("1", "微妙"),
    ("2", "やや不満"),
    ("3", "普通"),
    ("4", "良い"),
    ("5", "とても良い"),
]
DEFAULT_TEMP_BANDS = [
    "160°C未満",
    "160-169°C",
    "170-179°C",
    "180-189°C",
    "190-199°C",
    "200-209°C",
    "210-219°C",
    "220-229°C",
    "230°C以上",
]
DEFAULT_FLAVOR_AXES = ["酸味", "甘さ", "苦味", "ボディ", "香り", "後味"]
DEFAULT_ROAST_LEVELS = [
    ("ライトロースト", "浅煎りの最も明るい段階。酸味が強く、豆の個性がダイレクトに出る。", "浅煎り"),
    ("シナモンロースト", "浅煎り。フルーティで軽い。1ハゼ前後。", "浅煎り"),
    ("ミディアムロースト", "中煎りの入口。酸味と甘さのバランスが良い。", "中浅煎り"),
    ("ハイロースト", "中煎り。スペシャルティで最も多い。1ハゼ後。", "中煎り"),
    ("シティロースト", "中煎りの中心。甘さ・コク・酸味のバランスが安定。", "中深煎り"),
    ("フルシティロースト", "中深煎り。苦味と甘さが強まり、酸味は弱くなる。2ハゼ手前。", "中深煎り"),
    ("フレンチロースト", "深煎り。オイルが出始め、苦味が強い。アイスやカフェオレ向き。", "深煎り"),
    ("イタリアンロースト", "最も深い。表面が黒く光り、強い苦味とスモーキー感。", "深煎り"),
]

RECORD_FIELDS = [
    "name",
    "date",
    "roaster_id",
    "country",
    "region",
    "farm",
    "altitude",
    "screen",
    "defect_count",
    "grade",
    "processing",
    "green_weight_g",
    "roasted_weight_g",
    "roast_time",
    "cooling_time",
    "roast_level",
    "l_value",
    "charge_temp_c",
    "first_crack_start_temp_c",
    "first_crack_end_temp_c",
    "second_crack_start_temp_c",
    "drop_temp_c",
    "temperature_band",
    "taste_rating",
    "is_public",
    "public_summary",
    "comment",
]


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def init_db() -> None:
    RECORD_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ROASTER_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS roasters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                photo_path TEXT,
                thumbnail_path TEXT,
                memo TEXT DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS option_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS option_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_key TEXT NOT NULL,
                value TEXT NOT NULL,
                label TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT DEFAULT '',
                range_min REAL,
                range_max REAL,
                asset_key TEXT DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(group_key, value)
            );

            CREATE TABLE IF NOT EXISTS flavor_axes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL UNIQUE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS roast_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date TEXT NOT NULL,
                roaster_id INTEGER,
                country TEXT DEFAULT '',
                region TEXT DEFAULT '',
                farm TEXT DEFAULT '',
                altitude TEXT DEFAULT '',
                screen TEXT DEFAULT '',
                defect_count REAL,
                grade TEXT DEFAULT '',
                processing TEXT DEFAULT '',
                green_weight_g REAL,
                roasted_weight_g REAL,
                roast_time TEXT DEFAULT '',
                cooling_time TEXT DEFAULT '',
                roast_level TEXT DEFAULT '',
                l_value REAL,
                charge_temp_c REAL,
                first_crack_start_temp_c REAL,
                first_crack_end_temp_c REAL,
                second_crack_start_temp_c REAL,
                drop_temp_c REAL,
                temperature_band TEXT DEFAULT '',
                taste_rating INTEGER,
                is_public INTEGER NOT NULL DEFAULT 0,
                public_summary TEXT DEFAULT '',
                comment TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(roaster_id) REFERENCES roasters(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS roast_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(record_id) REFERENCES roast_records(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS flavor_scores (
                record_id INTEGER NOT NULL,
                axis_id INTEGER NOT NULL,
                score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
                PRIMARY KEY(record_id, axis_id),
                FOREIGN KEY(record_id) REFERENCES roast_records(id) ON DELETE CASCADE,
                FOREIGN KEY(axis_id) REFERENCES flavor_axes(id) ON DELETE CASCADE
            );
            """
        )
        migrate_schema(con)
        seed(con)


def migrate_schema(con: sqlite3.Connection) -> None:
    columns = {row["name"] for row in con.execute("PRAGMA table_info(roast_records)")}
    if "is_public" not in columns:
        con.execute("ALTER TABLE roast_records ADD COLUMN is_public INTEGER NOT NULL DEFAULT 0")
    if "public_summary" not in columns:
        con.execute("ALTER TABLE roast_records ADD COLUMN public_summary TEXT DEFAULT ''")


def seed(con: sqlite3.Connection) -> None:
    groups = [
        ("bean_name", "名称"),
        ("processing", "精選処理"),
        ("roast_level", "焙煎度"),
        ("taste_rating", "味の評価"),
        ("temperature_band", "温度帯"),
    ]
    for key, label in groups:
        con.execute("INSERT OR IGNORE INTO option_groups(key, label) VALUES(?, ?)", (key, label))

    for i, label in enumerate(DEFAULT_NAMES):
        add_option(con, "bean_name", label, label, "", "", None, None, "", i)
    for i, label in enumerate(DEFAULT_PROCESSING):
        add_option(con, "processing", label, label, "", "", None, None, "", i)
    for i, (value, label) in enumerate(DEFAULT_RATINGS):
        add_option(con, "taste_rating", value, f"{value}: {label}", "", "", None, None, "", i)
    for i, label in enumerate(DEFAULT_TEMP_BANDS):
        ranges = re.findall(r"\d+", label)
        rmin = float(ranges[0]) if ranges else None
        rmax = float(ranges[-1]) if len(ranges) > 1 else None
        add_option(con, "temperature_band", label, label, "", "", rmin, rmax, "", i)
    for i, (label, desc, category) in enumerate(DEFAULT_ROAST_LEVELS):
        add_option(con, "roast_level", label, label, desc, category, None, None, f"roast-level-{i}", i)
    for i, name in enumerate(DEFAULT_ROASTERS):
        con.execute(
            """
            INSERT OR IGNORE INTO roasters(name, sort_order, created_at, updated_at)
            VALUES(?, ?, ?, ?)
            """,
            (name, i, now_iso(), now_iso()),
        )
    for i, label in enumerate(DEFAULT_FLAVOR_AXES):
        con.execute(
            "INSERT OR IGNORE INTO flavor_axes(label, sort_order) VALUES(?, ?)",
            (label, i),
        )


def add_option(
    con: sqlite3.Connection,
    group_key: str,
    value: str,
    label: str,
    description: str,
    category: str,
    range_min: float | None,
    range_max: float | None,
    asset_key: str,
    sort_order: int,
) -> None:
    con.execute(
        """
        INSERT OR IGNORE INTO option_items(
            group_key, value, label, description, category, range_min, range_max, asset_key, sort_order
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (group_key, value, label, description, category, range_min, range_max, asset_key, sort_order),
    )


def row_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def parse_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def public_path(path: str | None) -> str | None:
    if not path:
        return None
    return "/" + path.replace("\\", "/").lstrip("/")


def save_upload(field_item, target_dir: Path) -> str:
    original = Path(field_item.filename or "upload.bin").name
    suffix = Path(original).suffix.lower()
    if suffix not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        suffix = ".bin"
    filename = f"{dt.datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(5)}{suffix}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    with target.open("wb") as f:
        shutil.copyfileobj(field_item.file, f)
    return str(target.relative_to(UPLOAD_DIR.parent)).replace("\\", "/")


def calc_record(record: dict) -> dict:
    green = record.get("green_weight_g")
    roasted = record.get("roasted_weight_g")
    loss = None
    loss_rate = None
    if green is not None and roasted is not None:
        loss = round(float(green) - float(roasted), 1)
        if float(green) > 0:
            loss_rate = round(loss / float(green) * 100, 1)
    record["loss_g"] = loss
    record["loss_rate"] = loss_rate
    record["total_time"] = sum_times(record.get("roast_time"), record.get("cooling_time"))
    return record


def sum_times(*values: str | None) -> str:
    total = 0
    for value in values:
        if not value or not re.match(r"^\d{1,3}:\d{2}$", value):
            continue
        minutes, seconds = value.split(":")
        total += int(minutes) * 60 + int(seconds)
    if total == 0:
        return ""
    return f"{total // 60:02d}:{total % 60:02d}"


class Handler(BaseHTTPRequestHandler):
    server_version = "RoastLog/1.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/api/bootstrap":
                self.json(self.bootstrap())
            elif path == "/api/public/journal":
                self.json(self.public_journal())
            elif path == "/api/records":
                self.json(self.list_records(query))
            elif re.match(r"^/api/records/\d+$", path):
                self.json(self.get_record(int(path.rsplit("/", 1)[1])))
            elif path == "/api/backup/export":
                self.export_backup()
            elif path.startswith("/uploads/"):
                self.serve_file(UPLOAD_DIR.parent / path.lstrip("/"))
            elif path.startswith("/assets/"):
                self.serve_file(ROOT / path.lstrip("/"))
            elif path.startswith("/static/"):
                self.serve_file(ROOT / path.lstrip("/"))
            elif path == "/admin" or path == "/admin/":
                self.serve_file(ADMIN_PAGE)
            elif path.startswith("/admin/"):
                self.serve_file(ADMIN_PAGE)
            else:
                self.serve_file(PUBLIC_PAGE)
        except Exception as exc:
            self.error(exc)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/records":
                self.json(self.save_record(parse_json(self)), HTTPStatus.CREATED)
            elif re.match(r"^/api/records/\d+/duplicate$", path):
                self.json(self.duplicate_record(int(path.split("/")[-2])), HTTPStatus.CREATED)
            elif re.match(r"^/api/records/\d+/photos$", path):
                self.upload_record_photo(int(path.split("/")[-2]))
            elif path == "/api/roasters":
                self.json(self.save_roaster(parse_json(self)), HTTPStatus.CREATED)
            elif re.match(r"^/api/roasters/\d+/photo$", path):
                self.upload_roaster_photo(int(path.split("/")[-2]))
            elif path == "/api/options":
                self.json(self.save_option(parse_json(self)), HTTPStatus.CREATED)
            elif path == "/api/flavor-axes":
                self.json(self.save_flavor_axis(parse_json(self)), HTTPStatus.CREATED)
            elif path == "/api/backup/import":
                self.import_backup()
            else:
                self.not_found()
        except Exception as exc:
            self.error(exc)

    def do_PUT(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if re.match(r"^/api/records/\d+$", path):
                self.json(self.save_record(parse_json(self), int(path.rsplit("/", 1)[1])))
            elif re.match(r"^/api/roasters/\d+$", path):
                self.json(self.save_roaster(parse_json(self), int(path.rsplit("/", 1)[1])))
            elif re.match(r"^/api/options/\d+$", path):
                self.json(self.save_option(parse_json(self), int(path.rsplit("/", 1)[1])))
            elif re.match(r"^/api/flavor-axes/\d+$", path):
                self.json(self.save_flavor_axis(parse_json(self), int(path.rsplit("/", 1)[1])))
            else:
                self.not_found()
        except Exception as exc:
            self.error(exc)

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if re.match(r"^/api/records/\d+$", path):
                self.delete_record(int(path.rsplit("/", 1)[1]))
            elif re.match(r"^/api/photos/\d+$", path):
                self.delete_photo(int(path.rsplit("/", 1)[1]))
            elif re.match(r"^/api/roasters/\d+$", path):
                self.soft_delete("roasters", int(path.rsplit("/", 1)[1]))
            elif re.match(r"^/api/options/\d+$", path):
                self.soft_delete("option_items", int(path.rsplit("/", 1)[1]))
            elif re.match(r"^/api/flavor-axes/\d+$", path):
                self.soft_delete("flavor_axes", int(path.rsplit("/", 1)[1]))
            else:
                self.not_found()
        except Exception as exc:
            self.error(exc)

    def bootstrap(self) -> dict:
        with connect() as con:
            options = {}
            for row in con.execute("SELECT * FROM option_items ORDER BY group_key, sort_order, id"):
                item = dict(row)
                options.setdefault(item["group_key"], []).append(item)
            roasters = [dict(row) for row in con.execute("SELECT * FROM roasters ORDER BY sort_order, id")]
            for roaster in roasters:
                roaster["photo_url"] = public_path(roaster.get("photo_path"))
                roaster["thumbnail_url"] = public_path(roaster.get("thumbnail_path") or roaster.get("photo_path"))
            axes = [dict(row) for row in con.execute("SELECT * FROM flavor_axes ORDER BY sort_order, id")]
            return {
                "options": options,
                "roasters": roasters,
                "flavor_axes": axes,
                "stats": self.stats(con),
                "today": dt.date.today().isoformat(),
            }

    def stats(self, con: sqlite3.Connection) -> dict:
        rows = [calc_record(dict(row)) for row in con.execute("SELECT * FROM roast_records")]
        count = len(rows)
        avg_loss = round(sum(r["loss_rate"] or 0 for r in rows if r["loss_rate"] is not None) / max(1, len([r for r in rows if r["loss_rate"] is not None])), 1) if rows else None
        ratings: dict[str, int] = {}
        for row in rows:
            if row.get("taste_rating"):
                ratings[str(row["taste_rating"])] = ratings.get(str(row["taste_rating"]), 0) + 1
        recent = [self.decorate_record(con, dict(row)) for row in con.execute("SELECT * FROM roast_records ORDER BY date DESC, id DESC LIMIT 5")]
        flavor_avg = []
        axes = con.execute("SELECT * FROM flavor_axes WHERE is_active=1 ORDER BY sort_order, id").fetchall()
        for axis in axes:
            avg = con.execute("SELECT AVG(score) value FROM flavor_scores WHERE axis_id=?", (axis["id"],)).fetchone()["value"]
            flavor_avg.append({"label": axis["label"], "score": round(avg, 1) if avg else None})
        return {"count": count, "avg_loss_rate": avg_loss, "ratings": ratings, "recent": recent, "flavor_average": flavor_avg}

    def list_records(self, query: dict) -> dict:
        clauses = []
        params = []
        q = query.get("q", [""])[0].strip()
        for key in ["roaster_id", "roast_level", "processing", "taste_rating", "temperature_band"]:
            value = query.get(key, [""])[0]
            if value:
                clauses.append(f"r.{key} = ?")
                params.append(value)
        if q:
            clauses.append("(r.name LIKE ? OR r.country LIKE ? OR r.region LIKE ? OR r.farm LIKE ? OR r.comment LIKE ?)")
            params.extend([f"%{q}%"] * 5)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        sort = query.get("sort", ["date_desc"])[0]
        order_map = {
            "date_asc": "r.date ASC, r.id ASC",
            "rating_desc": "r.taste_rating DESC, r.date DESC",
            "l_value_asc": "r.l_value ASC",
            "loss_desc": "(r.green_weight_g - r.roasted_weight_g) DESC",
            "charge_temp_desc": "r.charge_temp_c DESC",
            "drop_temp_desc": "r.drop_temp_c DESC",
            "date_desc": "r.date DESC, r.id DESC",
        }
        sql = f"SELECT r.*, ro.name roaster_name, ro.thumbnail_path roaster_thumbnail_path FROM roast_records r LEFT JOIN roasters ro ON ro.id=r.roaster_id {where} ORDER BY {order_map.get(sort, order_map['date_desc'])}"
        with connect() as con:
            rows = [calc_record(dict(row)) for row in con.execute(sql, params)]
            for row in rows:
                row["roaster_thumbnail_url"] = public_path(row.get("roaster_thumbnail_path"))
                row["photos"] = [public_path(p["file_path"]) for p in con.execute("SELECT file_path FROM roast_photos WHERE record_id=? ORDER BY sort_order, id", (row["id"],))]
            return {"records": rows}

    def public_journal(self) -> dict:
        with connect() as con:
            rows = [
                dict(row)
                for row in con.execute(
                    """
                    SELECT r.*, ro.name roaster_name
                    FROM roast_records r
                    LEFT JOIN roasters ro ON ro.id = r.roaster_id
                    WHERE r.is_public = 1
                    ORDER BY r.date DESC, r.id DESC
                    LIMIT 9
                    """
                )
            ]
            journal = [self.decorate_public_record(con, calc_record(row)) for row in rows]
            return {
                "journal": journal,
                "stats": self.public_stats(con),
            }

    def public_stats(self, con: sqlite3.Connection) -> dict:
        public_rows = [calc_record(dict(row)) for row in con.execute("SELECT * FROM roast_records WHERE is_public = 1 ORDER BY date DESC, id DESC")]
        countries = len({row["country"] for row in public_rows if row.get("country")})
        avg_rating_values = [row["taste_rating"] for row in public_rows if row.get("taste_rating") is not None]
        avg_rating = round(sum(avg_rating_values) / len(avg_rating_values), 1) if avg_rating_values else None
        recent = public_rows[0] if public_rows else None
        axes = con.execute("SELECT * FROM flavor_axes WHERE is_active=1 ORDER BY sort_order, id").fetchall()
        flavor_average = []
        for axis in axes:
            avg = con.execute(
                """
                SELECT AVG(fs.score) value
                FROM flavor_scores fs
                INNER JOIN roast_records rr ON rr.id = fs.record_id
                WHERE fs.axis_id = ? AND rr.is_public = 1
                """,
                (axis["id"],),
            ).fetchone()["value"]
            flavor_average.append({"label": axis["label"], "score": round(avg, 1) if avg else None})
        return {
            "count": len(public_rows),
            "countries": countries,
            "avg_rating": avg_rating,
            "recent_date": recent["date"] if recent else None,
            "flavor_average": flavor_average,
        }

    def decorate_public_record(self, con: sqlite3.Connection, record: dict) -> dict:
        photos = [dict(row) for row in con.execute("SELECT * FROM roast_photos WHERE record_id=? ORDER BY sort_order, id", (record["id"],))]
        lead_photo = public_path(photos[0]["file_path"]) if photos else None
        scores = []
        for row in con.execute(
            """
            SELECT fa.label, fs.score
            FROM flavor_scores fs
            INNER JOIN flavor_axes fa ON fa.id = fs.axis_id
            WHERE fs.record_id = ? AND fa.is_active = 1
            ORDER BY fa.sort_order, fa.id
            """,
            (record["id"],),
        ):
            scores.append({"label": row["label"], "score": row["score"]})
        return {
            "id": record["id"],
            "name": record["name"],
            "date": record["date"],
            "country": record.get("country") or "",
            "region": record.get("region") or "",
            "farm": record.get("farm") or "",
            "processing": record.get("processing") or "",
            "roast_level": record.get("roast_level") or "",
            "taste_rating": record.get("taste_rating"),
            "loss_rate": record.get("loss_rate"),
            "roaster_name": record.get("roaster_name") or "",
            "public_summary": self.public_summary_text(record),
            "lead_photo_url": lead_photo,
            "flavor_scores": scores,
        }

    def public_summary_text(self, record: dict) -> str:
        summary = (record.get("public_summary") or "").strip()
        if summary:
            return summary
        parts = [part for part in [record.get("country"), record.get("region"), record.get("processing")] if part]
        lead = " / ".join(parts[:3])
        roast = record.get("roast_level") or "焙煎"
        if lead:
            return f"{lead} の豆を {roast} で記録した一杯。"
        return f"{roast} で整えた焙煎ログ。"

    def get_record(self, record_id: int) -> dict:
        with connect() as con:
            row = con.execute("SELECT r.*, ro.name roaster_name, ro.thumbnail_path roaster_thumbnail_path FROM roast_records r LEFT JOIN roasters ro ON ro.id=r.roaster_id WHERE r.id=?", (record_id,)).fetchone()
            if not row:
                raise HttpError(HTTPStatus.NOT_FOUND, "Record not found")
            return {"record": self.decorate_record(con, dict(row))}

    def decorate_record(self, con: sqlite3.Connection, record: dict) -> dict:
        calc_record(record)
        record["roaster_thumbnail_url"] = public_path(record.get("roaster_thumbnail_path"))
        photos = [dict(row) for row in con.execute("SELECT * FROM roast_photos WHERE record_id=? ORDER BY sort_order, id", (record["id"],))]
        for photo in photos:
            photo["url"] = public_path(photo["file_path"])
        record["photos"] = photos
        scores = {}
        for row in con.execute("SELECT axis_id, score FROM flavor_scores WHERE record_id=?", (record["id"],)):
            scores[str(row["axis_id"])] = row["score"]
        record["flavor_scores"] = scores
        return record

    def save_record(self, payload: dict, record_id: int | None = None) -> dict:
        values = {field: payload.get(field) for field in RECORD_FIELDS}
        values["date"] = values["date"] or dt.date.today().isoformat()
        values["name"] = (values["name"] or "").strip()
        values["public_summary"] = (values.get("public_summary") or "").strip()
        for key in ["defect_count", "green_weight_g", "roasted_weight_g", "l_value", "charge_temp_c", "first_crack_start_temp_c", "first_crack_end_temp_c", "second_crack_start_temp_c", "drop_temp_c"]:
            values[key] = to_number(values.get(key))
        values["roaster_id"] = int(values["roaster_id"]) if values.get("roaster_id") else None
        values["taste_rating"] = int(values["taste_rating"]) if values.get("taste_rating") else None
        values["is_public"] = int(bool(payload.get("is_public")))
        with connect() as con:
            if payload.get("add_name_option") and values["name"]:
                add_option(con, "bean_name", values["name"], values["name"], "", "", None, None, "", 999)
            if record_id:
                assignments = ", ".join([f"{field}=?" for field in RECORD_FIELDS])
                con.execute(
                    f"UPDATE roast_records SET {assignments}, updated_at=? WHERE id=?",
                    [values[field] for field in RECORD_FIELDS] + [now_iso(), record_id],
                )
            else:
                fields = ", ".join(RECORD_FIELDS + ["created_at", "updated_at"])
                marks = ", ".join(["?"] * (len(RECORD_FIELDS) + 2))
                cur = con.execute(
                    f"INSERT INTO roast_records({fields}) VALUES({marks})",
                    [values[field] for field in RECORD_FIELDS] + [now_iso(), now_iso()],
                )
                record_id = cur.lastrowid
            self.save_scores(con, record_id, payload.get("flavor_scores", {}))
            con.commit()
        return self.get_record(record_id)

    def save_scores(self, con: sqlite3.Connection, record_id: int, scores: dict) -> None:
        con.execute("DELETE FROM flavor_scores WHERE record_id=?", (record_id,))
        for axis_id, score in scores.items():
            if score in ["", None]:
                continue
            con.execute(
                "INSERT INTO flavor_scores(record_id, axis_id, score) VALUES(?, ?, ?)",
                (record_id, int(axis_id), int(score)),
            )

    def duplicate_record(self, record_id: int) -> dict:
        with connect() as con:
            row = con.execute("SELECT * FROM roast_records WHERE id=?", (record_id,)).fetchone()
            if not row:
                raise HttpError(HTTPStatus.NOT_FOUND, "Record not found")
            data = dict(row)
            for key in ["id", "created_at", "updated_at"]:
                data.pop(key, None)
            data["date"] = dt.date.today().isoformat()
            data["taste_rating"] = None
            data["is_public"] = 0
            data["public_summary"] = ""
            data["comment"] = ""
            fields = list(data.keys())
            cur = con.execute(
                f"INSERT INTO roast_records({', '.join(fields)}, created_at, updated_at) VALUES({', '.join(['?'] * (len(fields) + 2))})",
                [data[field] for field in fields] + [now_iso(), now_iso()],
            )
            new_id = cur.lastrowid
            con.commit()
        return self.get_record(new_id)

    def upload_record_photo(self, record_id: int) -> None:
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type")})
        files = form["photos"] if "photos" in form else []
        if not isinstance(files, list):
            files = [files]
        with connect() as con:
            max_order = con.execute("SELECT COALESCE(MAX(sort_order), 0) value FROM roast_photos WHERE record_id=?", (record_id,)).fetchone()["value"]
            saved = []
            for item in files:
                if not item.filename:
                    continue
                path = save_upload(item, RECORD_UPLOAD_DIR)
                max_order += 1
                cur = con.execute("INSERT INTO roast_photos(record_id, file_path, sort_order, created_at) VALUES(?, ?, ?, ?)", (record_id, path, max_order, now_iso()))
                saved.append({"id": cur.lastrowid, "url": public_path(path)})
            self.json({"photos": saved}, HTTPStatus.CREATED)

    def delete_record(self, record_id: int) -> None:
        with connect() as con:
            photos = con.execute("SELECT file_path FROM roast_photos WHERE record_id=?", (record_id,)).fetchall()
            con.execute("DELETE FROM roast_records WHERE id=?", (record_id,))
        for photo in photos:
            safe_unlink(UPLOAD_DIR.parent / photo["file_path"])
        self.json({"ok": True})

    def delete_photo(self, photo_id: int) -> None:
        with connect() as con:
            photo = con.execute("SELECT file_path FROM roast_photos WHERE id=?", (photo_id,)).fetchone()
            con.execute("DELETE FROM roast_photos WHERE id=?", (photo_id,))
        if photo:
            safe_unlink(UPLOAD_DIR.parent / photo["file_path"])
        self.json({"ok": True})

    def save_roaster(self, payload: dict, roaster_id: int | None = None) -> dict:
        name = (payload.get("name") or "").strip()
        if not name:
            raise HttpError(HTTPStatus.BAD_REQUEST, "ロースター名は必須です")
        with connect() as con:
            if roaster_id:
                con.execute("UPDATE roasters SET name=?, memo=?, sort_order=?, is_active=?, updated_at=? WHERE id=?", (name, payload.get("memo", ""), int(payload.get("sort_order") or 0), int(bool(payload.get("is_active", 1))), now_iso(), roaster_id))
            else:
                cur = con.execute("INSERT INTO roasters(name, memo, sort_order, created_at, updated_at) VALUES(?, ?, ?, ?, ?)", (name, payload.get("memo", ""), int(payload.get("sort_order") or 0), now_iso(), now_iso()))
                roaster_id = cur.lastrowid
            return {"roaster": row_dict(con.execute("SELECT * FROM roasters WHERE id=?", (roaster_id,)).fetchone())}

    def upload_roaster_photo(self, roaster_id: int) -> None:
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type")})
        item = form["photo"] if "photo" in form else None
        if item is None or not item.filename:
            raise HttpError(HTTPStatus.BAD_REQUEST, "photo is required")
        path = save_upload(item, ROASTER_UPLOAD_DIR)
        with connect() as con:
            old = con.execute("SELECT photo_path FROM roasters WHERE id=?", (roaster_id,)).fetchone()
            con.execute("UPDATE roasters SET photo_path=?, thumbnail_path=?, updated_at=? WHERE id=?", (path, path, now_iso(), roaster_id))
        if old and old["photo_path"]:
            safe_unlink(UPLOAD_DIR.parent / old["photo_path"])
        self.json({"url": public_path(path)}, HTTPStatus.CREATED)

    def save_option(self, payload: dict, option_id: int | None = None) -> dict:
        group_key = payload.get("group_key")
        label = (payload.get("label") or payload.get("value") or "").strip()
        value = (payload.get("value") or label).strip()
        if not group_key or not label:
            raise HttpError(HTTPStatus.BAD_REQUEST, "group_key and label are required")
        with connect() as con:
            if option_id:
                con.execute(
                    """
                    UPDATE option_items
                    SET value=?, label=?, description=?, category=?, range_min=?, range_max=?, sort_order=?, is_active=?
                    WHERE id=?
                    """,
                    (value, label, payload.get("description", ""), payload.get("category", ""), to_number(payload.get("range_min")), to_number(payload.get("range_max")), int(payload.get("sort_order") or 0), int(bool(payload.get("is_active", 1))), option_id),
                )
            else:
                cur = con.execute(
                    """
                    INSERT INTO option_items(group_key, value, label, description, category, range_min, range_max, sort_order)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (group_key, value, label, payload.get("description", ""), payload.get("category", ""), to_number(payload.get("range_min")), to_number(payload.get("range_max")), int(payload.get("sort_order") or 0)),
                )
                option_id = cur.lastrowid
            return {"option": row_dict(con.execute("SELECT * FROM option_items WHERE id=?", (option_id,)).fetchone())}

    def save_flavor_axis(self, payload: dict, axis_id: int | None = None) -> dict:
        label = (payload.get("label") or "").strip()
        if not label:
            raise HttpError(HTTPStatus.BAD_REQUEST, "label is required")
        with connect() as con:
            if axis_id:
                con.execute("UPDATE flavor_axes SET label=?, sort_order=?, is_active=? WHERE id=?", (label, int(payload.get("sort_order") or 0), int(bool(payload.get("is_active", 1))), axis_id))
            else:
                cur = con.execute("INSERT INTO flavor_axes(label, sort_order) VALUES(?, ?)", (label, int(payload.get("sort_order") or 0)))
                axis_id = cur.lastrowid
            return {"axis": row_dict(con.execute("SELECT * FROM flavor_axes WHERE id=?", (axis_id,)).fetchone())}

    def soft_delete(self, table: str, item_id: int) -> None:
        with connect() as con:
            con.execute(f"UPDATE {table} SET is_active=0 WHERE id=?", (item_id,))
        self.json({"ok": True})

    def export_backup(self) -> None:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_path = Path(tmp.name)
        try:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                write_database_backup(zf)
                write_uploads_backup(zf)
                manifest = {"app": "roast-log", "created_at": now_iso(), "version": 1}
                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="roast-log-backup-{stamp}.zip"')
            self.send_header("Content-Length", str(tmp_path.stat().st_size))
            self.end_headers()
            with tmp_path.open("rb") as f:
                shutil.copyfileobj(f, self.wfile)
        finally:
            safe_unlink(tmp_path)

    def import_backup(self) -> None:
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type")})
        item = form["backup"] if "backup" in form else None
        if item is None or not item.filename:
            raise HttpError(HTTPStatus.BAD_REQUEST, "backup is required")
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "backup.zip"
            with zip_path.open("wb") as f:
                shutil.copyfileobj(item.file, f)
            extract_dir = Path(tmpdir) / "extract"
            with zipfile.ZipFile(zip_path) as zf:
                validate_backup_manifest(zf)
                extract_backup_zip(zf, extract_dir)
            database = extract_dir / "database.sqlite"
            if not database.exists():
                raise HttpError(HTTPStatus.BAD_REQUEST, "database.sqlite not found")
            validate_backup_database(database)
            restore_backup_contents(database, extract_dir / "uploads")
        init_db()
        self.json({"ok": True})

    def serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.not_found()
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        if is_relative_to(path, UPLOAD_DIR):
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with path.open("rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def not_found(self) -> None:
        raise HttpError(HTTPStatus.NOT_FOUND, "Not found")

    def error(self, exc: Exception) -> None:
        if isinstance(exc, HttpError):
            self.json({"error": exc.message}, exc.status)
        else:
            self.json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)


class HttpError(Exception):
    def __init__(self, status: HTTPStatus, message: str):
        self.status = status
        self.message = message
        super().__init__(message)


def to_number(value):
    if value in ["", None]:
        return None
    return float(value)


def safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        safe_unlink(path)


def unique_sibling(path: Path, suffix: str) -> Path:
    while True:
        candidate = path.parent / f".{path.name}.{secrets.token_hex(8)}.{suffix}"
        if not candidate.exists():
            return candidate


def write_database_backup(zf: zipfile.ZipFile) -> None:
    if not DB_PATH.exists():
        return
    with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite") as tmp:
        snapshot = Path(tmp.name)
    source = None
    dest = None
    try:
        source = sqlite3.connect(DB_PATH)
        dest = sqlite3.connect(snapshot)
        source.backup(dest)
        zf.write(snapshot, "database.sqlite")
    finally:
        if dest is not None:
            dest.close()
        if source is not None:
            source.close()
        safe_unlink(snapshot)


def write_uploads_backup(zf: zipfile.ZipFile) -> None:
    if not UPLOAD_DIR.exists():
        return
    if not UPLOAD_DIR.is_dir():
        raise HttpError(HTTPStatus.INTERNAL_SERVER_ERROR, "upload path is not a directory")
    zf.writestr("uploads/", "")
    for path in UPLOAD_DIR.rglob("*"):
        rel = path.relative_to(UPLOAD_DIR).as_posix()
        arcname = f"uploads/{rel}"
        if path.is_dir():
            zf.writestr(f"{arcname.rstrip('/')}/", "")
        elif path.is_file():
            zf.write(path, arcname)


def validate_backup_manifest(zf: zipfile.ZipFile) -> None:
    if "manifest.json" not in zf.namelist():
        return
    try:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HttpError(HTTPStatus.BAD_REQUEST, "invalid manifest.json") from exc
    app_name = manifest.get("app")
    if app_name and app_name != "roast-log":
        raise HttpError(HTTPStatus.BAD_REQUEST, "backup is not for roast-log")


def backup_member_path(root: Path, member_name: str) -> Path:
    normalized = member_name.replace("\\", "/")
    path = PurePosixPath(normalized)
    parts = path.parts
    if not parts or path.is_absolute() or any(part in ("", ".", "..") for part in parts):
        raise HttpError(HTTPStatus.BAD_REQUEST, f"invalid backup path: {member_name}")
    if any(":" in part for part in parts):
        raise HttpError(HTTPStatus.BAD_REQUEST, f"invalid backup path: {member_name}")
    return root.joinpath(*parts)


def extract_backup_zip(zf: zipfile.ZipFile, extract_dir: Path) -> None:
    for member in zf.infolist():
        target = backup_member_path(extract_dir, member.filename)
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member) as source, target.open("wb") as dest:
            shutil.copyfileobj(source, dest)


def validate_backup_database(database: Path) -> None:
    required_tables = {
        "roasters",
        "option_groups",
        "option_items",
        "flavor_axes",
        "roast_records",
        "roast_photos",
        "flavor_scores",
    }
    con = None
    try:
        con = sqlite3.connect(database)
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    except sqlite3.DatabaseError as exc:
        raise HttpError(HTTPStatus.BAD_REQUEST, "invalid database.sqlite") from exc
    finally:
        if con is not None:
            con.close()
    tables = {row[0] for row in rows}
    missing = sorted(required_tables - tables)
    if missing:
        raise HttpError(HTTPStatus.BAD_REQUEST, f"backup database is missing: {', '.join(missing)}")


def stage_uploads(source: Path, staging: Path) -> None:
    if source.exists():
        if not source.is_dir():
            raise HttpError(HTTPStatus.BAD_REQUEST, "uploads in backup is not a directory")
        shutil.copytree(source, staging)
    else:
        staging.mkdir(parents=True)


def restore_database_from_backup(database: Path) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    source = None
    dest = None
    try:
        source = sqlite3.connect(database)
        dest = sqlite3.connect(DB_PATH, timeout=30)
        source.backup(dest)
    except sqlite3.DatabaseError as exc:
        raise HttpError(HTTPStatus.INTERNAL_SERVER_ERROR, "could not restore database") from exc
    finally:
        if dest is not None:
            dest.close()
        if source is not None:
            source.close()


def restore_backup_contents(database: Path, uploads: Path) -> None:
    UPLOAD_DIR.parent.mkdir(parents=True, exist_ok=True)

    upload_staging = unique_sibling(UPLOAD_DIR, "restore")
    upload_backup = unique_sibling(UPLOAD_DIR, "old")

    try:
        stage_uploads(uploads, upload_staging)

        if UPLOAD_DIR.exists() or UPLOAD_DIR.is_symlink():
            UPLOAD_DIR.rename(upload_backup)
        upload_staging.rename(UPLOAD_DIR)
        restore_database_from_backup(database)
    except Exception:
        remove_path(UPLOAD_DIR)
        if upload_backup.exists() or upload_backup.is_symlink():
            upload_backup.rename(UPLOAD_DIR)
        raise
    finally:
        remove_path(upload_staging)
        remove_path(upload_backup)


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def main() -> None:
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", APP_PORT), Handler)
    print(f"Roast Log running on http://0.0.0.0:{APP_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
