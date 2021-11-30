#
# core.py
#
# Copyright (C) 2014-2016 Omar Alvarez <osurfer3@hotmail.com>
# Copyright (C) 2011 Jamie Lennox <jamielennox@gmail.com>
#
# Basic plugin template created by:
# Copyright (C) 2008 Martijn Voncken <mvoncken@gmail.com>
# Copyright (C) 2007-2009 Andrew Resch <andrewresch@gmail.com>
# Copyright (C) 2009 Damien Churchill <damoxc@gmail.com>
#
# Deluge is free software.
#
# You may redistribute it and/or modify it under the terms of the
# GNU General Public License, as published by the Free Software
# Foundation; either version 3 of the License, or (at your option)
# any later version.
#
# deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with deluge.    If not, write to:
#   The Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor
#   Boston, MA  02110-1301, USA.
#
#    In addition, as a special exception, the copyright holders give
#    permission to link the code of portions of this program with the OpenSSL
#    library.
#    You must obey the GNU General Public License in all respects for all of
#    the code used other than OpenSSL. If you modify file(s) with this
#    exception, you may extend this exception to your version of the file(s),
#    but you are not obligated to do so. If you do not wish to do so, delete
#    this exception statement from your version. If you delete this exception
#    statement from all source files in the program, then also delete it here.
#

import logging
from deluge.plugins.pluginbase import CorePluginBase
import deluge.component as component
import deluge.configmanager
from deluge.core.rpcserver import export

from twisted.internet import reactor
from twisted.internet.task import LoopingCall, deferLater
import os
import subprocess

import time

log = logging.getLogger(__name__)

DEFAULT_PREFS = {
    'max_seeds': 0,
    'filter': 'func_ratio',
    'filter2': 'func_added',
    'count_exempt': False,
    'remove_data': False,
    'trackers': [],
    'labels': [],
    'min': 0.0,
    'min2': 0.0,
    'hdd_space': -1.0,
    'use_quota_for_free_space': False,
    'interval': 0.5,  # hours
    'sel_func': 'and',
    'force_reannounce_before_remove': False,
    'reannounce_max_wait_sec': 20,
    'skip_removal_on_reannounce_failure': True,
    'remove': True,
    'enabled': False,
    'tracker_rules': {},
    'label_rules': {},
    'rule_1_enabled': True,
    'rule_2_enabled': True
}


def _get_ratio((i, t)):
    return t.get_ratio()


def _age_in_days((i, t)):
    now = time.time()
    #added = t.get_status(['time_added'])['time_added']  # this used in deluge v2 version
    added = t.time_added  # TODO likley need to change for Deluge v2
    log.debug("_age_in_days(): Now = {}, added = {}".format(now, added))
    age_in_days = round((now - added) / 86400.0, 4)
    log.debug("_age_in_days(): Returning age: [{} days]".format(age_in_days))
    return age_in_days


def _get_free_space_quota():
    q = '/usr/bin/quota'
    # if not os.path.isfile(q):
        # return default_method(path)

    quota_proc = subprocess.Popen([q, '--no-wrap', '--hide-device'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    q_out, q_err = quota_proc.communicate()
    if quota_proc.returncode != 0 or len(q_err) > 0:
        raise Exception('quota exited w/ {}'.format(quota_proc.returncode))

    q_out = q_out.split('\n')[2].split()  # take 3rd line and split it up
    free = (int(q_out[2]) - int(q_out[0])) / 976563  # hard_limit - used; note we convert KiB to GB
    return free  # free quota, in GB


def _get_seed_time((i, t)):
    st = round(t.get_status(['seeding_time'])['seeding_time'] / 3600.0, 4)
    log.debug("AutoRemovePlus._get_seed_time(): %s hours", st)
    return st


# def _date_added((i, t)):
    # return (time.time() - t.time_added) / 86400.0


# Add key label also to get_remove_rules():141
filter_funcs = {
    'func_ratio': _get_ratio,
    #'func_added': lambda (i, t): round((time.time() - t.time_added) / 86400.0, 4),
    'func_added': _age_in_days,
    'func_seed_time': _get_seed_time,
    'func_seeders': lambda (i, t): t.get_status(['total_seeds'])['total_seeds']
}


sel_funcs = {
    'and': lambda (a, b): a and b,
    'or': lambda (a, b): a or b,
    'xor': lambda (a, b): (a and not b) or (not a and b)
}


class Core(CorePluginBase):

    def enable(self):
        log.debug("AutoRemovePlus: Enabled")

        self.config = deluge.configmanager.ConfigManager(
            "autoremoveplus.conf",
            DEFAULT_PREFS
        )
        self.torrent_states = deluge.configmanager.ConfigManager(
            "autoremoveplusstates.conf",
            {}
        )

        # Safe after loading to have a default configuration if no gtkui
        self.config.save()
        self.torrent_states.save()

        # it appears that if the plugin is enabled on boot then it is called
        # before the torrents are properly loaded and so periodic_scan() receives an
        # empty list. So we must listen to SessionStarted for when deluge boots
        #  but we still have apply_now so that if the plugin is enabled
        # mid-program periodic_scan() is still run
        self.looping_call = LoopingCall(self.periodic_scan)
        deferLater(reactor, 5, self.start_looping)
        self.torrentmanager = component.get("TorrentManager")

    def disable(self):
        if self.looping_call.running:
            self.looping_call.stop()

    def update(self):
        pass

    def start_looping(self):
        log.info('check interval loop starting')
        self.looping_call.start(self.config['interval'] * 3600.0)

    @export
    def set_config(self, config):
        """Sets the config dictionary"""
        for key in config.keys():
            self.config[key] = config[key]
        self.config.save()
        if self.looping_call.running:
            self.looping_call.stop()
        self.looping_call.start(self.config['interval'] * 3600.0)

    @export
    def get_config(self):
        """Returns the config dictionary"""
        return self.config.config

    @export
    def get_remove_rules(self):
        return {
            'func_ratio': 'Ratio',
            'func_added': 'Age in days',
            'func_seed_time': 'Seed Time (h)',
            'func_seeders': 'Seeders'
        }

    @export
    def get_ignore(self, torrent_ids):
        if not hasattr(torrent_ids, '__iter__'):
            torrent_ids = [torrent_ids]

        return [self.torrent_states.config.get(t, False) for t in torrent_ids]

    @export
    def set_ignore(self, torrent_ids, ignore=True):
        log.debug(
            "AutoRemovePlus: Setting torrents %s to ignore=%s"
            % (torrent_ids, ignore)
        )

        if not hasattr(torrent_ids, '__iter__'):
            torrent_ids = [torrent_ids]

        for t in torrent_ids:
            self.torrent_states[t] = ignore

        self.torrent_states.save()

    def check_min_space(self):
        min_hdd_space = self.config['hdd_space']  # in GB
        # if deactivated delete torrents regardless of remaining free drive space:
        if min_hdd_space < 0.0:
            return False

        resolve_common_way = True
        if self.config['use_quota_for_free_space']:
            try:
                real_free_space = _get_free_space_quota()
                resolve_common_way = False
            except Exception as e:
                log.warning("check_min_space(): _get_free_space_quota() threw up: %s", e)

        if resolve_common_way:
            real_free_space = component.get("Core").get_free_space() / 1073741824.0  # bytes -> GB

        log.debug("Free Space in GB (real/min.required): %s/%s" % (real_free_space, min_hdd_space))

        # if hdd space below minimum delete torrents
        if real_free_space > min_hdd_space:
            return True  # there is enough space, do not delete torrents
        else:
            return False

    def pause_torrent(self, torrent):
        try:
            torrent.pause()
            log.debug("pause_torrent(): successfully paused torrent: [%s]", torrent.torrent_id)
        except Exception as e:
            log.warning(
                    "AutoRemovePlus: Problems pausing torrent: [%s]: %s", torrent.torrent_id, e
            )

    # note: great hint on libtorrent force_announce inner-workings is at https://forum.deluge-torrent.org/viewtopic.php?p=230210#p230210
    def reannounce(self, tid, t, force_announce):
        # note the first two announce_* arg values are the defaults from https://libtorrent.org/reference-Torrent_Handle.html#force_reannounce()
        announce_seconds = 0    # how many seconds from now to issue the tracker announces; default = 0
        announce_trkr_idx = -1  # specifies which tracker to re-announce. If set to -1 (which is the default), all trackers are re-announced.
        announce_flags = 1  # TODO: announce_flags type changes from libtorrent RC_1_2 so likley/maybe have to change for Deluge 2!:

        t_end = time.time() + self.config['reannounce_max_wait_sec']
        while time.time() < t_end:
            if force_announce:
                try:
                    # if t.force_reannounce(): return True  # this one uses Deluge torrent function, as opposed to directly calling libtorrent's
                    t.handle.force_reannounce(announce_seconds, announce_trkr_idx, announce_flags)  # note libtorrent's force_reannounce() returntype is void
                    log.debug("AutoRemovePlus.reannounce(): forced reannounce OK for torrent [%s]", tid)
                    return True
                except Exception as e:
                    log.warning(
                            "AutoRemovePlus.reannounce(): Problems calling libtorrent.torr.force_reannounce(): %s", e
                    )
            else:
                if t.force_reannounce():
                    log.debug("AutoRemovePlus.reannounce(): non-forced reannounce OK for torrent [%s]", tid)
                    return True
                else:
                    log.warning(
                        "AutoRemovePlus.reannounce(): non-forced reannouncing failed for torrent: [%s]", tid)
            time.sleep(5)  # TODO: make this configureable?

        log.error("AutoRemovePlus.reannounce(): Problems reannouncing for torrent: [%s]; giving up", tid)
        return False


    def remove_torrent(self, tid, torrent, remove_data):
        # extra logging for debugging premature torrent removal issues: {
        # seed_time = torrent.get_status(['seeding_time'])['seeding_time']
        # seed_time_h = _get_seed_time((tid, torrent))
        # log.error("remove_torrent(): pre-announce seed_time: [%s], h: [%s]", seed_time, seed_time_h)
        # }

        force_announce = self.config['force_reannounce_before_remove']

        # update trackers to make sure the latest upload amount & time are reflected
        # prior to nuking torrent.
        #
        # TODO: maybe reannounce should also be called on torrent completion event, not only prior to removal?
        if not self.reannounce(tid, torrent, force_announce):
            if self.config['skip_removal_on_reannounce_failure']:
                log.warning(
                    "AutoRemovePlus.remove_torrent(): reannounce (force = %s) failed for torrent: [%s]; skipping remove", force_announce, tid)
                return False
            else:
                log.warning(
                    "AutoRemovePlus.remove_torrent(): reannounce (force = %s) failed for torrent: [%s]; removing regardless...", force_announce, tid)

        try:
            seed_time = torrent.get_status(['seeding_time'])['seeding_time']
            seed_time_h = _get_seed_time((tid, torrent))
            total_time_uploaded = torrent.get_status(['total_uploaded'])['total_uploaded']  # in deluge's internal status, it's under status.all_time_upload
            total_time_downloaded = torrent.get_status(['all_time_download'])['all_time_download']
            age_sec = time.time() - torrent.time_added  # TODO likley need to change for Deluge v2, ie unsure if t.time_added property is still accessible like that
            # note these 2 total_time_* are in bytes, not time values:
            total_time_uploaded = torrent.get_status(['total_uploaded'])['total_uploaded']  # in deluge's internal status, it's under status.all_time_upload
            total_time_downloaded = torrent.get_status(['all_time_download'])['all_time_download']

            log.error("remove_torrent(): removing torrent [%s]... remove_data = %s, seed_time: [%s], h: [%s], ratio: %s, age_sec: [%s], total_time_up: [%s], total_time_down: [%s]",
                      tid, remove_data, seed_time, seed_time_h, torrent.get_ratio(), age_sec, total_time_uploaded, total_time_downloaded)

            self.torrentmanager.remove(tid, remove_data=remove_data)

            log.debug("remove_torrent(): successfully removed torrent: [%s]", tid)
        except Exception as e:
            log.warning(
                    "remove_torrent(): AutoRemovePlus: Problems removing torrent [%s]: %s", tid, e
            )
        try:
            del self.torrent_states.config[tid]
        except KeyError:
            log.warning("remove_torrent(): AutoRemovePlus: no saved state for torrent {}".format(tid))
            return True
        except Exception as e:
            log.warning("remove_torrent(): AutoRemovePlus: Error deleting state for torrent {}: {}".format(tid, e))
            return False
        else:
            return True

    def get_torrent_rules(self, id, torrent, tracker_rules, label_rules):

        total_rules = []

        try:
            for t in torrent.trackers:
                for name, rules in tracker_rules.iteritems():
                    log.debug("get_torrent_rules(): processing name = {}, rules = {}, url = {}, find = {} ".format(name, rules, t['url'], t['url'].find(name.lower())))
                    if (t['url'].find(name.lower()) != -1):
                        for rule in rules:
                            total_rules.append(rule)
        except Exception as e:
            log.warning("get_torrent_rules(): Exception with getting tracker rules for [{}]: {}".format(id, e))
            return total_rules

        if label_rules:
            try:
                # get label string
                label_str = component.get(
                    "CorePlugin.LabelPlus"
                ).get_torrent_label_name(id)

                # if torrent has labels check them
                labels = [label_str] if len(label_str) > 0 else []

                for label in labels:
                    if label in label_rules:
                        for rule in label_rules[label]:
                            total_rules.append(rule)
            except Exception as e:
                log.warning("get_torrent_rules(): Cannot obtain torrent label for [{}]: {}".format(id, e))

        log.debug("get_torrent_rules(): returning rules for [{}]: {}".format(id, total_rules))
        return total_rules

    # we don't use args or kwargs it just allows callbacks to happen cleanly
    def periodic_scan(self, *args, **kwargs):
        log.debug("AutoRemovePlus: beginning periodic_scan() exec")

        if not self.config['enabled']:
            log.debug("AutoRemovePlus: plugin not enabled, skipping periodic_scan()")
            return

        max_seeds = int(self.config['max_seeds'])
        count_exempt = self.config['count_exempt']
        remove_data = self.config['remove_data']
        exemp_trackers = self.config['trackers']
        exemp_labels = self.config['labels']
        min_val = float(self.config['min'])
        min_val2 = float(self.config['min2'])
        remove = self.config['remove']
        tracker_rules = self.config['tracker_rules']
        rule_1_chk = self.config['rule_1_enabled']
        rule_2_chk = self.config['rule_2_enabled']
        labels_enabled = False

        if 'LabelPlus' in component.get(
            "CorePluginManager"
        ).get_enabled_plugins():
            labels_enabled = True
            label_rules = self.config['label_rules']
        else:
            log.warning("WARNING! LabelPlus plugin not active")
            log.warning("No labels will be checked for exemptions!")
            label_rules = []

        # Negative max means unlimited seeds are allowed, so don't do anything
        if max_seeds < 0:
            return

        torrent_ids = self.torrentmanager.get_torrent_list()

        log.debug("Number of torrents: {0}".format(len(torrent_ids)))

        # If there are less torrents present than we allow
        # then there can be nothing to do
        if len(torrent_ids) <= max_seeds:
            return

        torrents = []
        ignored_torrents = []

        # relevant torrents to us exist and are finished
        for i in torrent_ids:
            t = self.torrentmanager.torrents.get(i, None)

            # TODO: deluge2.0 version of this script doesn't have this try-ex-else block:
            # likely because the end of this function is way more convoluted/feature-packed than in this - delugev1 - ver?
            try:
                finished = t.is_finished
            except Exception as e:
                log.warning("periodic_scan(): Cannot obtain torrent 'is_finished' attribute: {}".format(e))
                continue
            else:
                if not finished:
                    continue

            try:
                ignored = self.torrent_states[i]
            except KeyError as e:
                ignored = False

            ex_torrent = False
            trackers = t.trackers

            # check if trackers in exempted tracker list
            for tracker, ex_tracker in (
                (t, ex_t) for t in trackers for ex_t in exemp_trackers
            ):
                if (tracker['url'].find(ex_tracker.lower()) != -1):
                    log.debug("periodic_scan(): Found exempted tracker: [%s]" % (ex_tracker))
                    ex_torrent = True

            # check if labels in exempted label list if Label plugin is enabled
            if labels_enabled:
                try:
                    # get label string
                    label_str = component.get(
                        "CorePlugin.LabelPlus"
                    ).get_torrent_label_name(i)

                    # if torrent has labels check them
                    labels = [label_str] if len(label_str) > 0 else []

                    for label, ex_label in (
                        (l, ex_l) for l in labels for ex_l in exemp_labels
                    ):
                        if(label.find(ex_label.lower()) != -1):
                            log.debug("periodic_scan(): Found exempted label: [%s]" % (ex_label))
                            ex_torrent = True
                except Exception as e:
                    log.warning("periodic_scan(): problem obtaining torrent label: {}".format(e))

            # if torrent tracker or label in exemption list, or torrent ignored
            # insert in the ignored torrents list
            (ignored_torrents if (ignored or ex_torrent) else torrents).append((i, t))  # (id, torrent) tuple

        log.debug("periodic_scan(): Number of finished torrents: {0}".format(len(torrents)))
        log.debug("periodic_scan(): Number of ignored torrents: {0}".format(len(ignored_torrents)))

        # now that we have trimmed active torrents
        # check again to make sure we still need to proceed
        if len(torrents) + (len(ignored_torrents) if count_exempt else 0) <= max_seeds:
            return

        # if we are counting ignored torrents towards our maximum
        # then these have to come off the top of our allowance
        if count_exempt:
            max_seeds -= len(ignored_torrents)
            if max_seeds < 0:
                max_seeds = 0

        # Alternate sort by primary and secondary criteria
        # TODO: why is this sorting done?? we use tuple of (bool, bool) as sorting key??? why???
        #       think it's so a-la lower-ratio (or whatever else metric) torrents are
        #       processed, hence removed, sooner?
        torrents.sort(
            key=lambda x: (
                filter_funcs.get(
                    self.config['filter'],
                    _get_ratio
                )(x),
                filter_funcs.get(
                    self.config['filter2'],
                    _get_ratio
                )(x)
            ),
            reverse=False
        )

        changed = False

        # remove or pause these torrents
        for i, t in reversed(torrents[max_seeds:]):

            # check if free disk space below minimum
            if self.check_min_space():
                break  # break the loop, we have enough space

            log.debug(
                "periodic_scan(): AutoRemovePlus: starting remove-torrent rule checking for [%s], %s"
                % (i, t.get_status(['name'])['name'])
            )

            specific_rules = self.get_torrent_rules(i, t, tracker_rules, label_rules)

            remove_cond = False  # if torrent should be removed or paused

            # If there are specific rules, ignore general remove rules
            if specific_rules:
                # Sort rules according to logical operators; AND is evaluated first
                #
                # TODO: why do we want AND to be first? doesn't it make at least
                # very first AND pointless, as first rule's condition is dropped/ignored
                # anyways; think AND should be evaluated LAST instead!
                # oooor: don't sort at all, and leave the order as they're defined in conf/UI.
                # note it'd be perfect to disable the logic gate on first item as it's
                # ignored anyway;
                #
                # TODO2: also issues how specific_rules gets compiled: we process all tracker
                #        rules, followed by label rules. as it stands it's difficult to keep the
                #        _true_ rule order!
                specific_rules.sort(key=lambda rule: rule[0])

                first_spec_rule = specific_rules[0]
                remove_cond = filter_funcs.get(first_spec_rule[1])((i, t)) >= float(first_spec_rule[2])
                log.error("1. spec rule %s: gate [%s]. fun: [%s], val: %s; remove_cond: %s",
                          i, first_spec_rule[0], first_spec_rule[1], float(first_spec_rule[2]), remove_cond)

                for rule_seq, rule in enumerate(specific_rules[1:], start=2):
                    check_filter = filter_funcs.get(rule[1])((i, t)) >= float(rule[2])
                    logic_gate = sel_funcs.get(rule[0])  # and/or/xor func
                    # TODO: should we be calling logic_gate() with single, tuple arg?
                    remove_cond = logic_gate((
                        check_filter,
                        remove_cond
                    ))
                    log.error("%s. spec rule: gate [%s]. fun: [%s], val: %s; rule result: %s, aggregate remove_cond: %s",
                              rule_seq, rule[0], rule[1], float(rule[2]), check_filter, remove_cond)
            else:  # process general/global rules
                filter1_res = filter_funcs.get(self.config['filter'], _get_ratio)((i, t))
                filter2_res = filter_funcs.get(self.config['filter2'], _get_ratio)((i, t))

                # Get result of first condition test
                filter_1 = filter1_res >= min_val
                # Get result of second condition test
                filter_2 = filter2_res >= min_val2

                log.error("[{}] filter1 enabled: [{}], filter2 enabled: [{}]".format(i, rule_1_chk, rule_2_chk))
                log.error("filter1: {} >= {} = {}; filter2: {} >= {} = {}".format(filter1_res, min_val, filter_1, filter2_res, min_val2, filter_2))

                if rule_1_chk and rule_2_chk:
                    logic_gate = self.config['sel_func']
                    log.debug("both filters enabled, using logic gate: [{}]".format(logic_gate))

                    # If both rules active use custom logical function
                    logic_gate = sel_funcs.get(logic_gate)  # and/or/xor func

                    remove_cond = logic_gate((
                        filter_1,
                        filter_2
                    ))
                elif rule_1_chk and not rule_2_chk:
                    # Evaluate only first rule, since the other is not active
                    remove_cond = filter_1
                elif not rule_1_chk and rule_2_chk:
                    # Evaluate only second rule, since the other is not active
                    remove_cond = filter_2

            # If logical functions are satisfied, remove or pause torrent:
            if remove_cond:
                if not remove:
                    self.pause_torrent(t)
                else:
                    if self.remove_torrent(i, t, remove_data):
                        changed = True

        # If a torrent exemption state has been removed save changes
        if changed:
            self.torrent_states.save()
