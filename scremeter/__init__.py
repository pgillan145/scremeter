
import minorimpact.config

__VERSION__ = '0.0.1'

config = minorimpact.config.getConfig(script_name = 'scremeter')

def mp3_dir():
    if ('mp3_dir' in config['default']):
        return config['default']['mp3_dir']
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

def trigger_file():
    return config['default']['trigger_file']


