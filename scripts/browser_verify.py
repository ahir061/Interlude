"""Run actual browser tests without putting workspace credentials in command arguments."""
import argparse
import os
import subprocess
from pathlib import Path

from interlude.config import Settings


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--episode',type=Path)
    parser.add_argument('--url',default='http://localhost:8080')
    parser.add_argument('--report-dir',type=Path,default=Path('reports/phase3-workspace'))
    parser.add_argument('--test',action='append',default=[])
    args=parser.parse_args()
    env=dict(os.environ)
    env['INTERLUDE_WORKSPACE_PASSWORD']=Settings().workspace_password.get_secret_value()
    env['INTERLUDE_WEB_URL']=args.url
    env['INTERLUDE_REPORT_DIR']=str(args.report_dir.resolve())
    if args.manifest:
        env['INTERLUDE_MANIFEST']=str(args.manifest.resolve())
    if args.episode:
        env['INTERLUDE_EPISODE_UPLOAD']=str(args.episode.resolve())
    raise SystemExit(subprocess.run(['npm','run','test:browser','--',*args.test],cwd='apps/web',env=env).returncode)


if __name__=='__main__':
    main()
