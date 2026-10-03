
import base64
import calendar
import html
import random
from datetime import date
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
import streamlit as st

from database import (
    add_main_quest,
    add_sub_quest,
    complete_sub_quest,
    get_calendar_tasks,
    get_main_quest_by_id,
    get_main_quests,
    get_monster_by_id,
    get_monsters,
    get_player,
    get_sub_quests,
    init_db,
    mark_main_quest_cleared,
    save_player,
    update_monster_hp,
)
from player import add_exp_and_level, get_level_from_exp
from quest import IMPORTANCE_LABELS, get_damage_and_exp


st.set_page_config(page_icon="⚔️", layout="centered")

ASSET_DIR = Path(__file__).parent / "assets"
FIELD_BACKGROUND_DATA = base64.b64encode(
    (ASSET_DIR / "field.png").read_bytes()
).decode("ascii")
SUB_QUEST_FRAME_DATA = base64.b64encode(
    (ASSET_DIR / "枠2.png").read_bytes()
).decode("ascii")
SUB_QUEST_ATTACK_DATA = base64.b64encode(
    (ASSET_DIR / "攻撃.png").read_bytes()
).decode("ascii")
st.session_state.setdefault("screen", "start")

HOME_GRASSLAND_STYLE = ""
if st.session_state["screen"] == "home":
    grassland_data = base64.b64encode(
        (ASSET_DIR / "grassland.png").read_bytes()
    ).decode("ascii")
    HOME_GRASSLAND_STYLE = """
    .stApp {
        position: relative;
        isolation: isolate;
    }
    .stApp::after {
        content: "";
        position: fixed;
        inset: 0;
        z-index: 0;
        pointer-events: none;
        background-image: url("data:image/png;base64,GRASSLAND_BACKGROUND_DATA");
        background-position: center;
        background-repeat: no-repeat;
        background-size: cover;
    }
    [data-testid="stAppViewContainer"] {
        position: relative;
        z-index: 1;
    }
    """.replace("GRASSLAND_BACKGROUND_DATA", grassland_data)

CALENDAR_LAYOUT_STYLE = ""
if st.session_state["screen"] == "calendar":
    CALENDAR_LAYOUT_STYLE = """
    .block-container {
        width: 100%;
        max-width: none !important;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
    .calendar-weekdays,
    .calendar-days {
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
        gap: 2px;
    }
    .calendar-weekday {
        padding: 0.3rem 0;
        text-align: center;
        font-weight: 700;
        background: rgba(255, 255, 255, 0.82);
        border-radius: 6px;
    }
    .calendar-day {
        display: flex;
        flex-direction: column;
        min-width: 0;
        aspect-ratio: 3 / 4;
        overflow: hidden;
        padding: 3px;
        border: 1px solid rgba(70, 75, 55, 0.45);
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.84);
    }
    .calendar-day-outside {
        opacity: 0.52;
    }
    .calendar-day-today {
        border: 2px solid #d97822;
        background: rgba(255, 246, 209, 0.94);
    }
    .calendar-day-number {
        flex: 0 0 auto;
        font-size: clamp(0.65rem, 2.3vw, 1rem);
        font-weight: 700;
        line-height: 1.2;
    }
    .calendar-task-list {
        min-height: 0;
        overflow-y: auto;
        overscroll-behavior: contain;
        scrollbar-width: thin;
    }
    .calendar-task {
        margin-top: 3px;
        padding: 2px 3px;
        border-radius: 4px;
        background: rgba(94, 132, 62, 0.2);
        font-size: clamp(0.48rem, 1.65vw, 0.78rem);
        line-height: 1.25;
        overflow-wrap: anywhere;
    }
    .calendar-task a {
        display: block;
        color: inherit;
        text-decoration: none;
    }
    .calendar-task a:hover {
        text-decoration: underline;
    }
    .calendar-task-completed {
        opacity: 0.58;
        text-decoration: line-through;
    }
    @media (max-width: 480px) {
        .block-container {
            padding-left: 0.25rem;
            padding-right: 0.25rem;
        }
        .calendar-weekdays,
        .calendar-days {
            gap: 1px;
        }
        .calendar-day {
            padding: 2px;
            border-radius: 4px;
        }
        .calendar-task {
            padding: 1px 2px;
        }
    }
    """


def get_monster_visual_keys():
    """利用可能な通常モンスター画像のキーをファイル名から取得する。"""
    prefix = "monster_default_"
    return [
        path.stem.removeprefix(prefix)
        for path in sorted(ASSET_DIR.glob(f"{prefix}*.png"))
        if path.stem.removeprefix(prefix)
    ]


def choose_monster_visual():
    """現在利用できる画像の中から敵の見た目をランダムに選ぶ。"""
    visual_keys = get_monster_visual_keys()
    return random.choice(visual_keys) if visual_keys else "blue"


def get_monster_image(image_key, defeated=False):
    """敵の見た目キーから通常画像または専用の撃破画像を探す。"""
    if not defeated:
        image_path = ASSET_DIR / f"monster_default_{image_key}.png"
        if image_path.exists():
            return image_path
        return ASSET_DIR / "monster_default_blue.png"

    defeated_candidates = (
        ASSET_DIR / f"monster_defeated_{image_key}.png",
        ASSET_DIR / f"monster_{image_key}_defeated.png",
        ASSET_DIR / "monster_defeated.png",
        ASSET_DIR / "monster_defeated .png",
    )
    for image_path in defeated_candidates:
        if image_path.exists():
            return image_path
    return ASSET_DIR / f"monster_default_{image_key}.png"


@st.cache_data
def build_monster_image_with_outline(image_path):
    """モンスター画像に表示サイズで約3pxの白フチを付ける。"""
    image = Image.open(image_path).convert("RGBA")
    if image.getchannel("A").getextrema() == (255, 255):
        ImageDraw.floodfill(image, (0, 0), (0, 0, 0, 0), thresh=40)

    silhouette = image.getchannel("A").point(
        lambda alpha: 255 if alpha >= 128 else 0
    )
    expanded_silhouette = silhouette.filter(ImageFilter.MaxFilter(35))
    outline = ImageChops.subtract(expanded_silhouette, silhouette)

    outlined_image = Image.new("RGBA", image.size, (255, 255, 255, 0))
    outlined_image.putalpha(outline)
    outlined_image.alpha_composite(image)
    return outlined_image


def build_hp_bar_image(current_hp, max_hp):
    """フレーム画像にHPゲージと数値を合成する。"""
    ratio = max(0.0, min(1.0, current_hp / max_hp)) if max_hp else 0.0
    fill_color = "#b82f37" if ratio <= 0.4 else "#4aa64b"
    frame = Image.open(ASSET_DIR / "btn02_02_s_bk.png").convert("RGBA")
    bar = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(bar)
    inner_box = (4, 4, frame.width - 5, frame.height - 5)
    draw.rounded_rectangle(inner_box, radius=2, fill="#292929")

    fill_width = round((frame.width - 8) * ratio)
    if fill_width:
        draw.rounded_rectangle(
            (4, 4, min(frame.width - 5, 3 + fill_width), frame.height - 5),
            radius=2,
            fill=fill_color,
        )

    bar.alpha_composite(frame.crop((0, 0, frame.width, 4)), (0, 0))
    bar.alpha_composite(frame.crop((0, frame.height - 4, frame.width, frame.height)), (0, frame.height - 4))
    bar.alpha_composite(frame.crop((0, 4, 4, frame.height - 4)), (0, 4))
    bar.alpha_composite(frame.crop((frame.width - 4, 4, frame.width, frame.height - 4)), (frame.width - 4, 4))

    draw = ImageDraw.Draw(bar)
    text = f"{current_hp} / {max_hp}"
    font = ImageFont.load_default()
    draw.text(
        (frame.width // 2, frame.height // 2),
        text,
        font=font,
        anchor="mm",
        fill="white",
        stroke_width=1,
        stroke_fill="#202020",
    )
    return bar


def render_monster_hp_bar(current_hp, max_hp, label):
    """合計HPバーを中央に表示する。"""
    st.markdown(f"<div style='text-align:center;font-weight:700;'>{label}</div>", unsafe_allow_html=True)
    _, center_column, _ = st.columns([1, 3, 1])
    with center_column:
        st.image(build_hp_bar_image(current_hp, max_hp), width=300)


def render_monster_party(monsters):
    """敵ごとのHPバーと画像を、出現順に左から右へ表示する。"""
    if not monsters:
        st.info("敵がいません。サブクエストを追加すると敵が現れます。")
        return

    if len(monsters) >= 2:
        total_hp = sum(monster["hp"] for monster in monsters)
        total_max_hp = sum(monster["max_hp"] for monster in monsters)
        render_monster_hp_bar(total_hp, total_max_hp, "敵パーティの総HP")

    if len(monsters) == 1:
        _, monster_column, _ = st.columns([1, 2, 1])
        monster_columns = [monster_column]
    else:
        with st.container(key="monster_party_row"):
            monster_columns = st.columns(len(monsters), gap="small")

    for index, (monster, column) in enumerate(
        zip(monsters, monster_columns), start=1
    ):
        with column:
            image_path = get_monster_image(monster["image_key"], monster["hp"] <= 0)
            defeated_text = "（撃破）" if monster["hp"] <= 0 else ""
            image_width = 220 if len(monsters) == 1 else "stretch"
            st.image(
                build_hp_bar_image(monster["hp"], monster["max_hp"]),
                width=image_width,
            )
            if image_path.exists():
                st.image(
                    build_monster_image_with_outline(str(image_path)),
                    width=image_width,
                )
            st.caption(f"ドラゴン{index}{defeated_text}")


def render_optional_deadline(widget_key):
    """タスク期限を任意で設定し、未設定の場合はNoneを返す。"""
    deadline_setting = st.selectbox(
        "期限",
        ["設定しない", "設定する"],
        key=f"{widget_key}_setting",
    )
    deadline_date = st.date_input(
        "期限日（設定する場合）",
        key=f"{widget_key}_date",
    )
    return deadline_date if deadline_setting == "設定する" else None


def build_calendar_html(month):
    """指定月のタスクを、日付セルごとに表示するHTMLを作る。"""
    tasks_by_date = {}
    for task in get_calendar_tasks():
        event_date = date.fromisoformat(task["event_date"])
        tasks_by_date.setdefault(event_date, []).append(task)

    month_weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(
        month.year, month.month
    )
    weekdays = ("日", "月", "火", "水", "木", "金", "土")
    header = "".join(
        f'<div class="calendar-weekday">{weekday}</div>'
        for weekday in weekdays
    )
    cells = []
    today = date.today()
    for week in month_weeks:
        for cell_date in week:
            cell_classes = ["calendar-day"]
            if cell_date.month != month.month:
                cell_classes.append("calendar-day-outside")
            if cell_date == today:
                cell_classes.append("calendar-day-today")

            main_tasks = [
                task for task in tasks_by_date.get(cell_date, [])
                if task["task_type"] == "main"
            ]
            task_items = "".join(
                '<div class="calendar-task{}">'
                '<a href="?select_main_quest={}">{}</a></div>'.format(
                    " calendar-task-completed" if task["is_completed"] else "",
                    task["task_id"],
                    html.escape(task["title"]),
                )
                for task in main_tasks
            )
            cells.append(
                '<div class="{}">'
                '<div class="calendar-day-number">{}</div>'
                '<div class="calendar-task-list">{}</div>'
                "</div>".format(
                    " ".join(cell_classes),
                    cell_date.day,
                    task_items,
                )
            )

    return (
        '<div class="calendar-grid">'
        f'<div class="calendar-weekdays">{header}</div>'
        f'<div class="calendar-days">{"".join(cells)}</div>'
        "</div>"
    )


st.markdown(
    """
    <style>
    html, body {
        overscroll-behavior: none;
    }
    .block-container {
        max-width: 420px;
        padding-top: 1rem;
        padding-bottom: 2.5rem;
        margin: 0 auto;
    }
    .stApp {
        background-image:
            linear-gradient(rgba(255, 250, 240, 0.28), rgba(255, 250, 240, 0.18)),
            url("data:image/png;base64,FIELD_BACKGROUND_DATA");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }
    [data-testid="stAppViewContainer"] {
        background: transparent;
    }
    HOME_GRASSLAND_STYLE
    CALENDAR_LAYOUT_STYLE
    .st-key-new_quest_image_button {
        position: fixed;
        right: max(1rem, env(safe-area-inset-right));
        bottom: max(1rem, env(safe-area-inset-bottom));
        z-index: 1000;
        width: min(220px, 48vw);
    }
    .st-key-new_quest_image_button button {
        min-height: 56px;
    }
    .st-key-new_quest_image_button button a {
        color: inherit;
    }
    .stMetric {
        background: rgba(255,255,255,0.7);
        border-radius: 12px;
        padding: 0.5rem 0.4rem;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.2rem;
    }
    [data-testid="stHorizontalBlock"] {
        gap: 0.25rem;
    }
    div[data-testid="stFormSubmitButton"] button,
    div[data-testid="baseButton-secondary"] button,
    div[data-testid="baseButton-primary"] button {
        width: 100%;
        min-height: 44px;
        border-radius: 12px;
        font-size: 0.95rem;
        font-weight: 600;
    }
    input, textarea, select {
        font-size: 16px;
        border-radius: 10px;
    }
    .stProgress > div > div {
        height: 12px;
        border-radius: 999px;
    }
    .subquest-frame {
        display: flex;
        min-height: 120px;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
        padding: 12px 18px;
        aspect-ratio: 1626 / 967;
        text-align: center;
        background-image: url("data:image/png;base64,SUB_QUEST_FRAME_DATA");
        background-repeat: no-repeat;
        background-position: center;
        background-size: 100% 100%;
        overflow-wrap: anywhere;
    }
    .subquest-frame-title {
        margin: 0;
        font-weight: 700;
    }
    .subquest-frame-details {
        margin: 3px 0 0;
        font-size: 0.82rem;
    }
    [class*="st-key-subquest_action_"] button {
        width: 56px;
        min-height: 56px;
        padding: 0;
        border: 0;
        border-radius: 0;
        background-color: transparent;
        background-image: url("data:image/png;base64,SUB_QUEST_ATTACK_DATA");
        background-repeat: no-repeat;
        background-position: center;
        background-size: contain;
        box-shadow: none;
        color: transparent;
        font-size: 0;
    }
    [class*="st-key-subquest_action_"] button:hover,
    [class*="st-key-subquest_action_"] button:focus,
    [class*="st-key-subquest_action_"] button:active {
        border: 0;
        background-color: transparent;
        filter: brightness(1.08);
    }
    @media (max-width: 480px) {
        .st-key-monster_party_row [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important;
        }
        .st-key-monster_party_row [data-testid="column"] {
            min-width: 0 !important;
        }
    }
    @media (max-width: 480px) {
        .block-container {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
        .stMetric {
            padding: 0.4rem 0.2rem;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.1rem;
        }
        h1 {
            font-size: 2rem;
        }
    }
    </style>
    """
    .replace("FIELD_BACKGROUND_DATA", FIELD_BACKGROUND_DATA)
    .replace("SUB_QUEST_FRAME_DATA", SUB_QUEST_FRAME_DATA)
    .replace("SUB_QUEST_ATTACK_DATA", SUB_QUEST_ATTACK_DATA)
    .replace("HOME_GRASSLAND_STYLE", HOME_GRASSLAND_STYLE)
    .replace("CALENDAR_LAYOUT_STYLE", CALENDAR_LAYOUT_STYLE),
    unsafe_allow_html=True,
)

# アプリ起動時にDBを準備する
init_db()

requested_quest_id = st.query_params.get("select_main_quest")
if requested_quest_id is not None:
    if not requested_quest_id.isdecimal():
        st.error("選択されたメインタスクの指定が正しくありません。")
        st.stop()
    requested_quest = get_main_quest_by_id(int(requested_quest_id))
    if requested_quest is None:
        st.error("選択されたメインタスクが見つかりません。")
        st.stop()
    st.session_state["selected_quest_id"] = requested_quest["id"]
    st.session_state["screen"] = "home"
    del st.query_params["select_main_quest"]
    st.rerun()

player = get_player()
if player is None:
    st.error("プレイヤー情報を作成できませんでした。")
    st.stop()

current_level = get_level_from_exp(player["exp"])

if st.session_state["screen"] == "start":
    logo_path = ASSET_DIR / "ロゴ.png"
    start_frame_data = base64.b64encode(
        (ASSET_DIR / "枠1.png").read_bytes()
    ).decode("ascii")
    st.markdown(
        f"""
        <style>
        .st-key-start_screen {{
            position: fixed;
            inset: 0;
            z-index: 2;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .st-key-start_screen > div {{
            width: min(100%, 420px);
        }}
        .st-key-start_screen [data-testid="stImage"] {{
            display: flex;
            justify-content: center;
        }}
        .st-key-start_screen [data-testid="stButton"] button {{
            width: min(100%, 280px);
            aspect-ratio: 1619 / 971;
            min-height: 0;
            padding: 0;
            border: 0;
            border-radius: 0;
            background-color: transparent;
            background-image: url("data:image/png;base64,{start_frame_data}");
            background-size: 100% 100%;
            color: #2f241d;
            font-family: "Yu Mincho", "Hiragino Mincho ProN", "Noto Serif JP", serif;
            font-size: 1.6rem;
            font-weight: 600;
            box-shadow: none;
        }}
        .st-key-start_screen [data-testid="stButton"] button:hover {{
            border: 0;
            background-color: transparent;
            filter: brightness(1.08);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="start_screen"):
        _, center_column, _ = st.columns([1, 3, 1])
        with center_column:
            st.image(logo_path, width=280)
            if st.button("スタート", key="start_game", use_container_width=True):
                st.session_state["screen"] = "home"
                st.rerun()
    st.stop()

if st.session_state["screen"] == "calendar":
    st.subheader("カレンダー")
    st.session_state.setdefault("calendar_month", date.today().replace(day=1))
    calendar_month = st.session_state["calendar_month"]

    previous_column, month_column, next_column, today_column = st.columns(
        [1, 4, 1, 1]
    )
    with previous_column:
        if st.button("‹", key="calendar_previous_month"):
            if calendar_month.month == 1:
                calendar_month = date(calendar_month.year - 1, 12, 1)
            else:
                calendar_month = date(
                    calendar_month.year, calendar_month.month - 1, 1
                )
            st.session_state["calendar_month"] = calendar_month
            st.rerun()
    with month_column:
        st.markdown(
            f"### {calendar_month.year}年{calendar_month.month}月"
        )
    with next_column:
        if st.button("›", key="calendar_next_month"):
            if calendar_month.month == 12:
                calendar_month = date(calendar_month.year + 1, 1, 1)
            else:
                calendar_month = date(
                    calendar_month.year, calendar_month.month + 1, 1
                )
            st.session_state["calendar_month"] = calendar_month
            st.rerun()
    with today_column:
        if st.button("今月", key="calendar_current_month"):
            st.session_state["calendar_month"] = date.today().replace(day=1)
            st.rerun()

    st.markdown(build_calendar_html(calendar_month), unsafe_allow_html=True)
    if st.button("ホームへ戻る", key="back_from_calendar"):
        st.session_state["screen"] = "home"
        st.rerun()
    st.stop()

if st.session_state["screen"] == "completed_quests":
    st.subheader("達成済みメインクエスト")
    completed_quests = [
        quest for quest in get_main_quests() if quest["status"] == "cleared"
    ]

    if not completed_quests:
        st.info("達成済みのメインクエストはまだありません。")
    else:
        for quest in completed_quests:
            with st.expander(quest["title"]):
                if quest["deadline"]:
                    st.caption(f"期限：{quest['deadline']}")
                past_sub_quests = get_sub_quests(quest["id"])
                if past_sub_quests:
                    st.markdown("**サブクエスト**")
                    for item in past_sub_quests:
                        st.write(
                            f"・{item['title']}（攻撃力：{item['damage']}）"
                        )

    if st.button("ホームへ戻る", key="back_from_completed_quests"):
        st.session_state["screen"] = "home"
        st.rerun()
    st.stop()

if st.session_state["screen"] == "create_main_quest":
    st.subheader("メインクエストを作成")
    with st.form("create_main_quest"):
        title = st.text_input("タイトル")
        deadline = render_optional_deadline("main_quest_deadline")
        submitted = st.form_submit_button("サブタスクを追加⇒")

    if submitted:
        if title.strip():
            new_quest_id = add_main_quest(
                title.strip(),
                deadline=str(deadline) if deadline else None,
            )
            st.session_state["screen"] = "create_sub_quests"
            st.session_state["setup_quest_id"] = new_quest_id
            st.rerun()
        st.warning("タイトルを入力してください。")

    if st.button("ホームへ戻る", key="back_to_home"):
        st.session_state["screen"] = "home"
        st.rerun()
    st.stop()

if st.session_state["screen"] == "create_sub_quests":
    setup_quest_id = st.session_state.get("setup_quest_id")
    setup_quest = get_main_quest_by_id(setup_quest_id) if setup_quest_id else None
    if setup_quest is None:
        st.error("設定するメインクエストが見つかりません。")
        st.session_state["screen"] = "home"
        st.stop()

    st.subheader("サブクエストを設定")
    st.write(f"メインクエスト：{setup_quest['title']}")
    st.caption("大きなタスクを、取り組みやすい作業に分けて登録しましょう。")

    with st.form("setup_sub_quest"):
        sub_title = st.text_input("サブクエスト名")
        importance = st.selectbox(
            "攻撃力",
            ["low", "medium", "high"],
            format_func=IMPORTANCE_LABELS.get,
        )
        sub_deadline = render_optional_deadline("setup_sub_quest_deadline")
        add_submitted = st.form_submit_button("サブクエストを追加")

    if add_submitted:
        if sub_title.strip():
            damage, _ = get_damage_and_exp(importance)
            add_sub_quest(
                setup_quest_id,
                sub_title.strip(),
                importance,
                deadline=str(sub_deadline) if sub_deadline else None,
                damage=damage,
                image_key=choose_monster_visual(),
            )
            st.rerun()
        st.warning("サブクエスト名を入力してください。")

    setup_sub_quests = get_sub_quests(setup_quest_id)
    if setup_sub_quests:
        st.markdown("**追加済みサブクエスト**")
        for item in setup_sub_quests:
            st.write(f"・{item['title']}（攻撃力：{item['damage']}）")
    else:
        st.info("サブクエストは後から追加することもできます。")

    if st.button("設定完了してホームへ", key="finish_sub_quest_setup"):
        st.session_state["screen"] = "home"
        st.session_state["selected_quest_id"] = setup_quest_id
        st.rerun()
    st.stop()

if st.session_state["screen"] == "add_monster":
    main_quest_id = st.session_state.get("selected_quest_id")
    main_quest = get_main_quest_by_id(main_quest_id) if main_quest_id else None
    if main_quest is None:
        st.error("モンスターを追加するメインクエストが見つかりません。")
        st.session_state["screen"] = "home"
        st.stop()

    st.subheader("モンスター追加")
    st.write(f"メインクエスト：{main_quest['title']}")
    with st.form("add_monster_sub_quest"):
        sub_title = st.text_input("サブクエスト名")
        importance = st.selectbox(
            "攻撃力",
            ["low", "medium", "high"],
            format_func=IMPORTANCE_LABELS.get,
        )
        sub_deadline = render_optional_deadline("monster_sub_quest_deadline")
        submitted = st.form_submit_button("モンスターを追加")

    if submitted:
        if sub_title.strip():
            damage, _ = get_damage_and_exp(importance)
            add_sub_quest(
                main_quest_id,
                sub_title.strip(),
                importance,
                deadline=str(sub_deadline) if sub_deadline else None,
                damage=damage,
                image_key=choose_monster_visual(),
                summon_new=True,
            )
            st.session_state["screen"] = "home"
            st.rerun()
        st.warning("サブクエスト名を入力してください。")

    if st.button("ホームへ戻る", key="cancel_add_monster"):
        st.session_state["screen"] = "home"
        st.rerun()
    st.stop()

st.markdown(f"**今日：{date.today().strftime('%Y/%m/%d')}**")
if st.button("カレンダー", key="open_calendar", use_container_width=True):
    st.session_state["screen"] = "calendar"
    st.rerun()

add_task_image = ASSET_DIR / "btn02_02_g_rg.png"
if not add_task_image.exists():
    add_task_image = ASSET_DIR / "btn02_02_g_rd.png"
if add_task_image.exists():
    add_task_image_data = base64.b64encode(add_task_image.read_bytes()).decode("ascii")
    st.markdown(
        f"""
        <style>
        .block-container {{
            padding-bottom: 6rem;
        }}
        .st-key-new_quest_image_button button,
        .st-key-add_monster_image_button button,
        .st-key-completed_quests_button button {{
            min-height: 64px;
            padding: 0;
            border: 0;
            border-radius: 8px;
            background-color: transparent;
            background-image: url('data:image/png;base64,{add_task_image_data}');
            background-size: 100% 100%;
            background-position: center;
            color: #fff4ce;
            font-size: 1.1rem;
            font-weight: 700;
            text-shadow: 0 1px 3px #30120e;
            box-shadow: none;
        }}
        .st-key-new_quest_image_button button:hover,
        .st-key-add_monster_image_button button:hover,
        .st-key-completed_quests_button button:hover {{
            color: #ffffff;
            border: 0;
            filter: brightness(1.12);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="new_quest_image_button"):
        if st.button("新タスク追加", key="go_to_create_main_quest", use_container_width=True):
            st.session_state["screen"] = "create_main_quest"
            st.rerun()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("レベル", current_level)
with col2:
    st.metric("EXP", f"{player['exp']} / {current_level * 100}")
with col3:
    st.metric("クエスト数", len(get_main_quests()))

main_quests = get_main_quests()
if not main_quests:
    st.info("「新タスク追加」から、最初のメインクエストを作成してください。")
    st.stop()

quest_ids = [quest["id"] for quest in main_quests]
default_quest_index = 0
if st.session_state.get("selected_quest_id") in quest_ids:
    default_quest_index = quest_ids.index(st.session_state["selected_quest_id"])

selected_id = st.selectbox(
    "進めるクエスト",
    options=quest_ids,
    format_func=lambda qid: next(q["title"] for q in main_quests if q["id"] == qid),
    index=default_quest_index,
)

selected_quest = get_main_quest_by_id(selected_id)

st.subheader(selected_quest["title"])

monsters = get_monsters(selected_id)
render_monster_party(monsters)

with st.container(key="add_monster_image_button"):
    if st.button(
        "モンスター追加",
        key="open_add_monster",
        use_container_width=True,
    ):
        st.session_state["selected_quest_id"] = selected_id
        st.session_state["screen"] = "add_monster"
        st.rerun()

sub_quests = get_sub_quests(selected_id)
if sub_quests:
    st.subheader("サブクエスト一覧")
    with st.container(height=440 if len(sub_quests) >= 3 else "content"):
        for item in sub_quests:
            action_column, frame_column = st.columns([1, 5], gap="small")
            with action_column:
                if item["is_completed"] == 1:
                    st.image(ASSET_DIR / "完了.png", width=56)
                else:
                    if st.button(
                        "攻撃",
                        key=f"subquest_action_{item['id']}",
                        help="サブタスクを完了",
                    ):
                        monster = get_monster_by_id(item["monster_id"])
                        damage = item["damage"]
                        _, gained_exp = get_damage_and_exp(item["importance"])
                        new_hp = max(0, monster["hp"] - damage)
                        update_monster_hp(monster["id"], new_hp)
                        complete_sub_quest(item["id"])

                        player_now = get_player()
                        new_exp, new_level = add_exp_and_level(
                            player_now["exp"], gained_exp
                        )
                        save_player(new_level, new_exp)

                        remaining_monsters = get_monsters(selected_id)
                        if remaining_monsters and all(
                            enemy["hp"] == 0 for enemy in remaining_monsters
                        ):
                            mark_main_quest_cleared(selected_id)
                            st.success("モンスターを倒した！メインクエスト達成！")
                        else:
                            st.success(
                                f"サブクエスト完了！ {damage}ダメージ / +{gained_exp}EXP"
                            )
                        st.rerun()
            with frame_column:
                st.markdown(
                    '<div class="subquest-frame">'
                    f'<p class="subquest-frame-title">{html.escape(item["title"])}</p>'
                    f'<p class="subquest-frame-details">'
                    f'攻撃力：{item["damage"]}'
                    "</p></div>",
                    unsafe_allow_html=True,
                )
else:
    st.info("まだサブクエストがありません。追加して進めましょう。")

with st.container(key="completed_quests_button"):
    if st.button(
        "達成済みメインクエストを見る",
        key="go_to_completed_quests",
        use_container_width=True,
    ):
        st.session_state["screen"] = "completed_quests"
        st.rerun()
         