import asyncio
import json
import youtube_dl
import difflib
import yt_dlp

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
}

ffmpeg_options = {
    'options': '-vn',
}

#ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)



class Storage:
    def __init__(self):
        with open("storage.json", encoding="utf-8") as f:
            self.data = json.load(f)

    def add_yt_song(self, url, textchannel, loop):
        # download
        try:
            data = ytdl.extract_info(url)
        except youtube_dl.utils.DownloadError:
            asyncio.run_coroutine_threadsafe(textchannel.send("Fehler beim Adden"), loop)
            return
        # savestop
        title = data["title"]
        filename = ytdl.prepare_filename(data)
        self.data[title] = [filename, 0.5]
        self.save_data()
        asyncio.run_coroutine_threadsafe(textchannel.send("Added: "+title), loop)

    def save_data(self):
        with open("storage.json", "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4)

    def suggest_songs(self, string, suggestions=5):
        results = sorted([[difflib.SequenceMatcher(None, string.lower(), title.lower()).ratio(), title] for title in self.data.keys()],
                         reverse=True)
        print("suggestion results: " + str(results))
        return results[:suggestions]

    def get_filename(self, title):
        return "music/" + self.data[title][0]

    def get_volume(self, title):
        return self.data[title][1]


if __name__ == '__main__':
    s = Storage()
    print(s.suggest_songs("dihct mi fliga"))

    # s.add_yt_song("https://www.youtube.com/watch?v=vdFpZbMKsrM")
    # s.add_yt_song("https://www.youtube.com/watch?v=zJ7lUCxBt9k")
    # s.add_yt_song("https://www.youtube.com/watch?v=hzqcMvDON1g")
