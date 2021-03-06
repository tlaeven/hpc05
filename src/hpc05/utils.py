#!/usr/bin/env python

import glob
import os.path
import socket
import subprocess
import sys
import time

from .ssh_utils import setup_ssh


def on_hostname(hostname='hpc05'):
    return socket.gethostname() == hostname


def bash(cmd):
    # https://stackoverflow.com/a/25099813
    return f'/bin/bash -i -c "{cmd}"'


def get_local_env(env=None):
    if env is None:
        env = sys.exec_prefix.split('/')[-1]  # conda environment name
    cmd = f'conda list --export -n {env}'.split()
    local_env = subprocess.check_output(cmd).decode('utf-8')
    local_env = [l for l in local_env.split('\n')
                 if not l.startswith('# ') and l != '']
    return local_env


def get_remote_env(env=None):
    with setup_ssh() as ssh:
        cmd = 'conda list --export'
        if env:
            cmd += f" -n {env}"
        stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
        remote_env = [l[:-1].rstrip('\r') for l in stdout.readlines() if not l.startswith('# ')]
    return remote_env


def check_difference_in_envs(local_env_name=None, remote_env_name=None):
    """Only works when setting the Python env in your .bash_rc on the
    remote machine."""
    local_env = get_local_env(local_env_name)
    remote_env = get_remote_env(remote_env_name)
    not_on_remote = set(remote_env) - set(local_env)
    not_on_local = set(local_env) - set(remote_env)

    not_on_remote = [p + ' is installed on remote machine' for p in not_on_remote]
    not_on_local = [p + ' is installed on local machine' for p in not_on_local]

    def diff(first, second):
        second = [package.split('=')[0] for i, package in enumerate(second)]
        return sorted([v for v in first if v.split('=')[0] not in second])

    return {'missing_packages_on_remote': diff(not_on_local, not_on_remote),
            'missing_packages_on_local': diff(not_on_remote, not_on_local),
            'mismatches': sorted(not_on_local + not_on_remote)}
