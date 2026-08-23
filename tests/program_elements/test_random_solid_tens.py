from unittest.mock import MagicMock, patch

from program_elements.random_solid_tens import RandomSolidTens


def test_on_uses_default_max_duration() -> None:
    level_handler = MagicMock()
    tens = RandomSolidTens([level_handler], max_duration=30)

    with patch("program_elements.random_solid_tens.random.randint", return_value=55) as mock_randint:
        tens.on()

    mock_randint.assert_called_once_with(1, 99)
    level_handler.set_id.assert_called_once_with(55, 30, tens.setting_id)


def test_on_uses_explicit_duration_and_custom_range() -> None:
    level_handler = MagicMock()
    tens = RandomSolidTens([level_handler])
    tens.set_range((20, 40))

    with patch("program_elements.random_solid_tens.random.randint", return_value=25):
        tens.on(duration=120)

    level_handler.set_id.assert_called_once_with(25, 120, tens.setting_id)


def test_on_applies_to_all_handlers() -> None:
    handler_a = MagicMock()
    handler_b = MagicMock()
    tens = RandomSolidTens([handler_a, handler_b])

    with patch("program_elements.random_solid_tens.random.randint", side_effect=[10, 20]):
        tens.on(duration=5)

    handler_a.set_id.assert_called_once_with(10, 5, tens.setting_id)
    handler_b.set_id.assert_called_once_with(20, 5, tens.setting_id)


def test_off_unsets_all_handlers() -> None:
    handler_a = MagicMock()
    handler_b = MagicMock()
    tens = RandomSolidTens([handler_a, handler_b])

    tens.off()

    handler_a.unset.assert_called_once_with(tens.setting_id)
    handler_b.unset.assert_called_once_with(tens.setting_id)


def test_on_clamps_level_with_offset_to_0_127() -> None:
    level_handler = MagicMock()
    tens = RandomSolidTens([level_handler])
    tens.set_range((100, 100))
    tens.set_offset(50)

    with patch("program_elements.random_solid_tens.random.randint", return_value=100):
        tens.on(duration=5)

    level_handler.set_id.assert_called_once_with(127, 5, tens.setting_id)
