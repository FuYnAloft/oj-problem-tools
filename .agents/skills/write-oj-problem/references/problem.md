# problem.py 与数据生成规范

## 目录

- [必要接口](#必要接口)
- [内部数据模型](#内部数据模型)
- [直接使用字符串](#直接使用字符串)
- [Index 规划](#index-规划)
- [生成最佳实践](#生成最佳实践)
- [指定样例与手写 cases](#指定样例与手写-cases)

## 必要接口

从 `oj_problem_tools` 导入 `OjProblem`，定义一个子类：

```python
from random import Random
from oj_problem_tools import OjProblem

class Problem(OjProblem[InputData, Answer]):
    def generate(self, index: int, random: Random) -> InputData:
        ...

    def solve(self, data: InputData, index: int) -> Answer | None:
        ...
```

必须重写：

- `generate(index, random)`：创建一组内部输入数据。只使用传入的 `random`，不要使用模块级 `random` 或时间种子。
- `solve(data, index)`：计算标准答案。返回 `None` 表示本次随机数据不合适，框架会换 attempt 重试；每个 index 最多尝试 100 次。

通常还要重写：

- `format_input(data, random)`：把非字符串内部数据精确转换为输入文件。可使用这里单独提供的 `random` 随机化合法表示，例如列顺序。
- `format_output(answer)`：把非字符串答案转换为输出文件，显式处理换行和精度。

常用类属性：

- `case_range: Sequence[int] = range(50)`：完整测试点集合。可使用 `range`、`list`、`tuple` 等有序整数序列，因此也能写成 `[1, 2, 3, 8, 9, 10]` 这样的离散 index。
- `generate_range: Sequence[int] | None = None`：自动生成的 index；为 `None` 时使用 `case_range`。
- `test_range: Sequence[int] | None = None`：执行标准解验证的 index；为 `None` 时使用 `case_range`。
- `seed: str | None = None`：可复现随机种子；保持 `None` 时，框架会在创建子类时自动使用类名，故通常不写。若希望重命名类后仍生成完全相同的数据，则显式设置一个稳定字符串。
- `interpreter`：运行 `solution.py` 的解释器。
- `timeout_per_case = 1.0`：每个本地测试的超时秒数。
- `solution_script`、`data_dir`、`description_md`、`inject_js_output`：通常保持默认；相对路径会按 `problem.py` 所在目录解析。

因此，只重写 `case_range` 就会同时改变默认生成范围和默认测试范围，不需要再把它重复赋给 `generate_range`、`test_range`。空序列与 `None` 含义不同：空序列表示不处理任何 index，`None` 才表示回退到 `case_range`。

定义子类后无需写 main；模块退出时框架会生成注入脚本、生成数据并测试标准解。若需要单独控制，可实例化后显式调用 `generate_all()`、`test_solution()` 或 `generate_inject_script()`。

## 内部数据模型

复杂记录优先使用 dataclass，字段使用精确且有意义的单位。例如金额使用分、身高使用毫米或十分之一厘米，而不是先用 float。把仅供生成器使用的信息与真正输入字段分开。

`solve` 不应解析 `format_input` 生成的字符串；它直接读取内部模型。`solution.py` 才负责解析真实输入。两条实现路径相互独立，有助于发现格式和解析错误。

## 直接使用字符串

输入或输出格式简单时，不必为了形式统一额外定义包装类型：

- 输入本身就是一小段固定格式文本时，可以让输入类型 `T` 直接为 `str`，并使用框架默认的 `format_input`。
- 输出通常适合让答案类型 `R` 直接为 `str`。此时 `solve` 返回最终输出文本，使用框架默认的 `format_output`，避免把简单格式拆到另一个方法。
- 短小、行数固定的输出优先使用 f-string，并显式包含需要的换行：

```python
class Problem(OjProblem[InputData, str]):
    def solve(self, data: InputData, index: int) -> str:
        answer = compute(data)
        return f"{answer}\n"
```

- 输出行数较多、需要在分支或循环中逐步追加时，可以使用 `io.StringIO`：

```python
from io import StringIO

def solve(self, data: InputData, index: int) -> str:
    output = StringIO()
    for item in compute_items(data):
        output.write(f"{item}\n")
    return output.getvalue()
```

也可以先收集字符串再用 `"\n".join(lines)`。无论采用哪种方式，都要明确处理小数格式、字段间空格和末尾换行。只有答案的内部结构需要在多处复用，或格式化逻辑明显独立时，才保留结构化 `R` 并重写 `format_output`。

## Index 规划

在写代码前制作 index 覆盖表。推荐分配：

- 最前面的 index：题面指定样例和最小规模。
- 随后的固定 index：空集、单元素、全相同、严格单调、重复值、并列、无解、全部满足、一个都不满足等结构边缘。
- 中段：多种分布的小规模和中规模随机数据。
- 后段：极限值、退化结构、针对错误算法的数据。
- 最后几个 index：最大规模及接近最坏复杂度的数据。

不要只生成均匀随机数据。随机数据通常很难稳定覆盖并列、阈值恰好相等、空分组、图不连通等关键情况。为这些情况保留明确 index。

## 生成最佳实践

- 保证每个字段都满足题面范围、格式和关系约束。
- 用传入的 `Random` 保证同一有效 seed、index、attempt 可复现。默认 seed 来自类名，因此重命名题目类会改变随机数据；需要跨重命名稳定时显式设置字符串 seed。
- 让规模随 index 增长，但不要让全部大数据具有同一种结构。
- 对需要重试的性质，在 `solve` 返回 `None`；若可以直接构造，优先直接构造，避免低概率无限筛选。
- 对浮点和舍入，优先用整数缩放或 `Decimal` 构造。避免把答案放在二进制浮点误差或两种舍入规则的分界线上，除非题目专门测试该规则。
- 标准答案算法应以正确、清晰为首要目标，可以比选手算法慢一些，但必须在生成规模内可靠完成。
- 生成最大数据后检查真实文件大小和 `solve`、`solution.py` 的运行时间。
- 不要让 `solve` 调用 `solution.py`，也不要复制完全相同的易错逻辑。

## 指定样例与手写 cases

一般直接在 `generate` 中硬编码：

```python
def generate(self, index: int, random: Random) -> InputData:
    if index == 0:
        return specified_sample
    ...
```

若必须手写 index 0、1：

```python
case_range = range(50)
generate_range = range(2, 50)
```

然后创建 `cases/0.in`、`cases/0.out`、`cases/1.in`、`cases/1.out`。自动生成不会覆盖它们；`test_range` 保持默认的 `None`，测试时会回退到完整的 `case_range`，因此仍会包含它们。

如果仓库忽略所有 cases，必须在根 `../../../../.gitignore` 中重新包含目录和指定文件。把 `<problem>` 换成实际相对路径：

```gitignore
**/cases/
!<problem>/cases/
<problem>/cases/*
!<problem>/cases/0.in
!<problem>/cases/0.out
!<problem>/cases/1.in
!<problem>/cases/1.out
```

用 `git check-ignore -v <problem>/cases/0.in` 验证例外生效，并用 `git status --short` 确认文件可跟踪。不要只依赖 `git add -f` 隐藏规则问题。
