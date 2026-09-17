import shutil
import sys
from collections.abc import Sequence
from random import Random

from oj_problem_tools import OjProblem


class SequenceSum(OjProblem[Sequence[int], str]):
    interpreter = shutil.which("python3.8") or sys.executable

    def generate(self, index: int, random: Random) -> Sequence[int]:
        if index == 0:
            return [1, 2, 3]
        if index == 1:
            return [-10**9, 10**9]
        size = 1000 if index == 49 else random.randint(1, 100)
        return [random.randint(-10**9, 10**9) for _ in range(size)]

    def solve(self, data: Sequence[int], index: int) -> str:
        return f"{sum(data)}\n"

    def format_input(self, data: Sequence[int], random: Random) -> str:
        return f"{len(data)}\n{' '.join(map(str, data))}\n"
