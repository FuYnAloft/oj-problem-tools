from __future__ import annotations

import atexit
import inspect
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from random import Random
from typing import final

import pyperclip
from dotenv import load_dotenv, find_dotenv

from .oj_inject import generate_injection_script, generate_request_values
from .oj_upload import OjClient

printed: set[str] = set()


def print_err_once(message: str):
    if message not in printed:
        print(message, file=sys.stderr)
        printed.add(message)


def print_err(message: str):
    print(message, file=sys.stderr)


class OjProblem[T, R](ABC):
    case_range: Sequence[int] = range(50)
    generate_range: Sequence[int] | None = None
    test_range: Sequence[int] | None = None
    interpreter: str = "python3.8"
    timeout_per_case: float = 1.0
    solution_script: str = "solution.py"
    data_dir: str = "cases"
    description_md: str = "description.md"
    inject_js_output: str = "inject.js"
    problem_file: str = "problem.py"
    seed: str | None = None

    group_slug: str | None = None
    problem_id: int | None = None

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
        indices = self.generate_range if self.generate_range is not None else self.case_range
        os.makedirs(self.data_dir, exist_ok=True)
        for count, i in enumerate(indices):
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
            print(f"\r测试用例 {i}（{count + 1}/{len(indices)}）已生成。", end="")
        print("\n所有测试用例均已生成。")

    @final
    def test_solution(self) -> None:
        """测试 solution.py 是否正确"""
        self.__class__._manual_run = True
        indices = self.test_range if self.test_range is not None else self.case_range
        executable = shutil.which(self.interpreter) or self.interpreter

        times: list[float] = []

        runner_script = str((Path(__file__).parent / "_runner.py").resolve())

        # 启动单个常驻 Python 3.8 解释器子进程
        process = subprocess.Popen(
            [executable, runner_script, self.solution_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        try:
            for count, i in enumerate(indices):
                in_file = f"{self.data_dir}/{i}.in"
                out_file = f"{self.data_dir}/{i}.out"

                with open(out_file, "r", encoding="utf-8") as f:
                    expected_output_str = f.read()

                # 发送评测请求
                req_json = json.dumps({"in_path": in_file})
                process.stdin.write(req_json + "\n")
                process.stdin.flush()

                # 带超时控制读取输出
                res_line = [None]

                def read_stdout():
                    res_line[0] = process.stdout.readline()

                reader_thread = threading.Thread(target=read_stdout, daemon=True)
                reader_thread.start()
                reader_thread.join(timeout=self.timeout_per_case)

                if reader_thread.is_alive():
                    process.kill()
                    print_err(f"测试用例 {i} 超时，时间限制为 {self.timeout_per_case} 秒。")
                    break

                if not res_line[0]:
                    stderr_output = process.stderr.read()
                    print_err(f"测试用例 {i} 运行进程异常退出。")
                    if stderr_output:
                        print_err(f"错误输出：\n{stderr_output}")
                    break

                res = json.loads(res_line[0])
                if not res["success"]:
                    print_err(f"测试用例 {i} 运行失败。")
                    print_err(f"错误输出：\n{res['error']}")
                    break

                actual_output_str = res["output"]
                elapsed = res["time"]
                times.append(elapsed)

                if actual_output_str.strip() != expected_output_str.strip():
                    print_err(f"测试用例 {i} 未通过。")
                    print_err(f"期望输出：\n{expected_output_str}")
                    print_err(f"实际输出：\n{actual_output_str}")
                    break

                print(f"\r测试用例 {i}（{count + 1}/{len(indices)}）已通过。", end="")
            else:
                print("\n所有测试均已通过！")
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()

        if times:
            print(f"总耗时: {sum(times):.6f} 秒")
            print(f"最长耗时: {max(times):.6f} 秒")

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
        pyperclip.copy(js)
        print(f"已生成题目描述注入脚本，并复制到剪贴板。")

    @final
    def update_problem(self) -> None:
        """更新题目描述到 OpenJudge"""
        self.__class__._manual_run = True
        print("正在更新题目描述到 OpenJudge。")
        load_dotenv(find_dotenv())
        email = os.getenv("OJ_EMAIL")
        password = os.getenv("OJ_PASSWORD")
        if email is None or password is None:
            print_err("请在 .env 文件中设置 OJ_EMAIL 和 OJ_PASSWORD。")
            return
        if self.group_slug is None or self.problem_id is None:
            print_err("请在子类中设置 group_slug 和 problem_id。")
            return
        client = OjClient()
        try:
            client.login(email, password)
        except Exception as e:
            print_err(f"登录失败：{e}")
            return
        with open(self.description_md, "r", encoding="utf-8") as f:
            description = f.read()
        values = generate_request_values(description)
        client.update_existing_problem(self.group_slug, self.problem_id, values)
        print(f"题目描述已更新到 OpenJudge，题目 ID: {self.problem_id}。")

    @final
    def _auto_run(self) -> None:
        """自动运行生成和测试"""
        if self.__class__._manual_run:
            return
        print("自动运行：正在生成测试用例并测试标准解。")
        if self.group_slug is None or self.problem_id is None:
            self.generate_inject_script()
        else:
            self.update_problem()
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
