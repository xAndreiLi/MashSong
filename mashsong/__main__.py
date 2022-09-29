# encoding: utf-8
import os
import json
import logging
import argparse
import spotipy
from time import time
from pathlib import Path
from tkinter import Y
from masher import Masher
from mashdata import MashSong, Section
from spotipy import Spotify, SpotifyClientCredentials
# from spleeter.separator import Separator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mashsong")

def set_log_object(obj_list: list):
	names = ["masher", "mashdata"]
	loggers = [logging.getLogger(log) for log in names]
	objects = {"masher":"masher", "section":"mashdata.section", "mashsong":"mashdata.mashsong"}
	if isinstance(obj_list, str):
		obj_list = [obj_list]
	handler = logging.StreamHandler()
	for object in obj_list:
			handler.addFilter(logging.Filter(name=objects[object]))
	for logger in loggers:
		logger.addHandler(handler)
			

def log_time(func):
	def wrapper():
		start_time = time()
		func()
		logger.info(f"{func.__name__} ran in {time()-start_time} seconds")
	return wrapper

def init():
	logger.info("Initializing")
	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument("--logobject", nargs="+", type=str, 
							default="masher", help="Filter logs by data object [ masher (default), section, mashsong ]")
	arg_parser.add_argument("--loglevel", default="INFO")
	args = arg_parser.parse_args()
	set_log_object(args.logobject)

@log_time
def main():
	init()
	# for name in logging.root.manager.loggerDict:
	# 	print(name)
	# print(logging.getLogger().name)
	# API KEYS
	os.environ["SPOTIPY_CLIENT_ID"] = "512f913c9f7c473fa8c437edb10e8521"
	os.environ["SPOTIPY_CLIENT_SECRET"] = "a3bd19e4f0384f6a8d0b2718ca745cd2"

	# song1 = Masher.get_song("Sexy And I Know It", "Sexy And I Know It Audio", "LMFAO")
	song2 = Masher.get_song("Die For You")
	song2.create_mash_stem("test","A",0,3,2,140)

	# Masher.mash("SexyAngel.mp3", song1, song2, (1,3), (1,3))

	# for i in range(5):
	# 	song2.export_from_sections(i,i,"Vocals")
	# song1.export_from_times(37.635, 52.6531, "Accompaniment")


if __name__ == '__main__':
	main()