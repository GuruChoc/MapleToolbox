# Maple Toolbox v0.28 Public Beta

> ## ⚠️ WINDOWS 10/11 PC ONLY
> Maple Toolbox is designed for Windows PCs. It does not run on Android, iPhone/iPad, macOS or Chromebook.

**One Toolbox to run them all.**

Maple Toolbox is a Windows desktop control panel for the MapleStory: Idle RPG utility suite.

## Quick Start

1. Download the latest `MapleToolbox_vX.XX.zip` from **Releases**.
2. Extract it to a normal Windows folder. The recommended location is `C:\MapleProjects\MapleToolbox`.
3. Double-click `run_MapleToolbox.bat`.
4. Open **Directory Health → Change Directories**.
5. Set **Projects Root** to `C:\MapleProjects` and click **Auto-detect Projects**.
6. Check **Directory Health** and **System Requirements**.
7. Run **Check for Updates**.

Do not run Maple Toolbox from inside the ZIP.

## Recommended Folder Layout

```text
C:\MapleProjects\
    MapleToolbox\
    MapleOCR\
    EquipmentBagCaptureTool\
    BISMIRPG\
    MapleForge\
```

The configured Operating Folder is authoritative. Toolbox no longer requires a separate `C:\MapleOCR` working root.

## Normal BIS Workflow

1. Capture equipment screenshots.
2. Run **MapleOCR Dry Run**.
3. If clean, run **MapleOCR Real Run**.
4. Import the fresh `mapleupload.txt` into the optimiser.
5. Export a fresh `mapleexport.txt` back to the configured MapleOCR folder.
6. Click **Build BIS + Generate Report**.
7. Review the PDF and Lock/Unlock report.
8. Use **Approve Current BIS** only when you want that state to become the comparison baseline.

`mapleupload.txt` goes **into** the optimiser. `mapleexport.txt` comes **out** of the optimiser.

## What’s New in v0.28

- Unified project layout under `C:\MapleProjects`.
- Projects Root selector and **Auto-detect Projects** setup.
- Cleaner project-level Directory Health display.
- UTF-8 UI cleanup.
- Location-independent MapleOCR/BIS workflow.
- CUDA/GPU repair and verification for the MapleOCR environment.
- **Build BIS + Generate Report** one-click BIS workflow.
- Stale optimiser export and stale `BIS_stats.zip` protection.
- BIS builder path self-repair/verification before generation.
- Approved BIS baseline comparison and changed-cell shading retained.
- Added `WORKFLOW.md`, `BUTTON_REFERENCE.md` and `FOLDER_LAYOUT.md` documentation.

## Toolbox Sections

1. Directory Health
2. System Requirements
3. GitHub Update Manager
4. Equipment Bag Screenshot Capture Tool
5. MapleOCR
6. BISMIRPG
7. ZIP Inspector
8. MapleForge

MapleForge is currently unreleased and correctly reports no public downloadable release.

## Documentation

- `WORKFLOW.md` — step-by-step operating guide.
- `BUTTON_REFERENCE.md` — button descriptions grouped by Toolbox section.
- `FOLDER_LAYOUT.md` — recommended folder structure and auto-detection setup.

## Safety

- Nothing installs silently.
- Nothing updates silently.
- Failed shell runs stay open so the error can be read.
- Successful runs use visible countdowns where applicable.
- Toolbox-owned shell results are copied to the clipboard.
- Errors are logged under `Errors\`.

## Feedback

Use **Send Feedback / Report a Problem** inside Toolbox, or email:

`maple@arcadeheaven.com`
