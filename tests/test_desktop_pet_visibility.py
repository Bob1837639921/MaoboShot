import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ui.desktop_pet import DesktopPetWindow


class DesktopPetVisibilityTests(unittest.TestCase):
    def test_hidden_pet_does_not_show_translation_bubble(self):
        pet = SimpleNamespace(
            can_show_bubble=False,
            bubble=Mock(),
            _reanchor=Mock(),
            show=Mock(),
            raise_=Mock(),
            _bubble_timer=Mock(),
        )

        DesktopPetWindow.show_bubble(pet, timeout_ms=0)

        pet.bubble.show.assert_not_called()
        pet.show.assert_not_called()

    def test_begin_translation_stays_hidden_when_pet_is_disabled(self):
        pet = SimpleNamespace(
            _enabled=False,
            hide_bubble=Mock(),
            set_state=Mock(),
        )

        DesktopPetWindow.begin_translation(pet, "hello", show_bubble=True)

        pet.hide_bubble.assert_called_once_with()
        pet.set_state.assert_not_called()

    @patch("ui.desktop_pet.save_app_config")
    @patch("ui.desktop_pet.load_app_config", return_value={"PET_ENABLED": True})
    def test_disable_pet_updates_runtime_state_immediately(self, load_config, save_config):
        pet = SimpleNamespace(
            _enabled=True,
            _idle_action_timer=Mock(),
            sprite=Mock(),
            hide_bubble=Mock(),
            hide=Mock(),
            visibility_changed=Mock(),
        )

        DesktopPetWindow.disable_pet(pet)

        self.assertFalse(pet._enabled)
        save_config.assert_called_once_with({"PET_ENABLED": False})
        pet._idle_action_timer.stop.assert_called_once_with()
        pet.sprite.stop_action.assert_called_once_with()
        pet.hide_bubble.assert_called_once_with()
        pet.hide.assert_called_once_with()
        pet.visibility_changed.emit.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
