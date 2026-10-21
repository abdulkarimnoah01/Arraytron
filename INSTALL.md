# Installing Arraytron (v1.21.0)

Arraytron v1.21.0 works with **Houdini 22.0** (built and tested on 22.0.368) and with **Houdini 20.5 and 21** (built on 20.5.445, tested on 20.5.445 and 21.0.440) on Windows. The release carries two builds of the same node, one for Houdini 22 and one for Houdini 20.5 / 21 (Houdini 22 has a Point Instancer LOP that the older versions lack, so the older build uses their Instancer LOP; the output is the same, see `docs/PORT_HOUDINI_205.md`). The installer picks the right one for each Houdini it finds. No administrator rights are needed and nothing is copied into Houdini's own folders.

## Artists: install

1. Unpack **Arraytron_v1.21.0_Release.rar** anywhere (WinRAR or 7-Zip).
2. Double-click **Install Arraytron.cmd**.
3. Restart Houdini. In a Solaris (LOPs) network press Tab and type **Arraytron**.

The installer finds every Houdini 20.5, 21 and 22 you have used (their preferences folders in Documents) and sets Arraytron up for all of them at once, each with its own build. If it says it found none, start Houdini once so that it creates its preferences folder, then run it again.

The demos are installed too: open **`%LOCALAPPDATA%\Arraytron\versions\1.21.0\demos\Arraytron_v1.21.0_all_demos.hip`** in Houdini 22, or **`%LOCALAPPDATA%\Arraytron\versions\1.21.0\demos_h205\Arraytron_v1.21.0_H205_all_demos.hip`** in Houdini 20.5 / 21 (every demo as a separate network in one scene; click the display flag of the chain you want to see). The documentation is in the `docs` folder next to them; start with `docs\USER_GUIDE.md`.

**Houdini 20.5 / 21: restart Houdini after updating or removing Arraytron.** Those versions cannot load the same node type a second time in one session if a scene library recorded it (the node would come back without parameters); the installed package avoids this in normal work, and the demos are saved without a library record for the same reason. See `docs/TROUBLESHOOTING.md`.

## Update

Either:

- In Houdini, click **Check for Updates** on the **Arraytron** shelf. It reads `version.json` from the update source (installed copies come from the GitHub releases of `abdulkarimnoah01/Arraytron`), shows what is new and installs it if you say yes. The download is checked against its SHA-256 before anything is unpacked. Restart Houdini afterwards. Nothing is checked in the background. Another source (a shared folder or an https address) can be set through the `ARRAYTRON_UPDATE_SOURCE` variable or `arraytron_update.json` in the Houdini preferences folder.
- Or unpack the new download and double-click **Install Arraytron.cmd** again.

Both replace the old version and keep the one before it, so a bad update can be rolled back. Scenes keep the node type they were built with (`arraytron::instancer::<version>`), so an older scene keeps working; to move a scene to a newer version create the new node and copy the parameters (see `docs/CACHING_AND_PIPELINE.md`). Scenes made in Houdini 22 open in Houdini 22 only; a scene made with the Houdini 20.5 build opens in 20.5 and 21 (and in 22, where the node type of the same version is the Houdini 22 build).

## Remove

Double-click **Uninstall Arraytron.cmd**, then restart Houdini. Your scenes are not touched.

## Where things go

| What | Where |
| --- | --- |
| The plugin (HDAs, demos, docs) | `%LOCALAPPDATA%\Arraytron\versions\<version>\` (this one and the one before); `h22\otls` and `h205\otls` hold the two HDAs |
| The hook into Houdini | `Documents\houdini22.0\packages\arraytron.json` (and the same for `houdini21.0`, `houdini20.5`), one per Houdini |
| What was installed | `%LOCALAPPDATA%\Arraytron\installed.json` |

The package file adds the plugin's `h22` (Houdini 22) or `h205` (Houdini 20.5 / 21) folder to Houdini's path, so the HDA appears with no further setup. Command line options: `Install Arraytron.cmd -Houdini 22.0` (only that version; also 21.0 or 20.5), `-CreatePrefs -Houdini 20.5` (prepare a version you have not started yet), `-Uninstall`, `-Quiet` (no pause).

## Continuing development on another PC (Claude or a person)

Unpack **Arraytron_v1.21.0_DevKit.rar**. It holds the sources, build tools, test suites, documents, the built release files (both builds) and a copy of the Claude memory. Read `HANDOFF.md` first; it explains the state, the environment, how to continue and what is not verified. Check the setup with `python tools/check_docs.py`, `hython tests/validate_v016.py v1.21.0` (Houdini 22) and the same command with hython 20.5 for the other build (`docs/PORT_HOUDINI_205.md`).

## Whoever supplies Arraytron: build a release

Build the Houdini 22 HDA and demos with hython 22 and the Houdini 20.5 / 21 HDAs and demos with hython 20.5 (`tools/build_h205_all.sh`, `tools/build_h205_demos.sh`), run the suites with both (`CLAUDE.md` lists them; `tests/validate_h205.py` compares the two builds), `python tools/check_docs.py` (documents current), `python tools/make_manifest.py`, then `python tools/make_release.py` (needs WinRAR's `Rar.exe`; it builds `release/Arraytron_<version>_Release.rar` and `release/Arraytron_<version>_DevKit.rar`, tests the installer in a sandbox against every Houdini installed here and tests the archives).

## Publish a release on GitHub (the updater's source)

The repository holds the source, tools, tests, documents and installer; the built HDAs and demos are not in git (they are rebuilt with Houdini) and travel in the release.

1. Build and validate as above (`tools/make_release.py` checks the documents and the manifest first).
2. `python tools/make_update_zip.py --update-source https://github.com/abdulkarimnoah01/Arraytron/releases/latest/download/` writes `release/update/Arraytron-<version>.zip` and `release/update/version.json` (the notes come from the version's section in `CHANGELOG.md`; the update source is baked into the zip).
3. `git tag v<version>` and `git push origin main v<version>`, then
   `gh release create v<version> release/update/Arraytron-<version>.zip release/update/version.json --title "Arraytron <version>" --notes-file <notes>`.
   Both files must be attached: the updater reads `version.json` and then the zip beside it.
4. Test: install the previous release, click **Check for Updates**.

`python -m unittest tests.test_updater` checks the updater (plain Python).
