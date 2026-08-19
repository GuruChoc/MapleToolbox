# Maple Toolbox — Folder Layout

Maple Toolbox uses one common Windows project root:

```text
C:\MapleProjects\
    MapleToolbox\
    MapleOCR\
    EquipmentBagCaptureTool\
    BISMIRPG\
    MapleForge\
```

MapleOCR's working folders live inside its own project folder:

```text
C:\MapleProjects\MapleOCR\
    screenshots\
        Equipped\
    Results\
    Output\
    .venv\
```

The configured **Operating Folder** is the authority. Toolbox and its modules derive paths from the configured project folder or from the script's own location rather than from a hard-coded drive path.

There is no separate operational MapleOCR root outside `C:\MapleProjects`.

## Auto-detection

Select `C:\MapleProjects` as **Projects Root** and click **Auto-detect Projects**. The standard subfolders are detected and populated automatically.

Manual per-project **Select** buttons remain available for custom layouts.
