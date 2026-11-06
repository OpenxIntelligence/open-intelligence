"""Refuse verification evidence attributed to a different or modified Git revision."""
import argparse
import json
import re
import subprocess
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head", required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_head):
        parser.error("expected head must be a full commit SHA")

    def git(*arguments):
        return subprocess.check_output(["git", *arguments], text=True,
                                       stderr=subprocess.PIPE).strip()

    try:
        actual = git("rev-parse", "HEAD")
        if actual != args.expected_head:
            raise ValueError("Checkout does not match the expected proposed revision")
        if git("status", "--porcelain", "--untracked-files=no"):
            raise ValueError("Checkout contains tracked changes outside the proposed revision")
        tree = git("rev-parse", "HEAD^{tree}")
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        message = str(error) if isinstance(error, ValueError) else "Cannot inspect Git checkout"
        print(message, file=sys.stderr)
        return 1
    print(json.dumps({"commit": actual, "tree": tree, "tracked_tree_clean": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
