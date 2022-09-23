from __future__ import annotations, division
import logging
from typing import Tuple
from os import listdir
import json
import numpy as np
import pyrubberband as pyrb
from pathlib import Path
from pydub import AudioSegment
from spotipy import Spotify, SpotifyClientCredentials

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
	track_measures: np.ndarray

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

		self.logger = logging.getLogger(f"mashdata:section:{title}:{index}")
	
	def sync_to_measure(self) -> int:
		''' Sets start_time and duration to sync with closest measure times
			(Must be called from MashSong methods)
			Returns the end index to begin from the next iteration
		'''
		start_ind = 0
		end_ind = np.searchsorted(self.track_measures, self.end_time)-1

		# if end_ind >= len(self.track_measures):
		# 	end_ind = len(self.track_measures) - 1
		
		self.logger.info(f"Orig Times: {self.start_time} - {self.start_time+self.duration}")

		self.start_time = self.track_measures[start_ind]
		self.end_time = self.track_measures[end_ind]
		self.logger.info(f"Extended by {self.end_time-self.start_time - self.duration}")
		self.duration = self.end_time - self.start_time
		

		self.track_measures = self.track_measures[start_ind:end_ind]

		self.logger.info(f"Synced to {self.start_time} - {self.end_time}, spanning {end_ind} measures")
		return end_ind

	def __str__(self) -> str:
		string = f"Section {self.index}:\n\tStart: {self.start_time}\n\tStop: {self.end_time}\n\tLoudness: {self.loudness}\n\tDuration: {self.duration}"
		return string

class MashSong:
	'''	Defines data object that represents a Song Track 
		and holds its stems and Spotify analysis data
	'''

	FRAME_RATE: int = 44100		# (Sample Rate)
	SAMPLE_WIDTH: int = 2		# in bytes (1 = 8bit)
	CHANNELS: int = 2			# {mono:1, stereo:2}

	title: str
	key: int
	bpm: float
	sections: list[Section]
	measures: np.ndarray
	stems: dict[str,AudioSegment]

	def __init__(self, title: str, info: dict) -> None:
		self.title = title
		self.logger = logging.getLogger(f"mashdata:mashsong:{title}")
		self.key = int(info['track']['key'])	# int(0-11) that maps C, C#,...B
		self.bpm = float(info['track']['tempo'])
		self.logger.info(f"Measure Length: {(60/self.bpm)*16}")
		self.sections = [Section(section, ind, title) for ind, section in enumerate(info['sections'])]
		self.measures = measures_from_confident_beat(info['beats'])
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
		query = f'track:{title}'
		if artist: 
			query += f' artist:{artist}'
		query.replace(' ', '%20')
		
		spotify = Spotify(client_credentials_manager=SpotifyClientCredentials())
		uri = spotify.search(query, 1)['tracks']['items'][0]['uri']
		info = spotify.audio_analysis(uri)
		title = title.title().replace(' ', '')

		if save_data:
			
			data_path = Path.cwd() / 'data' / 'info'
			file = data_path / f'{title}Info.json'
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
		data_path = Path.cwd() / 'data' / 'info'
		file = data_path / filename
		with file.open() as f:
			info = json.load(f)
		title = filename.removesuffix('Info.json')
		return MashSong(title, info)

	def fetch_stems(self):
		stem_path = Path.cwd() / 'data' / 'music' / 'out'
		stems = {}
		for file in listdir(stem_path):
			if file.find(self.title) != -1:
				stem = AudioSegment.from_file(stem_path/file, format='.wav')
				stems[file.removeprefix(self.title).removesuffix(".wav")] = stem
		return stems
			

	def create_mash_stem(
				self, new_stem_name: str, src_stem_type: str, start_sec: int, end_sec: int, target_key: int = None, 
				target_bpm: float = None, target_song: MashSong = None) -> AudioSegment:
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
		if target_song:
			target_key = target_song.key
			target_bpm = target_song.bpm
		elif not (target_key or target_bpm):
			raise ValueError(
				'Must provide target_key and target_bpm or provide target_song')

		try:
			stem_segment = self.stems[src_stem_type]
			stem_segment = stem_segment[self.sections[start_sec].start_time*1000:self.sections[end_sec].end_time*1000]
		except KeyError as e:
			raise KeyError(
				f"No stem type of {src_stem_type} found in stems for {self.title}")

		# Get fraction of octave to shift
		shift_amt = (target_key-self.key)/12
		pitched_samples = pitch_shift_by_frame(stem_segment, shift_amt)
		
		# Time stretch data to correct BPM (pitch independant)
		bpm_ratio = target_bpm/self.bpm
		stretched_samples = pyrb.time_stretch(pitched_samples, 
								MashSong.FRAME_RATE, bpm_ratio)
		# Convert array data from 1-bit to 16-bit sample width
		stretched_samples = np.int16(stretched_samples * 2 ** 15)
		stretched_samples = stretched_samples.flatten()
		mash_stem = AudioSegment(stretched_samples.tobytes(), 
								frame_rate = MashSong.FRAME_RATE, 
								sample_width=MashSong.SAMPLE_WIDTH, 
								channels=MashSong.CHANNELS)
		
		self.stems[new_stem_name] = mash_stem
		return mash_stem

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


# Helper Functions
def pitch_shift_by_frame(stem_segment: AudioSegment, shift_amt: float) -> np.ndarray:
	''' Scale framerate to shift to target pitch. Returns np array of 16-bit samples.
		(Tempo changes as a side effect)
	'''
	# Scales framerate to shift to the target pitch
	new_frame_rate = int(MashSong.FRAME_RATE * (2.0 ** shift_amt))
	pitched_segment = stem_segment._spawn(stem_segment.raw_data, 
						overrides={'frame_rate':new_frame_rate})
	pitched_segment = pitched_segment.set_frame_rate(MashSong.FRAME_RATE)
	# Convert new data to np array and reshape for stero data
	pitched_samples = np.array(stem_segment.get_array_of_samples())
	pitched_samples = pitched_samples.reshape((-1,2))
	return pitched_samples

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
	measure_list = beats[start::16]
	start_times = [bar['start'] for bar in measure_list]
	measures = np.array(start_times,np.float32)
	return measures