#!/usr/bin/env python3
"""Build the pinned LibreChat image with its model picker in the composer."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".cache" / "librechat-v0.8.9"
PATCHES = ROOT / "scripts" / "librechat_patches"
IMAGE = "ab-agentic-ai/librechat-composer:v0.8.9"
TAG = "v0.8.9"


def run(*args: str, cwd: Path = ROOT) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def replace_once(path: Path, before: str, after: str) -> None:
    source = path.read_text()
    count = source.count(before)
    if count != 1:
        raise SystemExit(f"Expected one patch anchor in {path.relative_to(SOURCE)}, found {count}.")
    path.write_text(source.replace(before, after, 1))


def apply_composer_picker_patch() -> None:
    header = SOURCE / "client/src/components/Chat/Header.tsx"
    bar = SOURCE / "client/src/components/Chat/Input/Composer/Bar.tsx"
    selector = SOURCE / "client/src/components/Chat/Menus/Endpoints/ModelSelector.tsx"
    quota_component = SOURCE / "client/src/components/Chat/Input/GeminiQuotaIndicator.tsx"
    shutil.copyfile(PATCHES / "GeminiQuotaIndicator.tsx", quota_component)

    replace_once(
        header,
        "import ModelSelector from './Menus/Endpoints/ModelSelector';\n",
        "",
    )
    replace_once(header, "        {!readOnly && <ModelSelector startupConfig={startupConfig} />}\n", "")

    replace_once(
        bar,
        "import { cn } from '~/utils';\n",
        "import { cn } from '~/utils';\n"
        "import ModelSelector from '~/components/Chat/Menus/Endpoints/ModelSelector';\n"
        "import GeminiQuotaIndicator from '~/components/Chat/Input/GeminiQuotaIndicator';\n"
        "import { useGetStartupConfig } from '~/data-provider';\n",
    )
    replace_once(
        bar,
        "  const localize = useLocalize();\n  const context = useBadgeRowContext();\n",
        "  const localize = useLocalize();\n"
        "  const { data: startupConfig } = useGetStartupConfig();\n"
        "  const context = useBadgeRowContext();\n",
    )
    replace_once(
        bar,
        "            anchorRef={anchorRef}\n          />\n        </span>\n"
        "        {/* A box rather than `contents` so it has something to move: the split\n",
        "            anchorRef={anchorRef}\n          />\n        </span>\n"
        "        <div className=\"flex min-w-0 shrink items-center gap-1.5\">\n"
        "          <ModelSelector startupConfig={startupConfig} />\n"
        "          <GeminiQuotaIndicator\n"
        "            endpoint={endpoint}\n"
        "            model={conversation?.model}\n"
        "            agentId={conversation?.agent_id}\n"
        "            isSubmitting={isSubmitting}\n"
        "          />\n"
        "        </div>\n"
        "        {/* A box rather than `contents` so it has something to move: the split\n",
    )
    replace_once(
        selector,
        "className=\"border-border-light bg-presentation text-text-primary hover:bg-surface-active-alt rounded-theme-control flex h-9 max-w-full items-center gap-2 border px-3 py-2 text-sm\"",
        "className=\"border-border-light bg-presentation text-text-primary hover:bg-surface-active-alt rounded-theme-control flex h-7 max-w-full items-center gap-1.5 border px-2 py-1 text-xs\"",
    )


def main() -> None:
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    if not (SOURCE / ".git").exists():
        if SOURCE.exists():
            shutil.rmtree(SOURCE)
        run(
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            TAG,
            "https://github.com/LibreChat-AI/LibreChat.git",
            str(SOURCE),
        )
    else:
        current = subprocess.run(
            ["git", "-C", str(SOURCE), "rev-parse", "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        expected = subprocess.run(
            ["git", "-C", str(SOURCE), "rev-parse", f"refs/tags/{TAG}^{{commit}}"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        if current != expected:
            raise SystemExit(
                f"LibreChat source commit {current} does not match pinned tag {TAG} ({expected})."
            )

    # Reset just the source files so rerunning this script never applies a patch twice.
    for relative in (
        "client/src/components/Chat/Header.tsx",
        "client/src/components/Chat/Input/Composer/Bar.tsx",
        "client/src/components/Chat/Menus/Endpoints/ModelSelector.tsx",
    ):
        run("git", "-C", str(SOURCE), "checkout", "--", relative)
    apply_composer_picker_patch()
    run("docker", "build", "--tag", IMAGE, str(SOURCE))
    print(f"Built {IMAGE} with the model picker in the message composer.")


if __name__ == "__main__":
    main()
