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

def concat(concat_type, filename, files, archive = None):
    if (concat_type == 'timelapse'):
        frame_list_file = '/tmp/concat_files.txt'
        delete(frame_list_file)
        frame_list = open(frame_list_file, 'w')
        for file in files:
            file_info = scremeter.parse_filename(file)
            text = f"{file_info['month']}/{file_info['day']}/{file_info['year']} {file_info['hour']}:{file_info['minute']}"
            frame_list.write(f"file '{file}'\n")
            frame_list.write(f"file_packet_meta datetime '{text}'\n")
        frame_list.close()

        if (filename is not None):
            print(f"generating {filename}...")
            if (os.path.exists(filename)):
                delete(filename)
            text_settings = "drawtext=text='%{metadata\\:datetime}':fontsize=45:x=w-tw-20:y=h-th-20:fontcolor=white:box=1:boxcolor=black@.5"
            command = ['ffmpeg', '-r','30', '-f','concat', '-safe','0','-i',frame_list_file, '-vf',text_settings, '-c:v', 'libx264', filename]
            done = subprocess.run(command)
            if (done.returncode == 0):
                print("ffmpeg completed successfully")
                if (archive is not None):
                    print("archiving files...")
                    os.makedirs(archive, exist_ok = True)
                    for file in files:
                        base = os.path.basename(file)
                        archive_file = f'{archive}/{base}'
                        #print(f"moving {file} -> {archive_file}")
                        shutil.move(file, archive_file)
            else:
                raise Exception("ffmpeg failed")
    else:
        raise Exception('invalid concatenation type')

def scan_files(path):

    # Timelapse
    files = minorimpact.readdir(f'{path}/timelapse-raw')
    current_date_hour = makeDateHour()
    print("current date hour:" , current_date_hour)
    
    # TODO: get the first file, and then process all those items. Repeat as long as there are non-current files to process.
    
    to_concat = {}
    for file in sorted(files):
        file_date_hour = makeDateHour(file=file)
        #print(file, file_date_hour)
        if (file_date_hour >= current_date_hour):
            continue

        if (file_date_hour not in to_concat):
            to_concat[file_date_hour] = []

        to_concat[file_date_hour].append(file)

    for date_hour in to_concat.keys():
        if (len(to_concat[date_hour]) == 0):
            continue
        file_info = scremeter.parse_filename(to_concat[date_hour][0])
        concat('timelapse', f"{path}/timelapse/{file_info['header']}_{date_hour}.mp4", to_concat[date_hour], archive=f"/Volumes/Archive/Backups/scremus/timelapse-raw/{file_info['header']}-{date_hour}")
        #break


def makeDateHour(date = None, file = None, inc_minute = False):
    if (file is not None):
        file_info = scremeter.parse_filename(file)
        date = datetime(int(file_info['year']),int(file_info['month']),int(file_info['day']),hour=int(file_info['hour']), minute=int(file_info['minute']), second=int(file_info['second']))
    elif (date is None):
        date = datetime.now()

    year = date.year
    month = date.month
    day = date.day
    hour = date.hour
    minute = date.minute
    if (year < 10):
        year = f'000{year}'
    elif (year < 100):
        year = f'00{year}'
    elif (year < 1000):
        year = f'0{year}'

    if (month < 10):
        month = f'0{month}'

    if (day < 10):
        day = f'0{day}'

    if (hour < 10):
        hour = f'0{hour}'

    if (minute < 10):
        minute = f'0{minute}'

    if (inc_minute is True):
        date_hour = f'{year}{month}{day}{hour}{minute}'
    else:
        date_hour = f'{year}{month}{day}{hour}'

    return date_hour

def delete(file):
    #print(f"deleting {file}")
    if (os.path.exists(file)):
        os.remove(file)

def main():
    global cache
    parser = argparse.ArgumentParser(description = 'scremeter processor')
    parser.add_argument('-1', '--one', help = "process a single file/hour", action='store_true')
    parser.add_argument('--clear_cache', help = "clear the processing cache and reevaluate everything", action='store_true')
    parser.add_argument('--force', help = "consolidate all processed items even if we're still in the current hour", action='store_true')
    parser.add_argument('-r', '--reprocess', help = "reduce files even if they already exist", action='store_true')
    parser.add_argument('-v', '--verbose', help = "Verbose output", action='store_true')
    args = parser.parse_args()

    # cache = scremeter.get_cache(clear_cache = args.clear_cache)
    scremeter.turnWriteCacheOff()

    path = '/home/pgillan/Documents/scremus'
    scan_files(path)

if __name__ == '__main__':
    main()
