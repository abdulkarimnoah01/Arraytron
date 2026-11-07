# Installing Arraytron Stamp (v0.9.3)

Arraytron Stamp is a node for placing instances by hand in Solaris. It works with **Houdini 22.0** (built and tested on 22.0.368) and with **Houdini 20.5 and 21** (built on 20.5.445, tested on 20.5.445 and 21.0.440) on Windows. The package carries two builds of the same node, one for Houdini 22 and one for Houdini 20.5 / 21; the installer picks the right one for each Houdini it finds. No administrator rights are needed and nothing is copied into Houdini's own folders. It is independent of Arraytron (its own folder and package file); the two only share the Asset Library folder (`Documents\Arraytron\library`).

## Install

1. Unpack **Arraytron_Stamp_v0.9.3_Release.rar** anywhere (WinRAR or 7-Zip).
2. Double-click **Install Arraytron Stamp.cmd**.
3. Restart Houdini. In a Solaris (LOPs) network press Tab and type **Arraytron Stamp**. Wire the ground and the props into the first input, select the node and press Enter in the viewport.

The installer finds every Houdini 20.5, 21 and 22 you have used (their preferences folders in Documents) and sets the node up for all of them at once. If it says it found none, start Houdini once so that it creates its preferences folder, then run it again. The demo is installed too: `%LOCALAPPDATA%\ArraytronStamp\versions\0.9.3\demos\Arraytron_Stamp_v0.9.3_demo.hip` in Houdini 22, `...\demos_h205\Arraytron_Stamp_v0.9.3_H205_demo.hip` in Houdini 20.5 / 21. The documentation is `docs\ARRAYTRON_STAMP.md` next to them.

**Houdini 20.5 / 21: restart Houdini after updating or removing.**

## Update

Either click **Check for Updates** on the **Arraytron Stamp** shelf in Houdini (it reads `version.json` from the update source, the GitHub release `stamp-latest` of `abdulkarimnoah01/Arraytron`; it shows what is new and installs it if you say yes; the download is checked against its SHA-256 before anything is unpacked; nothing is checked in the background; another source can be set with the `ARRAYTRON_STAMP_UPDATE_SOURCE` variable or `arraytron_stamp_update.json` in the Houdini preferences folder), or unpack the new download and double-click **Install Arraytron Stamp.cmd** again. Both keep the version before as a rollback. Scenes keep the node type they were built with (`arraytron::stamp::<version>`).

## Remove

Double-click **Uninstall Arraytron Stamp.cmd**, then restart Houdini. Your scenes are not touched.

## Where things go

| What | Where |
| --- | --- |
| The plugin (HDAs, demos, docs) | `%LOCALAPPDATA%\ArraytronStamp\versions\<version>\` (this one and the one before); `h22\otls` and `h205\otls` hold the two HDAs |
| The hook into Houdini | `Documents\houdini22.0\packages\arraytron_stamp.json` (and the same for `houdini21.0`, `houdini20.5`) |
| What was installed | `%LOCALAPPDATA%\ArraytronStamp\installed.json` |

Options: `Install Arraytron Stamp.cmd -Houdini 22.0` (only that version; also 21.0 or 20.5), `-CreatePrefs -Houdini 20.5`, `-Uninstall`, `-Quiet`.

## Whoever supplies Arraytron Stamp: build and publish a release

`python tools/make_stamp_release.py` builds `release/stamp/` (the Release RAR, `Arraytron-Stamp-<version>.zip` and `version.json`, `SHA256SUMS.txt`) and proves the package: the installer is run in a sandbox with clean Houdinis and the update path end to end (`tests/validate_stamp_installer.py`). `python tools/publish_stamp_release.py` publishes it to the public GitHub repo as the release `stamp-v<version>` and as the rolling release `stamp-latest` that installed copies read; both are created as "not the latest release", so Arraytron's own updater (which reads the repo's latest release) is not affected. The version is `STAMP_VERSION` in `tools/build_stamp_light.py`; the notes are the section of `CHANGELOG_STAMP.md`.
