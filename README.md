# oj-problem-tools

一套面向 [OpenJudge](http://openjudge.cn/) 的出题工具，用 Markdown 编写题面，用 Python 生成测试数据、计算标准答案并验证参考程序。

项目还会把 Markdown 题面构建为适合 OpenJudge 的注入脚本。构建后的题目页支持代码高亮、LaTeX 公式、明暗主题、代码复制、页内提交和最近提交状态自动刷新。

## 功能

- 使用固定随机种子批量生成可复现的 `.in` / `.out` 测试数据。
- 通过出题者实现的 `solve` 计算标准答案。
- 使用独立的 Python 3.8 参考程序逐组验证数据，并检查单组运行超时。
- 将 Markdown、HTML、代码块和 LaTeX 公式转换为 OpenJudge 题面。
- 从 Markdown 一级标题和 frontmatter 同步题目名称、时间限制、内存限制和来源等字段。
- 自动同步更新线上题目。
- 使用 `:::oj-remove` 保留出题笔记，同时在发布时将其从学生可见题面中移除。

## 环境要求

- [uv](https://docs.astral.sh/uv/)
- Python 3.8（可选），推荐用于验证需要提交到 OpenJudge 的 `solution.py`
- 一个 OpenJudge 组管理员账号

## 安装

```bash
git clone https://github.com/FuYnAloft/oj-problem-tools.git
cd oj-problem-tools
uv sync
```

## 使用步骤

本项目强烈建议**配合 Agent 使用**以提高效率。

本项目附带了一个 skill `write-oj-problem`，包含此项目的详细使用方法。

你**只需要在 Agent** 中调用 skill：

```text
$write-oj-problem
```

然后描述题意、输入输出、数据范围、时间限制、样例和其他要求。Agent 会创建或完善一个题目目录。创建后，执行`uv run <path-to-problem-dir>/problem.py`或点击 IDE 的运行键，将会自动生成样例和题目描述。

有任何不懂的都可以直接问 Agent，通常可以快速地获得回复。

### 发布题目描述

将题目上传到 OpenJudge 需要人类操作。

#### 默认方式：使用 `inject.js`

`problem.py` 运行后会，在题目目录生成 `inject.js`，并将脚本复制到系统剪贴板。

打开 OpenJudge 中该题目的编辑页面，在浏览器开发者工具的控制台中粘贴并运行脚本。看到“`OJ Inject 已填入，请提交保存。`”后，检查字段并在页面上保存题目。

脚本执行后还会把测试数据目录复制到剪贴板，便于随后选择并上传测试用例。

#### 可选方式：自动上传/更新题目

本项目只能更新已经存在的题目，不能直接创建新题目。创建新题时，请先在 OpenJudge 中人工创建一个占位题目。

在项目根目录创建 `.env`：

```dotenv
OJ_EMAIL=登录邮箱
OJ_PASSWORD=登录密码
```

然后告诉 Agent 题目所属的组（例如 `cs101`）和题目的数字 ID，或手动在题目的 `OjProblem` 子类中设置：
```python
class ExampleProblem(OjProblem[InputType, OutputType]):
    group_slug = "cs101"
    problem_id = 31243
```

再次运行 `problem.py` 时，工具会登录 OpenJudge 并更新目标题目的描述和基本字段，不再生成 `inject.js`。运行前请仔细确认目标组和题号。
