"""The scripts "New from template" copies into the workspace (plan-u1 §6).

Each is a real etalon M0 script (2D TE) in ``etalon/studio/templates/`` that
runs in seconds on one GPU. Titles and descriptions are i18n keys in the
frontend (``templates.<id>.title/description``), so only ids and files live here.
"""

import re
from pathlib import Path
from typing import get_args

from etalon.studio.contract import NAME_PATTERN, Template, TemplateId
from etalon.studio.errors import StudioError

TEMPLATE_DIR = Path(__file__).with_name("templates")
TEMPLATE_IDS: tuple[TemplateId, ...] = get_args(TemplateId)


def list_templates() -> list[Template]:
    return [Template(id=template_id, file=f"{template_id}.py") for template_id in TEMPLATE_IDS]


def create_from_template(template: TemplateId, name: str, workspace: Path) -> Path:
    """Copy a template to ``<workspace>/<name>.py``; never overwrites."""
    if re.fullmatch(NAME_PATTERN, name) is None:
        raise StudioError(422, "bad_name", f"{name!r} is not a valid script name")
    source = TEMPLATE_DIR / f"{template}.py"
    target = workspace / f"{name}.py"
    try:
        with open(target, "xb") as file:
            file.write(source.read_bytes())
    except FileExistsError:
        raise StudioError(409, "exists", f"{target.name} already exists") from None
    return target
