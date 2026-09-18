import io
import json
import runpy
import sys
import time
import traceback


def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    solution_script = sys.argv[1]

    # 循环读取测试用例请求
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            break

        in_path = req["in_path"]

        old_stdin = sys.stdin
        old_stdout = sys.stdout

        try:
            with open(in_path, "r", encoding="utf-8") as fin:
                sys.stdin = fin
                out_buf = io.StringIO()
                sys.stdout = out_buf

                start_time = time.perf_counter()
                # 动态运行 solution.py
                runpy.run_path(solution_script, run_name="__main__")
                end_time = time.perf_counter()

            actual_output = out_buf.getvalue()
            res = {
                "success": True,
                "output": actual_output,
                "time": end_time - start_time,
                "error": "",
            }
        except Exception:
            res = {
                "success": False,
                "output": "",
                "time": 0.0,
                "error": traceback.format_exc(),
            }
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout

        # 将单次运行结果以 JSON 格式输出给主进程
        print(json.dumps(res, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
