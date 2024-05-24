#!/usr/bin/env python3

from datetime import datetime,timedelta
import pyaudio
import os
import re
import scremeter
import sys
import time
from threading import Thread, Event
import wave

chunk = 256  # How large each chunk of data we record will be. Larger values seem to come out crackly.
sample_format = pyaudio.paInt24  # 24 bits per sample
device_match_string = 'C-Media USB'
channels = 1
frequency = 44100  # Record at 44100 samples per second
pre_buffer = 10
post_buffer = 5
filename = "scremus"
stop_recording = False

def main():
    p = pyaudio.PyAudio()  # Create an interface to PortAudio

    frames = []
    recording_thread = None
    event = Event()
    try:
        recording_thread = Thread(target=record, name='recording', args=[p, frames, event])
        recording_thread.start()
    except:
        sys.exit('Error starting recording thread')

    buffer_frames = []
    trigger_time = None
    while (event.is_set() is False):
        try:
            # just run once a second
            time.sleep(1)

            t = trigger()
            if (t is not None):
                print("\ntrigger detected")
                trigger_time = t

            if (trigger_time is None):
                while (len(frames) > pre_buffer):
                    del frames[0]

            print(f"\rbuffer length: {len(frames)}s", end='')
            if (trigger_time is not None and trigger_time + timedelta(seconds=post_buffer) < datetime.now()):
                if (len(frames) > 0):
                    buffer_file = filename + trigger_time.strftime('%Y-%m-%d-%H_%M_%S') + '.wav'
                    print(f"\nwriting wav file: {buffer_file}")
                    wf = wave.open(buffer_file, 'wb')
                    wf.setnchannels(channels)
                    wf.setsampwidth(p.get_sample_size(sample_format))
                    wf.setframerate(frequency)
                    for i in range(0, len(frames)):
                        wf.writeframes(b''.join(frames[i]))
                    wf.close()
                    trigger_time = None

        except KeyboardInterrupt:
            break
    print("")
    event.set()


def record(p, frames, event):
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    deviceid = None
    print("scanning usb devices")
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            name = p.get_device_info_by_host_api_device_index(0, i).get('name')
            print("Input Device id ", i, " - ", name)
            if (re.match(device_match_string, name) and deviceid is None):
                deviceid = i
                print("Using ", name)

    if (deviceid is None):
        print("Couldn't get device id")
        event.set()
        return

    print('Recording: started')
    stream = p.open(format=sample_format,
                    channels=channels,
                    rate=frequency,
                    frames_per_buffer=chunk,
                    input_device_index = deviceid,
                    input=True)

    while(event.is_set() is False):
        f = []
        for i in range(0, int((frequency / chunk))):
            data = stream.read(chunk, False)
            f.append(data)
        frames.append(f)

    # Stop and close the stream 
    stream.stop_stream()
    stream.close()
    p.terminate()

    print('Recording: stopped')

def trigger():
    """Return a time if a recording trigger is detected. For now, this just look for a certain file defined in the 'scremeter' library to appear."""

    trigger_file = scremeter.trigger_file()
    if (os.path.exists(trigger_file)):
        os.remove(trigger_file)
        return datetime.now()

    return None

main()
