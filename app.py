
import base64
from PIL import Image, ImageDraw, ImageFont
import random
from pathlib import Path

import streamlit as st

from database import (
    add_main_quest,
    add_sub_quest,
    complete_sub_quest,
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


st.set_page_config(page_title="たすくえ", page_icon="⚔️", layout="centered")

ASSET_DIR = Path(__file__).parent / "assets"
FIELD_BACKGROUND_DATA = base64.b64encode(
    (ASSET_DIR / "field.png").read_bytes()
).decode("ascii")
st.session_state.setdefault("screen", "home")

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
                    image_path,
                    width=image_width,
                )
            st.caption(f"モンスター{index}{defeated_text}")


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
    .replace("HOME_GRASSLAND_STYLE", HOME_GRASSLAND_STYLE),
    unsafe_allow_html=True,
)

# アプリ起動時にDBを準備する
init_db()

player = get_player()
if player is None:
    st.error("プレイヤー情報を作成できませんでした。")
    st.stop()

current_level = get_level_from_exp(player["exp"])

st.title("たすくえ")
st.caption("RPGのように、やることを倒していこう")

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
                st.write(quest["description"] or "説明なし")
                if quest["deadline"]:
                    st.caption(f"期限：{quest['deadline']}")
                past_sub_quests = get_sub_quests(quest["id"])
                if past_sub_quests:
                    st.markdown("**サブクエスト**")
                    for item in past_sub_quests:
                        importance_label = IMPORTANCE_LABELS.get(
                            item["importance"], item["importance"]
                        )
                        st.write(
                            f"・{item['title']}（{importance_label}）"
                        )

    if st.button("ホームへ戻る", key="back_from_completed_quests"):
        st.session_state["screen"] = "home"
        st.rerun()
    st.stop()

if st.session_state["screen"] == "create_main_quest":
    st.subheader("メインクエストを作成")
    with st.form("create_main_quest"):
        title = st.text_input("タイトル")
        description = st.text_area("説明")
        deadline = st.date_input("期限")
        submitted = st.form_submit_button("サブタスクを追加⇒")

    if submitted:
        if title.strip():
            new_quest_id = add_main_quest(
                title.strip(), description, deadline=str(deadline)
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
            "重要度",
            ["low", "medium", "high"],
            format_func=IMPORTANCE_LABELS.get,
        )
        sub_deadline = st.date_input("期限")
        add_submitted = st.form_submit_button("サブクエストを追加")

    if add_submitted:
        if sub_title.strip():
            damage, _ = get_damage_and_exp(importance)
            add_sub_quest(
                setup_quest_id,
                sub_title.strip(),
                importance,
                deadline=str(sub_deadline),
                damage=damage,
                image_key=choose_monster_visual(),
            )
            st.rerun()
        st.warning("サブクエスト名を入力してください。")

    setup_sub_quests = get_sub_quests(setup_quest_id)
    if setup_sub_quests:
        st.markdown("**追加済みサブクエスト**")
        for item in setup_sub_quests:
            importance_label = IMPORTANCE_LABELS.get(
                item["importance"], item["importance"]
            )
            st.write(f"・{item['title']}（重要度：{importance_label}）")
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
            "重要度",
            ["low", "medium", "high"],
            format_func=IMPORTANCE_LABELS.get,
        )
        sub_deadline = st.date_input("サブクエスト期限")
        submitted = st.form_submit_button("モンスターを追加")

    if submitted:
        if sub_title.strip():
            damage, _ = get_damage_and_exp(importance)
            add_sub_quest(
                main_quest_id,
                sub_title.strip(),
                importance,
                deadline=str(sub_deadline),
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

add_task_image = ASSET_DIR / "btn02_02_g_rg.png"
if not add_task_image.exists():
    add_task_image = ASSET_DIR / "btn02_02_g_rd.png"
if add_task_image.exists():
    add_task_image_data = base64.b64encode(add_task_image.read_bytes()).decode("ascii")
    st.markdown(
        f"""
        <style>
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
st.write(selected_quest["description"] or "説明なし")

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
    for item in sub_quests:
        col_left, col_right = st.columns([4, 1])
        with col_left:
            status = "完了済み" if item["is_completed"] == 1 else "未完了"
            importance_label = IMPORTANCE_LABELS.get(
                item["importance"], item["importance"]
            )
            st.write(f"- {item['title']} ({importance_label}) / {status}")
        with col_right:
            if item["is_completed"] == 0:
                if st.button("完了", key=f"complete_{item['id']}"):
                    monster = get_monster_by_id(item["monster_id"])
                    damage = item["damage"]
                    _, gained_exp = get_damage_and_exp(item["importance"])
                    new_hp = max(0, monster["hp"] - damage)
                    update_monster_hp(monster["id"], new_hp)
                    complete_sub_quest(item["id"])

                    player_now = get_player()
                    new_exp, new_level = add_exp_and_level(player_now["exp"], gained_exp)
                    save_player(new_level, new_exp)

                    remaining_monsters = get_monsters(selected_id)
                    if remaining_monsters and all(
                        enemy["hp"] == 0 for enemy in remaining_monsters
                    ):
                        mark_main_quest_cleared(selected_id)
                        st.success("モンスターを倒した！メインクエスト達成！")
                    else:
                        st.success(f"サブクエスト完了！ {damage}ダメージ / +{gained_exp}EXP")
                    st.rerun()
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
         