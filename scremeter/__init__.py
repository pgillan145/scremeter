
import atexit
from dumper import dump
import minorimpact
import minorimpact.config
import os.path

__version__ = '0.0.1'

def archive_dir():
    if ('archive_dir' in config['default']):
        return config['default']['archive_dir']
    return None

def beep():
    if ('beep' in config['default']):
        return config['default']['beep']
    return None

def cache_file():
    if ('cache_file' in config['default']):
        return config['default']['cache_file']
    return None

def writeCache():
    global cache

    if (use_cache is False): return

    c_file = cache_file()
    if (c_file is not None):
        print(f"writing {c_file}")
        #dump(cache)
        minorimpact.write_cache(c_file, cache)

def flagged_dir():
    if ('flagged_dir' in config['default']):
        return config['default']['flagged_dir']
    return None

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
    if ('mp3_dir' in config['default']):
        return config['default']['mp3_dir']
    return None

def mp4_dir():
    if ('mp4_dir' in config['default']):
        return config['default']['mp4_dir']
    return None

def post_buffer():
    return int(config['default']['post_buffer'])

def pre_buffer():
    return int(config['default']['pre_buffer'])

def processed_dir():
    if ('processed_dir' in config['default']):
        return config['default']['processed_dir']
    return None

def raw_dir():
    return config['default']['raw_dir']

def title():
    if ('title' in config['default']):
        return config['default']['title']
    return 'scremeter'

def trigger_file():
    return config['default']['trigger_file']

def turnWriteCacheOff():
    global use_cache
    use_cache = False

def wav_dir():
    if ('wav_dir' not in config['default']):
        raise Exception('wav_dir is not defined')
    wav_dir = config['default']['wav_dir']
    if (os.path.exists(wav_dir) is False):
        raise Exception(f"{wav_dir} doesn't exist")
    return wav_dir

config = minorimpact.config.getConfig(script_name = 'scremeter')
cache = None
use_cache = True

atexit.register(writeCache)

