#!/usr/bin/env python3
'''
Munin plugin for monitoring number of open file descriptors
'''


# Environment variables that define plugin's behavior
ENV_PROCESS = 'fdcount_target'  # executable name for processes to monitor
ENV_STRICT =  'fdcount_strict'  # if set use full path to executable instead of just the filename


# Output templates
CONFIG = '\n'.join((
    'graph_title Open file descriptors for {target}',
    'graph_vlabel file descriptors',
    'graph_category fs',
))
PROCESS_CONFIG = '\n'.join((
    'pid{pid}.label PID {pid}',
    'pid{pid}.min 0',
))
PROCESS_FETCH = '\n'.join((
    'pid{pid}.value {value}',
))


# Other constants
ENV_STATEFILE = 'MUNIN_STATEFILE'
UNDEFINED = 'U'


import json
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


def count_fds(pid, not_available=UNDEFINED):
    '''Return number of open files for a process with given PID'''
    try:
        return len(os.listdir('/proc/{}/fd/'.format(pid)))
    except Exception:
        return not_available


def munin_state_read():
    '''Read saved state from previous plugin run'''
    try:
        with open(os.getenv(ENV_STATEFILE)) as statefile:
            return json.load(statefile)
    except Exception:
        return {}


def munin_state_write(state):
    '''Save plugin state for the next run'''
    with open(os.getenv(ENV_STATEFILE), 'w') as statefile:
        json.dump(state, statefile)


def munin_print(action=None):
    '''Print information that Munin expects'''
    settings = configure()
    new_pids = set(find_processes(**settings))
    old_pids = set(munin_state_read().get('pids', []))
    pids = new_pids.union(old_pids)
    munin_state_write(dict(pids=list(pids)))

    if action == 'config':
        response = [CONFIG.format(**settings)]
        response += [PROCESS_CONFIG.format(pid=pid) for pid in pids]
    elif action is None:
        response = [PROCESS_FETCH.format(pid=pid, value=count_fds(pid)) for pid in new_pids]
        response += [PROCESS_FETCH.format(pid=pid, value=UNDEFINED) for pid in old_pids.difference(new_pids)]
    else:
        raise ValueError('invalid action: {}'.format(action))
    print('\n'.join(response))


def main():
    if len(sys.argv) == 1:
        munin_print()
    elif sys.argv[1] == 'config':
        munin_print('config')
    else:
        raise ValueError('invalid arguments: {}'.format(' '.join(sys.argv[1:])))


if __name__ == '__main__':
    main()
