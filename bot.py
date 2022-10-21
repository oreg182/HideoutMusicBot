import asyncio
import threading
import time

import discord
from discord import Message, PCMVolumeTransformer, VoiceClient

from storage import Storage


def get_token():
    with open("token") as f:
        return f.read()


ffmpeg_options = {
    'options': '-vn',
}


async def help_command(message):
    string = """
        Songs müssen geadded werden bevor sie gespielt werden können.
Aktuell können nur yt links hinzugefügt werden.
Verfügbare Befehle:
        play SONGNAME
        add yt LINK
        schub+Zahl
        schub-Zahl
        schub=Zahl
        pause
        resume
        queue
        skip
        disconnect
        """
    await message.channel.send(string)


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

    async def schub_message(self, message):
        if message.content.startswith("schub+"):
            await self.schubplus(message)
        elif message.content.startswith("schub-"):
            await self.schubminus(message)
        elif message.content.startswith("schub="):
            await self.schubgleich(message)

    async def schubplus(self, message):
        try:
            mod = float(message.content.split("=")[1]) / 100
            if 0 < float(mod) < 1 - self.player.volume:
                self.player.volume += float(mod)
                self.player.volume = round(self.player.volume, 2)
                self.storage.change_volume(self.queue[0], self.player.volume)
            else:
                await message.channel.send(
                    "Aktuelle Lautstärke: {}%. Eingabe muss zwischen 0 und 100-Lautstärke sein.".format(
                        self.player.volume * 100))
        except ValueError:
            await message.channel.send(
                "Aktuelle Lautstärke: {}%. Eingabe muss zwischen 0 und 100-Lautstärke sein.".format(
                    self.player.volume * 100))

    async def schubminus(self, message):
        try:
            mod = float(message.content.split("-")[1]) / 100
            if 0 < float(mod) < self.player.volume:
                self.player.volume -= float(mod)
                self.player.volume = round(self.player.volume, 2)
                self.storage.change_volume(self.queue[0], self.player.volume)
            else:
                await message.channel.send(
                    "Aktuelle Lautstärke: {}%. Eingabe muss zwischen 0 und der Lautstärke sein.".format(
                        self.player.volume * 100))
        except ValueError:
            await message.channel.send("Aktuelle Lautstärke: {}%. Eingabe nach - muss eine Zahl sein.".format(
                self.player.volume * 100))

    async def schubgleich(self, message):
        try:
            mod = float(message.content.split("=")[1]) / 100
            if 0 < float(mod) < 1:
                self.player.volume = float(mod)
                self.player.volume = round(self.player.volume, 2)
                self.storage.change_volume(self.queue[0], self.player.volume)
            else:
                await message.channel.send(
                    "Aktuelle Lautstärke: {}%. Eingabe muss zwischen 0 und 100 sein.".format(
                        self.player.volume * 100))
        except ValueError:
            await message.channel.send(
                "Aktuelle Lautstärke: {}%. Eingabe nach = muss eine Zahl zwischen 0 und 100 sein.".format(
                    self.player.volume * 100))

    async def on_message(self, message: Message):
        print(message)
        if message.author == self.user:
            return
        if self.waiting_for_selection:
            if message.channel.id != self.selection_channel.id:
                return
            try:
                number = int(message.content)
            except ValueError:
                await message.channel.send("Ungültige Auswahl")
                await self.selection_msg.delete()
                return
            await self.handle_selection(message, number)

        if message.content.startswith("schub"):
            await self.schub_message(message)
        if message.content.startswith("disconnect"):
            await self.get_voice_client().disconnect(force=False)
            self.voice_client = None
        if message.content.startswith("play"):
            await self.play_command(message)
        if message.content.startswith("add yt"):
            await self.add_yt(message)
        if message.content.startswith("pause"):
            self.get_voice_client().pause()
        if message.content.startswith("resume"):
            self.get_voice_client().resume()
        if message.content.startswith("queue"):
            await self.queue_command(message)
        if message.content.startswith("help"):
            await help_command(message)
        if message.content.startswith("skip"):
            client: VoiceClient = self.get_voice_client()
            client.stop()

    async def queue_command(self, message):
        string = "{} Songs in Queue".format(len(self.queue))
        string += "\n(PLAYING) " + self.queue[0]
        for title in self.queue[1:]:
            string += "\n" + title
        await message.channel.send(string)

    async def handle_selection(self, message, number):
        if not (0 <= number <= self.suggestions_limit):
            return await self.invalid_song_selection(message)
        else:
            self.waiting_for_selection = False
            title = self.selection[number - 1][1]
            self.queue.append(title)
            await self.selection_msg.delete()
        if self.get_voice_client():
            client: VoiceClient = self.get_voice_client()
            if client.is_playing():
                await message.delete()
                return
            await self.play_song_by_title(title)
            await message.delete()
        else:
            self.voice_client = await message.author.voice.channel.connect()
            await self.play_song_by_title(title)
            await message.delete()

    async def invalid_song_selection(self, message):
        await message.channel.send("Ungültige Auswahl")
        self.waiting_for_selection = False
        return

    def after_song(self, error):
        print(error) if error else None
        self.queue.pop(0)
        if self.queue:
            time.sleep(1)
            asyncio.run_coroutine_threadsafe(self.play_song_by_title(self.queue[0]), self.loop)
        else:
            asyncio.run_coroutine_threadsafe(self.get_voice_client().disconnect(), self.loop)
            self.voice_client = None

    async def play_command(self, message):
        try:
            songname = message.content.split(" ")[1]
        except IndexError:
            await message.channel.send("Ungültige Eingabe. Siehe help")
            return
        suggestions = self.storage.suggest_songs(songname, self.suggestions_limit)
        suggestion_string = ""
        for i, s in enumerate(suggestions):
            suggestion_string += str(i + 1) + ": " + s[1] + "\n"
        self.selection_msg = await message.channel.send(suggestion_string)
        self.selection = suggestions
        self.selection_channel = message.channel
        self.waiting_for_selection = True

    async def play_song_by_title(self, title):
        filename = self.storage.get_filename(title)
        volume = self.storage.get_volume(title)
        source = discord.FFmpegPCMAudio(filename, **ffmpeg_options)
        self.player = PCMVolumeTransformer(source, volume=volume)
        self.get_voice_client().play(self.player, after=self.after_song)

    async def add_yt(self, message):
        url = message.content.split(" ")[2]
        thread = threading.Thread(target=self.storage.add_yt_song, args=(url, message.channel, self.loop), daemon=True)
        thread.start()

    def get_voice_client(self):
        return self.voice_client


if __name__ == '__main__':
    Client().run(get_token())
