# -*- coding: UTF-8 -*-
import re
import sys
import os
import time
import json
import zipfile
import rarfile
import urllib
import http.cookiejar as cookielib
import urllib.request as urllib2
from bs4 import BeautifulSoup

DEBUG_MODE = True

if not DEBUG_MODE:
    from kodi_six import xbmc, xbmcgui, xbmcaddon, xbmcplugin, xbmcvfs

    __addon__ = xbmcaddon.Addon()
    __author__ = __addon__.getAddonInfo("author")
    __scriptid__ = __addon__.getAddonInfo("id")
    __scriptname__ = __addon__.getAddonInfo("name")
    __version__ = __addon__.getAddonInfo("version")
    __language__ = __addon__.getLocalizedString
    __cwd__ = xbmc.translatePath(
        __addon__.getAddonInfo("path")).decode("utf-8")
    __profile__ = xbmc.translatePath(
        __addon__.getAddonInfo("profile")).decode("utf-8")
    __resource__ = xbmc.translatePath(os.path.join(__cwd__, "resources", "lib")).decode(
        "utf-8"
    )
    __temp__ = xbmc.translatePath(os.path.join(
        __profile__, "temp")).decode("utf-8")
    sys.path.append(__resource__)
    sys = reload(sys)
    sys.setdefaultencoding("UTF-8")

ZIMUKU_API = "https://zimuku.org/search?q=%s"
ZIMUKU_BASE = "https://zimuku.org"
ZIMUKU_DOWNLOAD = "https://s.zmk.pw"
USER_AGENT = "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; Trident/6.0)"
EXTS = [".srt", ".ass", ".rar", ".zip"]

REFERER_PAGE_HEADER = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
    'Host': 'zimuku.org',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-User': 'none',
    'Sec-Fetch-User': '?1',
    'TE': 'trailers',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:93.0) Gecko/20100101 Firefox/93.0'
}

DOWNLOAD_REQ_HEADER = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
    'Connection': 'keep-alive',
    'Cookie': '',
    'Host': 'zimuku.org',
    'Referer': '',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:93.0) Gecko/20100101 Firefox/93.0'
}


def DebugLog(*msgs):
    if DEBUG_MODE:
        print("[DEBUG]: ", msgs)
    else:
        if isinstance(msgs, unicode):
            msgs = msgs.encode("utf-8")
        xbmc.log(
            "{0}::{1} - {2}".format(
                __scriptname__, sys._getframe().f_code.co_name, msgs
            ),
            level=xbmc.LOGDEBUG,
        )


def HtmlRead(url, retry=5):
    data = ""
    for i in range(retry):
        try:
            req = urllib2.Request(url)
            req.add_header("User-Agent", USER_AGENT)
            socket = urllib2.urlopen(req)
            data = socket.read()
            socket.close()
            break
        except:
            DebugLog(
                "Reading html got error on line: %s, error: %s"
                % (sys.exc_info()[2].tb_lineno, sys.exc_info()[1])
            )
            time.sleep(30)
            DebugLog("After 30s, retry %d times.", i + 1)
            continue
    return BeautifulSoup(data, "html.parser")


def GetLink(sub):
    ret = ''
    try:
        td = sub.find("td", class_="first")
        #DebugLog("td: ", td)
        link = td.a.get("href")
        #DebugLog('link: ', link)
        ret = "%s%s" % (ZIMUKU_BASE, link)
    except:
        DebugLog(
            "Failed to get link on line: %s, error: %s"
            % (sys.exc_info()[2].tb_lineno, sys.exc_info()[1])
        )
    return ret


def GetLangs(sub):
    langs = ''
    language_name = ''
    language_flag = ''
    try:
        td = sub.find("td", class_="tac lang")
        #DebugLog("td: ", td)
        imgs = td.find_all("img")
        #DebugLog("imgs: ", imgs)
        titles = [x.get('title') for x in imgs]
        #DebugLog("titles: ", titles)
        for i in titles:
            langs = langs + i + ' '
        langs = langs.replace("English", "英语")
        langs = langs.rstrip()
        if '简体中文' in titles or '繁體中文' in titles or '双语' in titles:
            language_name = "Chinese"
            language_flag = "zh"
        else:
            language_name = "English"
            language_flag = "en"
    except:
        langs = '未知'
        DebugLog(
            "Failed to get languages on line: %s, error: %s"
            % (sys.exc_info()[2].tb_lineno, sys.exc_info()[1])
        )
    return langs, language_name, language_flag


def GetName(sub, langs):
    ret = ''
    try:
        td = sub.find("td", class_="first")
        #DebugLog("td: ", td)
        title = td.a.get("title")
        #DebugLog('title: ', title)
        for ext in EXTS:
            title = title.replace(ext, '')
        ret = "%s (%s)" % (title, langs)
        #DebugLog('name: ', ret)
    except:
        DebugLog(
            "Failed to get name on line: %s, error: %s"
            % (sys.exc_info()[2].tb_lineno, sys.exc_info()[1])
        )
    return ret


def GetRatingAndDownloadNum(sub):
    ret = 0, 0
    try:
        tds = sub.find_all("td", class_="tac hidden-xs")
        #DebugLog("tds: ", tds)
        title = tds[0].i.get("title")
        #DebugLog('title: ', title)
        rating = re.sub("[^0-9]", "", title)
        #DebugLog('rating: ', rating)
        text = tds[1].text
        #DebugLog('text: ', text)
        number = re.sub("[^0-9]", "", text)
        #DebugLog('download number: ', number)
        ret = rating, number
    except:
        DebugLog(
            "Failed to get rating and download number on line: %s, error: %s"
            % (sys.exc_info()[2].tb_lineno, sys.exc_info()[1])
        )
    return ret


def GetSubId(href):
    ret = 0
    try:
        ret = int(re.sub("[^0-9]", "", href))
    except:
        pass
    return ret


def Search(name):
    subtitles_list = []
    DebugLog("Search for [%s] by name" % name)
    url = ZIMUKU_API % (urllib.parse.quote(name))
    DebugLog("Search API url: %s" % url)
    soup = HtmlRead(url)
    results = soup.find_all("div", class_="item prel clearfix")
    # print(results)

    for it in results:
        movie_name = it.find("div", class_="title").a.text.encode("utf-8")
        DebugLog("Movie name: ", movie_name.decode("utf-8"))
        herf = it.find("div", class_="title").a.get("href")
        subid = GetSubId(herf)
        if subid == 0:
            continue
        movie_url = urllib.parse.urljoin(ZIMUKU_BASE, herf)
        DebugLog("Movie url: ", movie_url)
        soup = HtmlRead(movie_url).find("div", class_="subs box clearfix")
        subs = soup.tbody.find_all("tr")
        for sub in subs:
            link = GetLink(sub)
            langs, language_name, language_flag = GetLangs(sub)
            name = GetName(sub, langs)
            rating, download_num = GetRatingAndDownloadNum(sub)
            subtitles_list.append(
                {
                    "filename": name,
                    "link": link,
                    "language_name": language_name,
                    "language_flag": language_flag,
                    "rating": rating,
                    "download_num": download_num,
                    "subid": subid
                }
            )
    DebugLog("Sub titles:", len(subtitles_list))
    for it in subtitles_list:
        DebugLog(it)
    return subtitles_list


# select the right format and language of subtitle files
def SelectFile(rf):
    rf_list = rf.infolist()
    score_list = [0 for x in range(len(rf_list))]
    for i, f in enumerate(rf_list):
        if not f.is_dir():
            score_list[i] += 1
        if ".ass" in f.filename:
            score_list[i] += 2
        if ".srt" in f.filename:
            score_list[i] += 3
        if "eng" in f.filename:
            score_list[i] += 1
        if "cht" in f.filename:
            score_list[i] += 2
        if "chs" in f.filename:
            score_list[i] += 3
    at = score_list.index(max(score_list))
    return rf_list[at]


def UnzipAndClean(pkg_name, extension_name, path_to, new_name):
    if extension_name == ".rar":
        rf = rarfile.RarFile(pkg_name)
        f = SelectFile(rf)
        f.filename = os.path.basename(f.filename)
        DebugLog("Select subtitle file: %s, size: %d" %
                 (f.filename, f.file_size))
        rf.extract(f, path_to)
        old_name = f.filename
    elif extension_name == ".zip":
        zf = zipfile.ZipFile(pkg_name)
        f = SelectFile(zf)
        f.filename = os.path.basename(f.filename)
        DebugLog("Select subtitle file: %s, size: %d" %
                 (f.filename, f.file_size))
        ret = zf.extract(f, path_to)
        print(ret)
        old_name = f.filename
    elif extension_name == ".srt" or extension_name == ".ass":
        old_name = pkg_name

    # rename new file
    new_name += old_name[-4:]
    if os.path.exists(new_name):
        os.remove(new_name)
        DebugLog("Remove new file: %s" % new_name)
    if os.path.exists(old_name):
        os.rename(old_name, new_name)
        DebugLog("Rename file: %s to %s" % (old_name, new_name))

    # delete old files
    if os.path.exists(old_name):
        os.remove(old_name)
        DebugLog("Remove old file: %s" % old_name)

    # delete pkg files
    if os.path.exists(pkg_name):
        os.remove(pkg_name)
        DebugLog("Remove pkg file: %s" % pkg_name)

    return True


# try to download for a single link
def DownloadOne(link, referer):
    down_url = link.get("href")
    if down_url[:4] != "http":
        down_url = ZIMUKU_BASE + down_url
    try:
        DebugLog("Trying to download: %s" % down_url)
        # set cookies
        cj = cookielib.LWPCookieJar()
        cookie_support = urllib2.HTTPCookieProcessor(cj)
        # install opener
        opener = urllib2.build_opener(cookie_support, urllib2.HTTPHandler)
        urllib2.install_opener(opener)
        # open referer page to get cookie
        DebugLog("Trying to send referer request to: ", referer)
        DebugLog("Trying to send referer request header: ",
                 REFERER_PAGE_HEADER)
        request = urllib2.Request(referer, headers=REFERER_PAGE_HEADER)
        response = urllib2.urlopen(request)
        print(response.headers)
        # get cookie key words
        session_id = ''
        session_verify = ''
        for index, cookie in enumerate(cj):
            DebugLog("Cookie: ", cookie)
            if cookie.name == 'PHPSESSID':
                session_id = cookie.value
            if cookie.name == 'yunsuo_session_verify':
                session_verify = cookie.value
        if not session_id:
            DebugLog("Failed to get cookie, exit")
            return "", ""
        else:
            DebugLog("PHPSESSID: ", session_id)
            DebugLog("yunsuo_session_verify: ", session_verify)
        # prepare header with cookie
        subid = GetSubId(referer)
        DebugLog("Subtitle Id: ", subid)
        DOWNLOAD_REQ_HEADER['Cookie'] = 'yunsuo_session_verify=%s; zmk_home_view_subid=%s; PHPSESSID=%s' % (
            session_verify, subid, session_id)
        DOWNLOAD_REQ_HEADER['Referer'] = referer
        # open download url
        DebugLog("Trying to send download request to: ", down_url)
        DebugLog("Trying to send download request header: ",
                 DOWNLOAD_REQ_HEADER)
        request = urllib2.Request(down_url, headers=DOWNLOAD_REQ_HEADER)
        response = urllib2.urlopen(request)
        print(response.headers)
        DebugLog("Response header: ", response.headers['location'])
    except:
        raise
        DebugLog(
            "Failed to download on line: %s, error: %s"
            % (sys.exc_info()[2].tb_lineno, sys.exc_info()[1])
        )

    return "", ""


# from main page to get every link and select one to downloa to a file
def Download(url, path_to, new_name):
    soup = HtmlRead(url)
    download_page_url = soup.find("li", class_="dlsub").a.get("href")
    if not (
        download_page_url.startswith("http://")
        or download_page_url.startswith("https://")
    ):
        download_page_url = urllib.parse.urljoin(
            ZIMUKU_BASE, download_page_url)
    DebugLog("Download page: ", download_page_url)
    soup_d_page = HtmlRead(download_page_url)
    links = soup_d_page.find("div", {"class": "clearfix"}).find_all("a")
    DebugLog("Download links: ", links)
    for link in links:
        # trying to download
        filename, data = DownloadOne(link, download_page_url)
        # check size
        if len(data) < 1024:
            DebugLog("Download subtitle file size incorrect: %d" % len(data))
            continue
        DebugLog("Download subtitle file size: %d" % len(data))
        # check extension
        ext = os.path.splitext(filename)[1].lower()
        if not ext in EXTS:
            DebugLog("Download subtitle file extension unknown: %s" % filename)
            return False
        DebugLog("Download subtitle file name: %s" % filename)
        # write to a temporary file
        now = time.time()
        ts = time.strftime("%Y%m%d%H%M%S", time.localtime(now)) + str(
            int((now - int(now)) * 1000)
        )
        sub_name = os.path.join(
            path_to, "subtitles%s%s" % (ts, os.path.splitext(filename)[1])
        ).replace("\\", "/")
        with open(sub_name, "wb") as f:
            f.write(data)
        f.close()
        DebugLog("Write subtitle file: %s" % sub_name)
        # unzip and delete unnecessary files
        if UnzipAndClean(sub_name, ext, path_to, new_name):
            return True

    return False


# there are always severl matched subtitles, return ordered links with priority
def SlectSubtitle(subtitles_list):
    ret_list = []
    if len(subtitles_list) > 0:
        ret_list.append(subtitles_list[0]["link"])
    # for sub in subtitles_list:
    #     ret_list.append(sub['link'])
    return ret_list


if DEBUG_MODE:
    argv_len = len(sys.argv)
    if argv_len == 2:
        name = str(sys.argv[1]).strip()
        results = Search(name)
        ordered_link_list = SlectSubtitle(results)
        for link in ordered_link_list:
            DebugLog("Trying to download page: " + link)
            if Download(link, "./", name):
                DebugLog("Succeed to download subtitle, all done.")
                sys.exit(0)
        DebugLog("Failed to download subtitle, all done.")
else:
    params = dict(urlparse.parse_qsl(urlparse.urlparse(sys.argv[2]).query))
    if params["action"] == "search" or params["action"] == "manualsearch":
        item = {}
        item["temp"] = False
        item["rar"] = False
        item["mansearch"] = False
        item["year"] = xbmc.getInfoLabel("VideoPlayer.Year")  # Year
        item["season"] = str(xbmc.getInfoLabel("VideoPlayer.Season"))  # Season
        item["episode"] = str(xbmc.getInfoLabel(
            "VideoPlayer.Episode"))  # Episode
        item["tvshow"] = xbmc.getInfoLabel("VideoPlayer.TVshowtitle")  # Show
        item["title"] = xbmc.getInfoLabel(
            "VideoPlayer.OriginalTitle"
        )  # try to get original title
        item["file_original_path"] = urllib.unquote(
            xbmc.Player().getPlayingFile().decode("utf-8")
        )  # Full path of a playing file
        item["3let_language"] = []

        if "searchstring" in params:
            item["mansearch"] = True
            item["mansearchstr"] = params["searchstring"]

        for lang in urllib.unquote(params["languages"]).decode("utf-8").split(","):
            item["3let_language"].append(
                xbmc.convertLanguage(lang, xbmc.ISO_639_2))

        if item["title"] == "":
            item["title"] = xbmc.getInfoLabel(
                "VideoPlayer.Title"
            )  # no original title, get just Title
            if item["title"] == os.path.basename(
                xbmc.Player().getPlayingFile()
            ):  # get movie title and year if is filename
                title, year = xbmc.getCleanMovieTitle(item["title"])
                item["title"] = title.replace("[", "").replace("]", "")
                item["year"] = year

        if item["episode"].lower().find("s") > -1:  # Check if season is "Special"
            item["season"] = "0"  #
            item["episode"] = item["episode"][-1:]

        if item["file_original_path"].find("http") > -1:
            item["temp"] = True

        elif item["file_original_path"].find("rar://") > -1:
            item["rar"] = True
            item["file_original_path"] = os.path.dirname(
                item["file_original_path"][6:])

        elif item["file_original_path"].find("stack://") > -1:
            stackPath = item["file_original_path"].split(" , ")
            item["file_original_path"] = stackPath[0][8:]

        Search(item)

    elif params["action"] == "download":
        subs = Download(params["link"], params["lang"])
        for sub in subs:
            listitem = xbmcgui.ListItem(label=sub)
            xbmcplugin.addDirectoryItem(
                handle=int(sys.argv[1]), url=sub, listitem=listitem, isFolder=False
            )

    xbmcplugin.endOfDirectory(int(sys.argv[1]))
