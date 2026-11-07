"""Publish the Arraytron Stamp release (built by tools/make_stamp_release.py) to the public GitHub repo: python tools/publish_stamp_release.py [--repo owner/name] [--dry-run]
Needs the GitHub CLI (gh), logged in. Two releases are written, both marked "not the latest release" so that Arraytron's own updater, which reads the repo's latest release, never sees them:
  stamp-v<version>   the versioned release (history): the update zip, version.json, the installer RAR, SHA256SUMS
  stamp-latest       the rolling release the installed copies read (releases/download/stamp-latest/version.json): the same files of the newest version; the files of older versions are removed from it
Only release files are uploaded; no source is pushed to the public repo."""
from pathlib import Path
import argparse, json, subprocess, sys
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'release'/'stamp'
def gh(*args,check=True):
    r=subprocess.run(['gh',*args],capture_output=True,text=True)
    if check and r.returncode!=0:raise SystemExit('gh %s failed:\n%s\n%s'%(' '.join(args),r.stdout[-800:],r.stderr[-800:]))
    return r
def main():
    p=argparse.ArgumentParser(description=__doc__.split('\n')[0]);p.add_argument('--repo',default='abdulkarimnoah01/Arraytron');p.add_argument('--dry-run',action='store_true');a=p.parse_args()
    manifest=json.loads((OUT/'version.json').read_text(encoding='utf-8'));ver=manifest['version']
    if manifest.get('name')!='Arraytron Stamp':raise SystemExit('release/stamp/version.json is not the Stamp\'s.')
    files=[OUT/manifest['zip'],OUT/'version.json',OUT/('Arraytron_Stamp_v%s_Release.rar'%ver),OUT/'SHA256SUMS.txt']
    for f in files:
        if not f.is_file():raise SystemExit('Missing %s: run tools/make_stamp_release.py first.'%f)
    notes=OUT/'RELEASE_NOTES.md';notes.write_text('# Arraytron Stamp %s\n\n%s\n\nInstall: unpack Arraytron_Stamp_v%s_Release.rar and run Install Arraytron Stamp.cmd, or click Check for Updates on the Arraytron Stamp shelf of an installed copy.\n'%(ver,'\n'.join('* '+n for n in manifest['notes']),ver),encoding='utf-8')
    title='Arraytron Stamp %s'%ver
    if a.dry_run:print('would publish',[f.name for f in files],'as stamp-v%s and stamp-latest on %s'%(ver,a.repo));return
    for tag,rolling in (('stamp-v'+ver,False),('stamp-latest',True)):
        exists=gh('release','view',tag,'--repo',a.repo,check=False).returncode==0
        if exists:
            gh('release','edit',tag,'--repo',a.repo,'--title',title,'--notes-file',str(notes),'--latest=false')
            gh('release','upload',tag,'--repo',a.repo,'--clobber',*map(str,files))
        else:
            gh('release','create',tag,'--repo',a.repo,'--title',title,'--notes-file',str(notes),'--latest=false',*map(str,files))
        if exists and rolling:                                                       # the rolling release holds only the newest version's files
            names=json.loads(gh('release','view',tag,'--repo',a.repo,'--json','assets').stdout)['assets']
            for asset in names:
                if asset['name'] not in {f.name for f in files}:gh('release','delete-asset',tag,asset['name'],'--repo',a.repo,'--yes')
        print('published',tag)
if __name__=='__main__':main()
