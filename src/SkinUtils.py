# Copyright (C) 2018-2026 by xcentaurix
# License: GNU General Public License v3.0


from pathlib import Path
from Tools.Directories import SCOPE_SKIN
from skin import loadSkin, findSkinScreen
from .ScreenSummaryFix import patchScreenApplySkin
# from .Debug import logger


def getSkinPath(file_name):
    # logger.info("file_name: %s", file_name)
    skin_path = Path(__file__).parent / "skin" / file_name
    return str(skin_path)


def loadPluginSkin(screen_name=None, file_name="skin.xml", session=None):  # pylint: disable=unused-argument
    if screen_name is not None and findSkinScreen(screen_name) is not None:
        return
    skin_file = str(Path(__file__).parent / "skin" / "default" / file_name)
    loadSkin(skin_file, scope=SCOPE_SKIN)
    patchScreenApplySkin()
