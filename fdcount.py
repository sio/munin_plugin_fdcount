#!/usr/bin/env python3
'''
Munin plugin for monitoring number of open file descriptors

Processes with identical command lines are assumed to belong to the same daemon
after restart. If two processes running at the same time have the same command
line only one will be monitored (undefined behavior).

To track processes by PID instead of command line set 'fdcount_track_pids'
environment variable.
'''


import json
import os
import re
import sys
from collections import namedtuple
from glob import iglob
from hashlib import md5


# Environment variables that define plugin's behavior
ENV_PROCESS = 'fdcount_target'  # executable name for processes to monitor
ENV_STRICT =  'fdcount_strict'  # if set use full path to executable instead of just the filename
ENV_TRACKPIDS = 'fdcount_track_pids'  # track processes by pid instead of cmdline


# Output templates
CONFIG = '\n'.join((
    'graph_title Open file descriptors for {target}',
    'graph_vlabel file descriptors',
    'graph_category fs',
))
PROCESS_CONFIG = '\n'.join((
    'fd_{label}.label {command}',
    'fd_{label}.min 0',
))
PROCESS_FETCH = '\n'.join((
    'fd_{label}.value {value}',
))


# Other constants
ENV_STATEFILE = 'MUNIN_STATEFILE'  # defined by Munin daemon
UNDEFINED = 'U'


if not os.getenv(ENV_STATEFILE):
    raise ValueError('environment variable not defined: {}'.format(ENV_STATEFILE))


Process = namedtuple('Process', 'pid command')


def configure():
    '''Read plugin configuration from environment variables'''
    return dict(
        target = os.getenv(ENV_PROCESS, 'bash'),
        strict = bool(os.getenv(ENV_STRICT)),
        track_pids = bool(os.getenv(ENV_TRACKPIDS)),
    )


def find_processes(target, strict=False, **_):
    '''
    Yield PIDs of processes that match given executable name.
    Use full executable's path if strict is True.
    '''
    for filename in iglob('/proc/*/exe'):
        try:
            pid = int(os.path.basename(os.path.dirname(filename)))
        except ValueError:
            continue
        if is_relevant(pid, target, strict):
            yield pid


def is_relevant(pid, target, strict=False) -> bool:
    '''
    Return True if pid is relevant to provided target
    '''
    filename = '/proc/{}/exe'.format(pid)
    try:
        executable = os.readlink(filename)
    except OSError:
        return False
    if not strict:
        executable = os.path.basename(executable)
    return executable == target


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
        json.dump(state, statefile, indent=2, sort_keys=True, ensure_ascii=False)


def label(text):
    '''Convert any text into Munin-friendly data label'''
    return md5(text.encode()).hexdigest().upper()


def command_line(pid):
    '''Read commandline for provided PID'''
    filename = '/proc/{}/cmdline'.format(pid)
    try:
        with open(filename) as f:
            raw = f.read()
    except OSError:
        return 'Unknown command; pid {}'.format(pid)
    raw = raw.replace('\0', ' ').strip()
    return re.sub(r'\s+', ' ', raw)


def munin_print(action=None):
    '''Print information that Munin expects'''
    settings = configure()
    old_labels = munin_state_read().get('labels', {})

    new_labels = {}
    for pid in find_processes(**settings):
        command = command_line(pid)
        if settings['track_pids']:
            command = '{}: {}'.format(pid, command)
        new_labels[label(command)] = Process(pid, command)

    labels = old_labels.copy()
    labels.update(new_labels)
    munin_state_write(dict(labels=labels))

    if action == 'config':
        response = [CONFIG.format(**settings)]
        response += [PROCESS_CONFIG.format(label=label, pid=proc[0], command=proc[1])
                     for label, proc in labels.items()]
    elif action is None:
        response = [PROCESS_FETCH.format(label=label, pid=proc[0], command=proc[1], value=count_fds(proc[0]))
                    for label, proc in new_labels.items()]
        response += [PROCESS_FETCH.format(label=label, pid=proc[0], command=proc[1], value=UNDEFINED)
                     for label, proc in old_labels.items()
                     if label not in new_labels]
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
