from __future__ import annotations, division

import os, io, json, asyncio, logging
from pathlib import Path

import numpy as np, pandas as pd, music21.key as key
from pyrubberband.pyrb import __rubberband as pyrb; from scipy.io import wavfile
from pydub import AudioSegment; from spotipy import Spotify, SpotifyClientCredentials;

from pedalboard import *
from pedalboard.pedalboard import Pedalboard

from typing import Tuple, Dict, List
from numpy.typing import NDArray, ArrayLike

# from pyrubberband import pyrb

logger = logging.getLogger(__name__)
__notes: list[str] = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
__modes: list[str] = ['minor', 'major']

class Section:
	''' Defines data object that contains spotify analysis section data.
	
	Attrs:
		index (int): Index of section in track
		start_time (float): Start time in seconds from beginning of track
		duration (float): Duration of section in seconds
		confidence (float): Spotify Analysis Confidence of section designation
		loudness (float): Overall loudness of section in decibels
		tempo (Tuple[float, float]): Tempo in bpm and Tempo Confidence
		key (Tuple[int, float]): Key (0..11) and Key Confidence
		mode (Tuple[int, float]): Mode (-1..1):(Minor/Major) and Mode Confidence
		time_signature (Tuple[int, float]): Time signature (beats/bar) and Confidence
		track_measures (np.ndarray): Holds start and end measure indexes after sync

	'''
	index: int
	start_time: float					
	duration: float
	end_time: float
	confidence: float
	loudness: float
	tempo: Tuple[float, float]
	key: Tuple[int, float]
	mode: Tuple[int, float]
	time_signature: Tuple[int, float]
	track_measures: ArrayLike

	def __init__(self, section_data: dict, index: int, title: str) -> None:
		self.index = index
		self.track_title = title
		self.start_time = section_data['start']			
		self.duration = section_data['duration']
		self.end_time = self.start_time + self.duration
		self.confidence = section_data['confidence']
		self.loudness = section_data['loudness']
		self.tempo = section_data['tempo'], section_data['tempo_confidence']
		self.key = section_data['key'], section_data['key_confidence']
		self.mode = section_data['mode'], section_data['mode_confidence']
		self.time_signature = (section_data['time_signature'], 
							section_data['time_signature_confidence'])
	
	def sync_to_measure(self) -> int:
		''' Sets start_time and duration to sync with closest measure times
			(Must be called from MashSong methods)
			Returns the end index to begin from the next iteration
		'''
		start_ind: int = 0
		end_ind: int = np.searchsorted(self.track_measures, self.end_time, "left")-1
		if(end_ind >= len(self.track_measures)-1):
			end_ind = end_ind - 1

		if(self.end_time-self.track_measures[end_ind] > self.track_measures[end_ind+1]-self.end_time):
			end_ind = end_ind + 1
		
		#self.logger.info(f"Orig Times: {self.start_time} - {self.start_time+self.duration}")
		self.start_time = self.track_measures[start_ind]
		self.end_time = self.track_measures[end_ind]
		#self.logger.info(f"Extended by {self.end_time-self.start_time - self.duration}")
		self.duration = self.end_time - self.start_time
		self.track_measures = self.track_measures[start_ind:end_ind]
		#self.logger.info(f"Synced to {self.start_time} - {self.end_time}, spanning {end_ind} measures")
		return end_ind

	def __str__(self) -> str:
		string: str = f"Section {self.index}:\n\tStart: {self.start_time}\n\tStop: {self.end_time}\n\tLoudness: {self.loudness}\n\tDuration: {self.duration}"
		return string

class MashSong:
	'''	Defines data object that represents a Song Track 
		and holds its stems and Spotify analysis data
	'''

	FRAME_RATE: int = 44100		# (Sample Rate)
	SAMPLE_WIDTH: int = 2		# in bytes (1 = 8bit)
	CHANNELS: int = 2			# {mono:1, stereo:2}

	title: str
	key_no = int
	key: key.Key
	mode: str
	bpm: float
	duration: float
	sections: List[Section]
	measures: ArrayLike
	stems: Dict[str,AudioSegment]

	def __init__(self, title: str, info: dict) -> None:
		self.title = title
		self.logger = logging.getLogger(f"mashdata.mashsong.{title}")
		self.key_no = int(info['track']['key'])
		self.mode = __modes[int(info['track']['mode'])]
		self.key = key.Key(__notes[self.key_no], self.mode)	# int(0-11) that maps C, C#,...B
		self.bpm = float(info['track']['tempo'])
		self.duration = float(info['track']['duration'])
		self.logger.info(f"Measure Length: {(60/self.bpm)*16}")
		self.sections = [Section(section, ind, title) for ind, section in enumerate(info['sections'])]
		self.measures = np.append(bars_to_measures(info['bars']),self.duration)
		self.stems = self.fetch_stems()
		self.sync_sections_to_measures()

	@classmethod
	def get_song_from_search(
				cls: type, title: str, artist: str = None, 
				save_data: bool = True) -> MashSong:
		'''	Class Function that returns a new MashSong object based on Spotify API search
		
		Args:
			title (str): Track title
			artist (str): Artist name (optional)
			save_data (bool): Whether to save track info to .json locally

		Returns:
			MashSong object with title and info
		'''
		query: str = f'track:{title}'
		if artist: 
			query += f' artist:{artist}'
		query.replace(' ', '%20')
		
		spotify: Spotify = Spotify(client_credentials_manager=SpotifyClientCredentials(), requests_timeout=20)
		uri: str = spotify.search(query, 1)['tracks']['items'][0]['uri']
		info: Dict = spotify.audio_analysis(uri)
		title: str = title.title().replace(' ', '') + artist.title().replace(' ', '')

		if save_data:
			path: Path = Path.cwd() / 'data' / 'info'
			file: Path = path / f'{title}.json'
			with open(file, 'w') as f:
				json.dump(info, f)
		
		return MashSong(title, info)
	
	@classmethod
	def get_song_from_json(cls, filename: str) -> MashSong:
		'''	Takes json filename and returns loaded MashSong object
		
		Args:
			filename (str): Filename not including path. Must be in /data/info

		Returns:
			MashSong object from json data
		'''
		path: Path = Path.cwd() / 'data' / 'info'
		file: Path = path / filename
		with file.open() as f:
			info: Dict = json.load(f)
		title: str = filename.removesuffix('.json')
		return MashSong(title, info)

	def fetch_stems(self) -> Dict[AudioSegment]:
		stem_path: Path = Path.cwd() / 'data' / 'music' / 'out'
		stems: Dict[AudioSegment] = {}
		for file in os.listdir(stem_path):
			if file.lower().find(self.title.lower()) != -1:
				stem: AudioSegment = AudioSegment.from_file(stem_path/file, format="wav")
				stems[file.removeprefix(self.title).removesuffix(".wav")] = stem
		return stems
			
	def create_mash_stem(
				self, new_stem_name: str, src_stem_type: str, start_sec: int, end_sec: int, shift_amt: int = None, 
				bpm_ratio: float = None, target_song: MashSong = None) -> AudioSegment:
		'''	Creates a AudioSegment stem based on a stem in this instance and shifts to 
			target_key and target_bpm (or gets both from target_song). Saves new stem
			to self.stems with key new_stem_name.

		Args:
			new_stem_name (str): Name of key for new stem in self.stems
			src_stem_type (str): Key of desired base stem in self.stems
			target_key (int): Key to shift pitch to (optional)
			target_bpm (float): BPM to time stretch to (optional)
			target_song (MashSong): Song to match key and BPM with 
					(optional, overwrites target_key and target_bpm)

		Returns:
			AudioSegment object from base stem that matches target key and BPM
		'''
		path: Path = Path(__file__).parent.parent / "data/music/out"

		try:
			start_time:float = self.sections[start_sec].start_time*1000
			end_time:float = self.sections[end_sec].end_time*1000
			stem_segment: AudioSegment = self.stems[src_stem_type]
			stem_segment = stem_segment[start_time:end_time]
		except KeyError as e:
			raise KeyError(
				f"No stem type of {src_stem_type} found in stems for {self.title}")

		if not shift_amt:
			shift_amt: int = find_closest_key_shift(self, target_song)
		if not bpm_ratio:
			self.bpm = find_closest_bpm(self.bpm, target_song.bpm)
			mash_bpm: float = (self.bpm+target_song.bpm)/2
			bpm_ratio: float = mash_bpm/self.bpm
		
		samples: NDArray[np.float32] = MashSong.convert_to_pedal(stem_segment)
		pyrb_options={'--tempo':bpm_ratio,'--pitch':shift_amt,'-3':'-F'}
		samples = pyrb(samples,self.FRAME_RATE,**pyrb_options)

		# pitched_samples = pyrb.pitch_shift(samples, 
		# 						self.FRAME_RATE, shift_amt, rbargs={'-3':'-F'})
		# stretched_samples = pyrb.time_stretch(pitched_samples, 
		# 						self.FRAME_RATE, bpm_ratio, rbargs={'-3':"-F"})

		if(src_stem_type == "Vocals"):
			board = Pedalboard([
					LowpassFilter(8000),
					PeakFilter(1000, 6.0, .8),
					HighpassFilter(200)
					])
		else:
			board = Pedalboard([
					PeakFilter(75,6.0,.75),
					PeakFilter(6000, 6.0, .75),
					PeakFilter(1000, -6.0, .5)
					])

		samples = board(samples, self.FRAME_RATE)

		wav_io = io.BytesIO()
		wavfile.write(wav_io, self.FRAME_RATE, samples)
		wav_io.seek(0)
		mash_stem = AudioSegment.from_wav(wav_io)
		self.stems[new_stem_name] = mash_stem
		
		mash_stem.export(path.parent/f"test/{self.title}editR3.wav", format="wav")
		return mash_stem

	@classmethod
	def convert_to_pedal(cls, seg:AudioSegment) -> NDArray[np.float32]:
		channels = seg.split_to_mono()
		samples = [s.get_array_of_samples() for s in channels]
		audio = np.array(samples).T.astype(np.float32)
		audio /= np.iinfo(samples[0].typecode).max
		return audio

	def get_longest_section(self, offset: int = 0) -> Section:
		'''	Returns section with highest duration (index shifted by offset)
		'''
		sorted_sections = sorted(self.sections, key=lambda sec: sec.duration, reverse=True)
		longest_section = sorted_sections[offset]
		#longest_section.track_measures = self.measures
		return longest_section

	def sync_sections_to_measures(self) -> None:
		''' Iterates through all sections and syncs to nearest measure
		'''
		measures = self.measures
		for section in self.sections:
			section.track_measures = measures
			end_ind = section.sync_to_measure()
			measures = np.delete(measures, np.s_[:end_ind])

	# Log Methods
	
	def log_measures(self) -> None:
		print(f"Logging Measures for {self.title}")
		log_arr = self.measures
		print(f"Total Measures: {len(log_arr)-1}")
		for ind in range(len(log_arr)-1):
			print(f"Measure {ind+1}:\n\tStart: {log_arr[ind]}\n\tStop: {log_arr[ind+1]}")
		print("\n")

	def log_sections(self) -> None:
		print(f"Logging Sections for {self.title}")
		log_arr = self.sections
		print(f"Total Sections: {len(log_arr)}")
		for ind in range(len(log_arr)):
			print(f"Section {ind+1}")
			print(log_arr[ind])

	def export_from_measures(self, start_measure: int, end_measure: int, type: str, out: str = None) -> None:
		start_time = self.measures[start_measure]
		end_time = self.measures[end_measure]
		stem = self.stems[type]
		if not out:
			out = f"./data/music/measures/{self.title}{type}{start_measure}-{end_measure}.wav"

		stem[start_time*1000:end_time*1000].export(out)
	
	def export_from_times(self, start_time: float, end_time: float, type: str, out: str = None) -> None:
		stem = self.stems[type]
		if not out:
			out = f"./data/music/measures/{self.title}{type}{start_time}-{end_time}.wav"
		start_time = np.float16(start_time)*1000
		end_time = np.float16(end_time)*1000
		stem[start_time:end_time].export(out)

	def export_from_sections(self, start: int, end: int, type: str, out: str = None) -> None:
		start_sec = self.sections[start]
		end_sec = self.sections[end]
		stem = self.stems[type]
		start_time = start_sec.start_time
		end_time = end_sec.end_time
		if not out:
			out = f"./data/music/measures/{self.title}{type}{start}-{end}.wav"
		stem[start_time*1000:end_time*1000].export(out)

	def measures_from_downbeat(self, info:dict):
		beat_len = 60/self.bpm
		search_end = beat_len * 16
		segments = pd.DataFrame(info['segments'], columns=['start', 'loudness_max'])
		search = segments[segments['start']<search_end]
		downbeat = search.loc[search['loudness_max'].idxmax()][0]
		print(downbeat)
		beats = [beat['start'] for beat in info['beats']]
		beats = np.asarray(beats)
		start_ind = np.searchsorted(beats, downbeat, "left")
		measures = beats[start_ind::16]
		measures = np.array(measures,np.float32)
		print(measures)
		return measures

# Helper Functions
# async def 

def bars_to_measures(bars: list) -> np.ndarray:
	''' Converts list of bars into 1D np array
	'''
	measure_list = bars[::4]
	start_times = [bar['start'] for bar in measure_list]
	measures = np.array(start_times,np.float32)
	return measures

def beats_to_measures(beats: list) -> np.ndarray:
	''' Converts list of beats into 1D np array
	'''
	measure_list = beats[::16]
	start_times = [bar['start'] for bar in measure_list]
	measures = np.array(start_times,np.float32)
	return measures

def measures_from_confident_beat(beats: list) -> np.ndarray:
	confidences = [beat['confidence'] for beat in beats[0:2]]
	start = confidences.index(max(confidences))
	print(start)
	measure_list = beats[start::16]
	start_times = [bar['start'] for bar in measure_list]
	print(start_times)
	measures = np.array(start_times,np.float32)
	return measures

def find_measures(info: dict):
	bars = info['bars']
	beats = info['beats']
	bar_conf_list = np.asarray([bar['confidence'] for bar in bars])
	beat_conf_list = np.asarray([beat['confidence'] for beat in beats])
	print(beat_conf_list)
	best_bar_ind = bar_conf_list.index(max(bar_conf_list))
	best_beat_ind = beat_conf_list.index(max(beat_conf_list))
	print(bars[best_bar_ind]['start'])
	avg_beat_length = 60/info['track']['tempo']
	avg_bar_length = avg_beat_length*4
	start_time = bars[best_bar_ind]['start']
	while start_time > 0:
		start_time = start_time - (avg_bar_length*4)
	start_time = start_time+(avg_bar_length*4)
	measures = np.arange(start_time, info['track']['duration'], avg_bar_length*4)
	return measures

def find_closest_bpm(self_bpm, target_bpm):
	diff = abs(target_bpm-self_bpm)
	if(self_bpm < target_bpm):
		if(abs(target_bpm-(self_bpm*2)) < diff):
			self_bpm = self_bpm*2
	else:
		if(abs(target_bpm-(self_bpm/2)) < diff):
			self_bpm = self_bpm/2
	return self_bpm

def find_closest_key_shift(self: MashSong, target: MashSong):
	diff = 1
	print(f"{self.key}/{self.key.relative}/{self.key.parallel}")
	print(f"{target.key}/{target.key.relative}/{target.key.parallel}")
	
	while(True):
		new_key = self.key.transpose(diff)
		print(f"NewKey: {new_key}/{new_key.pitchFromDegree(1)}/{new_key.pitchFromDegree(1).ps}")
		if(new_key.pitchFromDegree(1).ps == target.key.pitchFromDegree(1).ps and new_key.mode == target.key.mode):
			break
		elif(new_key.pitchFromDegree(1).ps == target.key.relative.pitchFromDegree(1).ps and new_key.mode == target.key.relative.mode):
			break
		diff += 1
	if(diff > 6):
		diff = -12.1 + diff
	else:
		diff = diff - .1
	diff = round(diff/2)
	print(f"Original Key: {self.key}/{self.key.relative} + {diff}")
	new_key = self.key.transpose(diff)
	print(f"Key: {new_key}/{new_key.relative}")
	return diff

	


