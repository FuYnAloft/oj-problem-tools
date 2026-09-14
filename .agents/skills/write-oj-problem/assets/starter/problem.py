import shutil
import sys
from dataclasses import dataclass
from random import Random

from oj_problem_tools import OjProblem


@dataclass(frozen=True)
class ProblemData:
    values: tuple[int, ...]


class Problem(OjProblem[ProblemData, str]):
    interpreter = shutil.which("python3.8") or sys.executable

    def generate(self, index: int, random: Random) -> ProblemData:
        if index == 0:
            return ProblemData((1, 2, 3))
        if index == 1:
            return ProblemData((-10**9, 10**9))
        size = 1000 if index == 49 else random.randint(1, 100)
        return ProblemData(tuple(random.randint(-10**9, 10**9) for _ in range(size)))

    def solve(self, data: ProblemData, index: int) -> str:
        return f"{sum(data.values)}\n"

    def format_input(self, data: ProblemData, random: Random) -> str:
        return f"{len(data.values)}\n{' '.join(map(str, data.values))}\n"
