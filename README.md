# NAS Setup

This repository documents the setup of my Raspberry Pi NAS running DietPi, including Plex media server, OpenVPN for secure connectivity, Samba file sharing, HFS+ support for external drives, and an automated script for downloading and classifying YouTube videos.

## 📦 Project Structure

nas-setup/
├── README.md
├── plex_youtube_classifier/
│   ├── plex_youtube_classifier.py
│   └── requirements.txt
├── vpn/
│   ├── ovpn-files/
│   └── setup.md
├── plex/
│   ├── library-structure.md
│   └── metadata-guides.md
└── scripts/
    └── maintenance.sh

## 📺 Plex
- Installed via DietPi’s dietpi-software tool.
- Libraries organized into Movies, TV Shows, YouTube et al, Music Videos, Operas & Concerts.
- Metadata handled via naming conventions and optional local NFOs.

## 🔗 OpenVPN
- Configured with .ovpn files (excluded from version control).
- Used to securely route NAS traffic through a VPN provider.

## 🗄️ Samba Server
- Shares media directories on the local network for easy access from other devices.

## 💾 HFS+ Tools
- Installed `hfsprogs` to mount external HFS+ drives with read-write access.
- Drives checked with `fsck.hfsplus` before mounting.

## 🎥 YouTube Classifier Script
- The script in `plex_youtube_classifier/` downloads videos, embeds metadata, classifies them with OpenAI, and moves them to the appropriate Plex library folder.
- Supports automatic naming and library placement.

## 🚀 Next Steps
- Automate Plex library scans after downloads.
- Add systemd services for automated maintenance.
- Integrate a Telegram bot for remote control.

## ⚠️ Security Note
- VPN credentials and .ovpn files are **not** committed to this repository.

## 📄 License
This repository documents a personal setup. Use at your own risk.
