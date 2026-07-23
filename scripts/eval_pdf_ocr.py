#!/usr/bin/env python3
"""从仓库根目录运行生产 OCR engine 的合成扫描页回归门禁。"""

from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.documents.pdf_ocr_benchmark import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
