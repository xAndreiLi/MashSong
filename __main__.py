import os
import logging
from time import time
from pathlib import Path
from masher import Masher
from mashdata import MashSong, Section

logger = logging.getLogger("mashsong")

def log_time(func):
	def wrapper():
		start_time = time()
		func()
		logger.info(f"{func.__name__} ran in {time()-start_time} seconds")
	return wrapper

@log_time
def main():
	logging.basicConfig(level=logging.INFO)
	# API KEYS
	os.environ["SPOTIPY_CLIENT_ID"] = "512f913c9f7c473fa8c437edb10e8521"
	os.environ["SPOTIPY_CLIENT_SECRET"] = "a3bd19e4f0384f6a8d0b2718ca745cd2"

	#Masher.get_song("Good Things Fall Apart", "GoodThingsFallApart", "Illenium")
	
	song1 = MashSong.get_song_from_json("NoBlueberriesInfo.json")
	song2 = MashSong.get_song_from_json("GetLuckyInfo.json")

	Masher.mash("BlueLucky.wav",song1, song2,(0,5),(0,5), pitch_voc=True)
	
	#Masher.export_section_from_stem(0,song1,"Accompaniment")

if __name__ == '__main__':
	main()