from random import Random

from oj_problem_tools import OjProblem


class APlusB(OjProblem[tuple[int, int], int]):
    def generate(self, index: int, random: Random) -> tuple[int, int]:
        if index == 0:
            a, b = 1, 2
        elif index < 20:
            a = random.randint(0, 100)
            b = random.randint(0, 100)
        else:
            a = random.randint(0, 1 << 32)
            b = random.randint(0, 1 << 32)
        return a, b

    def solve(self, data: tuple[int, int], index: int) -> int | None:
        a, b = data
        result = a + b
        if result > 1 << 32:
            return None  # 如果数据不合理或不合适，返回 None
        return result

    def format_input(self, data: tuple[int, int], random: Random) -> str:
        a, b = data
        return f"{a} {b}\n"

    def format_output(self, data: int) -> str:
        return f"{data}\n"
