'''
Munin plugin for monitoring number of open file descriptors
'''


# Environment variables that define plugin's behavior
ENV_PROCESS = 'fdcount_target'  # executable name for processes to monitor
ENV_STRICT =  'fdcount_strict'  # if set use full path to executable instead of just the filename


# Output templates
CONFIG = '\n'.join((
    'graph_title Number of open files for {target}',
    'graph_vlabel files',
    'graph_category fs',
))
PROCESS_CONFIG = '\n'.join((
    'pid{pid}.label {pid}',
    'pid{pid}.min 0',
))
PROCESS_FETCH = '\n'.join((
    'pid{pid}.value {value}',
))


import os
import sys
from glob import glob


def configure():
    '''Read plugin configuration from environment variables'''
    return dict(
        target = os.getenv(ENV_PROCESS, 'bash'),
        strict = bool(os.getenv(ENV_STRICT)),
    )


def find_processes(target, strict=False):
    '''
    Yield PIDs of processes that match given executable name.
    Use full executable's path if strict is True.
    '''
    for filename in glob('/proc/*/exename'):
        with open(filename) as exename:
            executable = exename.read().strip()
        if not strict:
            executable = os.path.basename(executable)
        if executable == target:
            yield int(os.path.basename(os.path.dirname(filename)))


def count_fds(pid):
    '''Return number of open files for a process with given PID'''
    return len(os.listdir('/proc/{}/fd/'.format(pid)))


def munin_config():
    '''Output configuration values for munin plugin'''
    settings = configure()
    pids = find_processes(**settings)
    header = [CONFIG.format(**settings)]
    body = [PROCESS_CONFIG.format(pid=pid) for pid in pids]
    print('\n'.join(header + body))


def munin_fetch():
    '''Output data for munin-fetch'''
    settings = configure()
    pids = find_processes(**settings)
    body = (PROCESS_FETCH.format(pid=pid, value=count_fds(pid)) for pid in pids)
    print('\n'.join(body))


def main():
    if len(sys.argv) == 1:
        munin_fetch()
    elif sys.argv[1] == 'config':
        munin_config()
    else:
        raise ValueError('invalid arguments: {}'.format(' '.join(sys.argv[1:])))


if __name__ == '__main__':
    main()
