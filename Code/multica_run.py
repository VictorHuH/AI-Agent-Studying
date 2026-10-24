"""在 Multica 上建任务、派给智能体，等运行收敛后打印产出。

用法:
    python -I multica_run.py --title "试验任务" --assignee "Engineer"
    python -I multica_run.py --title "试验任务" --assignee "Engineer" --timeout 600
    python -I multica_run.py --self-test
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

TERMINAL = {"completed", "failed", "cancelled", "canceled"}
POLL_SECONDS = 5
STABLE_POLLS = 3  # 连续 3 次稳定才收工，给小队派活留出间隔
# ponytail: 固定轮询 + 稳定窗口，够用；要精确可改用 webhook/事件流


def cli_path():
    exe = shutil.which("multica")
    if exe:
        return exe
    fallback = os.path.expanduser("~/.multica/bin/multica.exe")
    if os.path.exists(fallback):
        return fallback
    sys.exit("找不到 multica，请先安装: https://multica.ai/docs/zh/cli")


def run_cli(*args):
    cp = subprocess.run(
        [cli_path(), *args, "--output", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if cp.returncode != 0:
        sys.exit(f"multica {' '.join(args)} 失败: {cp.stderr.strip() or cp.stdout.strip()}")
    return json.loads(cp.stdout)


def is_settled(runs):
    return bool(runs) and all(r.get("status") in TERMINAL for r in runs)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--title")
    p.add_argument("--assignee")
    p.add_argument("--description", default="")
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()

    if a.self_test:
        assert not is_settled([])
        assert not is_settled([{"status": "running"}])
        assert is_settled([{"status": "completed"}])
        assert not is_settled([{"status": "completed"}, {"status": "queued"}])
        print("self-test ok")
        return

    if not (a.title and a.assignee):
        p.error("--title 和 --assignee 必填（或使用 --self-test）")

    args = ["issue", "create", "--title", a.title, "--assignee", a.assignee]
    if a.description:
        args += ["--description", a.description]
    issue = run_cli(*args)
    ident = issue.get("identifier") or issue.get("id")
    print(f"已创建 {ident}（负责人: {a.assignee}），等待运行…")

    deadline = time.time() + a.timeout
    stable = 0
    runs = []
    while time.time() < deadline:
        runs = run_cli("issue", "runs", ident)
        stable = stable + 1 if is_settled(runs) else 0
        if stable >= STABLE_POLLS:
            break
        time.sleep(POLL_SECONDS)

    if not runs:
        sys.exit("超时：没有产生任何运行（检查运行时是否在线）")

    print(f"\n共 {len(runs)} 次运行：")
    for r in reversed(runs):  # CLI 最新在前，按时间正序打印
        u = r.get("usage") or [{}]
        tok = sum(x.get("input_tokens", 0) + x.get("output_tokens", 0) for x in u)
        print(f"  {r['status']:<10} {r.get('created_at', '')}  agent={r['agent_id'][:8]}  tok={tok}")

    done = [r for r in runs if r.get("status") == "completed" and (r.get("result") or {}).get("output")]
    if done:
        print("\n最后一条产出：\n" + done[0]["result"]["output"])
    else:
        print("\n没有成功产出，检查失败运行的 error 字段。")


if __name__ == "__main__":
    main()
