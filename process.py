#!/usr/bin/env python3

import argparse
import copy
from dumper import dump
import minorimpact
import noisereduce as nr
import numpy
import os.path
import re
from scipy.io import wavfile
import scipy.signal
import scremeter
import sys

raw_dir = scremeter.raw_dir()
processed_dir = scremeter.processed_dir()
mp3_dir = scremeter.mp3_dir()
prop_decrease = .85

def main():
    parser = argparse.ArgumentParser(description = 'scremeter processor')
    parser.add_argument('-1', '--one', help = "process a single file", action='store_true')
    parser.add_argument('-r', '--reprocess', help = "reduce files even if they already exist", action='store_true')
    parser.add_argument('-v', '--verbose', help = "Verbose output", action='store_true')
    args = parser.parse_args()

    if (processed_dir is None):
        print("processed_dir is not defined")
        sys.exit()

    # load data
    wav_files = sorted(minorimpact.readdir(raw_dir))

    for file in wav_files:
        basename = os.path.basename(file)
        print(f"processing {basename}")
        m = re.search("^(.+)-(\d\d\d\d-\d\d-\d\d-\d\d_\d\d_\d\d)", basename)
        if (m is not None):
            header = m[1]
            date = m[2]
        else:
            print("invalid filename: {basename}")
            continue

        reduced_basename = f"{header}-{date}-reduced.wav"
        reduced_file = processed_dir + "/" + reduced_basename

        if (os.path.exists(reduced_file) and args.reprocess is False):
            print(f"  already processed")
            continue
        rate, data = wavfile.read(file)

        seconds = data.shape[0]/rate
        print(f"  length: {seconds} seconds")



        #data2 = copy.deepcopy(data)
        #data2 = data[0:(rate*2)]
        # Use the last 3 seconds as room tone
        data2 = data[-(rate*3):]

        #seconds2 = data2.shape[0]/rate
        #wavfile.write("short.wav", rate, data2)

        # perform noise reduction
        reduced_noise = nr.reduce_noise(y=data, y_noise=data2, sr=rate, prop_decrease=prop_decrease, stationary=True)

        # try to find the places in the file where shit's the loudest
        peaks, unknown = scipy.signal.find_peaks(reduced_noise, distance=rate/2, height=260000000)
        #print(f"  peaks:{len(peaks)}")
        #if (len(peaks) < 10):
        #    dump(scipy.signal.peak_prominences(reduced_noise, peaks))
        #    for p in peaks:
        #        print(f"  {p/rate}")


        # number of seconds to keep before and after the first/last peaks
        peak_padding = 1

        trim_start = 0
        trim_end = len(reduced_noise)
        if (peaks[0] > rate*peak_padding):
            trim_start = peaks[0] - (rate*peak_padding)
        if (peaks[-1] < len(reduced_noise) - (rate*peak_padding)):
            trim_end = peaks[-1] + (rate*peak_padding)

        print(f"  cropping from {trim_start/rate} to {trim_end/rate}")
        reduced_noise = reduced_noise[trim_start:trim_end]
        print(f"  writing {reduced_file}")
        wavfile.write(reduced_file, rate, reduced_noise)
        if (args.one):
            break

if __name__ == '__main__':
    main()
