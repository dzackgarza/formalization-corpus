#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "port-sources" / "acl2__acl2"

signal = re.compile(
    r"(?im)^\s*\((?:[\w:.-]*def(?:un|thm|macro|const|pkg|stobj|absstobj|section|aggregate|prod|enum|tagsum|list|projection|xdoc|rstobj|parser)|"
    r"define|encapsulate|mutual-recursion|defchoose|defequiv|defcong|defrefinement|make-event|assert-event|table|"
    r"[\w:.-]*define|[\w:.-]*defparser|[\w:.-]*defsection)\b"
)

for unit in sys.argv[1:]:
    mf = ROOT / "filtering" / "repository-review" / "files" / "acl2__acl2" / f"{unit}.jsonl"
    print(f"### {unit}")
    for line in mf.read_text().splitlines():
        row = json.loads(line)
        p = row["path"]
        if row["current_primary_status"] != "primary-retained" or "/.sys/" in p:
            continue
        text = (SOURCE / p).read_text(errors="replace")
        if not signal.search(text):
            print(f"{p}\t{len(text)}")
