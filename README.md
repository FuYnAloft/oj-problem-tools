# oj-problem-tools

一套面向 [OpenJudge](http://openjudge.cn/) 的出题工具，用 Markdown 编写题面，用 Python 生成测试数据、计算标准答案并验证参考程序。

项目还会把 Markdown 题面构建为适合 OpenJudge 的注入脚本。构建后的题目页支持代码高亮、LaTeX 公式、明暗主题、代码复制、页内提交和最近提交状态自动刷新。

## 功能

- 使用固定随机种子批量生成可复现的 `.in` / `.out` 测试数据。
- 通过出题者实现的 `solve` 计算标准答案。
- 使用独立的 Python 3.8 参考程序逐组验证数据，并检查单组运行超时。
- 将 Markdown、HTML、代码块和 LaTeX 公式转换为 OpenJudge 题面。
- 从 Markdown 一级标题和 frontmatter 同步题目名称、时间限制、内存限制和来源等字段。
- 默认生成 `inject.js` 并复制到剪贴板，也可以自动更新已经存在的 OpenJudge 题目。
- 使用 `:::oj-remove` 保留出题笔记，同时在发布时将其从学生可见题面中移除。

## 环境要求

- [uv](https://docs.astral.sh/uv/)
- Python 3.12 或更高版本，用于运行本项目
- Python 3.8，推荐用于验证需要提交到 OpenJudge 的 `solution.py`
- 一个 OpenJudge 账号；发布前需要先在 OpenJudge 中创建题目

## 安装

```bash
git clone https://github.com/FuYnAloft/oj-problem-tools.git
cd oj-problem-tools
uv sync
```

## 使用步骤

### 1. 使用 Agent 编写题目

在 Agent 中调用：

```text
$write-oj-problem
```

然后描述题意、输入输出、数据范围、时间限制、样例和其他要求。Agent 会创建或完善一个题目目录，通常包含：

```text
<题目目录>/
├── description.md  # Markdown 题面
├── problem.py      # 数据生成器和标准答案函数
└── solution.py     # 独立的 Python 3.8 参考程序
```

Agent 还会检查题面、生成器、标准答案和参考程序是否使用同一套规格，并覆盖样例、边界数据、随机数据和最大规模数据。

### 2. 生成数据并验证参考程序

在项目根目录运行：

```bash
uv run python <题目目录>/problem.py
```

默认会依次执行：

1. 根据 `description.md` 生成题面注入脚本。
2. 在 `<题目目录>/cases/` 中生成测试输入和答案。
3. 使用 `solution.py` 运行全部测试数据。
4. 报告未通过、运行错误或超时的测试用例。

生成过程是确定性的；相同题目类、种子和用例编号会得到相同的数据。

### 3. 发布题目描述

#### 默认方式：使用 `inject.js`

如果 `problem.py` 没有设置 `group_slug` 和 `problem_id`，运行后会：

- 在题目目录生成 `inject.js`。
- 将脚本复制到系统剪贴板。

打开 OpenJudge 中该题目的编辑页面，在浏览器开发者工具的控制台中粘贴并运行脚本。看到“`OJ Inject 已填入，请提交保存。`”后，检查字段并在页面上保存题目。

脚本执行后还会把测试数据目录复制到剪贴板，便于随后选择并上传测试用例。

#### 可选方式：自动上传/更新题目

本项目只能更新已经存在的题目，不能直接创建新题目。创建新题时，请先在 OpenJudge 中人工创建一个占位题目。

在项目根目录创建 `.env`：

```dotenv
OJ_EMAIL=登录邮箱
OJ_PASSWORD=登录密码
```

`.env` 已被 Git 忽略，不要提交或分享其中的凭据。然后在题目的 `OjProblem` 子类中设置：

```python
class ExampleProblem(OjProblem[InputType, OutputType]):
    group_slug = "cs101"
    problem_id = 31243
```

其中：

- `group_slug` 是组域名的第一段，例如 `cs101.openjudge.cn` 对应 `cs101`。
- `problem_id` 是 OpenJudge 中已经存在的整数题号。

再次运行 `problem.py` 时，工具会登录 OpenJudge 并更新目标题目的描述和基本字段，不再生成 `inject.js`。运行前请仔细确认目标组和题号。

### 4. 上传测试数据

将 `<题目目录>/cases/` 中生成的 `.in` / `.out` 文件上传到 OpenJudge。

自动更新功能目前只更新题目描述，不会上传测试数据；测试数据始终需要人工上传。

## 题目文件

### `description.md`

题面使用 Markdown 编写，文件开头可以包含 YAML frontmatter：

```yaml
---
timeLimit: 1000
caseTimeLimit: 100
memoryLimit: 65536
source: 题目来源
config:
  # 略，通常不需要调整
---

# 题目名称
```

注意：

- 全文必须且只能有一个一级标题，一级标题会作为题目名称。
- frontmatter 应放在文件最开头。

仅供出题者阅读的内容可以这样书写：

````markdown
:::oj-remove
这里可以记录题解、数据设计或其他不希望学生看到的内容。
:::
````

### `problem.py`

`problem.py` 定义一个 `OjProblem[T, R]` 子类，核心方法是：

- `generate(index, random)`：生成第 `index` 组结构化数据。
- `solve(data, index)`：计算标准答案；返回 `None` 时会重新生成该组数据。
- `format_input(data, random)`：将结构化数据转换为输入文本。
- `format_output(data)`：在答案不是字符串时自定义输出格式。

常用类属性：

| 属性 | 默认值 | 说明 |
| --- | --- | --- |
| `case_range` | `range(50)` | 应当存在和测试的用例编号 |
| `generate_range` | `None` | 实际自动生成的编号；`None` 表示使用 `case_range` |
| `test_range` | `None` | 实际测试的编号；`None` 表示使用 `case_range` |
| `interpreter` | `python3.8` | 运行 `solution.py` 的解释器 |
| `timeout_per_case` | `1.0` | 本地验证时每组数据的超时秒数 |
| `seed` | 题目类名 | 确定性随机种子 |

### `solution.py`

参考程序应当是独立的竞赛程序：

- 从标准输入读取数据，并向标准输出写入答案。
- 不导入 `oj_problem_tools`。
- 不依赖第三方包。
- 保持与 OpenJudge 使用的 Python 3.8 兼容。

## 项目结构

```text
.
├── .agents/skills/write-oj-problem/  # Agent 出题技能
├── src/oj_problem_tools/             # 工具实现
├── template/                         # 简单示例模板
├── pyproject.toml
└── uv.lock
```
