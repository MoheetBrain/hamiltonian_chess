"""Read-only source inventory. Writes only the requested forensic snapshot path."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def command(*args, cwd=None):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path('/Users/moheet/Documents/ChatGPT/hamiltonian_chess')
    blocks = command('git', 'worktree', 'list', '--porcelain', cwd=root)['stdout'].strip().split('\n\n')
    worktrees = []
    for block in blocks:
        lines = block.splitlines()
        path = Path(lines[0].removeprefix('worktree '))
        entry = {"path": str(path), "git": block, "status": command('git', 'status', '--short', '--branch', cwd=path)}
        entry['goal_sha256'] = digest(path / 'GOAL.md')
        if 'hamiltonian-phase-8-experiment' in str(path):
            paths = command('git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard', cwd=path)['stdout'].split('\0')
            entry['files'] = {p: {"sha256": digest(path / p), "bytes": (path / p).stat().st_size}
                              for p in paths if p and (path / p).is_file()}
        worktrees.append(entry)
    models = []
    for path in sorted(Path('/Users/moheet/.ollama/models/manifests').rglob('*')):
        if not path.is_file():
            continue
        data = json.loads(path.read_text())
        config = Path('/Users/moheet/.ollama/models/blobs') / data['config']['digest'].replace(':', '-')
        models.append({"name": str(path.relative_to(Path('/Users/moheet/.ollama/models/manifests'))),
                       "manifest_sha256": digest(path), "bytes": sum(l['size'] for l in data['layers']) + data['config']['size'],
                       "config": json.loads(config.read_text()) if config.is_file() else None})
    report = {"utc": datetime.now(timezone.utc).isoformat(), "worktrees": worktrees, "models": models,
              "branches": command('git', 'branch', '-avv', cwd=root),
              "hardware": command('sysctl', '-n', 'hw.memsize', 'hw.model', 'hw.logicalcpu'),
              "cloud": command('gcloud', 'compute', 'instances', 'list', '--format=json(name,zone,machineType,status)', '--quiet'),
              "processes": command('pgrep', '-fl', 'fitness_v7|phase8|rendered_shortcut|ollama|pytest')}
    args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
