---
timeLimit: 1000 # 时间限制，单位为ms。
caseTimeLimit: 100 # 单个测试用例时间限制，单位为ms。如不需要限制此项，删掉此行。
memoryLimit: 65536 # 内存限制，单位为kB。

config: # 题目描述输出配置调整，通常不用写
  style: github-tweaked # 网页样式，支持 none, github（GitHub 原版）, github-tweaked（GitHub 优化）, github-tweaked-compact（GitHub 优化 紧凑），默认 github-tweaked。
  widening: 0 # 题目描述区域加宽，单位 px，默认 0。
  singleLineBreak: true # 是否把普通单换行转换成 <br>，默认开启
  stripOjRemove: true # 是否剔除 `:::oj-remove` 区域，默认开启
---

# 示例题目一

（可以自由写 Markdown 语法和 HTML 标签）
（支持代码块语法高亮、LaTeX 公式等，暂不支持 mermaid）
（以下的段落可以任意增删）

## 描述
这是一道算法题

## 输入格式
输入一些文本

## 输出格式
你需要输出一些文本

## 样例
**样例输入1**
```text
（待数据生成后填入）
```

**样例输出1**
```text
（待数据生成后填入）
```

**样例输入2**
```text
（待数据生成后填入）
```

**样例输出2**
```text
（待数据生成后填入）
```

(样例写几个都行。如果只写一个，不要写`1`。)

## 提示
（可以写提示；可以写需要的算法，如 dfs 等；可以写题目的分类，例如数据统计；可以不写）

## 来源
（可以不写）

:::oj-remove
从`:::oj-remove`到`:::`之间的内容会被剔除，可以在这里写不让学生看到的内容，如思路分析。可以不写。
:::