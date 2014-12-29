#!/usr/bin/env python
"""
Usage:
  $ python backup.py SRC DST
  SRC and DST can be ssh or local paths

  Make sure the DST path already exists, the dir
  will not be created by the script. This is to
  prevent mistakes.


TODO NIELS:
    Send an email upon error in the log file
    write a simple BACKUP.log to the DST with date of backup.
"""
from datetime import date
import sys
import os
import logging
import subprocess
import glob


def is_remote(arg):
    """Return True if the given SRC or DEST argument specifies a remote path,
    False if it specifies a local path.

    """
    # If it has a : before the first / then it's a remote path.
    return ':' in arg.split('/')[0]


def parse_rsync_arg(arg):
    """Parse the given SRC or DEST argument and return tuple containing its
    user, host and path parts:

    user    :    The username in a remote path spec.
                'seanh' in 'seanh@mydomain.org:/path/to/backups'.
                None if arg is a local path or a remote path without a
                username.
    host    :    The hostname in a remote path spec.
                'mydomain.org' in 'seanh@mydomain.org:/path/to/backups'.
                None if arg is a local path.
    path    :    The path in a local or remote path spec.
                '/path/to/backups' in the remote path 'seanh@mydomain.org:/path/to/backups'.
                '/media/BACKUP' in the local path '/media/BACKUP'.

    """
    if is_remote(arg):
        before_first_colon, after_first_colon = arg.split(':', 1)
        if '@' in before_first_colon:
            user = before_first_colon.split('@')[0]
        else:
            user = None
        host = before_first_colon.split('@')[-1]
        path = after_first_colon
    else:
        user = None
        host = None
        path = os.path.abspath(os.path.expanduser(arg.strip()))
    return user, host, path


def construct_rsync_options(options):
    # Construct the list of options to be passed to rsync.
    rsync_options = ['--archive',  # Copy recursively and preserve times, permissions, symlinks, etc.
                     '--partial',
                     '--partial-dir=partially_transferred_files',
                     # Keep partially transferred files if the transfer is interrupted
                     '--one-file-system',  # Don't cross filesystem boundaries
                     '--delete',  # Delete extraneous files from dest dirs
                     '--delete-excluded',  # Also delete excluded files from dest dirs
                     '--itemize-changes',  # Output a change-summary for all updates
                     '--link-dest=../latest.snapshot',  # Make hard-links to the previous snapshot, if any
                     '--human-readable',  # Output numbers in a human-readable format
                     # '-F', # Enable per-directory .rsync-filter files.
                     ]
    if options.compress:
        rsync_options.append('--compress')  # Compress files during transfer
    if options.fuzzy:
        rsync_options.append('--fuzzy')  # Look for basis files for any destination files that are missing
    if options.progress:
        rsync_options.append('--progress')  # Print progress while transferring files
    if os.path.isfile(os.path.expanduser("~/.backup/excludes")):
        rsync_options.append('--exclude-from=$HOME/.backup/excludes')  # Read exclude patterns from file
    if options.debug:
        rsync_options.append('--dry-run')
    if options.exclude is not None:
        for pattern in options.exclude:
            rsync_options.append("--exclude '%s'" % pattern)

    return rsync_options


def construct_rsync_cmd(rsync_options, host, user, snapshots_root):
    rsync_cmd = "rsync %s '%s' " % (' '.join(rsync_options), SRC)
    if host is not None:
        if user is not None:
            rsync_cmd += "%s@" % user
        rsync_cmd += "%s:" % host
    rsync_cmd += "%s/incomplete.snapshot" % snapshots_root

    return rsync_cmd


# Runs a shell command <cmd> and returns the result (not output!)
# set ssh to True if it should be send via SSH to the host
def run_cmd(cmd, ssh=False):
    if ssh:
        server = ''
        if user is not None:
            server += "%s@" % user
        server += '%s ' % host
        cmd = 'ssh ' + server + '"' + cmd + '"'

    logging.info('run_cmd: ' + cmd)
    print 'running cmd'
    print cmd
    try:
        output = subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError, error:
        logging.critical('run_cmd FAILED: ' + cmd)
        logging.critical('run_cmd result: ' + str(error))
        sys.exit('command failed with: ' + str(error))

    return output


def create_dir_structure(snapshots_root):
    dirs = [snapshots_root + '/daily', snapshots_root + '/weekly', snapshots_root + '/monthly',
            snapshots_root + '/yearly']

    for path in dirs:
        if not dir_exists(path):
            dir_create(path)


# Checks if a directory <dir> exists on the host
# Returns a list of all the matches.
# Allows patterns
def dir_exists(path):
    if host is None:
        return glob.glob(path)
    else:
        split = path.split('/')
        cmd = 'find ' + '/'.join(split[:-1]) + ' -name \"' + split[-1] + '"'
        output = run_cmd(cmd, ssh=True).strip()
        if output == '':
            return []
        else:
            return output.split('\n')


# Creates a directory <path> on local and ssh host
def dir_create(path):
    if host is None:
        logging.info('dir_create: ' + path)
        os.makedirs(path)
    else:
        run_cmd('mkdir ' + path, ssh=True)


# Decide where to place the backup (daily, weekly, monthly, etc)
# Yearly: 2014-<date>
# Monthly: 1-<date> .. 12-<date>
# Weekly: 1-<date> .. 5-<date> (we take: week# % 5)
def get_target(snapshots_root):
    # today = date(2014,9,9) # Used for testing the rotation
    today = date.today()
    isotoday = today.isocalendar()
    strtoday = '%d%02d%02d' % (today.year, today.month, today.day)

    if today != date.today():
        print '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
        print 'WARNING DEBUGGING DATE STILL ON!!!'
        print '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
        logging.warning('DEBUGGING DATE STILL ON!')

    previous_yearly = dir_exists(snapshots_root + '/yearly/%d-*.snapshot' % isotoday[0])
    if not previous_yearly:
        return 'yearly/%d-%s' % (isotoday[0], strtoday)

    previous_monthly = dir_exists(snapshots_root + '/monthly/%02d-*.snapshot' % today.month)
    if not previous_monthly:
        return 'monthly/%02d-%s' % (today.month, strtoday)
    else:
        if len(previous_monthly) > 1:
            logging.critical('More monthly snapshots than expected (1 for every month)')
            sys.exit('More monthly snapshots than expected (1 for every month)')
        if previous_monthly[0].split('/')[-1][3:7] != str(isotoday[0]):
            return 'monthly/%02d-%s' % (today.month, strtoday)

    previous_weekly = dir_exists(snapshots_root + '/weekly/%d-*.snapshot' % (isotoday[1] % 5 + 1))
    if not previous_weekly:
        return 'weekly/%d-%s' % (isotoday[1] % 5 + 1, strtoday)
    else:
        if len(previous_weekly) > 1:
            logging.critical('More weekly snapshots than expected')
            sys.exit('More monthly snapshots than expected')
        if int(previous_weekly[0].split('/')[-1][6:8]) != today.month:
            return 'weekly/%d-%s' % (isotoday[1] % 5 + 1, strtoday)

    return 'daily/%d-%s' % (isotoday[2], strtoday)


def construct_mv_cmd(snapshots_root, target):
    mv_cmd = ''

    # remove the old source using wildcards
    target_remove = target[:-8] + '*'

    mv_cmd += 'rm -rf %s/%s.snapshot &&' % (snapshots_root, target_remove)
    mv_cmd += "mv %s/incomplete.snapshot %s/%s.snapshot " % (snapshots_root, snapshots_root, target)
    mv_cmd += "&& rm -f %s/latest.snapshot " % snapshots_root
    mv_cmd += "&& ln -s %s.snapshot %s/latest.snapshot" % (target, snapshots_root)

    return mv_cmd


if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] SRC DEST")
    parser.add_option('-d', '--debug', '-n', '--dry-run', dest='debug', action='store_true', default=False,
                      help='Perform a trial-run with no changes made (pass the --dry-run option to rsync)')
    parser.add_option('--no-compress', dest='compress', action='store_false', default=True,
                      help='Do not compress file data during transfer (do not pass the --compress argument to rsync)')
    parser.add_option('--no-fuzzy', dest='fuzzy', action='store_false', default=True,
                      help='Do not look for basis files for destination files that are missing '
                           '(do not pass the --fuzzy argument to rsync)')
    parser.add_option('--no-progress', dest='progress', action='store_false', default=True,
                      help='Do not show progress during transfer (do not pass the --progress argument to rsync)')
    parser.add_option('--exclude', type='string', dest='exclude', metavar="PATTERN", action='append',
                      help="Exclude files matching PATTERN, e.g. --exclude '.git/*' "
                           "(see the --exclude option in `man rsync`)")
    (options, args) = parser.parse_args()

    if len(args) != 2:
        sys.exit(parser.get_usage())
    SRC = args[0]
    DEST = args[1]

    if options.debug:
        logging.basicConfig(filename='backup.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(message)s',
                            datefmt='%Y/%m/%d %H:%M:%S')
    else:
        logging.basicConfig(filename='backup.log', level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s',
                            datefmt='%Y/%m/%d %H:%M:%S')
    logging.info('** Started run **')
    maxWeeklySnapshots = 5

    # Make sure SRC ends with / because this affects how rsync behaves.
    if not SRC.endswith(os.sep):
        SRC += os.sep

    user, host, snapshots_root = parse_rsync_arg(DEST)
    create_dir_structure(snapshots_root)
    rsync_options = construct_rsync_options(options)
    backup_target = get_target(snapshots_root)
    rsync_cmd = construct_rsync_cmd(rsync_options, host, user, snapshots_root)
    mv_cmd = construct_mv_cmd(snapshots_root, backup_target)

    logging.info("src: %s" % SRC)
    logging.info("dest: %s" % DEST)
    logging.info("host: %s" % host)
    logging.info("user: %s" % user)
    logging.info("target: %s" % backup_target)

    run_cmd(rsync_cmd)
    if host is not None:
        run_cmd(mv_cmd, ssh=True)
    else:
        run_cmd(mv_cmd)
    logging.info('** Finished run **')
