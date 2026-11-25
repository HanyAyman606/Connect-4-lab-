"""Top-level application window and screen router for Connect 4 vs The Devils."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QWidget

from setup.game_session import GameSession
from setup.session_settings import SessionSettings
from ui.devils import DEVILS, DevilProfile
from ui.screens.archive_screen import ArchiveScreen
from ui.screens.battle_screen import BattleScreen
from ui.screens.main_menu import MainMenuScreen
from ui.screens.map_screen import RealmMapScreen
from ui.screens.prefight_screen import PreFightScreen
from ui.screens.result_screen import EndingScreen, ResultScreen, build_fight_summary
from ui.screens.story_screen import StoryScreen
from ui.theme import Palette


class ConnectFourWindow(QMainWindow):
    """Main window hosting the complete multi-screen game flow."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Connect 4: vs The Devils")
        self.setMinimumSize(1160, 720)
        self.resize(1420, 840)

        self.setStyleSheet(
            f"QMainWindow {{ background-color: {Palette.BG_VOID.name()}; }}"
        )

        self._cleansed_ids: set[str] = set()
        self._story_seen: bool = False
        self._archive_return_target: Optional[QWidget] = None

        self._stack = QStackedWidget(self)
        self.setCentralWidget(self._stack)

        # 1. Main Menu
        self._main_menu = MainMenuScreen(self)
        self._main_menu.start_journey_requested.connect(self._on_start_journey)
        self._main_menu.open_map_requested.connect(self.show_map)
        self._main_menu.open_archive_requested.connect(lambda: self.show_archive(self._main_menu))
        self._main_menu.toggle_fullscreen_requested.connect(self.toggle_fullscreen)
        self._main_menu.quit_requested.connect(self.close)

        # 2. Brief Hero Story
        self._story_screen = StoryScreen(self)
        self._story_screen.finished_story.connect(self._on_story_finished)
        self._story_screen.back_to_menu.connect(self.show_main_menu)
        self._story_screen.toggle_fullscreen_requested.connect(self.toggle_fullscreen)

        # 3. Realm of the Three Devils (Map Hub)
        self._map_screen = RealmMapScreen(self)
        self._map_screen.devil_selected.connect(self.show_prefight)
        self._map_screen.back_to_menu.connect(self.show_main_menu)
        self._map_screen.replay_story_requested.connect(self.show_story)
        self._map_screen.open_archive_requested.connect(lambda: self.show_archive(self._map_screen))
        self._map_screen.open_ending_requested.connect(self.show_ending)
        self._map_screen.toggle_fullscreen_requested.connect(self.toggle_fullscreen)

        # 4. Devil Pre-Fight Setup & Heuristic Inspector
        self._prefight_screen = PreFightScreen(self)
        self._prefight_screen.back_to_map.connect(self.show_map)
        self._prefight_screen.start_battle_requested.connect(self.show_battle)
        self._prefight_screen.toggle_fullscreen_requested.connect(self.toggle_fullscreen)

        # 5. Connect 4 Battlefield
        self._battle_screen = BattleScreen(self)
        self._battle_screen.exit_to_map.connect(self._on_battle_exit)
        self._battle_screen.open_result_summary.connect(self._on_battle_summary)
        self._battle_screen.toggle_fullscreen_requested.connect(self.toggle_fullscreen)

        # 6. Ritual Result & Cleansing Summary
        self._result_screen = ResultScreen(self)
        self._result_screen.inspect_board_requested.connect(self._return_to_finished_battle)
        self._result_screen.rematch_requested.connect(self._rematch_from_result)
        self._result_screen.continue_to_map_requested.connect(self.show_map)
        self._result_screen.witness_ending_requested.connect(self.show_ending)
        self._result_screen.toggle_fullscreen_requested.connect(self.toggle_fullscreen)

        # 7. Golden Spirit Tree Finale (all 3 Devils cleansed)
        self._ending_screen = EndingScreen(self)
        self._ending_screen.return_to_map.connect(self.show_map)
        self._ending_screen.return_to_menu.connect(self.show_main_menu)
        self._ending_screen.open_archive.connect(lambda: self.show_archive(self._ending_screen))
        self._ending_screen.toggle_fullscreen_requested.connect(self.toggle_fullscreen)

        # 8. Experimental Report & Viva Archive
        self._archive_screen = ArchiveScreen(self)
        self._archive_screen.back_requested.connect(self._on_archive_back)
        self._archive_screen.toggle_fullscreen_requested.connect(self.toggle_fullscreen)

        self._all_screens: tuple[QWidget, ...] = (
            self._main_menu,
            self._story_screen,
            self._map_screen,
            self._prefight_screen,
            self._battle_screen,
            self._result_screen,
            self._ending_screen,
            self._archive_screen,
        )
        for screen in self._all_screens:
            self._stack.addWidget(screen)

        self.show_main_menu()

    # -------------------------------------------------------------- accessors
    @property
    def main_menu(self) -> MainMenuScreen:
        return self._main_menu

    @property
    def story_screen(self) -> StoryScreen:
        return self._story_screen

    @property
    def map_screen(self) -> RealmMapScreen:
        return self._map_screen

    @property
    def prefight_screen(self) -> PreFightScreen:
        return self._prefight_screen

    @property
    def battle_screen(self) -> BattleScreen:
        return self._battle_screen

    @property
    def result_screen(self) -> ResultScreen:
        return self._result_screen

    @property
    def ending_screen(self) -> EndingScreen:
        return self._ending_screen

    @property
    def archive_screen(self) -> ArchiveScreen:
        return self._archive_screen

    # ------------------------------------------------------------- navigation
    def _switch_to(self, target: QWidget) -> None:
        for screen in self._all_screens:
            if screen is not target and hasattr(screen, "pause_effects"):
                screen.pause_effects()
        self._stack.setCurrentWidget(target)
        if hasattr(target, "resume_effects"):
            target.resume_effects()

    def show_main_menu(self) -> None:
        self._main_menu.set_cleansed_count(len(self._cleansed_ids))
        self._switch_to(self._main_menu)

    def show_story(self) -> None:
        self._story_screen.reset_to_start()
        self._switch_to(self._story_screen)

    def show_map(self) -> None:
        self._map_screen.set_cleansed_ids(self._cleansed_ids)
        self._switch_to(self._map_screen)

    def show_prefight(self, devil_id: str) -> None:
        self._prefight_screen.load_devil(devil_id, self._cleansed_ids)
        self._switch_to(self._prefight_screen)

    def show_battle(self, devil: DevilProfile, settings: SessionSettings) -> None:
        self._battle_screen.start_match(devil, settings)
        self._switch_to(self._battle_screen)

    def show_ending(self) -> None:
        self._ending_screen.reset_finale()
        self._switch_to(self._ending_screen)

    def show_archive(self, return_to: Optional[QWidget] = None) -> None:
        self._archive_return_target = return_to or self._main_menu
        self._switch_to(self._archive_screen)

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ hooks
    def _on_start_journey(self) -> None:
        if not self._story_seen:
            self.show_story()
        else:
            self.show_map()

    def _on_story_finished(self) -> None:
        self._story_seen = True
        self.show_map()

    def _on_battle_exit(self, human_won: bool, devil_id: str) -> None:
        if human_won:
            self._cleansed_ids.add(devil_id)
        self.show_map()

    def _on_battle_summary(self, devil: DevilProfile, session: GameSession) -> None:
        summary = build_fight_summary(devil, session)
        if summary.human_won:
            self._cleansed_ids.add(devil.devil_id)
        all_cleansed = len(self._cleansed_ids) >= len(DEVILS)
        self._result_screen.show_summary(summary, all_three_cleansed=all_cleansed)
        self._switch_to(self._result_screen)

    def _return_to_finished_battle(self) -> None:
        self._switch_to(self._battle_screen)

    def _rematch_from_result(self) -> None:
        self._battle_screen.restart_match()
        self._switch_to(self._battle_screen)

    def _on_archive_back(self) -> None:
        target = self._archive_return_target or self._main_menu
        if target is self._map_screen:
            self.show_map()
        elif target is self._ending_screen:
            self.show_ending()
        else:
            self.show_main_menu()

    def closeEvent(self, event) -> None:  # noqa: N802
        for screen in self._all_screens:
            if hasattr(screen, "pause_effects"):
                screen.pause_effects()
        QApplication.quit()
        super().closeEvent(event)
