"""
Script to cull idle IPython parallel engines.

Any engines that have not run any tasks for the specified period will be
shutdown.
"""
# Copyright (c) Min RK and modified by Bas Nijholt
# Distributed under the terms of the Modified BSD License

from collections import defaultdict
from datetime import datetime
import sys

from tornado import ioloop, options
from tornado.log import app_log
from ipyparallel import Client

start_time = datetime.utcnow()

class EngineCuller(object):
    """An object for culling idle IPython parallel engines."""

    def __init__(self, client, timeout=300):
        """Initialize culler, with current time."""
        self.client = client
        self.timeout = timeout
        self.activity = defaultdict(lambda: {
            'last_active': datetime.utcnow(),
            'completed': 0})
        self.max_active = 0
        self.active_now = 0
        self.num_times_zero = 0

    def update_state(self):
        """Check engine status and cull any engines that have become idle.

        Call this method periodically to cull engines.
        """
        app_log.debug("Updating state")
        status = self.client.queue_status()
        for eid in self.client.ids:
            state = status[eid]
            engine_activity = self.activity[eid]
            if state['queue'] \
               or state['tasks'] \
               or state['completed'] != engine_activity['completed']:
                # tasks pending or history changed, update timestamp
                engine_activity['last_active'] = datetime.utcnow()
            engine_activity['completed'] = state['completed']
        self.cull_idle()

        # remember how many engines were active last check and now
        last_active = self.active_now
        self.active_now = len(self.activity)
        running_time = (datetime.utcnow() - start_time).total_seconds()

        # save how many times zero engines have been active
        if (self.active_now == 0 and last_active == 0 and running_time > 3600):
            self.num_times_zero += 1

        # stop ipcontroller, ipengines, and this script when
        # both last check and now there are zero active engines and
        # the number of engines is going down after having reached a maximum.
        # or when there have always only been zero engines, this only starts
        # counting after 1hr.
        if (len(self.activity) == 0 and
            self.active_now < self.max_active and
            last_active == self.active_now or
            self.num_times_zero > 10):
            self.client.shutdown(hub=True)
            sys.exit()
        self.max_active = max(self.max_active, self.active_now)


    def cull_idle(self):
        """Cull any engines that have become idle for too long."""
        idle_ids = []
        for eid, state in self.activity.items():
            idle = (datetime.utcnow() - state['last_active']).total_seconds()
            app_log.debug("%s idle since %s", eid, state['last_active'])
            if idle > self.timeout:
                idle_ids.append(eid)
        if idle_ids:
            app_log.info("Culling engines %s", idle_ids)
            self.client.shutdown(
                [eid for eid in idle_ids if eid in self.client.ids])
            for eid in idle_ids:
                self.activity.pop(eid)


def main():
    """Start IO loop that checks every 60 seconds whether the engines are
    running, if inactive for two hours they are culled."""
    options.define('timeout', default=7200,
                   help="""Time (in seconds) after which to consider an engine
                   idle that should be shutdown.""")
    options.define('interval', default=60,
                   help="""Interval (in seconds) at which state should be checked
                   and culling performed.""")
    options.parse_command_line()
    loop = ioloop.IOLoop.current()
    culler = EngineCuller(Client(profile='pbs'), options.options.timeout)

    ioloop.PeriodicCallback(
        culler.update_state, options.options.interval * 1000).start()
    loop.start()

if __name__ == '__main__':
    print('running')
    main()