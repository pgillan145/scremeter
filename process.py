#!/usr/bin/env python3

import argparse
import copy
from dumper import dump
import minorimpact
import noisereduce as nr
import numpy
import os
import os.path
import re
from scipy.io import wavfile
import scipy.signal
import scremeter
import shutil
import subprocess
import sys

archive_dir = scremeter.archive_dir()
flagged_dir = scremeter.flagged_dir()
mp3_dir = scremeter.mp3_dir()
processed_dir = scremeter.processed_dir()
raw_dir = scremeter.raw_dir()

cache = {}
prop_decrease = .85

def consolidate(date_hour):
    print(f"CONS {date_hour}")
    anchor_rate = None
    
    consolidate = []
    consolidated_header = 'consolidated'
    start = None
    end = None
    m = re.search("(\d\d\d\d)(\d\d)(\d\d)(\d\d)", date_hour)
    if (m is None):
        raise Exception(f"invalid date_hour:{date_hour}")

    date = f"{m[1]}-{m[2]}-{m[3]}-{m[4]}"
    hour = m[4]
    files = minorimpact.readdir(raw_dir)
    for file in sorted(files):
        #print(file)
        basename = os.path.basename(file)
        m = re.search("^(.+)-(\d\d\d\d-\d\d-\d\d-\d\d_\d\d_\d\d)", basename)
        if (m is None):
            continue

        header = m[1]
        file_date = m[2]
        if (consolidated_header == 'consolidated'):
            consolidated_header = header

        if (re.search(date, file)):
            minute = re.sub(date, '', file_date)
            if (start is None):
                start = minute
            end = minute
            consolidate.append(file)

    wav_file = mp3_dir + '/' + consolidated_header + '-' + date + start + '-' + hour + end + '.wav'
    mp3_file = mp3_dir + '/' + consolidated_header + '-' + date + start + '-' + hour + end + '.mp3'
    consolidated_data = None
    for file in consolidate:
        reduced_file = reduced_filename(file)
        #print(file)
        #print(reduced_file)
        rate, data = wavfile.read(reduced_file)
        if (anchor_rate is None):
            anchor_rate = rate
        elif (anchor_rate != rate):
            raise Exception(f"{file} rate is {rate}, should be {anchor_rate}")

        if (consolidated_data is None):
            consolidated_data = data
        else:
            consolidated_data = numpy.append(consolidated_data, data)
            
    wavfile.write(wav_file, anchor_rate, consolidated_data)
    if (os.path.exists(mp3_file)):
        delete(mp3_file)
    command = ['ffmpeg', '-i', wav_file, mp3_file]
    subprocess.run(command)
    delete(wav_file)
    for file in consolidate:
        basename = os.path.basename(file)
        archive_file = archive_dir + '/' + basename
        #print(f"move {file} to {archive_file}")
        shutil.move(file, archive_file)

        reduced_file = reduced_filename(file)
        #print(f"delete {reduced_file}")
        delete(reduced_file)
    #    delete reduced files
    #    move from raw into archive

def delete(file):
    #print(f"deleting {file}")
    if (os.path.exists(file)):
        os.remove(file)

def main():
    global cache
    parser = argparse.ArgumentParser(description = 'scremeter processor')
    parser.add_argument('-1', '--one', help = "process a single file", action='store_true')
    parser.add_argument('--clear_cache', help = "clear the processing cache and reevaluate everything", action='store_true')
    parser.add_argument('-e', '--edits', help = "show files that need to be edited", action='store_true')
    parser.add_argument('-f', '--flagged', help = "show flagged files", action='store_true')
    parser.add_argument('-r', '--reprocess', help = "reduce files even if they already exist", action='store_true')
    parser.add_argument('-v', '--verbose', help = "Verbose output", action='store_true')
    args = parser.parse_args()

    cache = scremeter.get_cache(clear_cache = args.clear_cache)

    if (processed_dir is None):
        print("processed_dir is not defined")
        sys.exit()

    # load data
    wav_files = sorted(minorimpact.readdir(raw_dir))

    files = list(cache['files'].keys())
    for file in files:
        if (file not in wav_files):
            del(cache['files'][file])

    date_hour_log = {}
    flagged_dir = scremeter.flagged_dir()
    last_date_hour = None
    for file in wav_files:
        status = None
        basename = os.path.basename(file)
        m = re.search("^(.+)-(\d\d\d\d-\d\d-\d\d-\d\d_\d\d_\d\d)", basename)
        if (m is not None):
            header = m[1]
            date = m[2]
            m2 = re.search("(\d\d\d\d-\d\d-\d\d-\d\d)_\d\d_\d\d", date)
            if (m2 is not None):
                date_hour = re.sub("-","", m2[1])
                if (date_hour != last_date_hour and last_date_hour is not None):
                    if (date_hour_log[last_date_hour] == 0):
                        # if everything in a given hour is "keep", then we want to:
                        #   combine all the files into an mp3
                        #   move the raw files into "archive"
                        #   delete the "reduced" files.
                        consolidate(last_date_hour)
                last_date_hour = date_hour

                if (date_hour not in date_hour_log):
                    date_hour_log[date_hour] = 0
                date_hour_log[date_hour] = date_hour_log[date_hour] + 1
                #print(f"date_hour_log[{date_hour}] = {date_hour_log[date_hour]}")
        else:
            print("invalid filename: {basename}")
            continue

        md5 = minorimpact.md5dir(file)
        #reduced_basename = f"{header}-{date}-reduced.wav"
        #reduced_file = processed_dir + "/" + reduced_basename
        reduced_file = reduced_filename(file)

        if (file in cache['files']):
            status = cache['files'][file]['status']
            flagged = cache['files'][file]['flagged']
            if (flagged is True):
                if (flagged_dir is not None):
                    flagged_file = flagged_dir + '/' + basename
                    if (os.path.exists(flagged_file) is False):
                        print(f"copying {file} to {flagged_file}")
                        shutil.copyfile(file, flagged_file)
                if (args.flagged is True):
                    print(f"{basename}")
                    continue
            if(status == 'keep'): 
                date_hour_log[date_hour] = date_hour_log[date_hour] - 1
                #print(f"date_hour_log[{date_hour}] = {date_hour_log[date_hour]}")
                #print(f"{basename}")
                #print(f"  status:{status}, flagged:{flagged}")
                #continue
            elif (status == 'edit'):
                if (md5 == cache['files'][file]['md5']):
                    if (args.edits is True):
                        print(f"{basename}")
                    continue
                elif ( md5 != cache['files'][file]['md5']):
                    #print(f"{basename}")
                    #print("  original file has changed")
                    delete(reduced_file)
                    del(cache['files'][file])

        if (args.edits is True): continue
        if (args.flagged is True): continue

        if (os.path.exists(reduced_file) is False or args.reprocess is True):
            print(f"processing {basename}")
            rate, data = wavfile.read(file)

            seconds = data.shape[0]/rate
            print(f"  length: {seconds} seconds")

            #data2 = copy.deepcopy(data)
            #data2 = data[0:(rate*2)]
            # Use the last 3 seconds as room tone
            data2 = data[-(rate*3):]

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

        #play(reduced_file)
        while(True and status != 'keep'):
            print(f"{basename}:")
            c = minorimpact.getChar(default='', end='\n', prompt="command? ", echo=True).lower()
            if (c == 'd'):
                c = minorimpact.getChar(default='', end='\n', prompt="again ", echo=True).lower()
                if (c == 'd'):
                    delete(file)
                    delete(reduced_file)
                    break
            elif (c == 'e'):
                cache['files'][file] = { 'status':'edit', 'flagged':False, 'md5':md5 }
                delete(reduced_file)
                break
            elif (c == 'f'):
                cache['files'][file] = { 'status':'keep', 'flagged':True }
                flagged_file = flagged_dir + '/' + basename
                if (os.path.exists(flagged_file) is False):
                    shutil.copyfile(file, flagged_file)
                break
            elif (c == 'k'):
                cache['files'][file] = { 'status':'keep', 'flagged':False }
                status = 'keep'
                date_hour_log[date_hour] = date_hour_log[date_hour] - 1
                #print(f"date_hour_log[{date_hour}] = {date_hour_log[date_hour]}")
                break
            elif (c == 'p' or c == ' '):
                play(reduced_file)
            elif (c=='q'):
                sys.exit()

        if (args.one):
            break

    minorimpact.write_cache(scremeter.cache_file(), cache)


def play(file, play_command = 'aplay'):
    if (file is None):
        return
    command = [play_command,file]
    subprocess.run(command)

def reduced_filename(file):
    basename = os.path.basename(file)
    m = re.search("^(.+)-(\d\d\d\d-\d\d-\d\d-\d\d_\d\d_\d\d)", basename)
    if (m is None):
        raise Exception(f"invalid filename {file}")

    header = m[1]
    date = m[2]

    reduced_basename = f"{header}-{date}-reduced.wav"
    reduced_file = processed_dir + "/" + reduced_basename

    return reduced_file

if __name__ == '__main__':
    main()
