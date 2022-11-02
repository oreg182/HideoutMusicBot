import asyncio
import threading
import time

import discord
from discord import Message, PCMVolumeTransformer, VoiceClient

from storage import Storage


def get_token():
    try:
        with open("token") as f:
            return f.read()
    except FileNotFoundError:
        print("Token file not found. press enter to end")
        input()
        raise FileNotFoundError


ffmpeg_options = {
    'options': '-vn',
}





class Client(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super(Client, self).__init__(intents=intents)
        self.player: PCMVolumeTransformer = None
        self.storage = Storage()
        self.selection_channel = None
        self.selection = []
        self.waiting_for_selection = False
        self.suggestions_limit = 5
        self.selection_msg = None
        self.voice_client = None
        self.queue = []
        self.prefix = "!"
        self.autoplay = False
        self.song_playing = None

    async def help_command(self, message):
        string = """
            Songs müssen geadded werden bevor sie gespielt werden können.
    Aktuell können nur yt links hinzugefügt werden.
    Verfügbare Befehle:
            {}play SONGNAME
            {}p = play
            {}play yt LINK
            {}add yt LINK
            {}schub+ZAHL
            {}schub-ZAHL
            {}schub=ZAHL
            {}pause
            {}resume
            {}queue
            {}skip
            {}disconnect
            """.format(*[self.prefix for _ in range(11)])
        await message.channel.send(string)

    async def schub_message(self, message):
        if message.content.startswith("{}schub+".format(self.prefix)):
            await self.schubplus(message)
        elif message.content.startswith("{}schub-".format(self.prefix)):
            await self.schubminus(message)
        elif message.content.startswith("{}schub=".format(self.prefix)):
            await self.schubgleich(message)
        elif message.content == "{}schub".format(self.prefix):
            await message.channel.send("Aktueller Schub: {}".format(self.player.volume * 100))

    async def schubplus(self, message):
        try:
            mod = float(message.content.split("+")[1]) / 100
            if 0 < float(mod) <= 1 - self.player.volume:
                self.player.volume += float(mod)
                self.player.volume = round(self.player.volume, 2)
                self.storage.change_volume(self.queue[0], self.player.volume)
            else:
                await message.channel.send(
                    "Aktuelle Lautstärke: {}%. Eingabe muss zwischen 0 und 100-Lautstärke sein.".format(
                        self.player.volume * 100))
        except ValueError:
            await message.channel.send(
                "Aktuelle Lautstärke: {}%. Eingabe muss zwischen 0 und 100-Lautstärke sein. ValueError".format(
                    self.player.volume * 100))
        except IndexError:
            await message.channel.send(
                "Aktuelle Lautstärke: {}%. Eingabe muss zwischen 0 und 100-Lautstärke sein. IndexError".format(
                    self.player.volume * 100))

    async def schubminus(self, message):
        try:
            mod = float(message.content.split("-")[1]) / 100
            if 0 < float(mod) <= self.player.volume:
                self.player.volume -= float(mod)
                self.player.volume = round(self.player.volume, 2)
                self.storage.change_volume(self.queue[0], self.player.volume)
            else:
                await message.channel.send(
                    "Aktuelle Lautstärke: {}%. Eingabe muss zwischen 0 und der Lautstärke sein.".format(
                        self.player.volume * 100))
        except ValueError:
            await message.channel.send(
                "Aktuelle Lautstärke: {}%. Eingabe nach - muss eine Zahl sein. ValueError".format(
                    self.player.volume * 100))
        except IndexError:
            await message.channel.send(
                "Aktuelle Lautstärke: {}%. Eingabe nach - muss eine Zahl sein. IndexError".format(
                    self.player.volume * 100))

    async def schubgleich(self, message):
        try:
            mod = float(message.content.split("=")[1]) / 100
            if 0 < float(mod) <= 1:
                self.player.volume = float(mod)
                self.player.volume = round(self.player.volume, 2)
                self.storage.change_volume(self.queue[0], self.player.volume)
            else:
                await message.channel.send(
                    "Aktuelle Lautstärke: {}%. Eingabe muss zwischen 0 und 100 sein.".format(
                        self.player.volume * 100))
        except ValueError:
            await message.channel.send(
                "Aktuelle Lautstärke: {}%. Eingabe nach = muss eine Zahl zwischen 0 und 100 sein. ValueError".format(
                    self.player.volume * 100))
        except IndexError:
            await message.channel.send(
                "Aktuelle Lautstärke: {}%. Eingabe nach = muss eine Zahl zwischen 0 und 100 sein. IndexError".format(
                    self.player.volume * 100))

    async def on_message(self, message: Message):
        print(message.author, message.content)
        if message.author == self.user:
            return
        if self.waiting_for_selection:
            if message.channel.id != self.selection_channel.id:
                return
            try:
                number = int(message.content)
            except ValueError:
                await message.channel.send("Ungültige Auswahl")
                await self.cleanup_selection()
                return
            await self.handle_selection(message, number)

        if message.content.startswith("{}schub".format(self.prefix)):
            await self.schub_message(message)
        if message.content.startswith("{}disconnect".format(self.prefix)):
            await self.get_voice_client().disconnect(force=False)
            self.voice_client = None
        if message.content.startswith("{}play ".format(self.prefix)):
            if message.content.startswith("{}play yt ".format(self.prefix)):
                await self.add_yt_and_play(message)
            else:
                await self.play_command(message)
        if message.content.startswith("{}p ".format(self.prefix)):
            await self.play_command(message)
        if message.content.startswith("{}add yt".format(self.prefix)):
            await self.add_yt(message)
        if message.content.startswith("{}pause".format(self.prefix)):
            self.get_voice_client().pause()
        if message.content.startswith("{}resume".format(self.prefix)):
            self.get_voice_client().resume()
        if message.content.startswith("{}queue".format(self.prefix)):
            await self.queue_command(message)
        if message.content.startswith("{}help".format(self.prefix)):
            await self.help_command(message)
        if message.content.startswith("{}skip".format(self.prefix)):
            client: VoiceClient = self.get_voice_client()
            client.stop()  # calls after_song method
        if message.content.startswith("{}autoplay on".format(self.prefix)):
            if self.queue:
                self.autoplay = True
            else:
                self.autoplay = True
                if self.get_voice_client():
                    client: VoiceClient = self.get_voice_client()
                    if client.is_playing():
                        return
                    await self._play_song_by_title(self.storage.get_random_title())
                else:
                    self.voice_client = await message.author.voice.channel.connect()
                    await self._play_song_by_title(self.storage.get_random_title())
        if message.content.startswith("{}autoplay off".format(self.prefix)):
            self.autoplay = False

    async def queue_command(self, message):
        string = "{} Songs in Queue".format(len(self.queue))
        string += "\n(PLAYING) " + self.queue[0]
        for title in self.queue[1:]:
            string += "\n" + title
        await message.channel.send(string)

    async def handle_selection(self, message, number):
        if number == 0:
            await message.delete()
            await self.cleanup_selection()
            return
        if not (0 < number <= self.suggestions_limit):
            await self.invalid_song_election_number(message)
            await self.cleanup_selection()
            return
        else:
            title = self.selection[number - 1][1]
            await self.play_song(message.author.voice.channel, title)
            await self.cleanup_selection()
            await message.delete()

    async def play_song(self, voice_channel, title):
        self.queue.append(title)
        if self.get_voice_client():
            client: VoiceClient = self.get_voice_client()
            if client.is_playing():
                return
            await self._play_song_by_title(title)
        else:
            self.voice_client = await voice_channel.connect()
            await self._play_song_by_title(title)

    async def cleanup_selection(self):
        await self.selection_msg.delete()
        self.selection = None
        self.waiting_for_selection = False

    async def invalid_song_election_number(self, message):
        await message.channel.send("Ungültige Zahl")
        self.waiting_for_selection = False
        return

    def after_song(self, error):
        print(error) if error else None
        if self.queue:
            if self.queue[0] == self.song_playing:
                self.queue.pop(0)
            if self.queue:
                time.sleep(1)
                asyncio.run_coroutine_threadsafe(self._play_song_by_title(self.queue[0]), self.loop)
            else:
                asyncio.run_coroutine_threadsafe(self.get_voice_client().disconnect(), self.loop)
                self.voice_client = None
        elif self.autoplay:
            asyncio.run_coroutine_threadsafe(self._play_song_by_title(self.storage.get_random_title()), self.loop)
        else:
            asyncio.run_coroutine_threadsafe(self.get_voice_client().disconnect(force=False), self.loop)
            self.voice_client = None


    async def play_command(self, message):
        try:
            songname = message.content.split(" ")[1]
        except IndexError:
            await message.channel.send("Ungültige Eingabe. Siehe help")
            return
        suggestions = self.storage.suggest_songs(songname, self.suggestions_limit)
        suggestion_string = "Zum Abbrechen 0 eingeben\n"
        for i, s in enumerate(suggestions):
            suggestion_string += str(i + 1) + ": " + s[1] + "\n"
        self.selection_msg = await message.channel.send(suggestion_string)
        self.selection = suggestions
        self.selection_channel = message.channel
        self.waiting_for_selection = True

    async def _play_song_by_title(self, title):
        self.song_playing = title
        filename = self.storage.get_filename(title)
        volume = self.storage.get_volume(title)
        source = discord.FFmpegPCMAudio(filename, **ffmpeg_options)
        self.player = PCMVolumeTransformer(source, volume=volume)
        self.get_voice_client().play(self.player, after=self.after_song)

    async def add_yt(self, message):
        url = message.content.split(" ")[2]
        thread = threading.Thread(target=self.storage.add_yt_song, args=(url, message.channel, self.loop), daemon=True)
        thread.start()

    def thread_target_add_yt_and_play(self, url, message, loop):
        title = self.storage.add_yt_song(url, message.channel, self.loop)
        if title:
            asyncio.run_coroutine_threadsafe(self.play_song(message.author.voice.channel, title), loop)

    async def add_yt_and_play(self, message):
        url = message.content.split(" ")[2]
        thread = threading.Thread(target=self.thread_target_add_yt_and_play, args=(url, message, self.loop), daemon=True)
        thread.start()

    def get_voice_client(self):
        return self.voice_client


if __name__ == '__main__':
    Client().run(get_token())
