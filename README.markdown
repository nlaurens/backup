A simple backup script that keeps daily, weekly, monthly and yearly backups.

Initial code and idea from Sean Hammond (this is a fork from his code):
https://github.com/seanh/backup

Info
----
Makes a snapshot backup of SRC inside DEST. Running the same backup command
repeatedly creates incremental, snapshot backups of SRC inside DEST:

	DEST/
		latest.snapshot/  - Link to the latest snapshot taken;
        yearly/..         - Snapshots beginning of each year;
        monthly/..        - Snapshots Jan - Dec;
        weekly/..         - Snapshots last 5 weeks (usually from Monday);
        daily/..          - Snapshots Tuesday till Sunday

Each snapshot directory contains a complete copy of the SRC directory (but
hardlinks are used between snapshots to save bandwidth and storage space).
However the backup _does not cross filesystem boundaries_ within SRC, for each
mount-point encountered in SRC there will be just an empty directory in DEST.
If symlinks are encountered in SRC, the symlinks themselves are copied to the
snapshot, not the files or directories that the symlinks refer to.

To restore selected files just copy them back from a snapshot directory to the
live system. To restore an entire snapshot just copy the entire snapshot
directory back to the live system.

Old snapshots (or selected files within old snapshots) can be deleted without
affecting newer snapshots.

If a backup command is interrupted the transferred files will be stored in an
`incomplete.snapshot` directory in DEST, and the backup can be resumed by
running the same command again.

Usage
-----

	backup [options] SRC DEST

Either SRC or DEST (but not both) can be a remote directory, e.g.:
`you@yourdomain.org:/path/to/snapshots`.

Options:

	--debug        Performs a trial-run; nothing is synced.
	--no-compress  Does not compress files during transfer
	--no-fuzzy     Do not look for missing basis files on DEST
	--no-progress  Does not show progress during transfer
	--exclude      Exclude file matching <PATTERN> (see rsync man)
