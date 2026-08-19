# Maple Toolbox — Workflow Guide

## First-time setup

- Download the latest Maple Toolbox release ZIP.
- Extract it to `C:\MapleProjects\MapleToolbox` or another normal Windows folder.
- Run `run_MapleToolbox.bat`.
- Open **Directory Health → Change Directories**.
- Set **Projects Root** to the parent folder containing the Maple projects, normally `C:\MapleProjects`.
- Click **Auto-detect Projects**.
- Toolbox looks for `MapleOCR`, `EquipmentBagCaptureTool`, `BISMIRPG` and `MapleForge`.
- Found folders are filled in automatically.
- Use an individual **Select** button only for a project stored somewhere non-standard.
- Click **Save / Refresh**.
- Run **Check Directories**.
- Use **Create Safe Missing Folders** only if Toolbox reports safe folders that can be created.
- Check **System Requirements**.
- Install any missing requirements using the Toolbox buttons.
- Run **Check for Updates** in GitHub Update Manager.

## Normal equipment / BIS workflow

- Capture the equipment bag screenshots with **Equipment Bag Screenshot Capture Tool**.
- Capture the currently equipped Basic Preset items into the `screenshots\Equipped` set.
- In **MapleOCR**, run **Dry Run** first.
- Check the Dry Run result for obvious OCR/import problems.
- If the Dry Run is clean, run **Real Run**.
- The Real Run creates the current `mapleupload.txt`, lock files, review files and pending BIS marker.
- Open the MapleStory Idle RPG optimiser.
- Import the fresh `mapleupload.txt`.
- Let the optimiser update the equipment state/presets.
- Export a fresh `mapleexport.txt` back into the configured MapleOCR operating folder.
- Return to Maple Toolbox.
- Click **Build BIS + Generate Report**.
- Toolbox checks that the optimiser export belongs to the current OCR workflow.
- Toolbox builds a fresh `BIS_stats.zip`.
- Toolbox verifies the ZIP is current.
- BISMIRPG generates the PDF and Lock/Unlock text report.
- Review the generated BIS report.
- Use **Approve Current BIS** only when you want that report to become the comparison baseline.
- Future BIS reports compare against the approved baseline and shade changed cells.

## Important rules

- Do not use an old `mapleexport.txt` after a new OCR Real Run.
- Do not manually reuse an old `BIS_stats.zip` for a newer OCR run.
- Dry Run is for checking; Real Run is the authoritative OCR/import run.
- `mapleupload.txt` goes **into** the optimiser.
- `mapleexport.txt` comes **out of** the optimiser.
- **Build BIS + Generate Report** is the normal BIS button.
- **Generate Existing BIS ZIP** is only for an already-current BIS ZIP.
- Approving a BIS report changes the future comparison baseline; generating a report alone does not.
- If a shell/terminal run fails, leave the window open and use the copied clipboard output/error log for troubleshooting.
