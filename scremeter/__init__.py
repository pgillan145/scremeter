
import atexit
from dumper import dump
import minorimpact
import minorimpact.config
import os.path
import re

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
    dir = f'{scremeter_dir(archive=archive)}/flagged'
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
    return audio_dir()

def mp4_dir():
    return f'{audio_dir()}-mp4'

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

def post_buffer():
    return int(config['default']['post_buffer'])

def pre_buffer():
    return int(config['default']['pre_buffer'])

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

def trigger_file():
    return config['default']['trigger_file']

def turnWriteCacheOff():
    global use_cache
    use_cache = False

def writeCache():
    global cache

    if (use_cache is False): return

    c_file = cache_file()
    if (c_file is not None):
        print(f"writing {c_file}")
        #dump(cache)
        minorimpact.write_cache(c_file, cache)

def wav_dir():
    dir = f'{audio_dir()}-wav'
    if (os.path.exists(dir) is False):
        os.makedirs(dir, exist_ok = True)
    return dir

def video_device():
    if ('video_device' in config['default']):
        return config['default']['video_device']
    return None

config = minorimpact.config.getConfig(script_name = 'scremeter')
cache = None
use_cache = True

atexit.register(writeCache)

