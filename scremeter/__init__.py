
import atexit
from dumper import dump
import minorimpact
import minorimpact.config
import noisereduce as nr
import numpy
import os.path
import re
from scipy.io import wavfile
import scipy.signal

__version__ = '0.0.1'

def audio_device():
    if ('audio_device' in config['default']):
        return config['default']['audio_device']
    return None

def audio_dir(raw = False, archive = False, processed = False):
    dir = f'{scremeter_dir(archive = archive)}/audio'
    if (raw is True): dir = dir + '-raw'
    elif (processed is True): dir = dir + '-processed'


    if (os.path.exists(dir) is False):
        os.makedirs(dir, exist_ok = True)
    return dir

def beep():
    if ('beep' in config['default']):
        return config['default']['beep']
    return None

def cache_file():
    if ('cache_file' in config['default']):
        return config['default']['cache_file']
    return None

def flagged_dir(archive = False):
    dir = f'{scremeter_dir(archive = archive)}/flagged'
    if (os.path.exists(dir) is False):
        os.makedirs(dir, exist_ok = True)
    return dir

def get_cache(clear_cache = False):
    global cache

    if (clear_cache is True):
        cache = { 'files': {} }
        minorimpact.write_cache(cache_file(), cache)
        return cache

    if (cache is None):
        cache = minorimpact.read_cache(cache_file())

    if (cache is None):
        cache = { 'files': {} }
    #print(cache_file())
    #from dumper import dump
    #dump(cache)
    if ('files' not in cache):
        cache['files'] = {}

    return cache

def mp3_dir():
    return f'{audio_dir()}-mp3'

def mp4_dir():
    return f'{audio_dir()}-mp4'

def parse_filename(file):
    # TODO: Grab extension and extra stuff after the datetime so we have enough info to turn this back into the original filename.
    file_info = {}
    basename = os.path.basename(file)
        #'^(?P<series>.+) (?P<issue>-\d+[^ ]*) \[(?P<year>\d\d\d\d)(?P<month>\d\d)(?P<day>\d\d)\]\.(?P<extension>cb[rz])$',
        #m = re.search(f, description)
        #if (m is not None):
        #    g = m.groupdict()
        #    if 'description' in g: description = g['description']

    m = re.search("^(.+)-(\\d\\d\\d\\d)-(\\d\\d)-(\\d\\d)-(\\d\\d)_(\\d\\d)_(\\d\\d)[^.]*\\.([^.]+)$", basename)
    if (m is not None):
        header = m[1]
        year = m[2]
        month = m[3]
        day = m[4]
        hour = m[5]
        minute = m[6]
        second = m[7]
        ext = m[8]
        file_info['header'] = header
        file_info['year'] = year
        file_info['month'] = month
        file_info['day'] = day
        file_info['hour'] = hour
        file_info['minute'] = minute
        file_info['second'] = second
        file_info['ext'] = ext
        file_info['date'] = f'{year}-{month}-{day}'

    if ('header' not in file_info):
        raise Exception(f"invalid filename: {basename}")
    return file_info

def post_buffer():
    return int(config['default']['post_buffer'])

def pre_buffer():
    return int(config['default']['pre_buffer'])

def process_audio_file(file, noise_seconds = 3, prop_decrease = .85, stationary = True, peak_start_override = 0, peak_end_override = 0, crop_start = 0, crop_end = 0, verbose = False, trim_to_peaks = False):
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
    if (trim_to_peaks is True):
        reduced_noise = reduced_noise[peak_trim_start:peak_trim_end]
    reduced_seconds = reduced_noise.shape[0]/rate

    output_length = 60
    print(f"  raw:        0.00s - {raw_length:5.2f}s: {raw_length:5.2f}s")
    print(f"  trimmed:   {trim_start/rate:5.2f}s (0+{crop_start}) - {trim_end/rate:5.2f}s ({raw_length:5.2f}-{crop_end}): {data.shape[0]/rate:5.2f}s")
    if (len(peaks) > 0 and trim_to_peaks is True):
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

    if (verbose):
        print(output)

    #processed_file = processed_filename(file)
    #wavfile.write(processed_file, rate, reduced_noise)

    tmp_file = tmp_dir() + '/' + unparse_file_info(parse_filename(file), extra = 'temp')
    print(f"  writing {tmp_file}")
    wavfile.write(tmp_file, rate, reduced_noise)
    return tmp_file

def scremeter_dir(archive = False):
    dir = None
    if (archive is True):
        if ('archive_dir' in config['default']):
            dir = config['default']['archive_dir']
    else:
        if ('scremeter_dir' in config['default']):
           dir = config['default']['scremeter_dir']

    if (dir is None):
        raise Exception('scremeter_dir is not defined')
    if (os.path.exists(dir) is False):
        raise Exception(f'{dir} does not exist')

    return dir

def timelapse_dir(raw = False, archive = False):
    dir = f'{scremeter_dir(archive = archive)}/timelapse'
    if (raw is True): dir = dir + '-raw'

    if (os.path.exists(dir) is False):
        os.makedirs(dir, exist_ok = True)
    return dir

def title():
    if ('title' in config['default']):
        return config['default']['title']
    return 'scremeter'

def tmp_dir():
    dir = None
    if ('tmp_dir' in config['default']):
       dir = config['default']['tmp_dir']

    if (dir is None):
        raise Exception('tmp_dir is not defined')

    if (os.path.exists(dir) is False):
        os.makedirs(dir, exist_ok = True)
    return dir

def trigger_file():
    return config['default']['trigger_file']

def turnWriteCacheOff():
    global use_cache
    use_cache = False

def unparse_file_info(file_info, ext = None, extra = None):
    new_filename = f"{file_info['header']}-{file_info['year']}-{file_info['month']}-{file_info['day']}-{file_info['hour']}_{file_info['minute']}_{file_info['second']}"
    if (extra is not None):
        new_filename = f"{new_filename}-{extra}"
    if (ext is None and 'ext' in file_info):
        ext = file_info['ext']
    elif (ext is None):
        raise Exception('file extension is not defined')
    new_filename = f"{new_filename}.{ext}"

    return new_filename

def video_device():
    if ('video_device' in config['default']):
        return config['default']['video_device']
    return None

def video_dir(raw = False, archive = False):
    dir = f'{scremeter_dir(archive = archive)}/video'
    if (raw is True): dir = dir + '-raw'

    if (os.path.exists(dir) is False):
        os.makedirs(dir, exist_ok = True)
    return dir

def writeCache():
    global cache

    if (use_cache is False): return

    c_file = cache_file()
    if (c_file is not None):
        print(f"writing {c_file}")
        #dump(cache)
        minorimpact.write_cache(c_file, cache)

def wav_dir():
    dir = f'{audio_dir()}'
    if (os.path.exists(dir) is False):
        os.makedirs(dir, exist_ok = True)
    return dir

config = minorimpact.config.getConfig(script_name = 'scremeter')
cache = None
use_cache = True

atexit.register(writeCache)

