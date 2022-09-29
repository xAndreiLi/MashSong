import shutil
import subprocess
from pathlib import Path
import os
import re
import numpy as np
import pandas as pd
from mashdata import MashSong

class Vamp:
	vamp_path = Path.cwd() / 'plugins'
	os.environ["VAMP_PATH"] = str(vamp_path)

	def run_plugin(plugin: str = None, plugin_lib: str = None, input: str = None, *args, **kwargs):
		'''
		Wrapper function for Vamp Plugins

		Args
			-o output: str 		File to output data to (.txt) Otherwise output to stdout
			-s label_sample: bool 	Whether or not to label results with sample frame or seconds
			-l List plugin libraries
			--list-outputs	List plugin outputs

		'''
		#set VAMP_PATH = {vamp_path.absolute} & 
		vamp_path = Path.cwd() / 'plugins'
		cmd = f"set VAMP_PATH = {vamp_path} & VampSimpleHost.exe {plugin_lib}:{plugin} {input}"
		for key, value in kwargs:
			cmd += f"{key} {value}"
		for arg in args:
			cmd += f"{arg}"
		subprocess.call(cmd, shell=True, )

#"qm-tempotracker", "qm-vamp-plugins", Path(path)

	def tempo_beat_tracker(input: str, *args, **kwargs):
		'''
		Tempo and Beat Tracker analyses a single channel of audio and estimates the positions of metrical 
		beats within the music (the equivalent of a human listener tapping their foot to the beat).
		Parameters
			Beat Tracking Method : The method used to track beats. The default, "New", uses a hybrid of the 
				"Old" two-state beat tracking model (see reference Davies 2007) and a dynamic programming method 
				(see reference Ellis 2007). A more detailed description is given below within the Bar and Beat Tracker plugin.
			Onset Detection Function Type : The algorithm used to calculate the onset likelihood function. 
				The most versatile method is the default, "Complex Domain" (see reference, Duxbury et al 2003). 
				"Spectral Difference" may be appropriate for percussive recordings, "Phase Deviation" for 
				non-percussive music, and "Broadband Energy Rise" (see reference, Barry et al 2005) for 
				identifying percussive onsets in mixed music.
			Adaptive Whitening : This option evens out the temporal and frequency variation in the 
				signal, which can yield improved performance in onset detection, for example in audio 
				with big variations in dynamics.
		Outputs
			Beats : The estimated beat locations, returned as a single feature, with timestamp but 
				no value, for each beat, labelled with the corresponding estimated tempo at that beat.
			Onset Detection Function : The raw note onset likelihood function used in beat estimation.
			Tempo : The estimated tempo, returned as a feature each time the estimated tempo changes, 
				with a single value for the tempo in beats per minute. 
		'''
		cmds = [shutil.which("VampSimpleHost.exe"), "qm-vamp-plugins:qm-tempotracker", input]
		for key, value in kwargs:
			args.append(key)
			args.append(value)
		for arg in args:
			args.append(arg)
		out = subprocess.check_output(cmds).decode("utf-8")
		regList = re.findall(r"(\d*\.\d*)[\:] (\d*\.\d*)", out)
		beat_tempo_arr = np.array(regList).reshape([-1,2])
		return beat_tempo_arr

	def detect_note_onset(input: str, *args, **kwargs):
		'''
		Note Onset Detector analyses a single channel of audio and estimates the onset times of notes within the music : 
		that is, the times at which notes and other audible events begin.
		It calculates an onset likelihood function for each spectral frame, and picks peaks in a smoothed version of this 
		function. The plugin is non-causal, returning all results at the end of processing.
		Parameters
			Onset Detection Function Type : The method used to calculate the onset likelihood function. The most versatile 
				method is the default, "Complex Domain" (see reference, Duxbury et al 2003). "Spectral Difference" may be appropriate 
				for percussive recordings, "Phase Deviation" for non-percussive music, and "Broadband Energy Rise" 
				(see reference, Barry et al 2005) for identifying percussive onsets in mixed music.
			Onset Detector Sensitivity : Sensitivity level for peak detection in the onset likelihood function. 
				The higher the sensitivity, the more onsets will (rightly or wrongly) be detected. The peak 
				picker does not have a simple threshold level; instead, this parameter controls the required 
				"steepness" of the slopes in the smoothed detection function either side of a peak value, 
				in order for that peak to be accepted as an onset.1
				Adaptive Whitening : This option evens out the temporal and frequency variation in the 
				signal, which can yield improved performance in onset detection, for example in audio 
				with big variations in dynamics.
		Outputs
			Note Onsets : The detected note onset times, returned as a single feature with timestamp but no value for each detected note. 
		'''
		cmds = [shutil.which("VampSimpleHost.exe"), "qm-vamp-plugins:qm-onsetdetector", input]
		for key, value in kwargs:
			args.append(key)
			args.append(value)
		for arg in args:
			args.append(arg)
		out = subprocess.check_output(cmds).decode("utf-8")
		subprocess.call
		regList = re.findall(r"(\d*\.\d*)", out)
		note_onset_arr = np.ndarray(regList)
		return note_onset_arr
		
	def bar_beat_tracker(input: str, *args, **kwargs):
		cmds = [shutil.which("VampSimpleHost.exe"), "qm-vamp-plugins:qm-barbeattracker:bars", input]
		for key, value in kwargs:
			args.append(key)
			args.append(value)
		for arg in args:
			args.append(arg)
		out = subprocess.check_output(cmds).decode("utf-8")
		# regList = re.findall(r"(\d*\.\d*)[:] (\d)", out)
		regList = re.findall(r"(\d*\.\d*)", out)
		# df = pd.DataFrame(regList,columns=['time','beat_no'])
		# dt = np.dtype("float,int")
		# beats_arr = np.array(regList, dtype=dt)
		# measures_arr = beats_arr[np.where(beats_arr[:][1]==1)]
		# bars = df['time'][df["beat_no"]=="1"]
		print(regList)
		# return bars


	beats = bar_beat_tracker("./data/music/src/NoBlueberries.wav")
		
	# # beats = Vamp.tempo_beat_tracker("./data/music/src/NoBlueberries.wav")
	# # print(type(beats[0,0]))
	song = MashSong.get_song_from_json('NoBlueberriesInfo.json')

	song.export_from_times(.35972917, 7.693562500, "Accompaniment", "./data/music/measures/NoBlueNew2.wav")
	song.export_from_measures(0, 1, "Accompaniment", "./data/music/measures/NoBlueOld.wav")
	print(f"{song.measures[0]} - {song.measures[1]}")