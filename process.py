#!/usr/bin/env python3

import argparse
import copy
from datetime import datetime
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
mp4_dir = scremeter.mp4_dir()
wav_dir = scremeter.wav_dir()
processed_dir = scremeter.processed_dir()
raw_dir = scremeter.raw_dir()

cache = {}
prop_decrease = .85


def audio_length(file):
    rate, data = wavfile.read(file)

    seconds = data.shape[0]/rate
    return seconds

def consolidate(date_hour, force = False):
    print(f"CONS {date_hour}")

    consolidate = []
    consolidated_header = 'consolidated'
    start = None
    end = None
    m = re.search("(\\d\\d\\d\\d)(\\d\\d)(\\d\\d)(\\d\\d)", date_hour)
    if (m is None):
        raise Exception(f"invalid date_hour:{date_hour}")

    date = f"{m[1]}-{m[2]}-{m[3]}-{m[4]}"
    hour = m[4]
    files = minorimpact.readdir(raw_dir)
    for file in sorted(files):
        #print(file)
        basename = os.path.basename(file)
        m = re.search("^(.+)-(\\d\\d\\d\\d-\\d\\d-\\d\\d-\\d\\d_\\d\\d_\\d\\d)", basename)
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

    wav_file = wav_dir + '/' + consolidated_header + '-' + date + start + '-' + hour + end + '.wav'
    mp3_file = None
    mp4_file = None
    mp4_title = consolidated_header

    if (mp3_dir is not None):
        mp3_file = mp3_dir + '/' + consolidated_header + '-' + date + start + '-' + hour + end + '.mp3'

    if (mp4_dir is not None):
        mp4_file = mp4_dir + '/' + consolidated_header + '-' + date + start + '-' + hour + end + '.mp4'
        t = date + start + ' to ' + date + end
        t = re.sub('(\\d\\d\\d\\d)-(\\d\\d)-(\\d\\d)-','\\g<1>\\/\\g<2>\\/\\g<3> ', t)
        t = re.sub('_', '\\\\\\:',t)

        mp4_title = mp4_title + '\n' + t + '\n' + str(len(consolidate)) + ' event'
        print(mp4_title)
        if (len(consolidate) > 1): mp4_title = mp4_title + 's'

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

    if (mp3_file is not None):
        print(f"generating {mp3_file}")
        if (os.path.exists(mp3_file)):
            delete(mp3_file)
        command = ['ffmpeg', '-i', wav_file, mp3_file]
        subprocess.run(command)

    if (mp4_file is not None):
        print(f"generating {mp4_file}")
        if (os.path.exists(mp4_file)):
            delete(mp4_file)
        base = os.path.basename(mp4_file)
        if (mp4_title is None):
            mp4_title = base
        command = ['ffmpeg', '-f', 'lavfi', '-i', 'color=c=blue:s=1280x720', '-i', wav_file, '-vf', f'drawtext=fontfile=/path/to/font.ttf:text={mp4_title}:fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-text_w)/2:y=(h-text_h)/2', '-shortest', '-fflags', '+shortest', mp4_file]
        subprocess.run(command)

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
    parser.add_argument('--force', help = "consolidate all processed items even if we're still in the current hour", action='store_true')
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
    # collect the number of files for each hour so we know when we're done and can start to process them.
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
            process_file(file)

        # let the user decide what to do with this file
        while(True and status != 'keep'):
            print(f"unkept files in this block:{date_hour_log[date_hour]}")
            print(f"{basename} (status:'{status}'):")
            c = minorimpact.getChar(default='', end='\n', prompt="command? ", echo=True).lower()
            if (c == 'c'):
                crop_mode = 'raw'
                crop_start = scremeter.pre_buffer() - 2
                crop_end = 0
                peak_start_override = 0
                peak_end_override = 0
                process_file(file, crop_start = crop_start, peak_start_override = peak_start_override, crop_end = crop_end, peak_end_override = peak_end_override)
                crop_side = 'start'
                while(True):
                    c = minorimpact.getChar(default='', end='\n', prompt=f"  crop command (mode:{crop_mode}, side:{crop_side})? ", echo=True).lower()
                    if (c == 'm'):
                        if (crop_mode == 'raw'): crop_mode = 'peak'
                        elif (crop_mode == 'peak'): crop_mode = 'raw'
                    elif (c == 'p'):
                        crop_mode = 'peak'
                    elif (c == 'q' or c == 'k'):
                        break
                    elif (c == 'r'):
                        crop_mode = 'raw'
                    elif (c == 'x' or c == 'e'):
                        crop_side = 'end'
                    elif (c == 'z' or c == 's'):
                        crop_side = 'start'
                    elif (c == ' '):
                        play(reduced_file)
                    elif (c == '-'):
                        if (crop_mode == 'peak'):
                            if (crop_side == 'start'):
                                peak_start_override -= .5
                            elif (crop_side == 'end'):
                                peak_end_override -= .5
                        elif (crop_mode == 'raw'):
                            peak_start_override = 0
                            peak_end_override = 0
                            if (crop_side == 'start'):
                                crop_start -= 1
                            elif (crop_side == 'end'):
                                crop_end += 1

                        process_file(file, crop_start = crop_start, peak_start_override = peak_start_override, crop_end = crop_end, peak_end_override = peak_end_override)
                    elif (c == '+' or c == '='):
                        if (crop_mode == 'peak'):
                            if (crop_side == 'start'):
                                peak_start_override += .5
                            elif (crop_side == 'end'):
                                peak_end_override += .5
                        elif (crop_mode == 'raw'):
                            peak_start_override = 0
                            peak_end_override = 0
                            if (crop_side == 'start'):
                                crop_start += 1
                            elif (crop_side == 'end'):
                                crop_end -= 1
                                if (crop_end < 0): crop_end = 0

                        process_file(file, crop_start = crop_start, peak_start_override = peak_start_override, crop_end = crop_end, peak_end_override = peak_end_override)
            elif (c == 'd'):
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
            elif (c == ' '):
                play(reduced_file)
            elif (c=='q'):
                sys.exit()

        current_date_hour = datetime.now().strftime("%Y%m%d%H")
        # once every file for this hour has been marked 'keep', consolidate the hour
        if (date_hour_log[date_hour] == 0):
            if (date_hour != current_date_hour or args.force is True):
                consolidate(date_hour)

    minorimpact.write_cache(scremeter.cache_file(), cache)

def parse_filename(file):
    basename = os.path.basename(file)
    m = re.search("^(.+)-(\\d\\d\\d\\d)-(\\d\\d)-(\\d\\d)-(\\d\\d)_(\\d\\d)_(\\d\\d)", basename)
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

def process_file(file, noise_seconds = 3, prop_decrease = .85, stationary = True, peak_start_override = 0, peak_end_override = 0, crop_start = scremeter.pre_buffer() - 2, crop_end = 0):
    basename = os.path.basename(file)

    print(f"processing {basename}")
    rate, raw_data = wavfile.read(file)
    raw_length = raw_data.shape[0]/rate

    trim_start = 0
    trim_end = len(raw_data)
    if (crop_start > 0):
        trim_start = int(crop_start * rate)

    if (crop_end > 0):
        trim_end = len(raw_data) - int(crop_end * rate)

    if (trim_start > trim_end):
        raise Exception(f"Invalid raw crop range {trim_start} to {trim_end}")

    if (trim_start > 0 or trim_end < len(raw_data)):
        print(f"  cropping initial file: 0(+{crop_start}) = {int(trim_start/rate)} to {int(len(raw_data)/rate)}(-{crop_end}) = {int(trim_end/rate)}")

    data = raw_data[trim_start:trim_end]

    # Use the last 3 seconds as room tone
    noise_data = data[-(rate*noise_seconds):]

    # perform noise reduction
    reduced_noise = nr.reduce_noise(y=data, y_noise=noise_data, sr=rate, prop_decrease=prop_decrease, stationary=stationary)

    # try to find the places in the file where shit's the loudest
    peaks, unknown = scipy.signal.find_peaks(reduced_noise, distance=rate/2, height=260000000)
    #print(f"  peaks:{len(peaks)}")
    #if (len(peaks) < 10):
    #    dump(scipy.signal.peak_prominences(reduced_noise, peaks))
    #    for p in peaks:
    #        print(f"  {p/rate}")

    # number of seconds to keep before and after the first/last peaks
    peak_padding = 1

    peak_trim_start = 0
    peak_trim_end = len(reduced_noise)
    if (len(peaks) > 0):
        if (peaks[0] > peak_padding * rate):
            peak_trim_start = peaks[0] - (peak_padding * rate)
        if (peaks[-1] < (len(reduced_noise) - (peak_padding * rate))):
            peak_trim_end = peaks[-1] + (peak_padding * rate)
    else:
        numpy.append(peaks, 0)
        numpy.append(peaks, len(reduced_noise))

    peak_trim_start = peak_trim_start + int(peak_start_override * rate)
    #print(f"  first peak: {(peaks[0]/rate):.2f}+({peak_start_override}) = {(peak_trim_start/rate):.2f}")
    peak_trim_end = peak_trim_end + int(peak_end_override * rate)
    #print(f"  last peak: {(peaks[-1]/rate):.2f}+({peak_end_override}) = {(peak_trim_end/rate):.2f}")

    if (peak_trim_start < 0): peak_trim_start = 0
    if (peak_trim_end > len(reduced_noise)): peak_trim_end = len(reduced_noise)
    if (peak_trim_start > peak_trim_end):
        raise Exception(f"invalid crop range '{peak_trim_start}' to '{peak_trim_end}'")

    #print(f"  cropping reduced file from {(peak_trim_start/rate):.2f} to {(peak_trim_end/rate):.2f}")
    reduced_noise = reduced_noise[peak_trim_start:peak_trim_end]
    reduced_seconds = reduced_noise.shape[0]/rate

    output_length = 60
    print(f"  raw:        0.00s - {raw_length:5.2f}s: {raw_length:5.2f}s")
    print(f"  trimmed:   {trim_start/rate:5.2f}s (0+{crop_start}) - {trim_end/rate:5.2f}s ({raw_length:5.2f}-{crop_end}): {data.shape[0]/rate:5.2f}s")
    print(f"  peak trim: {((peak_trim_start+trim_start)/rate):5.2f}s ({(((peaks[0]+trim_start)+(peak_padding*rate))/rate):5.2f}+{peak_start_override})  - {((peak_trim_end+trim_start)/rate):5.2f}s ({(((peaks[-1]+trim_start)-(peak_padding*rate))/rate):5.2f}+{peak_end_override}): {reduced_noise.shape[0]/rate:.2f}s")
    peak_map = {}
    for p in peaks:
        peak_map[int(((((p+trim_start)/rate)*(output_length-1))/raw_length)+1)] = True

    output = ''
    for i in range(1,output_length+1):
        if (i == int(((((peak_trim_start+trim_start)/rate)*(output_length-1))/raw_length)+1)):
            output += '['
        elif (i == int(((((peak_trim_end+trim_start)/rate)*(output_length-1))/raw_length)+1)):
            output += ']'
        elif (i in peak_map):
            output += '^'
        elif (i < int((((trim_start/rate)*(output_length-1))/raw_length)+1) or i > int((((trim_end/rate)*(output_length-1))/raw_length)+1)):
            output += '.'
        else:
            output += '-'

    print(output)


    reduced_file = reduced_filename(file)
    print(f"  writing {reduced_file}")
    wavfile.write(reduced_file, rate, reduced_noise)

def reduced_filename(file):
    basename = os.path.basename(file)
    m = re.search("^(.+)-(\\d\\d\\d\\d-\\d\\d-\\d\\d-\\d\\d_\\d\\d_\\d\\d)", basename)
    if (m is None):
        raise Exception(f"invalid filename {file}")

    header = m[1]
    date = m[2]

    reduced_basename = f"{header}-{date}-reduced.wav"
    reduced_file = processed_dir + "/" + reduced_basename

    return reduced_file

if __name__ == '__main__':
    main()
