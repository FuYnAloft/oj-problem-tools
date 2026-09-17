---
name: write-oj-problem
description: Create or complete an OpenJudge programming problem using oj_problem_tools, including description.md, a deterministic problem.py data generator and oracle, a standalone Python 3.8 solution.py, generated or manual cases, and end-to-end validation. Use when asked to write, scaffold, migrate, repair, review, or test an OJ problem, its statement, generator, reference solution, edge cases, or judge data, even when no template directory is available.
---

# 编写 OpenJudge 题目

从题意创建一个可以生成数据、计算答案并验证标准解的完整题目目录。不要假设工作区存在 `../../../template`；优先使用本技能 `assets/starter` 中的自包含骨架，并按实际题目彻底改写。

## 开始前

1. 检查工作区结构、`../../../pyproject.toml`、已安装包和已有题目约定。
2. 确认 `oj_problem_tools` 可以导入；项目使用 uv 时先在根目录执行 `uv sync`，不要通过 `PYTHONPATH` 临时注入。
3. 从用户给出的题意提取输入约束、输出规则、时空限制、并列规则、精度规则和指定样例。只有会实质改变题意的缺失信息才询问用户。
4. 新建独立题目目录，通常命名为 `<题号>.<题名>`，至少包含：

```text
<题目目录>/
├── description.md
├── problem.py
└── solution.py
```

5. 创建完整题目时，依次读取并遵守：
   - `references/description.md`：题面和 frontmatter。
   - `references/problem.md`：生成器、标准答案函数和数据覆盖。
   - `references/solution-and-testing.md`：Python 3.8 标准解、解释器选择和验证。

## 工作流

### 1. 写清规格

先列出可机械检查的规格：数据范围、格式、合法性、答案唯一性、排序与并列、舍入方式、空集行为。题面、生成器、`solve` 和 `solution.py` 必须使用同一规格。

### 2. 创建文件

以 `assets/starter/description.md`、`assets/starter/problem.py`、`assets/starter/solution.py` 为骨架。复制其结构和必要接口，不保留示例题意、示例数据或无关字段。用户已有文件时在原文件上谨慎修改，不覆盖无关内容。

### 3. 实现题面

先完成正式定义，再写样例。明确所有容易产生多种理解的细节。frontmatter 放在文档最开头，全文只使用一个一级标题。生成测试数据后再次核对题面样例的输入和输出。

### 4. 实现生成器和答案函数

按输入的概念结构选择 `T`，不要为了包装而定义 dataclass：只有一个字段时直接使用该字段的类型；按只读方式使用的同质序列标注为 `collections.abc.Sequence[T]`，生成时已有 list 就直接返回 list，不要仅为不可变性转成 tuple。多个有名称的字段时，再使用 dataclass。格式简单时也可以直接使用 `str`。尤其可以让答案类型 `R` 为 `str`：短输出用 f-string 直接构造，多行输出可用 `io.StringIO` 累积，从而省去单独的 `format_output`。使用框架传入的 `Random`，按 `index` 安排样例、边缘、小规模随机、大规模随机和最大规模数据。让 `solve` 成为可靠、直接且尽可能使用精确运算的答案函数。

通常把指定样例硬编码在 `generate` 的前几个 index。只有样例必须逐字节保持、由外部给定或不适合内部数据模型时，才手写 `cases/<index>.in` 与 `.out`；此时让 `generate_range` 排除这些 index，并解除这些文件的 gitignore。通常保持 `test_range = None`，让测试范围回退到包含这些 index 的 `case_range`；只有需要测试特定子集时，才显式设置 `test_range`。具体规则见 `references/problem.md`。

### 5. 实现 Python 3.8 标准解

`solution.py` 必须是独立的竞赛程序，不导入 `oj_problem_tools`，不依赖第三方包，并兼容 Python 3.8。优先使用实际 Python 3.8 解释器测试；找不到时使用用户明确提供的解释器，否则使用当前项目解释器。不要因为本机解释器较新而使用 3.9+ 语法。

### 6. 验证

至少完成以下检查：

1. 使用项目解释器编译 `problem.py`。
2. 使用选定的测试解释器编译 `solution.py`；有 Python 3.8 时必须使用它。
3. 从项目环境运行 `problem.py`。
4. 确认全部生成成功且全部测试通过。
5. 独立检查每组输入满足题面约束、指定样例一致、边缘 index 确实触发目标情况、最大数据达到预期规模。
6. 检查失败时先判断是生成器、答案函数、标准解还是题面不一致，不得只修改预期输出掩盖错误。

## 交付要求

简要报告创建或修改的文件、关键数据覆盖、使用的标准解解释器以及通过的测试数量。明确指出任何因环境缺失而未执行的验证。
