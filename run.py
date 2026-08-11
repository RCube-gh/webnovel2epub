"""開発中でもインストールせずにCLIを実行するための入口。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from narou2kindle.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
