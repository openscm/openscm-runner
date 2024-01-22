"""
Re-write previous CHANGELOG.rst into lines required by docs/source/changelog.md
"""
from __future__ import annotations

import re

section_header_map = {
    "Added": "Features",
    "Changed": "Improvements",
    "Fixed": "Bug Fixes",
}


def main() -> None:
    """
    Re-write the CHANGELOG
    """
    with open("CHANGELOG.rst") as fh:
        contents = fh.read()

    lines = tuple(contents.splitlines())
    for i, line in enumerate(lines):
        if not line:
            continue

        if line.startswith("v0."):
            version, date = line.split(" - ")
            new_header = f"## openscm-runner {version} ({date})"
            print()
            print(new_header)
            print()
            continue

        if all(c == "~" for c in line):
            section_header_original = lines[i - 1]
            section_name = section_header_map[section_header_original]
            section_header = f"### {section_name}"
            print()
            print(section_header)
            print()
            continue

        if line.startswith("- "):
            match = re.match(
                r"- \(`#(?P<pr_number>\d+)\s.*\) (?P<desc>.*)",
                line,
            )
            try:
                pr_number = match.group("pr_number")
            except AttributeError:
                continue

            desc = match.group("desc")
            new_line = f"- {desc} ([#{pr_number}](https://github.com/openscm/openscm-runner/pulls/{pr_number}))"
            print(new_line)


if __name__ == "__main__":
    main()
