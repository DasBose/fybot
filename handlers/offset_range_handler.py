class OffsetRangeHandler():
    """A handler for maintaining a set range with a varying offset."""

    def __init__(self, name: str, range: tuple[int, int], min: int, max: int) -> None:
        self.name = name
        self.range = range
        self.min = min
        self.max = max
        self.offset = 0

    def set_offset(self, offset: int) -> None:
        self.offset = offset
    
    def increment_offset(self, increment: int) -> None:
        self.offset += increment
    
    def get_range(self) -> tuple[int, int]:
        current_min = self.range[0] + self.offset
        current_min = max(min(current_min, self.max), self.min)
        current_max = self.range[1] + self.offset
        current_max = min(max(current_max, self.min), self.max)
        current_max = max(current_min, current_max)
        return (current_min, current_max)