# RailRoad

Python Based C2 for Linux Red Team Competitiong

# Give permissions

chmod +x dist/client

# Updating Instructions

- When updating client, use [ pyinstaller --onefile systemd-slve.py ] to download file as binary to be ran on ansible

- use chmod + systemd-slve if testing locally

- cd to the file in /dist and upload it to drive.

- go to drive and download file and upload it to github and edit the release

# Run ansible on server and then run server.py

- ansible-playbook -i "[client IP,]" playbook.yml -u [user] -b -k -K
- python server.py
