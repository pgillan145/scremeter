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
import resampy
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

    if (len(consolidate) == 0):
        return

    wav_file = mp3_dir + '/' + consolidated_header + '-' + date + start + '-' + hour + end + '.wav'
    mp3_file = mp3_dir + '/' + consolidated_header + '-' + date + start + '-' + hour + end + '.mp3'

    anchor_rate, d = wavfile.read(consolidate[0])
    beep = scremeter.beep()
    if (beep is not None):
        beep_rate, beep_data = wavfile.read(beep)

    consolidated_data = None
    i = 0
    for file in consolidate:
        reduced_file = reduced_filename(file)
        if (os.path.exists(reduced_file) is False):
            raise Exception(f"{reduced_file} doesn't exist")

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
        i = i + 1
        if (i < len(consolidate) and beep is not None):
            consolidated_data = numpy.append(consolidated_data, beep_data)

            
    wavfile.write(wav_file, anchor_rate, consolidated_data)
    if (os.path.exists(mp3_file)):
        delete(mp3_file)
    command = ['ffmpeg', '-i', wav_file, mp3_file]
    subprocess.run(command)
    delete(wav_file)
    for file in consolidate:
        basename = os.path.basename(file)
        archive_file = archive_dir + '/' + basename
        reduced_file = reduced_filename(file)

        # moved the raw files we used into the archive directory and remove the "reduced" files
        shutil.move(file, archive_file)
        delete(reduced_file)
        del(cache['files'][file])

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

    # Clear invalid entries from the cache
    cache_files = list(cache['files'].keys())
    for file in cache_files:
        if (file not in wav_files):
            del(cache['files'][file])


    date_hour_log = {}
    # collect the number of files for each hour so we know when to 
    for file in wav_files:
        parsed = parse_filename(file)

        date_hour = parsed['year'] + parsed['month'] + parsed['day'] + parsed['hour']
        if (date_hour not in date_hour_log):
            date_hour_log[date_hour] = 0

        #print(date_hour)
        date_hour_log[date_hour] = date_hour_log[date_hour] + 1

    #for dh in date_hour_log.keys():
    #    print(f"{dh}: {date_hour_log[dh]}")
    #dump(cache)
        
    flagged_dir = scremeter.flagged_dir()
    for file in wav_files:
        status = None
        basename = os.path.basename(file)
        parsed = parse_filename(file)
        date_hour = parsed['year'] + parsed['month'] + parsed['day'] + parsed['hour']

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
                if (os.path.exists(reduced_file) is False):
                    status = None
                    del(cache['files'][file])
                else:
                    date_hour_log[date_hour] = date_hour_log[date_hour] - 1
                #print(f"date_hour_log[{date_hour}] = {date_hour_log[date_hour]}")
                #print(f"{basename}")
                #print(f"  status:{status}, flagged:{flagged}")
                #continue
            elif (status == 'edit'):
                if (md5 == cache['files'][file]['md5']):
                    print(f"{basename} still needs to be edited")
                    continue
                elif ( md5 != cache['files'][file]['md5']):
                    #print(f"{basename}")
                    #print("  original file has changed")
                    delete(reduced_file)
                    del(cache['files'][file])

        # If the user just wanted to look at flagged files, we're done with that, go on to the next item
        if (args.edits is True): continue
        if (args.flagged is True): continue

        # clean up the raw file, if it hasn't been already
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


        # let the user decide what to do with this file
        while(True and status != 'keep'):
            print(f"unkept files in this block:{date_hour_log[date_hour]}")
            print(f"{basename} (status:'{status}'):")
            c = minorimpact.getChar(default='', end='\n', prompt="command? ", echo=True).lower()
            if (c == 'd'):
                c = minorimpact.getChar(default='', end='\n', prompt="again, please ", echo=True).lower()
                if (c == 'd'):
                    delete(file)
                    delete(reduced_file)
                    date_hour_log[date_hour] = date_hour_log[date_hour] - 1
                    break
            elif (c == 'e'):
                cache['files'][file] = { 'status':'edit', 'flagged':False, 'md5':md5 }
                delete(reduced_file)
                break
            elif (c == 'f'):
                # This one is special, we want to flag it for future consideration
                flagged_file = flagged_dir + '/' + basename
                if (os.path.exists(flagged_file) is False):
                    shutil.copyfile(file, flagged_file)

                cache['files'][file] = { 'status':'keep', 'flagged':True }
                status = 'keep'
                date_hour_log[date_hour] = date_hour_log[date_hour] - 1
                break
            elif (c == 'k'):
                cache['files'][file] = { 'status':'keep', 'flagged':False }
                status = 'keep'
                date_hour_log[date_hour] = date_hour_log[date_hour] - 1
                break
            elif (c == 'p' or c == ' '):
                play(reduced_file)
            elif (c=='q'):
                sys.exit()

        # once every file for this hour has been marked 'keep', consolidate the hour
        if (date_hour_log[date_hour] == 0):
            consolidate(date_hour)

    minorimpact.write_cache(scremeter.cache_file(), cache)

def parse_filename(file):
    basename = os.path.basename(file)
    m = re.search("^(.+)-(\d\d\d\d)-(\d\d)-(\d\d)-(\d\d)_(\d\d)_(\d\d)", basename)
    if (m is not None):
        header = m[1]
        year = m[2]
        month = m[3]
        day = m[4]
        hour = m[5]
        minute = m[6]
        second = m[7]
        return { 'header':header, 'year':year, 'month':month, 'day':day, 'hour':hour, 'minute':minute, 'second':second }
    raise Exception(f"invalid filename: {basename}")

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
