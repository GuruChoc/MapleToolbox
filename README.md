# Maple Toolbox v0.25 Public Beta

> ## ⚠️ WINDOWS PC ONLY
> **Maple Toolbox is designed for Windows 10/11 PCs.**
>
> It will not run on Android phones/tablets, iPhone/iPad, macOS or Chromebook.

**One Toolbox to run them all.**

Maple Toolbox is a Windows desktop control panel for the MapleStory: Idle RPG utility suite.

## Quick Start

1. Go to **Releases** and download the latest `MapleToolbox_vX.XX.zip` file to your **Windows 10/11 PC**.
2. **Extract the ZIP to a normal folder.**
3. Open the extracted folder.
4. Double-click **`run_MapleToolbox.bat`**.
5. Start with **Directory Health**, then **System Requirements**.

**Do not run Maple Toolbox from inside the ZIP.**

`run_MapleToolbox.bat` is a Windows batch file. Do not associate `.bat` files with WPS Office, Word or another document application.

## Toolbox Workflow

1. Directory Health
2. System Requirements
3. GitHub Update Manager
4. Equipment Bag Screenshot Capture Tool
5. MapleOCR
6. ZIP Inspector
7. BISMIRPG
8. MapleForge

MapleForge remains unreleased and is shown last.

## What's new in v0.25

- **Directory Health** and **System Requirements** automatically collapse to a compact `All OK ✓` row when every check passes. Use **Show Details** to reopen them; any later problem automatically expands the section again.
- **BISMIRPG** is now a working Toolbox module and can generate BIS reports from the current `BIS_stats.zip`.
- BIS handoff validation checks both optimiser preset IDs and OCR Equipped IDs before report generation, catching stale/mismatched `mapleexport.txt` data before the generator runs.
- Hover **tooltips** have been added to the main action buttons, including first-time workflow guidance.
- MapleOCR Dry/Real Run windows show live progress, elapsed time, activity/heartbeat output and a visible close countdown.
- Toolbox run windows are independent of the main Toolbox window and remember their last position/size, including multi-monitor setups.
- Successful Toolbox-launched CMD/PowerShell jobs show a visible countdown before closing; failure windows stay open.
- Toolbox-owned shell output is copied to the Windows clipboard for easier support, Discord and email sharing.
- Brighter Maple Toolbox **taskbar/window icon**. No artwork has been added inside the GUI.
- Windows-only setup guidance and feedback/reporting have been improved.

## BIS Workflow

For a current BIS report, use this order:

`OCR scan → import mapleupload.txt into optimiser → export fresh mapleexport.txt → rebuild/refresh BIS_stats.zip → Generate BIS Report`

Do not use an old `mapleexport.txt` with a new OCR scan. Toolbox validates the handoff and stops the BIS run if required equipment IDs do not match.

## GitHub Update Manager

Maple Toolbox checks public GitHub releases for:

- Maple Toolbox
- Equipment Bag Screenshot Capture Tool
- MapleOCR
- BISMIRPG

Private or unreleased modules such as MapleForge are shown separately and do not count as downloadable releases.

## Requirements

- **Windows 10 or Windows 11 PC**
- Internet connection for GitHub release checks, downloads and prerequisite installation
- Required software is checked by **System Requirements** inside Toolbox

## Safety

- Nothing installs silently.
- Nothing updates silently.
- Prerequisite installs are shown in a visible terminal.
- Errors only are logged under `Errors\`.
- Failed runs stay open so the error can be read.
- Successful run windows show a visible close countdown.

## Feedback

Use **Send Feedback / Report a Problem** inside Toolbox, or email:

`maple@arcadeheaven.com`

If an error log exists, Toolbox tells you which log to attach.
