from __future__ import annotations, division
import http
import os
from urllib import response
import urllib3
import re
import subprocess
from typing import Tuple, Type
from pytube import YouTube
from pytube.query import StreamQuery
from pathlib import Path
import warnings
from pydub import AudioSegment
from mashdata import MashSong
warnings.filterwarnings('ignore')
if os.environ["SPLEETER_LOAD_FLAG"] == "True":
	from spleeter.separator import Separator
	from spleeter.audio.adapter import AudioAdapter 

class Masher:
	'''	Interface to download and separate audio.
	'''
	def __init__(self, separator_config: str = 'spleeter:2stems', sample_rate: float = 44100, multiprocess: bool = False, save_data: bool = True) -> None:
		if os.environ["SPLEETER_LOAD_FLAG"] == "True":
			self.audio_loader = AudioAdapter.default()
			self.separator = Separator(separator_config, multiprocess=multiprocess)
			self.sample_rate = sample_rate
			self.save_data = save_data

	def separate(self, filename: str, ) -> dict:
		''' Separates stems from wav file and returns dict of stems

		Args:
			filename (str): Track wav file, must be in /data/music/src
			sample_rate (int): Sample rate for output (default = 44100)
			save_data (bool): Whether to save stem .wav file locally
		
		Returns:
			
		'''
		path = Path.cwd() / 'data/music/src'
		file = path / filename
		waveform, _ = self.audio_loader.load(file, sample_rate=self.sample_rate)
		print(f"waveform:\n{waveform}")
		
		prediction = self.separator.separate(waveform)

		print(f"Prediction:\n{prediction}")

		if self.save_data:
			path = Path.cwd() / 'data/music/out'
			filename = filename.removesuffix('.wav')
			for key, value in prediction.items():
				file = path / f"{filename}{str(key).capitalize()}.wav"
				self.audio_loader.save(file, value, self.sample_rate)

		return prediction

	def separate_from_wav(self, filename: str):
		self.separate(filename)

	def separate_from_list(self, wav_list: list):
		for filename in wav_list:
			self.separate(filename)

	def get_yt_download(cls, url: str) -> None:
		yt = YouTube(url)
		stream = yt.streams.filter(only_audio=True, mime_type="audio/mp4").first()
		stream.download('./data/music/download')

	def get_yt_url(cls, query: str) -> str:
		keywords = query.replace(" ", "+")
		query = f"https://www.youtube.com/results?search_query={keywords}"
		http = urllib3.PoolManager()
		response = http.request('GET', query)
		html = response.data
		top_video_id = re.findall(r"watch\?v=(\S{11})", html.decode())[0]
		print(top_video_id)
		url = f"https://www.youtube.com/watch?v={top_video_id}"
		return url

	def convert_mp4_wav(cls, file_in: str, file_out: str):
		cmd = f"ffmpeg -i ./data/music/download/{file_in} -ab 160k -ac 2 -ar 44100 -vn ./data/music/src/{file_out} -> None"
		subprocess.call(cmd)

	def mash(output: str, voc: MashSong, acc: MashSong, voc_secs: Tuple[int, int], acc_secs: Tuple[int, int], speedVoc: bool = True) -> None:
		if speedVoc:
			mash_stem = voc.create_mash_stem("VocMash","Vocals", voc_secs[0], voc_secs[1], target_song=acc)
			target_stem = acc.stems["Accompaniment"][acc.sections[acc_secs[0]].start_time*1000:acc.sections[acc_secs[1]].end_time*1000]
		else:
			mash_stem = acc.create_mash_stem("AccMash","Accompaniment", acc_secs[0], acc_secs[1], target_song=voc)
			target_stem = voc.stems["Vocals"][voc.sections[voc_secs[0]].start_time*1000:voc.sections[voc_secs[1]].end_time*1000]

		mash = mash_stem.overlay(target_stem)
		mash.export(f"./data/music/mash/{output}")


# Helper Methods		

