#!/usr/bin/env python3

import cv2
from datetime import datetime,timedelta
import pyaudio
import os
import random
import re
import scremeter
import sys
import time
from threading import Thread, Event
import wave

pre_buffer = scremeter.pre_buffer()
post_buffer = scremeter.post_buffer()

# audio variables
chunk = 256  # How large each chunk of data we record will be. Larger values seem to come out crackly.
sample_format = pyaudio.paInt24  # 24 bits per sample
audio_device_match_string = scremeter.audio_device()
channels = 1
frequency = 44100  # Record at 44100 samples per second
#   goes into a separate directory.
audio_base_filename = scremeter.audio_dir(raw = True) + '/' + scremeter.title() + '-'

# timelapse/video variables
video_device_match_string = scremeter.video_device()
print(f"VIDEO:{video_device_match_string}")
if (video_device_match_string is not None):
    audio_base_filename = scremeter.video_dir(raw = True) + '/' + scremeter.title() + '-'
timelapse_base_filename = f'{scremeter.timelapse_dir(raw = True)}/{scremeter.title()}-'
video_base_filename = f'{scremeter.video_dir(raw = True)}/{scremeter.title()}-'
video_codec = 'MJPG'
video_ext = 'avi'
width = 1920
height = 1080
fps = 24

random.seed()
scremeter.turnWriteCacheOff()

def expand_frames(frames, fps):
    new_frames = frames.copy()
    while (len(new_frames) < fps):
        rand = random.randrange(len(new_frames)-1)
        new_frames.insert(rand, new_frames[rand])

    while (len(new_frames) > fps):
        rand = random.randrange(len(new_frames)-1)
        del new_frames[rand]

    return new_frames

def main():
    p = pyaudio.PyAudio()  # Create an interface to PortAudio

    audio_frames = []
    video_frames = []
    audio_recording_thread = None
    video_recording_thread = None
    timelapse_recording_thread = None
    kill = Event()

    try:
        audio_recording_thread = Thread(target=record_audio, name='audio_recording', args=[p, audio_frames, kill])
        audio_recording_thread.start()
        video_recording_thread = Thread(target=record_video, name='video_recording', args=[video_frames, kill])
        video_recording_thread.start()
        timelapse_recording_thread = Thread(target=record_timelapse, name='timelapse_recording', args=[video_frames, kill])
        timelapse_recording_thread.start()
    except:
        sys.exit('Error starting recording threads')

    trigger_time = None

    # delete the trigger file, if there's still an old one hanging around
    trigger_file = scremeter.trigger_file()
    if (os.path.exists(trigger_file)):
        os.remove(trigger_file)

    trigger_post_buffer = post_buffer
    last = datetime.now()
    while (kill.is_set() is False):
        try:
            # just run once a couple of times a second
            time.sleep(.5)

            t = trigger()
            if (t is not None):
                print("\ntrigger detected")
                trigger_time = t
                trigger_end_time = trigger_time + timedelta(seconds = trigger_post_buffer)
                trigger_post_buffer = trigger_post_buffer + 1

            if (trigger_time is None):
                trigger_end_time = None
                trigger_post_buffer = post_buffer
                while (len(audio_frames) > pre_buffer or len(audio_frames) > len(video_frames)):
                    del audio_frames[0]
                while (len(video_frames) > pre_buffer or len(video_frames) > len(audio_frames)):
                    del video_frames[0]

            if (trigger_time is not None and trigger_end_time > datetime.now()):
                print(f"\rbuffer length: a:{len(audio_frames)}s/v:{len(video_frames)}s, trigger remaining:{int((trigger_end_time - datetime.now()).seconds)}s", end='')
            elif (trigger_time is not None and trigger_end_time < datetime.now() and len(audio_frames) > 0 and len(video_frames) >= len(audio_frames)):
                try:
                    audio_trigger_frames = audio_frames.copy()
                    video_trigger_frames = video_frames.copy()
                    write_file_thread = Thread(target=write_file, name='write_file', args=[p, trigger_time, audio_trigger_frames, video_trigger_frames])
                    write_file_thread.start()
                except:
                    sys.exit("error starting file write thread")

                trigger_time = None
            else:
                if (len(video_frames) > 0 and len(video_frames[0]) > 0 and len(audio_frames) > 0 and len(audio_frames[0]) > 0):
                    print(f"\rbuffer length: a:{len(audio_frames)}s({len(audio_frames[0])})/v:{len(video_frames)}s({len(video_frames[0])})", end='')
                else:
                    print(f"\rbuffer length: a:{len(audio_frames)}s/v:{len(video_frames)}s", end='')

        except KeyboardInterrupt:
            break
    print("")
    kill.set()


def record_audio(p, frames, kill):
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    deviceid = None
    print("scanning usb devices")
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            devinfo = p.get_device_info_by_host_api_device_index(0, i)
            name = devinfo.get('name')
            print("audio input Device id ", i, " - ", name)
            #print(float(frequency), i, channels, sample_format)
            #if (p.is_format_supported(float(frequency), input_device=i, input_channels=channels, input_format=sample_format)):
            #    print("SUPPORTED")
            #    if (re.match(audio_device_match_string, name) and deviceid is None):
            #        deviceid = i
            #        print("Using ", name)
            #else:
            #    print("UNSUPPORTED")
            if (re.match(audio_device_match_string, name) and deviceid is None):
                deviceid = i
                print("audio using ", name)

    if (deviceid is None):
        print("audio recorder couldn't get device id")
        kill.set()
        return

    print('audio recording: started')
    stream = p.open(format=sample_format,
                    channels=channels,
                    rate=frequency,
                    frames_per_buffer=chunk,
                    input_device_index = deviceid,
                    input=True,
                    output=False)

    n = datetime.now().second
    while(kill.is_set() is False):
        f = []

        #for i in range(0, int((frequency / chunk))):
        #    data = stream.read(chunk, False)
        #    f.append(data)
        while (datetime.now().second == n):
            data = stream.read(chunk, False)
            f.append(data)
        frames.append(f)
        n = datetime.now().second

    # Stop and close the stream
    stream.stop_stream()
    stream.close()
    p.terminate()

    print('audio recording: stopped')

def record_timelapse(frames, kill):
    print('timelapse recording: started')
    n = datetime.now().second
    while(kill.is_set() is False):
        # Every second pull the earliest frame of video and write it to a file.
        time.sleep(.5)
        if (datetime.now().second != n and len(frames) > 0 and len(frames[0]) > 0):
            frame = frames[-1][0]
            hms = datetime.now().strftime('%Y-%m-%d-%H_%M_%S')
            cv2.imwrite(f'{timelapse_base_filename}{hms}.jpg', frame)
            n = datetime.now().second
    print('timelapse recording: stopped')

def record_video(frames, kill):
    deviceid = None
    # TODO: scan usb devices for the corrent deviceid

    deviceid = 0
    if (deviceid is None):
        print("video ouldn't get device id")
        kill.set()
        return

    print('video recording: started')
    # setup

    cap = cv2.VideoCapture(deviceid)
    codec = cv2.VideoWriter_fourcc(*video_codec)
    cap.set(cv2.CAP_PROP_FOURCC, codec)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 10)

    n = datetime.now().second
    while(kill.is_set() is False):
        f = []
        while (datetime.now().second == n):
            ret, frame = cap.read()
            f.append(frame)
        frames.append(f)
        n = datetime.now().second
        #print(f"frames: {len(frames)}, f: {len(f)}")

    # Stop and close the stream
    cap.release()
    cv2.destroyAllWindows()
    print('video recording: stopped')

def trigger():
    """Return a time if a recording trigger is detected. For now, this just look for a certain file defined in the 'scremeter' library to appear."""

    trigger_file = scremeter.trigger_file()
    if (os.path.exists(trigger_file)):
        os.remove(trigger_file)
        return datetime.now()

    return None

def write_file(p, trigger_time, audio_frames, video_frames):
    frame_count = len(audio_frames)
    file_time = trigger_time.strftime('%Y-%m-%d-%H_%M_%S')
    print("")
    print(f"write_file: writing {file_time} files")
    audio_buffer_file = audio_base_filename + file_time + '.wav'
    wf = wave.open(audio_buffer_file, 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(sample_format))
    wf.setframerate(frequency)
    for i in range(frame_count):
        wf.writeframes(b''.join(audio_frames[i]))
    wf.close()

    video_buffer_file = video_base_filename + file_time + f'.{video_ext}'
    #print("")
    #print(f"write_file: writing avi file: {video_buffer_file}...")
    codec = cv2.VideoWriter_fourcc(*video_codec)
    output = cv2.VideoWriter(f'{video_buffer_file}', codec, float(fps), (width, height))
    for i in range(frame_count):
        frames = video_frames[i]
        for frame in expand_frames(frames, fps):
            output.write(frame)
    output.release()
    print("")
    print(f"write_file: done writing {file_time} files")

    return

main()
