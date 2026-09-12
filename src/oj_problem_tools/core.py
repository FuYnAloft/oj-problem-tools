from __future__ import annotations

import atexit
import inspect
import json
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from random import Random
from typing import final

from .oj_inject import generate_injection_script


printed: set[str] = set()


def print_err_once(message: str):
    if message not in printed:
        print(message, file=sys.stderr)
        printed.add(message)


def print_err(message: str):
    print(message, file=sys.stderr)


class OjProblem[T, R](ABC):
    case_range: range = range(50)
    generate_range: range = case_range
    test_range: range = case_range
    interpreter: str = "python3.8"
    timeout_per_case: float = 1.0
    solution_script: str = "solution.py"
    data_dir: str = "cases"
    description_md: str = "description.md"
    inject_js_output: str = "inject.js"
    problem_file: str = "problem.py"
    seed: str | None = None

    _manual_run: bool = False

    @abstractmethod
    def generate(self, index: int, random: Random) -> T:
        """生成数据，可以带随机性"""
        ...

    @abstractmethod
    def solve(self, data: T, index: int) -> R | None:
        """求解数据，返回 None 表示数据不合理，将会重新生成"""
        ...

    def format_input(self, data: T, random: Random) -> str:
        """将数据的内部表示转换为字符串，写入输入文件，这一步也可以有随机性"""
        if isinstance(data, str):
            return data
        print_err_once("警告：输入数据不是字符串，将使用 str() 进行格式化。")
        return str(data)

    def format_output(self, data: R) -> str:
        """将数据的内部表示转换为字符串，写入输出文件"""
        if isinstance(data, str):
            return data
        print_err_once("警告：输出数据不是字符串，将使用 str() 进行格式化。")
        return str(data)

    @final
    def generate_all(self) -> None:
        """生成所有测试数据"""
        self.__class__._manual_run = True
        os.makedirs(self.data_dir, exist_ok=True)
        for count, i in enumerate(self.generate_range):
            for attempt in range(100):
                input_data = self.generate(i, Random(f"{self.seed}:generate:{i}:{attempt}"))
                output_data = self.solve(input_data, i)
                if output_data is not None:
                    break
            else:
                print_err(f"\n测试用例 {i} 生成失败，尝试了 100 次仍未生成合理数据。")
                continue

            input_str = self.format_input(input_data, Random(f"{self.seed}:format:{i}"))
            output_str = self.format_output(output_data)
            with open(f"{self.data_dir}/{i}.in", "w") as f:
                f.write(input_str)
            with open(f"{self.data_dir}/{i}.out", "w") as f:
                f.write(output_str)
            print(f"\r测试用例 {i}（{count + 1}/{len(self.generate_range)}）已生成。", end="")
        print("\n所有测试用例均已生成。")

    @final
    def test_solution(self) -> None:
        """测试 solution.py 是否正确"""
        self.__class__._manual_run = True
        executable = shutil.which(self.interpreter) or self.interpreter
        for count, i in enumerate(self.test_range):
            with open(f"{self.data_dir}/{i}.in", "r") as f:
                input_str = f.read()
            with open(f"{self.data_dir}/{i}.out", "r") as f:
                expected_output_str = f.read()
            process = subprocess.Popen(
                [executable, self.solution_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                actual_output_str, stderr = process.communicate(input=input_str, timeout=self.timeout_per_case)
            except subprocess.TimeoutExpired:
                process.kill()
                print_err(f"测试用例 {i} 超时，时间限制为 {self.timeout_per_case} 秒。")
                break
            if process.returncode != 0:
                print_err(f"测试用例 {i} 运行失败，返回码为 {process.returncode}。")
                print_err(f"错误输出：\n{stderr}")
                break
            if actual_output_str.strip() != expected_output_str.strip():
                print_err(f"测试用例 {i} 未通过。")
                print_err(f"期望输出：\n{expected_output_str}")
                print_err(f"实际输出：\n{actual_output_str}")
                break
            print(f"\r测试用例 {i}（{count + 1}/{len(self.test_range)}）已通过。", end="")
        else:
            print("\n所有测试均已通过！")

    @final
    def generate_inject_script(self) -> None:
        """生成 oj-inject 注入脚本"""
        self.__class__._manual_run = True
        with open(self.description_md, "r") as f:
            md: str = f.read()
        inject = generate_injection_script(md)
        js = f"""\
{inject}
(function() {{
const el = document.createElement('textarea')
el.value = {json.dumps(self.data_dir, ensure_ascii=False)}
el.style.position = 'fixed'
el.style.opacity = '0'
document.body.appendChild(el)
el.select()
document.execCommand('copy')
document.body.removeChild(el)
console.log('题目描述路径已复制到剪贴板。')
}})();"""
        with open(self.inject_js_output, "w") as f:
            f.write(js)
        print(f"已生成题目描述注入脚本。")

    @final
    def _auto_run(self) -> None:
        """自动运行生成和测试"""
        if self.__class__._manual_run:
            return
        print("自动运行：正在生成测试用例并测试标准解。")
        self.generate_inject_script()
        self.generate_all()
        self.test_solution()

    def __init_subclass__(cls, **kwargs):
        """如果没有手动调用操作，则自动运行生成和测试"""
        super().__init_subclass__(**kwargs)

        if cls.seed is None:
            cls.seed = cls.__name__

        class_file = Path(inspect.getfile(cls)).resolve()
        class_dir = class_file.parent

        for attribute in ("solution_script", "data_dir", "description_md", "inject_js_output"):
            path = Path(getattr(cls, attribute))
            if not path.is_absolute():
                setattr(cls, attribute, str((class_dir / path).resolve()))
        setattr(cls, "problem_file", str(class_file))

        atexit.register(lambda: cls()._auto_run())
