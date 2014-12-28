#!/bin/bash
python backup.py /home/niels/src/ /home/niels/dst/ --exclude tmp
python backup.py /home/niels/src/ user@host:/mnt/backups/dst/ --exclude tmp

python backup.py /home/niels/src2/ /home/niels/dst2/ --exclude tmp
python backup.py /home/niels/src2/ user@host:/mnt/backups/dst2/ --exclude tmp
