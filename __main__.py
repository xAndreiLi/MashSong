import os
from time import time
from pathlib import Path
from mashdata import MashSong, Section

# Enable to load TensorFlow and Spleeter for separation
os.environ["SPLEETER_LOAD_FLAG"] = "False" # "True"
from masher import Masher

# API KEYS
os.environ["SPOTIPY_CLIENT_ID"] = "512f913c9f7c473fa8c437edb10e8521"
os.environ["SPOTIPY_CLIENT_SECRET"] = "a3bd19e4f0384f6a8d0b2718ca745cd2"


start = time()

song1 = MashSong.get_song_from_json("PictureInMyMindInfo.json")
song2 = MashSong.get_song_from_json("NoBlueberriesInfo.json")

Masher.mash("BlueWarMash.wav", song1, song2, (2,6), (5,7), speedVoc=True)

#src_list = ["NoBlueberries.wav", "PictureInMyMind.wav", "Skeletons.wav", "WarWithHeaven.wav"]

# url = masher.get_yt_url("supalonely benee")
# masher.get_yt_download(url)

song1.log_sections()
song2.log_sections()



print(f"Time Spent in Total: {time()-start}")