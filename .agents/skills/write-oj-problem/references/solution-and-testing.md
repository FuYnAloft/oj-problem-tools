# solution.py 与验证规范

## Python 3.8 兼容

标准解必须能由 Python 3.8 独立执行：

- 只使用 Python 3.8 标准库，不导入 `oj_problem_tools` 或生成器代码。
- 避免 `match/case`、`X | None`、`list[int]`、`dataclass(slots=True)`、`str.removeprefix` 等较新接口或语法。
- 需要类型标注时使用 `typing.List`、`typing.Tuple`、`typing.Dict`、`typing.Optional`。
- 可以使用 dataclass，但不要传 `slots=True`。
- 大输入优先使用 `sys.stdin.buffer`；输出集中拼接，避免不必要的逐项 flush。
- 不假设当前工作目录，不读取额外文件，不依赖环境变量。
- 输出格式必须精确，包括行数、空格、小数位和末尾内容。

若题目要求十进制精确计算或明确的 ROUND_HALF_UP，不要直接依赖二进制 float 和 Python 的 ties-to-even `round`；使用整数缩放或 `decimal.Decimal`。

## 选择测试解释器

按以下顺序选择 `OjProblem.interpreter`：

1. 查找真实的 Python 3.8，例如 `python3.8`、用户给出的 3.8 路径或项目保存的 3.8 解释器。
2. 如果没有 3.8，使用用户明确指定且确实存在的 Python 解释器。
3. 否则使用运行 `problem.py` 的当前项目解释器 `sys.executable`，并明确告知用户没有完成真实 3.8 验证。

通用回退写法：

```python
import shutil
import sys

class Problem(OjProblem[InputData, Answer]):
    interpreter = shutil.which("python3.8") or sys.executable
```

若用户提供了其他路径，把它放在 `sys.executable` 之前。不要仅根据可执行文件名推断版本；运行 `<interpreter> --version` 确认。

题目生成器使用项目要求的较新 Python；`interpreter` 只控制框架启动 `solution.py` 的子进程，两者可以不同。

## 验证顺序

1. 确认项目包可编辑安装：项目使用 uv 时运行 `uv sync`。
2. 检查解释器版本：`python3.8 --version` 或所选路径的 `--version`。
3. 用所选解释器执行 `-m py_compile solution.py`。
4. 不设置 `PYTHONPATH`，用项目解释器运行题目目录中的 `problem.py`。
5. 阅读生成/测试日志，确认每个 `generate_range` index 已生成、每个 `test_range` index 已通过。
6. 直接运行题面样例并与 `description.md` 比较。
7. 编写一次性只读校验，解析所有 `.in` 检查 N、token 数、数值范围、唯一性、图结构或其他约束。
8. 检查固定边缘 index 的语义，而不只是检查程序退出码。
9. 对最大测试记录时间和输出大小，确认低于本地超时并为评测环境留余量。

对拍通过只能说明 `solve` 与 `solution.py` 一致，不能证明二者都正确。至少用手算样例、独立性质检查或另一种小规模暴力算法验证答案函数。

## 常见失败

- 导入失败：先 `uv sync`，并使用 `from oj_problem_tools import OjProblem`；不要设置临时 `PYTHONPATH` 掩盖安装问题。
- 找不到 `python3.8`：按解释器优先级选择回退，并在交付时声明。
- 手写样例找不到：检查 `test_range`、文件名和 `../../../../.gitignore` 例外。
- 随机数据偶发变化：检查是否误用了全局 random、当前时间、无序集合迭代或不稳定哈希。
- 100 次仍生成失败：改为直接构造目标性质，或提高接受概率；不要盲目增加重试次数。
- 样例与题面不一致：以确认后的规格为准，同时修正生成器、答案函数、标准解和题面。
