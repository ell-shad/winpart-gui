# NTFS Partition Manager for Linux

A Linux GUI utility for safely inspecting, mounting, browsing, and copying files from NTFS partitions commonly used by Windows installations.

This tool is especially useful when Linux refuses to mount an NTFS partition because the Windows installation was hibernated or Fast Startup is enabled.

> Developed with assistance from Qwen.

> **Important:** The permanent safe fix for hibernation/Fast Startup mount errors is to boot into the installed operating system and disable Fast Startup or hibernation.

---

## Features

- Detects NTFS-related partitions
- Detects partitions that appear to be BitLocker-encrypted and warns the user
- Safe read-only mounting options
- UDisks read-only mount support
- Optional `ntfsfix -d` repair attempt
- Read/write mounting only with explicit warning
- Dangerous hibernation-removal option separated and clearly warned
- Built-in file browser
- Folder and file icons
- Copy selected files/folders from the mounted partition into Linux
- Dark modern UI
- Optional `ttkbootstrap` theme
- Built-in dark fallback theme if `ttkbootstrap` is not installed
- Information tab explaining safe usage
- Detailed operation log

---

## What this app does NOT do

- It does **not** copy the whole partition into Linux when mounting.
- It does **not** bypass encryption without proper unlocking or recovery keys.
- It does **not** perform full filesystem repair like a native OS repair tool.
- It does **not** make a hibernated partition safe for read/write access.

Mounting is a live view of the partition.

If you want files inside Linux, use the copy button in the Files tab.

---

## Requirements

### Required system packages

On Ubuntu/Debian:

```bash
sudo apt update
sudo apt install python3-tk ntfs-3g util-linux
```

On Fedora:

```bash
sudo dnf install python3-tkinter ntfs-3g util-linux
```

On Arch Linux:

```bash
sudo pacman -S tk ntfs-3g util-linux
```

### Optional Python package

For a more modern dark theme:

```bash
pip install ttkbootstrap
```

The app also works without `ttkbootstrap` using a built-in dark theme.

---

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/ntfs-partition-manager.git
cd ntfs-partition-manager
```

Optionally create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run the app:

```bash
python3 winpart_gui.py
```

---

## Usage

### 1. Select a partition

Open the **Partitions & Fixes** tab.

The app lists partitions that appear to be NTFS or related filesystems.

### 2. Try safe mounting

Recommended order:

1. **UDisks read-only**
2. **Mount RO ntfs-3g**
3. **Mount RO ntfs3**
4. **Auto safe methods**

If the partition is mounted successfully, the Files tab opens automatically.

### 3. Browse files

In the Files tab:

- Expand folders
- Double-click files to open them with the default application
- Select files/folders
- Copy selected items to a Linux folder

### 4. Copy files safely

Use:

```text
Copy selected to Ubuntu folder...
```

This creates real copies inside Linux.

Those copied files can be deleted normally.

### 5. Unmount

Use the **Unmount** button.

After unmounting, the Files tab is cleared if it was showing the unmounted partition.

---

## Mount point behavior

The default mount point is:

```text
~/WindowsPartitionMount
```

This folder is only a view into the mounted partition.

It is not a copy.

After unmounting, the files disappear from that folder.

If the folder contains local files, mounting may temporarily hide them.

Use **Remove empty mount folder** only when the folder is empty and unmounted.

---

## Hibernation errors

Common errors:

```text
Windows is hibernated, refusing to mount.
The NTFS partition is in an unsafe state.
Metadata kept in Windows, refused to mount.
```

This usually means the installed operating system was not fully shut down.

### Safe permanent fix

Boot into the installed operating system.

Disable Fast Startup from the power options.

Then open a terminal or command prompt as administrator and run:

```text
powercfg /h off
shutdown /s /t 0
```

After that, boot into Linux and try mounting again.

---

## Encrypted partitions

If a partition appears to be encrypted with BitLocker, normal NTFS mounting will not work.

You need either:

1. Unlock the drive from the installed operating system, or
2. Use `dislocker` with the recovery key.

Example:

```bash
sudo apt install dislocker

sudo mkdir -p /mnt/dislocker
sudo mkdir -p /mnt/win

sudo dislocker /dev/sdXn -pRECOVERY_KEY -- /mnt/dislocker
sudo mount -o ro /mnt/dislocker/dislocker-file /mnt/win
```

Replace `/dev/sdXn` and `RECOVERY_KEY` with your actual values.

---

## Safety levels

### Safe

- UDisks read-only
- Mount read-only with ntfs-3g
- Mount read-only with ntfs3
- Copy files to Linux

### Medium risk

- `ntfsfix -d`

This can clear some NTFS dirty flags, but it is not a full filesystem repair.

### Dangerous

- `remove_hiberfile`

This removes the hibernation state.

It may cause data loss or filesystem inconsistency.

Use only as a last resort.

---

## Troubleshooting

### The app asks for authentication

Privileged commands use one of:

- `pkexec`
- `sudo`

If authentication is cancelled, the command will fail.

### UDisks mount fails

Try:

- Mount RO ntfs-3g
- Mount RO ntfs3
- Auto safe methods

### Mount still fails

Check the Log tab.

The app tries to explain common errors:

- Hibernation
- Unsafe NTFS state
- Encryption
- Missing NTFS driver
- Permission denied
- Device busy

### Files tab shows old files after unmount

The app now automatically clears the Files tab after unmounting.

If needed, use:

```text
Refresh files
```

or restart the app.

---

## Security notes

- The GUI does not need to be run as root.
- Privileged operations are executed through `pkexec` or `sudo`.
- The app warns before risky operations.
- The hibernation-removal option is explicitly marked dangerous.
- Copying files into Linux is the safest way to preserve data.

For production packaging, consider creating a dedicated Polkit helper instead of invoking raw privileged commands.

---

## Repository structure

```text
ntfs-partition-manager/
├── README.md
├── LICENSE
├── requirements.txt
├── .gitignore
└── winpart_gui.py
```

---

## Trademark notice

Windows and BitLocker are trademarks of Microsoft Corporation.

Use of these names is for descriptive purposes only to indicate compatibility and interoperability.

This project is not affiliated with, endorsed by, or sponsored by Microsoft Corporation.

All trademarks are the property of their respective owners.

---

## Credits

Developed with assistance from Qwen.

---

## License

MIT License.
