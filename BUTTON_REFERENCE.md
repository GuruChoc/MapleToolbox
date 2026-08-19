# Maple Toolbox — Button Reference

This guide is organised in the same sections as Maple Toolbox.

## 1. Directory Health

- **Check Directories** — checks the configured project folders and required MapleOCR internals.
- **Change Directories** — opens Operating Folders so project locations can be changed.
- **Create Safe Missing Folders** — creates only folders Toolbox considers safe to create automatically.
- **Open Errors Folder** — opens the Toolbox error-log folder.
- **Re-check** — runs Directory Health again after a change.

Directory Health shows only project-level status. MapleOCR's internal `screenshots`, `Equipped`, `Results`, `Output` and `.venv` folders are still validated silently.

## 2. System Requirements

- Requirement check buttons verify the software needed by Toolbox and its modules.
- Install/repair buttons are shown only where Toolbox can safely perform that action.
- Once everything is green, this section can collapse out of the way.

## 3. GitHub Update Manager

- **Check for Updates** — checks public GitHub releases for Toolbox and supported modules.
- **Refresh Status** — refreshes the displayed installed/update state.
- **Latest Release / Latest Public Release** — opens the current public release.
- **Get Update** — opens/downloads the available module update.
- **GitHub Repository** — opens a project repository when no downloadable public release exists.
- **Open Updates Log** — opens the update-check log.

## 4. Equipment Bag Screenshot Capture Tool

- Launch/open controls start the separate screenshot capture utility.
- Use this before MapleOCR whenever the equipment bag or equipped Basic Preset has changed.

## 5. MapleOCR

- **Dry Run** — scans screenshots and builds review output without committing the normal Real Run workflow.
- **Real Run** — performs the authoritative OCR run and creates the current optimiser/BIS handoff files.
- Output/Results controls open the relevant MapleOCR folders or generated ZIPs.
- Terminal output is kept visible while running and copied to the clipboard when finished.

## 6. BISMIRPG

- **Build BIS + Generate Report** — normal BIS workflow button. Checks freshness, builds `BIS_stats.zip`, verifies it, then generates the report.
- **Generate Existing BIS ZIP** — generates from an already-current `BIS_stats.zip`; stale ZIPs are blocked.
- **Refresh Reports** — rescans the Reports folder and refreshes the report picker.
- **Open Selected Report** — opens the PDF selected in the report picker.
- **Open Lock-Unlock TXT** — opens the matching text companion report.
- **Approve Current BIS** — makes the current BIS state the approved baseline for future changed-cell comparisons.
- **Open BIS Reports** — opens the BISMIRPG Reports folder.

## 7. ZIP Inspector

- **Open Latest ZIP** — opens the newest supported Output ZIP directly for inspection.
- **Choose ZIP...** — lets you select another ZIP.
- ZIP Inspector reads files inside the archive without extracting them.

## 8. MapleForge

- MapleForge controls launch/open the module when installed.
- Until MapleForge has a public downloadable release, Update Manager correctly reports that no public release is available.

## Operating Folders

- **Select Root** — choose the main project parent folder, normally `C:\MapleProjects`.
- **Auto-detect Projects** — scans the selected root and fills the known module folders automatically.
- **Select** — manually choose one module if it lives outside the standard root.
- **Save / Refresh** — saves/refreshes the resulting configuration.
- **Repair / Re-run Setup** — maintenance setup; normally unnecessary once auto-detection is correct.

## Top-bar controls

- **GitHub** — opens the Maple Toolbox GitHub repository/release area.
- **Settings** — opens Toolbox settings, including Operating Folders.
- **About** — shows Toolbox/version information.

## Rule of thumb

For a normal equipment update, the buttons you should actually need are:

`Capture → MapleOCR Dry Run → MapleOCR Real Run → optimiser import/export → Build BIS + Generate Report`
