import pytest

from program_elements.program import (
    BooleanOutput,
    BooleanParameter,
    DigitalInput,
    EnumParameter,
    IntegerParameter,
    Program,
    RangeParameter,
    StringParameter,
    VariableOutput,
)


class StubProgram(Program):
    NAME = "stub"
    PARAMETERS = {
        "count": IntegerParameter("count", 1, 10, 5),
        "enabled": BooleanParameter("enabled", True),
        "mode": EnumParameter("mode", ["a", "b"], "a"),
        "span": RangeParameter("span", 0, 100, (10, 20)),
        "name": StringParameter("name", "default"),
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


class TestStringParameter:
    def test_get_default(self) -> None:
        param = StringParameter("name", "default")
        assert param.get_value() == "default"

    def test_set_valid_value(self) -> None:
        param = StringParameter("name", "default")
        param.set_value("non-default")
        assert param.get_value() == "non-default"

    def test_set_none_raises(self) -> None:
        param = StringParameter("name", "default")
        with pytest.raises(ValueError, match="Invalid value"):
            param.set_value(None)

    def test_set_empty_string_raises(self) -> None:
        param = StringParameter("name", "default")
        with pytest.raises(ValueError, match="Invalid value"):
            param.set_value("")


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


class TestBooleanOutput:
    def test_set_and_get(self) -> None:
        seen: list[bool] = []
        output = BooleanOutput("pump", set_fn=seen.append)
        output.set_value(True)
        assert output.get_value() is True
        assert seen == [True]
        output.set_value(False)
        assert output.get_value() is False
        assert seen == [True, False]

    def test_get_fn_override(self) -> None:
        output = BooleanOutput(
            "pump",
            set_fn=lambda _v: None,
            get_fn=lambda: True,
        )
        output.set_value(False)
        assert output.get_value() is True


class TestVariableOutput:
    def test_set_and_get(self) -> None:
        seen: list[int] = []
        output = VariableOutput("level", 0, 127, set_fn=seen.append)
        output.set_value(40)
        assert output.get_value() == 40
        assert seen == [40]

    def test_out_of_range_raises(self) -> None:
        output = VariableOutput("level", 0, 127, set_fn=lambda _v: None)
        with pytest.raises(ValueError, match="out of range"):
            output.set_value(200)


class TestDigitalInput:
    def test_get_value(self) -> None:
        inp = DigitalInput("btn", get_fn=lambda: True)
        assert inp.get_value() is True


class TestProgramIoTest:
    def test_default_io_test_sets_ready_and_waits(self) -> None:
        program = StubProgram()

        def stop_soon() -> None:
            assert program.io_ready.wait(timeout=1.0)
            program.stop()

        import threading

        stopper = threading.Thread(target=stop_soon)
        stopper.start()
        program.start_io_test()
        stopper.join(timeout=2.0)
        assert not program.io_ready.is_set()
        assert program.boolean_outputs == {}
        assert program.variable_outputs == {}
        assert program.inputs == {}

