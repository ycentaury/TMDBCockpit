# Copyright (C) 2018-2026 by xcentaurix
# License: GNU General Public License v3.0


import os
from twisted.internet import threads, reactor
from enigma import eServiceReference
from Components.ActionMap import HelpableActionMap
from Components.Button import Button
from Components.config import config
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.ScrollLabel import ScrollLabel
from Screens.ChoiceBox import ChoiceBox
from Screens.InfoBar import MoviePlayer
from Screens.HelpMenu import HelpableScreen
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Tools.LoadPixmap import LoadPixmap
from Tools.BoundFunction import boundFunction
from .__init__ import _
from .SetupScreen import SetupScreen
from .ScreenPeople import ScreenPeople
from .ScreenSeason import ScreenSeason
from .Picture import Picture
from .Debug import logger
from .SearchMovie import SearchMovie
from .MoreOptions import MoreOptions
from .PluginUtils import getPlugin, WHERE_SEARCH
from .Utils import temp_dir
from .YouTubeVideoUrl import YouTubeVideoUrl


class TrailerPlayer(MoviePlayer):
    """Custom trailer player based on TMDB plugin"""
    def __init__(self, session, service, trailer_path=None):
        MoviePlayer.__init__(self, session, service)
        self.skinName = 'MoviePlayer'
        self.trailer_path = trailer_path
        self["actions"] = HelpableActionMap(
            self,
            "MoviePlayerActions",
            {
                "leavePlayer": (self.leavePlayer, _("Leave trailer player"))
            }
        )
        self.setTitle(_("Trailer Player"))

    def leavePlayer(self):
        self.close()

    def doEofInternal(self, _playing):
        self.close()

    def showMovies(self):
        pass

    def openServiceList(self):
        if hasattr(self, 'toggleShow'):
            self.toggleShow()

    def close(self, *args):
        if self.trailer_path and os.path.isfile(self.trailer_path):
            try:
                os.remove(self.trailer_path)
            except OSError as e:
                logger.error("Failed to delete downloaded trailer: %s", e)
            self.trailer_path = None
        MoviePlayer.close(self, *args)


class ScreenMovie(MoreOptions, Picture, Screen, HelpableScreen):

    def __init__(self, session, movie, media, cover_url, ident, service_path, backdrop_url):
        logger.debug(
            "movie: %s, media: %s, cover_url: %s, ident: %s, service_path: %s, backdrop_url: %s",
            movie, media, cover_url, ident, service_path, backdrop_url
        )
        Screen.__init__(self, session)
        self.skinName = "ScreenMovie"
        Picture.__init__(self)
        MoreOptions.__init__(self, session, service_path)
        self.title = _("Movie Details")
        self.session = session
        self.movie = movie
        self.media = media
        self.cover_url = cover_url
        self.backdrop_url = backdrop_url
        self.ident = ident
        self.service_path = service_path
        self.files_saved = False
        self.overview = ""
        self.result = {}
        self.movie_title = ""
        self.original_title = ""
        self.videos = []
        self._wait_box = None
        self._pending_trailer = None

        self["genre"] = Label()
        self["genre_txt"] = Label()
        self["fulldescription"] = self.fulldescription = ScrollLabel("")
        self["rating"] = Label()
        self["votes"] = Label()
        self["votes_brackets"] = Label()
        self["votes_txt"] = Label()
        self["runtime"] = Label()
        self["runtime_txt"] = Label()
        self["year"] = Label()
        self["year_txt"] = Label()
        self["country"] = Label()
        self["country_txt"] = Label()
        self["director"] = Label()
        self["director_txt"] = Label()
        self["author"] = Label()
        self["author_txt"] = Label()
        self["studio"] = Label()
        self["studio_txt"] = Label()

        self.fields = {
            "genre": (_("Genre:"), "-"),
            "fulldescription": (None, ""),
            "rating": (None, "0.0"),
            "votes": (_("Votes:"), "-"),
            "votes_brackets": (None, ""),
            "runtime": (_("Runtime:"), "-"),
            "year": (_("Year:"), "-"),
            "country": (_("Countries:"), "-"),
            "director": (_("Director:"), "-"),
            "author": (_("Author:"), "-"),
            "studio": (_("Studio:"), "-"),
        }

        self["key_red"] = Button(_("Exit"))
        self["key_green"] = Button(_("Crew"))
        self["key_yellow"] = Button(
            _("Seasons")) if self.media == "tv" else Button("")
        self["key_blue"] = Button(
            _("more ...")) if self.service_path else Button("")
        self["key_menu"] = Button(_("Menu"))

        self["searchinfo"] = Label()
        self["cover"] = Pixmap()
        self["backdrop"] = Pixmap()
        self["fsklogo"] = Pixmap()
        self["star"] = Pixmap()
        self.fsk = {"0": "fsk_0.png", "6": "fsk_6.png", "12": "fsk_12.png", "16": "fsk_16.png", "18": "fsk_18.png"}

        HelpableScreen.__init__(self)
        self["actions"] = HelpableActionMap(
            self,
            "TMDBActions",
            {
                "ok": (self.green, _("Crew")),
                "red": (boundFunction(self.exit, True), _("Exit")),
                "up": (self.fulldescription.pageUp, _("Selection up")),
                "down": (self.fulldescription.pageDown, _("Selection down")),
                "left": (self.fulldescription.pageUp, _("Page up")),
                "right": (self.fulldescription.pageDown, _("Page down")),
                "cancel": (boundFunction(self.exit, False), _("Cancel")),
                "green": (self.green, _("Crew")),
                "yellow": (self.yellow, _("Seasons")),
                "blue": (self.showMenu, _("more ...")),
                "menu": (self.setup, _("Setup")),
                "eventview": (self.search, _("Search"))
            },
            -1,
        )

        self.onLayoutFinish.append(self.__onLayoutFinish)

    def __onLayoutFinish(self):
        logger.debug("movie: %s", self.movie)
        self.showPicture(self["cover"], "cover", self.ident, self.cover_url)
        self.showPicture(self["backdrop"], "backdrop",
                         self.ident, self.backdrop_url)
        self["searchinfo"].setText(_("Looking up: %s ...") % self.movie)
        threads.deferToThread(self.getData, self.gotData)

    def getData(self, callback):
        result = SearchMovie().getResult(self.result, self.ident, self.media)
        logger.debug("result: %s", result)
        reactor.callFromThread(callback, result)

    def gotData(self, result):
        if not result:
            self["searchinfo"].setText(_("No results for: %s") % self.movie)
            self.overview = ""
        else:
            self["searchinfo"].setText(self.movie)
            path = "/usr/lib/enigma2/python/Plugins/Extensions/TMDBCockpit/skin/images/star.png"
            self["star"].instance.setPixmap(LoadPixmap(path))
            path = "/usr/lib/enigma2/python/Plugins/Extensions/TMDBCockpit/skin/images/" + \
                self.fsk.get(result["fsk"], "fsk_0.png")
            self["fsklogo"].instance.setPixmap(LoadPixmap(path))

            for field, (label, default) in self.fields.items():
                # logger.debug("field: %s", field)
                # logger.debug("result: %s", result[field])
                if label:
                    self[field + "_txt"].setText(label)
                if result[field]:
                    self[field].setText(result[field])
                else:
                    self[field].setText(default)

            self.overview = result["overview"]

            self.movie_title = self.original_title = ""
            if self.media == "movie":
                self.movie_title = result["title"]
                self.original_title = result["original_title"]
                self.videos = result["videos"]
                videos_label = _("Videos")
                self["key_yellow"].setText(
                    f"{videos_label} ({len(self.videos)})")
            elif self.media == "tv":
                self.movie_title = result["name"]

    def showMenu(self):
        self.menu(self.ident, self.overview)

    def search(self):
        search_plugin = getPlugin(WHERE_SEARCH)
        if search_plugin:
            search_plugin(self.session, self.movie_title, self.original_title)
        else:
            self.session.open(MessageBox, _(
                "No search provider registered."), type=MessageBox.TYPE_INFO)

    def setup(self):
        self.session.open(SetupScreen)

    def yellow(self):
        if self.media == "tv":
            self.session.openWithCallback(
                self.screenSeasonCallback, ScreenSeason, self.movie, self.ident, self.media, self.service_path)
        elif self.media == "movie" and self.videos:
            videolist = []
            for video in self.videos:
                vKey = video["key"]
                vName = video["name"]
                videolist.append((str(vName), str(vKey)))

            if len(videolist) > 1:
                videolist = sorted(videolist, key=lambda x: x[0])
                self.session.openWithCallback(
                    self.videolistCallback,
                    ChoiceBox,
                    title=_("Please select a video"),
                    list=videolist,
                )
            elif len(videolist) == 1:
                self.videolistCallback(videolist[0])

    def screenSeasonCallback(self, do_exit, files_saved):
        self.files_saved = files_saved
        if do_exit:
            self.exit(True)

    def videolistCallback(self, ret):
        if ret:
            video_id = ret[1]
            video_name = ret[0]
            # YouTube now blocks direct streaming of the combined-format URLs yt-dlp
            # can extract (403 Forbidden without a PO token), so the trailer is
            # downloaded (DASH video+audio merged via ffmpeg) and played back locally.
            self._pending_trailer = None
            # Must use openWithCallback here: Session.close() only *schedules* the
            # dialog-stack pop via a delayed timer, so opening TrailerPlayer right
            # after wait_box.close() (before that pop actually runs) hits Enigma2's
            # "Modal open are allowed only from a screen which is modal" guard. The
            # openWithCallback callback only fires once that pop has completed.
            self._wait_box = self.session.openWithCallback(
                self.trailerWaitBoxClosed, MessageBox, _('Downloading trailer ...'),
                MessageBox.TYPE_INFO, enable_input=False)
            resolution_itag = config.plugins.tmdbcockpit.yttrailer_best_resolution.value
            use_dash = config.plugins.tmdbcockpit.yttrailer_useDashMP4.value
            deferred = threads.deferToThread(
                YouTubeVideoUrl.download, video_id, temp_dir, resolution_itag, use_dash)
            deferred.addCallback(boundFunction(self.trailerDownloaded, video_name))
            deferred.addErrback(self.trailerDownloadFailed)

    def trailerDownloaded(self, video_name, path):
        self._pending_trailer = (video_name, path)
        self._wait_box.close()

    def trailerDownloadFailed(self, failure):
        logger.error("Failed to download YouTube trailer: %s", failure.getErrorMessage())
        self._pending_trailer = None
        self._wait_box.close()

    def trailerWaitBoxClosed(self, *_args):
        self._wait_box = None
        pending, self._pending_trailer = self._pending_trailer, None
        if pending:
            video_name, path = pending
            ref = eServiceReference(4097, 0, path)
            ref.setName(video_name)
            self.session.open(TrailerPlayer, ref, path)
        else:
            self.session.open(MessageBox, _('Trailer playback failed.'), MessageBox.TYPE_INFO, timeout=3)

    def green(self):
        self.session.openWithCallback(self.screenPeopleCallback, ScreenPeople,
                                      self.movie, self.ident, self.media, self.cover_url, self.backdrop_url)

    def screenPeopleCallback(self, do_exit):
        if do_exit:
            self.exit(True)

    def exit(self, do_exit):
        self.close(do_exit, self.files_saved)
