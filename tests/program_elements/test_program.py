import pytest

from program_elements.program import (
    BooleanParameter,
    EnumParameter,
    IntegerParameter,
    Program,
    RangeParameter,
)


class StubProgram(Program):
    NAME = "stub"
    PARAMETERS = {
        "count": IntegerParameter("count", 1, 10, 5),
        "enabled": BooleanParameter("enabled", True),
        "mode": EnumParameter("mode", ["a", "b"], "a"),
        "span": RangeParameter("span", 0, 100, (10, 20)),
    }

    def __init__(self) -> None:
        super().__init__()

    def run(self) -> None:
        pass


class TestIntegerParameter:
    def test_get_default(self) -> None:
        param = IntegerParameter("x", 1, 10, 5)
        assert param.get_value() == 5

    def test_set_valid_value(self) -> None:
        param = IntegerParameter("x", 1, 10, 5)
        param.set_value(7)
        assert param.get_value() == 7

    def test_set_below_min_raises(self) -> None:
        param = IntegerParameter("x", 1, 10, 5)
        with pytest.raises(ValueError, match="out of range"):
            param.set_value(0)

    def test_set_above_max_raises(self) -> None:
        param = IntegerParameter("x", 1, 10, 5)
        with pytest.raises(ValueError, match="out of range"):
            param.set_value(11)


class TestBooleanParameter:
    def test_set_and_get(self) -> None:
        param = BooleanParameter("flag", False)
        param.set_value(True)
        assert param.get_value() is True


class TestEnumParameter:
    def test_set_valid_value(self) -> None:
        param = EnumParameter("choice", ["on", "off"], "on")
        param.set_value("off")
        assert param.get_value() == "off"

    def test_set_invalid_value_raises(self) -> None:
        param = EnumParameter("choice", ["on", "off"], "on")
        with pytest.raises(ValueError, match="Invalid value"):
            param.set_value("maybe")


class TestRangeParameter:
    def test_get_default(self) -> None:
        param = RangeParameter("range", 0, 100, (10, 20))
        assert param.get_value() == (10, 20)

    def test_set_valid_range(self) -> None:
        param = RangeParameter("range", 0, 100, (10, 20))
        param.set_value((30, 40))
        assert param.get_value() == (30, 40)

    def test_set_out_of_bounds_raises(self) -> None:
        param = RangeParameter("range", 0, 100, (10, 20))
        with pytest.raises(ValueError, match="out of range"):
            param.set_value((-1, 50))

    def test_set_min_greater_than_max_raises(self) -> None:
        param = RangeParameter("range", 0, 100, (10, 20))
        with pytest.raises(ValueError, match="min value must be less or equal to max value"):
            param.set_value((50, 30))


class TestProgram:
    def test_set_and_get_parameters(self) -> None:
        program = StubProgram()
        program.set_parameter("count", 3)
        program.set_parameter("enabled", False)
        program.set_parameter("mode", "b")
        program.set_parameter("span", (1, 2))

        assert program.get_parameter("count") == 3
        assert program.get_parameter("enabled") is False
        assert program.get_parameter("mode") == "b"
        assert program.get_parameter("span") == (1, 2)
