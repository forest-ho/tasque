import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("quest_app.db")


def set_db_path(path):
    """SQLiteの保存先を設定する。"""
    global DB_PATH
    DB_PATH = Path(path)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_connection():
    """SQLiteへの接続を作る関数。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """必要なテーブルを作成する。"""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                level INTEGER NOT NULL DEFAULT 1,
                exp INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS main_quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                monster_name TEXT NOT NULL DEFAULT 'ドラゴン',
                monster_max_hp INTEGER NOT NULL DEFAULT 100,
                monster_hp INTEGER NOT NULL DEFAULT 100,
                deadline TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quest_monsters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                main_quest_id INTEGER NOT NULL,
                image_key TEXT NOT NULL,
                hp INTEGER NOT NULL DEFAULT 0,
                max_hp INTEGER NOT NULL DEFAULT 0,
                position INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (main_quest_id) REFERENCES main_quests(id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sub_quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                main_quest_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                importance TEXT NOT NULL DEFAULT 'medium',
                deadline TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_completed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                monster_id INTEGER,
                damage INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (main_quest_id) REFERENCES main_quests(id),
                FOREIGN KEY (monster_id) REFERENCES quest_monsters(id)
            )
            """
        )

        sub_quest_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(sub_quests)")
        }
        if "created_at" not in sub_quest_columns:
            conn.execute("ALTER TABLE sub_quests ADD COLUMN created_at TEXT")
        conn.execute(
            "UPDATE sub_quests SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
        )
        if "monster_id" not in sub_quest_columns:
            conn.execute(
                "ALTER TABLE sub_quests ADD COLUMN monster_id INTEGER REFERENCES quest_monsters(id)"
            )
        if "damage" not in sub_quest_columns:
            conn.execute(
                "ALTER TABLE sub_quests ADD COLUMN damage INTEGER NOT NULL DEFAULT 0"
            )

        conn.execute(
            """
            UPDATE sub_quests
            SET damage = CASE importance
                WHEN 'low' THEN 10
                WHEN 'high' THEN 50
                ELSE 20
            END
            WHERE damage = 0
            """
        )

        main_quests = conn.execute("SELECT * FROM main_quests").fetchall()
        for main_quest in main_quests:
            monsters = conn.execute(
                "SELECT * FROM quest_monsters WHERE main_quest_id = ? ORDER BY position, id",
                (main_quest["id"],),
            ).fetchall()
            if not monsters:
                sub_quests = conn.execute(
                    "SELECT * FROM sub_quests WHERE main_quest_id = ? ORDER BY id",
                    (main_quest["id"],),
                ).fetchall()
                if sub_quests:
                    max_hp = sum(item["damage"] for item in sub_quests)
                    hp = sum(
                        item["damage"]
                        for item in sub_quests
                        if item["is_completed"] == 0
                    )
                    cursor = conn.execute(
                        """
                        INSERT INTO quest_monsters (main_quest_id, image_key, hp, max_hp, position)
                        VALUES (?, 'blue', ?, ?, 0)
                        """,
                        (main_quest["id"], hp, max_hp),
                    )
                    conn.execute(
                        "UPDATE sub_quests SET monster_id = ? WHERE main_quest_id = ? AND monster_id IS NULL",
                        (cursor.lastrowid, main_quest["id"]),
                    )
                else:
                    hp = 0
                    max_hp = 0
                conn.execute(
                    "UPDATE main_quests SET monster_hp = ?, monster_max_hp = ? WHERE id = ?",
                    (hp, max_hp, main_quest["id"]),
                )
            else:
                first_monster_id = monsters[0]["id"]
                conn.execute(
                    "UPDATE sub_quests SET monster_id = ? WHERE main_quest_id = ? AND monster_id IS NULL",
                    (first_monster_id, main_quest["id"]),
                )
                _update_main_quest_party_hp(conn, main_quest["id"])

        player = conn.execute("SELECT * FROM player WHERE id = 1").fetchone()
        if player is None:
            conn.execute(
                "INSERT INTO player (id, level, exp) VALUES (1, 1, 0)"
            )


def get_player():
    """プレイヤー情報を1人分だけ取得する。"""
    with get_connection() as conn:
        return conn.execute("SELECT * FROM player WHERE id = 1").fetchone()


def save_player(level, exp):
    """プレイヤーのレベルとEXPを保存する。"""
    with get_connection() as conn:
        conn.execute(
            "UPDATE player SET level = ?, exp = ? WHERE id = 1",
            (level, exp),
        )


def add_main_quest(title, description="", monster_name="ドラゴン", monster_max_hp=0, deadline=None):
    """メインクエストを追加する。"""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO main_quests (title, description, monster_name, monster_max_hp, monster_hp, deadline)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, description, monster_name, monster_max_hp, monster_max_hp, deadline),
        )
        return cur.lastrowid


def get_main_quests():
    """メインクエスト一覧を取得する。"""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM main_quests ORDER BY created_at DESC"
        ).fetchall()


def add_sub_quest(
    main_quest_id,
    title,
    importance,
    deadline=None,
    *,
    damage,
    image_key,
    summon_new=False,
):
    """サブクエストを追加し、担当する敵のHPにも反映する。"""
    with get_connection() as conn:
        if summon_new:
            position = conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM quest_monsters WHERE main_quest_id = ?",
                (main_quest_id,),
            ).fetchone()[0]
            cursor = conn.execute(
                """
                INSERT INTO quest_monsters (main_quest_id, image_key, hp, max_hp, position)
                VALUES (?, ?, ?, ?, ?)
                """,
                (main_quest_id, image_key, damage, damage, position),
            )
            monster_id = cursor.lastrowid
        else:
            monster = conn.execute(
                "SELECT id FROM quest_monsters WHERE main_quest_id = ? ORDER BY position, id LIMIT 1",
                (main_quest_id,),
            ).fetchone()
            if monster is None:
                cursor = conn.execute(
                    """
                    INSERT INTO quest_monsters (main_quest_id, image_key, hp, max_hp, position)
                    VALUES (?, ?, 0, 0, 0)
                    """,
                    (main_quest_id, image_key),
                )
                monster_id = cursor.lastrowid
            else:
                monster_id = monster["id"]
            conn.execute(
                "UPDATE quest_monsters SET hp = hp + ?, max_hp = max_hp + ? WHERE id = ?",
                (damage, damage, monster_id),
            )

        conn.execute(
            """
            INSERT INTO sub_quests (
                main_quest_id, title, importance, deadline, created_at, monster_id, damage
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
            """,
            (main_quest_id, title, importance, deadline, monster_id, damage),
        )
        _update_main_quest_party_hp(conn, main_quest_id)
        return monster_id


def get_calendar_tasks():
    """期限日、または登録日をカレンダー表示用の日付としてタスクを取得する。"""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id AS task_id, title,
                   COALESCE(deadline, date(created_at, 'localtime')) AS event_date,
                   'main' AS task_type, status = 'cleared' AS is_completed
            FROM main_quests
            UNION ALL
            SELECT NULL AS task_id, title,
                   COALESCE(deadline, date(created_at, 'localtime')) AS event_date,
                   'sub' AS task_type, is_completed
            FROM sub_quests
            ORDER BY event_date, title
            """
        ).fetchall()


def get_sub_quests(main_quest_id):
    """指定したメインクエストのサブクエスト一覧を取得する。"""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM sub_quests
            WHERE main_quest_id = ?
            ORDER BY id ASC
            """,
            (main_quest_id,),
        ).fetchall()


def get_monsters(main_quest_id):
    """メインクエストに属する敵を表示順で取得する。"""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM quest_monsters WHERE main_quest_id = ? ORDER BY position, id",
            (main_quest_id,),
        ).fetchall()


def get_monster_by_id(monster_id):
    """敵をIDで1体取得する。"""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM quest_monsters WHERE id = ?",
            (monster_id,),
        ).fetchone()


def complete_sub_quest(sub_quest_id):
    """サブクエストを完了済みにする。"""
    with get_connection() as conn:
        conn.execute(
            "UPDATE sub_quests SET is_completed = 1, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (sub_quest_id,),
        )


def get_main_quest_by_id(main_quest_id):
    """1件のメインクエストを取得する。"""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM main_quests WHERE id = ?",
            (main_quest_id,),
        ).fetchone()


def update_monster_hp(monster_id, new_hp):
    """敵1体のHPを更新し、パーティ合計も同期する。"""
    with get_connection() as conn:
        monster = conn.execute(
            "SELECT main_quest_id FROM quest_monsters WHERE id = ?",
            (monster_id,),
        ).fetchone()
        if monster is None:
            return
        conn.execute(
            "UPDATE quest_monsters SET hp = ? WHERE id = ?",
            (max(0, new_hp), monster_id),
        )
        _update_main_quest_party_hp(conn, monster["main_quest_id"])


def _update_main_quest_party_hp(conn, main_quest_id):
    """敵のHP合計をメインクエストにも保存する。"""
    totals = conn.execute(
        """
        SELECT COALESCE(SUM(hp), 0) AS hp, COALESCE(SUM(max_hp), 0) AS max_hp
        FROM quest_monsters WHERE main_quest_id = ?
        """,
        (main_quest_id,),
    ).fetchone()
    conn.execute(
        "UPDATE main_quests SET monster_hp = ?, monster_max_hp = ? WHERE id = ?",
        (totals["hp"], totals["max_hp"], main_quest_id),
    )


def mark_main_quest_cleared(main_quest_id):
    """クエスト達成を記録する。"""
    with get_connection() as conn:
        conn.execute(
            "UPDATE main_quests SET status = 'cleared' WHERE id = ?",
            (main_quest_id,),
        )
