# Copyright (C) 2018-2026 by xcentaurix
# License: GNU General Public License v3.0


from Components.config import config
from Plugins.Plugin import PluginDescriptor
from .__init__ import _
from .Debug import logger
from .Version import VERSION
from . import ConfigInit  # noqa: F401, pylint: disable=unused-import
from .ScreenMain import ScreenMain
from .ScreenTMDB import ScreenTMDB
from .PluginUtils import WHERE_TMDB_SEARCH, WHERE_TMDB_MOVIELIST
from .SkinUtils import loadPluginSkin


loadPluginSkin("ScreenMain")


def monkeyPatchAllEPGScreens():
    """
    Monkey patch EPGSelectionBase without requiring any core system changes
    This overrides both the button action AND the button label
    """
    from Screens.EpgSelectionBase import EPGSelectionBase, EPGStandardButtons
    from Screens.UserDefinedButtons import UserDefinedButtons

    # Store originals
    original_helpKeyAction = EPGStandardButtons.helpKeyAction
    original_udb_init = UserDefinedButtons.__init__

    def customOpenTMDb(self):
        """TMDBCockpit custom handler"""
        logger.info("[TMDBCockpit] EPG red button pressed (openTMDb)")
        event = self["list"].getCurrent()[0]
        if event is not None:
            event_name = event.getEventName()
            logger.info("[TMDBCockpit] Opening for event: %s", event_name)
            self.session.open(ScreenMain, event_name, 2)

    def customHelpKeyAction(self, actionName):
        """Override helpKeyAction to use our custom openTMDb only if TMDb is selected"""
        if actionName == "red" and self.tmdb:  # Only override if TMDb is selected
            return (customOpenTMDb.__get__(self, type(self)), _("TMDB Infos for current event"))
        return original_helpKeyAction(self, actionName)

    def customUDBInit(self, epgConfig, *args):
        """Override UserDefinedButtons.__init__ to patch button config"""
        # Call original init
        original_udb_init(self, epgConfig, *args)
        # After init, update the button config to point to openTMDb
        # This ensures UserDefinedButtons-based screens use our handler
        if hasattr(self, '_UserDefinedButtons__actions') and 'openTMDb' in self._UserDefinedButtons__actions:
            # The action exists, no need to change - our openTMDb override will be used
            pass

    # Apply monkey patches
    EPGSelectionBase.openTMDb = customOpenTMDb
    EPGStandardButtons.helpKeyAction = customHelpKeyAction
    UserDefinedButtons.__init__ = customUDBInit

    logger.info("[TMDBCockpit] EPG override installed for TMDb button (no system changes required)")


def showEventInfos(session, event="", service="", **__):
    if not service:
        service = session.nav.getCurrentlyPlayingServiceReference()
    if not event:
        info = session.nav.getCurrentService()
        if info:
            info = info.info()
            if info:
                event = info.getEvent(0)  # 0 = now, 1 = next
    event_name = event and event.getEventName() or (service and service.getName()) or ""
    session.open(ScreenMain, event_name, 2)


def queryEventInfos(search, callback, **__):
    logger.info("search: %s", search)
    ScreenTMDB(search, callback)


def movieList(session, service, **kwargs):
    logger.info("...")
    callback = kwargs["callback"] if "callback" in kwargs else None
    if callback:
        session.openWithCallback(callback, ScreenMain, service, 1)
    else:
        session.open(ScreenMain, service, 1)


def main(session, **__):
    session.open(ScreenMain, "", 3)


def autoStart(reason, **__):
    if reason == 0:  # startup
        logger.info("+++ Version: %s starts...", VERSION)
        # session = kwargs["session"]
        if config.plugins.tmdbcockpit.key_red.value:
            try:
                monkeyPatchAllEPGScreens()
            except Exception as e:
                logger.error("key red patch failed: %s", e)
    elif reason == 1:  # shutdown
        logger.info("--- shutdown")


def Plugins(**__):
    descriptors = [
        PluginDescriptor(
            where=[
                PluginDescriptor.WHERE_AUTOSTART,
                PluginDescriptor.WHERE_SESSIONSTART,
            ],
            fnc=autoStart,
            needsRestart=True
        ),
        PluginDescriptor(
            name="TMDBCockpit",
            description=_("TMDB Infos"),
            where=[
                WHERE_TMDB_MOVIELIST,
                PluginDescriptor.WHERE_MOVIELIST,
            ],
            fnc=movieList,
            needsRestart=True
        ),
        PluginDescriptor(
            name="TMDBCockpit",
            description=_("TMDB Infos"),
            where=[
                WHERE_TMDB_SEARCH,
            ],
            fnc=queryEventInfos,
            needsRestart=True
        ),
        PluginDescriptor(
            name=_("TMDB Infos"),
            description=_("TMDb Search"),
            where=[
                PluginDescriptor.WHERE_EVENTINFO,
                # PluginDescriptor.WHERE_CHANNEL_CONTEXT_MENU,
            ],
            fnc=showEventInfos,
            needsRestart=True
        ),
        PluginDescriptor(
            name=_("TMDBCockpit"),
            description=_("TMDB Infos"),
            where=[
                PluginDescriptor.WHERE_PLUGINMENU,
                PluginDescriptor.WHERE_EXTENSIONSMENU,
            ],
            icon="plugin.png",
            fnc=main,
            needsRestart=True
        ),
    ]
    try:
        descriptors += [
            PluginDescriptor(
                where=PluginDescriptor.WHERE_SKINCHANGE,
                fnc=loadPluginSkin
            )
        ]
    except Exception:
        pass

    return descriptors
