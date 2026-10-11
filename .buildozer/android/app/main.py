import calendar
import random
import sqlite3
from datetime import date
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex

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
    set_db_path,
    update_monster_hp,
)
from player import add_exp_and_level, get_level_from_exp
from quest import IMPORTANCE_LABELS, get_damage_and_exp


ASSET_DIR = Path(__file__).parent / "assets"
BACKGROUND_COLOR = get_color_from_hex("#fffaf0")
TEXT_COLOR = get_color_from_hex("#2f241d")


def choose_monster_visual():
    """利用可能な通常モンスター画像からランダムに選ぶ。"""
    prefix = "monster_default_"
    visual_keys = [
        path.stem.removeprefix(prefix)
        for path in sorted(ASSET_DIR.glob(f"{prefix}*.png"))
    ]
    return random.choice(visual_keys) if visual_keys else "blue"


def get_monster_image(image_key, defeated=False):
    if not defeated:
        image_path = ASSET_DIR / f"monster_default_{image_key}.png"
        if image_path.exists():
            return image_path
        return ASSET_DIR / "monster_default_blue.png"

    for image_path in (
        ASSET_DIR / f"monster_defeated_{image_key}.png",
        ASSET_DIR / f"monster_{image_key}_defeated.png",
        ASSET_DIR / "monster_defeated.png",
        ASSET_DIR / "monster_defeated .png",
    ):
        if image_path.exists():
            return image_path
    return ASSET_DIR / f"monster_default_{image_key}.png"


class QuestApp(App):
    title = "クエスト冒険"

    def build(self):
        Window.clearcolor = BACKGROUND_COLOR
        self.root = FloatLayout()
        self.screen_name = "loading"
        self.selected_quest_id = None
        self.setup_quest_id = None
        self.calendar_month = date.today().replace(day=1)
        self.message = ""

        loading = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            size_hint=(None, None),
            size=(dp(280), dp(320)),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        loading.add_widget(
            Image(
                source=str(ASSET_DIR / "ローディング.png"),
                allow_stretch=True,
                keep_ratio=True,
            )
        )
        loading.add_widget(self.make_label("読み込み中…", height=dp(44)))
        self.root.add_widget(loading)
        Clock.schedule_once(self.initialize_app, 0)
        return self.root

    def initialize_app(self, _dt):
        try:
            set_db_path(Path(self.user_data_dir) / "quest_app.db")
            init_db()
        except (OSError, sqlite3.Error) as error:
            self.show_initialization_error(error)
            return
        self.show_screen("start")

    def show_initialization_error(self, error):
        self.root.clear_widgets()
        panel = BoxLayout(
            orientation="vertical",
            padding=dp(24),
            spacing=dp(16),
            size_hint=(1, 1),
        )
        panel.add_widget(self.make_label("データベースを開けませんでした。"))
        panel.add_widget(self.make_label(str(error), height=dp(100)))
        self.root.add_widget(panel)

    @staticmethod
    def make_label(text, height=dp(42), font_size=dp(16), bold=False):
        return Label(
            text=str(text),
            size_hint_y=None,
            height=height,
            color=TEXT_COLOR,
            font_size=font_size,
            bold=bold,
            halign="center",
            valign="middle",
            text_size=(Window.width - dp(40), None),
        )

    def make_button(self, text, callback, height=dp(48)):
        button = Button(
            text=text,
            size_hint_y=None,
            height=height,
            background_normal="",
            background_down="",
            background_color=get_color_from_hex("#d97706"),
            color=(1, 1, 1, 1),
            font_size=dp(16),
        )
        button.bind(on_release=lambda _button: callback())
        return button

    def make_input(self, hint, multiline=False):
        return TextInput(
            hint_text=hint,
            multiline=multiline,
            size_hint_y=None,
            height=dp(48 if not multiline else 90),
            padding=(dp(12), dp(12)),
            font_size=dp(16),
            foreground_color=TEXT_COLOR,
            background_normal="",
            background_active="",
            background_color=(1, 1, 1, 0.9),
        )

    def make_content(self):
        content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(10),
            padding=(dp(12), dp(12)),
        )
        content.bind(minimum_height=content.setter("height"))
        return content

    def add_section(self, parent, text):
        parent.add_widget(
            self.make_label(text, height=dp(48), font_size=dp(20), bold=True)
        )

    def show_screen(self, screen_name):
        self.screen_name = screen_name
        self.root.clear_widgets()
        background_name = (
            "grassland.png" if screen_name == "home" else "field.png"
        )
        self.root.add_widget(
            Image(
                source=str(ASSET_DIR / background_name),
                fit_mode="cover",
                size_hint=(1, 1),
            )
        )

        page = BoxLayout(
            orientation="vertical",
            padding=(dp(12), dp(8)),
            spacing=dp(8),
            size_hint=(1, 1),
        )
        self.root.add_widget(page)
        if screen_name != "start":
            page.add_widget(
                self.make_button("⌂ ホーム", lambda: self.show_screen("home"))
            )

        if screen_name == "start":
            self.render_start(page)
        else:
            scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
            self.content = self.make_content()
            scroll.add_widget(self.content)
            page.add_widget(scroll)
            renderer = {
                "home": self.render_home,
                "create_main": self.render_create_main,
                "setup_sub": self.render_setup_sub,
                "add_monster": self.render_add_monster,
                "calendar": self.render_calendar,
                "completed": self.render_completed,
            }.get(screen_name)
            if renderer is None:
                self.show_screen("home")
                return
            renderer(self.content)

    def render_start(self, page):
        page.add_widget(Label())
        page.add_widget(
            Image(
                source=str(ASSET_DIR / "ロゴ.png"),
                size_hint=(1, None),
                height=dp(300),
                allow_stretch=True,
                keep_ratio=True,
            )
        )
        page.add_widget(
            self.make_button("スタート", lambda: self.show_screen("home"))
        )
        page.add_widget(Label())

    def render_home(self, content):
        player = get_player()
        if player is None:
            content.add_widget(self.make_label("プレイヤー情報が見つかりません。"))
            return

        level = get_level_from_exp(player["exp"])
        self.add_section(content, "クエスト冒険")
        content.add_widget(
            self.make_label(
                f"レベル {level}　 EXP {player['exp']} / {level * 100}",
                height=dp(48),
                bold=True,
            )
        )
        content.add_widget(
            self.make_button("新しいメインクエスト", lambda: self.show_screen("create_main"))
        )
        content.add_widget(
            self.make_button("カレンダー", lambda: self.show_screen("calendar"))
        )
        content.add_widget(
            self.make_button("達成済みクエスト", lambda: self.show_screen("completed"))
        )
        if self.message:
            content.add_widget(
                self.make_label(self.message, height=dp(52), bold=True)
            )
            self.message = ""

        quests = get_main_quests()
        content.add_widget(
            self.make_label(f"メインクエスト：{len(quests)}件", bold=True)
        )
        if not quests:
            content.add_widget(
                self.make_label("「新しいメインクエスト」から登録してください。")
            )
            return

        quest_ids = [quest["id"] for quest in quests]
        if self.selected_quest_id not in quest_ids:
            self.selected_quest_id = quest_ids[0]
        selected = get_main_quest_by_id(self.selected_quest_id)
        if selected is None:
            self.selected_quest_id = quests[0]["id"]
            selected = quests[0]
        selector = Spinner(
            text=selected["title"],
            values=[quest["title"] for quest in quests],
            size_hint_y=None,
            height=dp(48),
            background_normal="",
            background_color=get_color_from_hex("#fff4ce"),
            color=TEXT_COLOR,
        )

        def select_quest(_spinner, title):
            matching_quest = next(
                (quest for quest in quests if quest["title"] == title), None
            )
            if matching_quest:
                self.selected_quest_id = matching_quest["id"]
                self.show_screen("home")

        selector.bind(text=select_quest)
        content.add_widget(selector)
        content.add_widget(
            self.make_label(
                selected["title"],
                height=dp(48),
                font_size=dp(20),
                bold=True,
            )
        )

        monsters = get_monsters(selected["id"])
        if monsters:
            total_hp = sum(monster["hp"] for monster in monsters)
            total_max_hp = sum(monster["max_hp"] for monster in monsters)
            if len(monsters) > 1:
                self.add_hp_bar(
                    content, total_hp, total_max_hp, "敵パーティの総HP"
                )
            for index, monster in enumerate(monsters, start=1):
                self.add_hp_bar(
                    content,
                    monster["hp"],
                    monster["max_hp"],
                    f"ドラゴン{index}"
                    + ("（撃破）" if monster["hp"] <= 0 else ""),
                )
                image_path = get_monster_image(
                    monster["image_key"], monster["hp"] <= 0
                )
                if image_path.exists():
                    content.add_widget(
                        Image(
                            source=str(image_path),
                            size_hint_y=None,
                            height=dp(170),
                            allow_stretch=True,
                            keep_ratio=True,
                        )
                    )
        else:
            content.add_widget(
                self.make_label("敵がいません。サブクエストを追加しましょう。")
            )
        content.add_widget(
            self.make_button(
                "モンスターを追加",
                lambda: self.show_screen("add_monster"),
            )
        )

        sub_quests = get_sub_quests(selected["id"])
        self.add_section(content, "サブクエスト一覧")
        if not sub_quests:
            content.add_widget(
                self.make_label("まだサブクエストがありません。")
            )
        for item in sub_quests:
            details = f"{item['title']}　攻撃力：{item['damage']}"
            if item["deadline"]:
                details += f"　期限：{item['deadline']}"
            content.add_widget(
                self.make_label(
                    details,
                    height=dp(58),
                    font_size=dp(14),
                )
            )
            if item["is_completed"]:
                content.add_widget(
                    self.make_label("✓ 完了", height=dp(34), bold=True)
                )
            else:
                content.add_widget(
                    self.make_button(
                        "攻撃して完了",
                        lambda sub_quest=item: self.complete_quest(
                            sub_quest, selected["id"]
                        ),
                    )
                )

    def add_hp_bar(self, parent, hp, max_hp, label):
        parent.add_widget(self.make_label(f"{label}　{hp} / {max_hp}"))
        bar = ProgressBar(
            max=max_hp or 1,
            value=max(0, min(hp, max_hp)) if max_hp else 0,
            size_hint_y=None,
            height=dp(18),
        )
        parent.add_widget(bar)

    def complete_quest(self, item, main_quest_id):
        monster = get_monster_by_id(item["monster_id"])
        if monster is None:
            self.message = "担当モンスターが見つかりませんでした。"
            self.show_screen("home")
            return
        damage = item["damage"]
        _, gained_exp = get_damage_and_exp(item["importance"])
        update_monster_hp(monster["id"], max(0, monster["hp"] - damage))
        complete_sub_quest(item["id"])

        player = get_player()
        if player is None:
            self.message = "プレイヤー情報が見つかりませんでした。"
            self.show_screen("home")
            return
        new_exp, new_level = add_exp_and_level(player["exp"], gained_exp)
        save_player(new_level, new_exp)

        monsters = get_monsters(main_quest_id)
        if monsters and all(enemy["hp"] == 0 for enemy in monsters):
            mark_main_quest_cleared(main_quest_id)
            self.message = "モンスターを倒しました！メインクエスト達成！"
        else:
            self.message = f"サブクエスト完了！ {damage}ダメージ / +{gained_exp}EXP"
        self.show_screen("home")

    @staticmethod
    def parse_deadline(value):
        value = value.strip()
        if not value:
            return None
        return date.fromisoformat(value).isoformat()



    def create_main_quest(self, title_input, deadline_input):
        title = title_input.text.strip()
        if not title:
            self.message = "タイトルを入力してください。"
            self.show_screen("create_main")
            return
        try:
            deadline = self.parse_deadline(deadline_input.text)
        except ValueError:
            self.message = "期限は YYYY-MM-DD 形式で入力してください。"
            self.show_screen("create_main")
            return
        self.setup_quest_id = add_main_quest(title, deadline=deadline)
        self.show_screen("setup_sub")

    def render_sub_quest_form(self, content, main_quest_id, summon_new):
        quest = get_main_quest_by_id(main_quest_id)
        if quest is None:
            content.add_widget(
                self.make_label("メインクエストが見つかりませんでした。")
            )
            return
        self.add_section(
            content,
            "モンスターを追加" if summon_new else "サブクエストを設定",
        )
        content.add_widget(self.make_label(f"メインクエスト：{quest['title']}"))
        title_input = self.make_input("サブクエスト名")
        deadline_input = self.make_input("期限（任意・YYYY-MM-DD）")
        content.add_widget(title_input)
        content.add_widget(deadline_input)
        importance = Spinner(
            text=IMPORTANCE_LABELS["medium"],
            values=list(IMPORTANCE_LABELS.values()),
            size_hint_y=None,
            height=dp(48),
            background_normal="",
            background_color=get_color_from_hex("#fff4ce"),
            color=TEXT_COLOR,
        )
        content.add_widget(importance)
        content.add_widget(
            self.make_button(
                "モンスターを追加" if summon_new else "サブクエストを追加",
                lambda: self.add_sub_quest_from_form(
                    title_input,
                    deadline_input,
                    importance,
                    main_quest_id,
                    summon_new,
                ),
            )
        )
        if not summon_new:
            existing = get_sub_quests(main_quest_id)
            if existing:
                self.add_section(content, "追加済みサブクエスト")
                for item in existing:
                    content.add_widget(
                        self.make_label(
                            f"{item['title']}（攻撃力：{item['damage']}）"
                        )
                    )

    def add_sub_quest_from_form(
        self, title_input, deadline_input, importance_spinner, main_quest_id, summon_new
    ):
        title = title_input.text.strip()
        if not title:
            self.message = "サブクエスト名を入力してください。"
            self.show_screen("add_monster" if summon_new else "setup_sub")
            return
        try:
            deadline = self.parse_deadline(deadline_input.text)
        except ValueError:
            self.message = "期限は YYYY-MM-DD 形式で入力してください。"
            self.show_screen("add_monster" if summon_new else "setup_sub")
            return
        importance = next(
            key
            for key, label in IMPORTANCE_LABELS.items()
            if label == importance_spinner.text
        )
        damage, _ = get_damage_and_exp(importance)
        add_sub_quest(
            main_quest_id,
            title,
            importance,
            deadline=deadline,
            damage=damage,
            image_key=choose_monster_visual(),
            summon_new=summon_new,
        )
        self.message = "モンスターを追加しました。" if summon_new else "追加しました。"
        self.show_screen("home" if summon_new else "setup_sub")

    def render_create_main(self, content):
        self.add_section(content, "メインクエストを作成")
        if self.message:
            content.add_widget(self.make_label(self.message, bold=True))
            self.message = ""
        title_input = self.make_input("タイトル")
        deadline_input = self.make_input("期限（任意・YYYY-MM-DD）")
        content.add_widget(title_input)
        content.add_widget(deadline_input)
        content.add_widget(
            self.make_button(
                "サブクエストを設定",
                lambda: self.create_main_quest(title_input, deadline_input),
            )
        )

    def render_setup_sub(self, content):
        if self.message:
            content.add_widget(self.make_label(self.message, bold=True))
            self.message = ""
        self.render_sub_quest_form(content, self.setup_quest_id, False)
        content.add_widget(
            self.make_button(
                "設定完了してホームへ",
                lambda: self.finish_sub_quest_setup(),
            )
        )

    def finish_sub_quest_setup(self):
        self.selected_quest_id = self.setup_quest_id
        self.message = ""
        self.show_screen("home")

    def render_add_monster(self, content):
        if self.message:
            content.add_widget(self.make_label(self.message, bold=True))
            self.message = ""
        self.render_sub_quest_form(content, self.selected_quest_id, True)

    def render_calendar(self, content):
        month = self.calendar_month
        self.add_section(content, f"{month.year}年{month.month}月")
        navigation = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(48),
            spacing=dp(8),
        )
        navigation.add_widget(
            self.make_button("‹ 前月", self.previous_month)
        )
        navigation.add_widget(
            self.make_button("今月", self.current_month)
        )
        navigation.add_widget(
            self.make_button("次月 ›", self.next_month)
        )
        content.add_widget(navigation)

        tasks_by_date = {}
        for task in get_calendar_tasks():
            task_date = date.fromisoformat(task["event_date"])
            if task_date.year == month.year and task_date.month == month.month:
                tasks_by_date.setdefault(task_date, []).append(task)
        month_days = calendar.monthrange(month.year, month.month)[1]
        if not tasks_by_date:
            content.add_widget(self.make_label("今月のタスクはありません。"))
        for day in range(1, month_days + 1):
            task_date = date(month.year, month.month, day)
            tasks = tasks_by_date.get(task_date, [])
            if not tasks:
                continue
            self.add_section(
                content,
                f"{month.year}/{month.month:02d}/{day:02d} "
                f"{'月火水木金土日'[task_date.weekday()]}",
            )
            for task in tasks:
                if task["task_type"] == "main":
                    content.add_widget(
                        self.make_button(
                            f"{'✓ ' if task['is_completed'] else ''}{task['title']}",
                            lambda quest_id=task["task_id"]: self.open_quest(
                                quest_id
                            ),
                            height=dp(42),
                        )
                    )
                else:
                    prefix = "✓ " if task["is_completed"] else "・"
                    content.add_widget(
                        self.make_label(f"{prefix}{task['title']}", height=dp(36))
                    )

    def previous_month(self):
        month = self.calendar_month
        self.calendar_month = (
            date(month.year - 1, 12, 1)
            if month.month == 1
            else date(month.year, month.month - 1, 1)
        )
        self.show_screen("calendar")

    def next_month(self):
        month = self.calendar_month
        self.calendar_month = (
            date(month.year + 1, 1, 1)
            if month.month == 12
            else date(month.year, month.month + 1, 1)
        )
        self.show_screen("calendar")

    def current_month(self):
        self.calendar_month = date.today().replace(day=1)
        self.show_screen("calendar")

    def open_quest(self, quest_id):
        self.selected_quest_id = quest_id
        self.show_screen("home")

    def render_completed(self, content):
        self.add_section(content, "達成済みメインクエスト")
        completed = [
            quest for quest in get_main_quests()
            if quest["status"] == "cleared"
        ]
        if not completed:
            content.add_widget(
                self.make_label("達成済みのメインクエストはまだありません。")
            )
            return
        for quest in completed:
            title = f"✓ {quest['title']}"
            if quest["deadline"]:
                title += f"\n期限：{quest['deadline']}"
            content.add_widget(
                self.make_label(title, height=dp(58), bold=True)
            )
            for item in get_sub_quests(quest["id"]):
                content.add_widget(
                    self.make_label(
                        f"・{item['title']}（攻撃力：{item['damage']}）",
                        height=dp(36),
                        font_size=dp(14),
                    )
                )


if __name__ == "__main__":
    QuestApp().run()
