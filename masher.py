from __future__ import annotations, division
import os
import re
import urllib3
import logging
import subprocess

from typing import Tuple, Type
from pytube import YouTube
from pathlib import Path

from pydub import AudioSegment
from mashdata import MashSong, Section

logger = logging.getLogger(__name__)

class Masher:
	'''	Interface to download and separate audio.
	'''

	audio_loader: object = None
	separator: object = None
	sep_config: str = "spleeter:2stems"
	sample_rate: float = 44100
	save_data: bool = True

	@classmethod
	def separate(cls, filename: str, ) -> dict:
		''' Separates stems from wav file and returns dict of stems

		Args:
			filename (str): Track wav file, must be in /data/music/src
			sample_rate (int): Sample rate for output (default = 44100)
			save_data (bool): Whether to save stem .wav file locally
		
		Returns:
			dict with stem names as keys and np.ndarray audio data as value
		'''
		if cls.audio_loader is None:
			logging.getLogger("tensorflow").setLevel(logging.CRITICAL)
			logger.info("Loading spleeter libraries")
			from spleeter.separator import Separator
			from spleeter.audio.adapter import AudioAdapter 
			logging.getLogger("spleeter").setLevel(logging.CRITICAL)
			
		cls.audio_loader = AudioAdapter.default()
		cls.separator = Separator(cls.sep_config, multiprocess=False)
		path = Path.cwd() / 'data/music/src'
		file = path / f"{filename}.wav"
		logger.info("Separating audio...")
		waveform, _ = cls.audio_loader.load(file, sample_rate=cls.sample_rate)
		prediction = cls.separator.separate(waveform)

		if cls.save_data:
			path = Path.cwd() / 'data/music/out'
			filename = filename.removesuffix('.wav')
			for key, value in prediction.items():
				out = f"{filename}{str(key).capitalize()}.wav"
				file = path / out
				cls.audio_loader.save(file, value, cls.sample_rate)
				logger.info(f"{out} saved successfully")

		return prediction

	@classmethod
	def separate_from_list(cls, wav_list: list) -> None:
		''' Takes a list of filenames and separates each into stems
		'''
		for filename in wav_list:
			cls.separate(filename)

	@classmethod
	def get_yt_song(cls, query: str, out: str):
		''' Takes YouTube search query and downloads first result, converting to wav
		'''

		def get_yt_url(query: str) -> str:
			''' Takes search query and returns url of first result
				Returns url str
			'''
			keywords = query.replace(" ", "+")
			query = f"https://www.youtube.com/results?search_query={keywords}"
			http = urllib3.PoolManager()
			response = http.request('GET', query)
			html = response.data
			top_video_id = re.findall(r"watch\?v=(\S{11})", html.decode())[0]
			url = f"https://www.youtube.com/watch?v={top_video_id}"
			logger.info(f"Downloading from {url}")
			return url

		def get_yt_download(url: str, out: str) -> None:
			''' Takes str with youtube url and attempts to download mp4 audio
				Saves to data/music/download/{out}.mp4
			'''
			yt = YouTube(url)
			out = out + ".mp4"
			mp4 = yt.streams.filter(only_audio=True, mime_type="audio/mp4").first()
			mp4.download('./data/music/download', filename=out)
			logger.info(f"Downloading {mp4.title}")

		def convert_mp4_wav(file: str):
			''' Takes mp4 file and converts to wav file
			'''
			file_in = Path.cwd() / 'data/music/download' / f"{file}.mp4"
			out = Path.cwd() / 'data/music/src' / f"{file}.wav"
			cmd = f"ffmpeg -i {file_in} -ab 160k -ac 2 -ar 44100 -vn {out} -loglevel quiet"
			logger.info(f"Converting to wav: {file_in}")
			subprocess.call(cmd)
			logger.info(f"Converted wav saved in {out}")
			if out.exists():
				os.remove(file_in)

		url = get_yt_url(query)
		get_yt_download(url, out)
		convert_mp4_wav(out)


	@classmethod
	def mash(cls, output: str, voc: MashSong, acc: MashSong, voc_secs: Tuple[int, int], 
			acc_secs: Tuple[int, int], pitch_voc: bool = True) -> None:
		''' Takes two MashSong objects, mashes them together, and outputs to wav file

		Args:
			output (str): filename to output to (saved in data/music/mash)
			voc (MashSong): MashSong to be used as vocals
			acc (MashSong): MashSong to be used as accompaniment
			voc_secs: ((int,int)): Sections of vocal track to be included
			acc_secs: ((int,int)): Sections of accompaniment track to be included
			pitch_voc (bool): Whether vocals or accompaniment should be sped up. Default = True
		'''
		if pitch_voc:
			mash_stem = voc.create_mash_stem("VocMash","Vocals", voc_secs[0], voc_secs[1], target_song=acc)
			target_stem = acc.stems["Accompaniment"][acc.sections[acc_secs[0]].start_time*1000:acc.sections[acc_secs[1]].end_time*1000]
		else:
			mash_stem = acc.create_mash_stem("AccMash","Accompaniment", acc_secs[0], acc_secs[1], target_song=voc)
			target_stem = voc.stems["Vocals"][voc.sections[voc_secs[0]].start_time*1000:voc.sections[voc_secs[1]].end_time*1000]

		mash = mash_stem.overlay(target_stem)
		out = Path.cwd() / 'data/music/mash' / output
		mash.export(out)
		logger.info(f"Mash saved to {out}")

	@classmethod
	def export_section_from_stem(cls, ind: int, song: MashSong, type: str):
		section = song.sections[ind]
		stem = song.stems[type]
		out = f"./data/music/sections/{song.title}{type}{ind}.wav"
		stem[section.start_time*1000:section.end_time*1000].export(out)

	@classmethod
	def get_song(cls, query: str, out: str, artist: str = None):
		cls.get_yt_song(query+artist, out)
		cls.separate(out)
		return MashSong.get_song_from_search(query, artist)


# Helper Methods		

