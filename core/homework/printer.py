"""Safe local macOS printing adapter for reviewed/generated homework PDFs."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class PrinterError(RuntimeError):
    pass


def list_printers(*, runner=subprocess.run) -> list[str]:
    if sys.platform != "darwin":
        raise PrinterError("自动打印目前仅支持家庭 Mac；请在 Mac 上运行")
    try:
        result = runner(["/usr/bin/lpstat", "-p"], capture_output=True, text=True,
                        timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PrinterError("无法读取 macOS 打印队列") from exc
    if result.returncode != 0:
        raise PrinterError("读取打印队列失败")
    names = []
    for line in (result.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "printer":
            name = parts[1]
            if name and all(ch.isalnum() or ch in "._-" for ch in name):
                names.append(name)
    return sorted(set(names))


def submit_pdf(pdf_path: str | Path, *, printer: str, generated_dir: str | Path,
               confirmed: bool = False, runner=subprocess.run) -> str:
    """Submit only a generated PDF, and only after explicit human confirmation."""
    if not confirmed:
        raise PrinterError("打印尚未确认；请先预览 PDF 并显式确认")
    if sys.platform != "darwin":
        raise PrinterError("自动打印目前仅支持家庭 Mac")
    if not printer or not all(ch.isalnum() or ch in "._-" for ch in printer):
        raise PrinterError("无效的打印机名称")
    root = Path(generated_dir).expanduser().resolve()
    target = Path(pdf_path).expanduser().resolve()
    if root not in target.parents:
        raise PrinterError("只允许打印糖糖生成目录内的文件")
    if not target.is_file() or target.suffix.lower() != ".pdf":
        raise PrinterError("打印文件必须是存在的 PDF")
    try:
        result = runner(["/usr/bin/lp", "-d", printer, "--", str(target)],
                        capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PrinterError("提交打印任务失败") from exc
    if result.returncode != 0:
        raise PrinterError("打印队列拒绝了任务")
    return (result.stdout or "打印任务已提交").strip()[:300]
