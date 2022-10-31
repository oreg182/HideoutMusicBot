import asyncio
import json
import difflib
import random

import yt_dlp
from pathlib import Path

yt_dlp.YoutubeDL()

ytdl_format_options = {
    'format': 'bestaudio',
    'outtmpl': 'music/%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'error',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
    "max_filesize": 10000000
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class Storage:
    def __init__(self):
        try:
            with open("storage.json", encoding="utf-8") as f:
                self.data = json.load(f)
        except FileNotFoundError:
            self.data = {}
        Path("./music").mkdir(parents=True, exist_ok=True)

    def add_yt_song(self, url, textchannel, loop):
        # download
        try:
            data = ytdl.extract_info(url)
        except yt_dlp.utils.DownloadError:
            asyncio.run_coroutine_threadsafe(textchannel.send("Fehler beim Adden"), loop)
            return 0
        if data["filesize"] > 10000000:
            title = data["title"]
            asyncio.run_coroutine_threadsafe(textchannel.send("Fehler - file zu groß - " + title), loop)
            return
        # save
        title = data["title"]
        filename = ytdl.prepare_filename(data)
        self.data[title] = [filename, 0.5]
        self.save_data()
        asyncio.run_coroutine_threadsafe(textchannel.send("Added: " + title), loop)
        return title

    def save_data(self):
        with open("storage.json", "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4)

    def suggest_songs(self, string, suggestions=5):
        l = [[difflib.SequenceMatcher(None, string.lower(), title.lower()).ratio(), title] for title in
                          self.data.keys()]
        print(l)
        matching_blocks = [[max(match.size for match in difflib.SequenceMatcher(None, string.lower(), title.lower()).get_matching_blocks()), title] for title in
                          self.data.keys()]
        sorted_by_blocks = sorted(matching_blocks, reverse=True)
        print(sorted_by_blocks)
        results = sorted(l, reverse=True)
        print("suggestion results: " + str(results))
        return sorted_by_blocks[:suggestions]

    def get_filename(self, title):
        return self.data[title][0]

    def get_volume(self, title):
        return self.data[title][1]

    def change_volume(self, title, new_volume):
        self.data[title][1] = new_volume
        self.save_data()

    def get_random_title(self):
        return random.choice(list(self.data.keys()))

class Playlists:
    def __init__(self):
        self.playlists = {}
        self.load()
        print(self.playlists)

    def add_playlist(self, name):
        self.playlists[name] = Playlist(name)

    def save(self):
        playlists = {}
        for key in self.playlists:
            playlists[key] = self.playlists[key]
        with open("playlists.json", "w") as f:
            json.dump(playlists, f, indent=4)


    def load(self):
        with open("playlists.json") as f:
            jsondata = json.load(f)
        for key in jsondata:
            self.playlists[key] = Playlist(key, jsondata[key])

    def add_title_to_playlist(self, playlist, title):
        self.playlists[playlist].append(title)


class Playlist(list):
    def __init__(self, name, *songs):
        super(Playlist, self).__init__(*songs)
        self.played_songs = []
        self.name = name

    def next_title(self):
        return self[0]

    def save(self):
        return str([self.name, self])




if __name__ == '__main__':
    plists = Playlists()
    plists.save()

    # s.add_yt_song("https://www.youtube.com/watch?v=vdFpZbMKsrM")
    # s.add_yt_song("https://www.youtube.com/watch?v=zJ7lUCxBt9k")
    # s.add_yt_song("https://www.youtube.com/watch?v=hzqcMvDON1g")
