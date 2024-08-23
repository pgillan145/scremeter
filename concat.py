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

cache = {}

def consolidated_filename(files, ext=None, seconds = True):
    default_header = 'consolidated'
    start = None
    end = None

    date = None
    hour = None
    if (len(files) == 0):
        raise Exception("no files to parse")

    for file in sorted(files):
        basename = os.path.basename(file)
        file_info = scremeter.parse_filename(file)
        if (ext is None):
            ext = file_info['extension']
        if (date is None):
            date = f"{file_info['year']}-{file_info['month']}-{file_info['day']}-{file_info['hour']}"
            hour = file_info['hour']

        file_date = f"{file_info['year']}-{file_info['month']}-{file_info['day']}-{file_info['hour']}"

        if (default_header == 'consolidated'):
            default_header = file_info['header']

        minute = file_info['minute']
        second = file_info['second']
        if (start is None):
            start = f'_{minute}'
            if (seconds is True): start = f'{start}_{second}'
        end = f'_{minute}'
        if (seconds is True): end = f'{end}_{second}'

    name = default_header + '-' + date + start + '-' + hour + end + f".{ext}"
    return name

def concat(concat_type, filename, files, archive = None):
    if (len(files) == 0):
        return

    if (concat_type == 'audio'):
        default_header = 'consolidated'
        start = None
        end = None

        date = None
        hour = None
        for file in sorted(files):
            print(file)
            basename = os.path.basename(file)
            file_info = scremeter.parse_filename(file)
            if (date is None):
                date = f"{file_info['year']}-{file_info['month']}-{file_info['day']}-{file_info['hour']}"
                hour = file_info['hour']

            file_date = f"{file_info['year']}-{file_info['month']}-{file_info['day']}-{file_info['hour']}"

            if (default_header == 'consolidated'):
                default_header = file_info['header']

            minute = file_info['minute']
            second = file_info['second']
            if (start is None):
                start = f'_{minute}_{second}'
            end = f'_{minute}_{second}'

        name = default_header + '-' + date + start + '-' + hour + end
        print(f"{name}")

        anchor_rate, d = wavfile.read(files[0])
        beep = scremeter.beep()
        if (beep is not None):
            beep_rate, beep_data = wavfile.read(beep)

        consolidated_data = None
        i = 0
        for file in files:
            if (os.path.exists(file) is False):
                raise Exception(f"{file} doesn't exist")

            rate, data = wavfile.read(file)
            if (anchor_rate is None):
                anchor_rate = rate
            elif (anchor_rate != rate):
                raise Exception(f"{file} rate is {rate}, should be {anchor_rate}")

            if (consolidated_data is None):
                consolidated_data = data
            else:
                consolidated_data = numpy.append(consolidated_data, data)
            i = i + 1
            if (i < len(files) and beep is not None):
                consolidated_data = numpy.append(consolidated_data, beep_data)

        wav_dir = scremeter.audio_dir()
        wav_file = wav_dir + '/' + name + '.wav'
        wavfile.write(wav_file, anchor_rate, consolidated_data)

        mp3_dir = scremeter.mp3_dir()
        if (mp3_dir is not None):
            mp3_file = mp3_dir + '/' + name + '.mp3'

            print(f"generating {mp3_file}")
            if (os.path.exists(mp3_file)):
                delete(mp3_file)
            command = ['ffmpeg', '-i', wav_file, mp3_file]
            done = subprocess.run(command)
            if (done.returncode != 0):
                raise Exception(f"ffmpeg failed to write {mp3_file}:{done.returncode}")

        mp4_dir = scremeter.mp4_dir()
        if (mp4_dir is not None):
            mp4_file = mp4_dir + '/' + name + '.mp4'

            t = date + start + ' to ' + date + end
            t = re.sub('(\\d\\d\\d\\d)-(\\d\\d)-(\\d\\d)-','\\g<1>\\/\\g<2>\\/\\g<3> ', t)
            t = re.sub('_', '\\\\\\:',t)

            mp4_title = re.sub('_', ' ',  default_header)
            mp4_title = mp4_title + '\n' + t + '\n' + str(len(files)) + ' event'
            if (len(files) > 1): mp4_title = mp4_title + 's'

            print(f"generating {mp4_file}")
            if (os.path.exists(mp4_file)):
                delete(mp4_file)
            base = os.path.basename(mp4_file)
            if (mp4_title is None):
                mp4_title = base
            command = ['ffmpeg', '-f', 'lavfi', '-i', 'color=c=blue:s=1280x720', '-i', wav_file, '-vf', f'drawtext=fontfile=/path/to/font.ttf:text={mp4_title}:fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-text_w)/2:y=(h-text_h)/2', '-shortest', '-fflags', '+shortest', mp4_file]
            done = subprocess.run(command)
            if (done.returncode != 0):
                raise Exception(f"ffmpeg failed to write {mp4_file}:{done.returncode}")

        if (archive is not None):
            print(f"archiving files to {archive}...")
            os.makedirs(archive, exist_ok = True)
            for file in files:
                base = os.path.basename(file)
                archive_file = f'{archive}/{base}'
                print(f"moving {file} -> {archive_file}")
                shutil.move(file, archive_file)

    elif (concat_type == 'timelapse'):
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
                    print(f"archiving files to {archive}...")
                    os.makedirs(archive, exist_ok = True)
                    for file in files:
                        base = os.path.basename(file)
                        archive_file = f'{archive}/{base}'
                        #print(f"moving {file} -> {archive_file}")
                        shutil.move(file, archive_file)
                        #TODO: tar archive files?
            else:
                raise Exception("ffmpeg failed")
    elif (concat_type == 'video'):
        # Combine anthing in either audio-raw or audio-processed (I haven't decided which) with the matching entry in video-raw to create a video file with audio.
        print(filename, files, archive)
        if (filename is not None):
            print(f"generating {filename}...")
            if (os.path.exists(filename)):
                delete(filename)
            #text_settings = "drawtext=text='%{metadata\\:datetime}':fontsize=45:x=w-tw-20:y=h-th-20:fontcolor=white:box=1:boxcolor=black@.5"
            #command = ['ffmpeg', '-r','30', '-f','concat', '-safe','0','-i',frame_list_file, '-vf',text_settings, '-c:v', 'libx264', filename]

            # TODO: Test which one of files is the video file and which one is the audio file
            audio_file = scremeter.process_audio_file(files[0])
            video_file = files[1]

            #concat('video', scremeter.video_dir() + '/' + scremeter.unparse_file_info(audio_file_info, ext = 'mp4'), [processed_audio_file, test_video_file] , archive=f"{scremeter.video_dir(raw = True, archive = True)}")
            command = ['ffmpeg', '-i', audio_file, '-i', video_file, '-c:v','copy', '-c:a', 'aac', filename]
            done = subprocess.run(command)
            if (done.returncode == 0):
                print("ffmpeg completed successfully")
                if (archive is not None):
                    print(f"archiving files to {archive}...")
                    os.makedirs(archive, exist_ok = True)
                    for file in files:
                        print(f"moving {file} -> {archive}")
                        shutil.move(file, archive)
                        #TODO: tar archive files?
    else:
        raise Exception('invalid concatenation type')

def scan_files(path):
    current_date_hour = makeDateHour()
    print("current date hour:" , current_date_hour)

    # Timelapse
    files = minorimpact.readdir(f'{scremeter.timelapse_dir(raw = True)}')

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
        file = consolidated_filename(to_concat[date_hour], 'mp4')
        archive_dir = re.sub('.mp4$', '', file)
        #concat('timelapse', f"{scremeter.timelapse_dir()}/{file_info['header']}_{date_hour}.mp4", to_concat[date_hour], archive=f"{scremeter.timelapse_dir(raw=True, archive = True)}/{file_info['header']}-{date_hour}")
        concat('timelapse', f"{scremeter.timelapse_dir()}/{file}", to_concat[date_hour], archive=f"{scremeter.timelapse_dir(raw = True, archive = True)}/{archive_dir}")

    # Audio
    files = minorimpact.readdir(f'{scremeter.audio_dir(processed = True)}')
    raw_files = minorimpact.readdir(f'{scremeter.audio_dir(raw = True)}')

    # Make a list of unprocessed blocks to ignore.
    to_ignore = []
    for file in sorted(raw_files):
        file_date_hour = makeDateHour(file=file)
        if (file_date_hour not in to_ignore):
            to_ignore.append(file_date_hour)

    # Get a list of blocks that need to be processed
    to_concat = {}
    for file in sorted(files):
        file_date_hour = makeDateHour(file=file)
        if (file_date_hour >= current_date_hour or file_date_hour in to_ignore):
            continue

        # ignore anything with files that still need to be processed.
        if (file_date_hour not in to_concat):
            to_concat[file_date_hour] = []

        to_concat[file_date_hour].append(file)

    for date_hour in to_concat.keys():
        print(f"{date_hour}:")
        if (len(to_concat[date_hour]) == 0):
            continue
        for file in to_concat[date_hour]:
            print(file)

        file = consolidated_filename(to_concat[date_hour])
        concat('audio', f"{scremeter.audio_dir()}/{file}", to_concat[date_hour], archive=f"{scremeter.audio_dir(processed=True, archive = True)}/{file_info['header']}-{date_hour}")

    # Video
    # Pull '.wav' files from both the raw audio directory and the raw video directory, but only fuck with files that have a matching '.avi' in the video-raw
    #   directory.
    audio_files = minorimpact.readdir(f'{scremeter.audio_dir(raw = True)}')
    audio_files = audio_files + list(filter(lambda x:re.search('\\.wav$', x), minorimpact.readdir(f'{scremeter.video_dir(raw = True)}')))

    for audio_file in sorted(audio_files):
        audio_file_info = scremeter.parse_filename(audio_file)
        test_video_file = scremeter.video_dir(raw = True) + '/' + scremeter.unparse_file_info(audio_file_info, ext = 'avi')
        if (os.path.exists(test_video_file)):
            # TODO: cleanup items in the video-raw directory that didn't have a mate.
            print(f"combining {audio_file} and {test_video_file}")
            concat('video', scremeter.video_dir() + '/' + scremeter.unparse_file_info(audio_file_info, ext = 'mp4'), [audio_file, test_video_file] , archive=f"{scremeter.video_dir(raw = True, archive = True)}")

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

    scan_files(scremeter.scremeter_dir())

if __name__ == '__main__':
    main()
