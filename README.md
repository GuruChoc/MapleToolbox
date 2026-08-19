# Maple Toolbox v0.26 Public Beta

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
6. BISMIRPG
7. ZIP Inspector
8. MapleForge

MapleForge remains unreleased and is shown last.

## What's new in v0.26

- **BISMIRPG v1.0.0 integration** now uses the generator's supported command-line interface instead of patching source code.
- **Generated BIS Report picker** shows the latest report automatically and lets you select older reports.
- Direct **Open Selected Report** and **Open Lock-Unlock TXT** actions.
- The latest selected BIS report is visually highlighted.
- **Approved BIS baseline** status is shown in the GUI.
- **Approve Current BIS** saves the current BIS state as the approved comparison baseline.
- Future reports use that approved state for the BIS report's light-grey changed-cell shading.
- If no baseline exists, Toolbox warns that changed-cell shading cannot appear.
- Same-run baseline comparisons are detected before launch and handled cleanly.
- BISMIRPG report generation no longer opens Explorer automatically.
- Successful BISMIRPG CMD windows close correctly after the visible countdown.
- Shell output is copied to the Windows clipboard.
- BISMIRPG local release detection now recognises semantic versions such as **v1.0.0**.
- Development Toolbox builds are distinguished from the latest public release in the Update Manager.
- BISMIRPG is now workflow section **6** and ZIP Inspector is **7**.
- Main window title now uses the central app version, preventing stale version text.
- Directory Health and System Requirements retain the v0.25 auto-collapse behaviour once fully green.
- Hover help, independent run windows, multi-monitor position memory and visible close countdowns remain enabled.

## BIS Workflow

Use this order for a current BIS report:

`OCR scan → import mapleupload.txt into optimiser → export fresh mapleexport.txt → rebuild/refresh BIS_stats.zip → Generate BIS Report`

Do not use an old `mapleexport.txt` with a new OCR scan.

For change shading:

`Generate BIS Report → Approve Current BIS → future BIS reports compare against that approved baseline`

Generating a report does **not** silently replace the approved baseline.

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
- Toolbox-owned shell results are copied to the clipboard.

## Feedback

Use **Send Feedback / Report a Problem** inside Toolbox, or email:

`maple@arcadeheaven.com`

If an error log exists, Toolbox tells you which log to attach.
