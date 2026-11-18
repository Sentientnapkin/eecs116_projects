"""Private Hugging Face sync for teacher runs: create the repo, push a run, pull one to resume."""
import argparse
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

DEFAULT_REPO = "SentientNapkin/viobench-teacher-lab"


def ensure_private(repo=DEFAULT_REPO):
    api = HfApi()
    api.create_repo(repo, private=True, exist_ok=True)
    if not api.repo_info(repo).private:
        raise RuntimeError(f"{repo} is public; refusing to sync checkpoints")
    return api


def push_epoch(run_dir, epoch, repo=DEFAULT_REPO):
    """Upload run metadata, best weights, and the newest complete checkpoint only."""
    run_dir = Path(run_dir)
    api = ensure_private(repo)
    checkpoint = f"checkpoints/epoch-{epoch:04d}"
    api.upload_folder(repo_id=repo, folder_path=str(run_dir), path_in_repo=f"runs/{run_dir.name}",
                      allow_patterns=["manifest.json", "config.json", "metrics.json", "source/*", "source/configs/*",
                                      "best.safetensors", f"{checkpoint}/*"],
                      commit_message=f"{run_dir.name}: epoch {epoch}")


def pull(run_name, destination, repo=DEFAULT_REPO):
    """Download a run so teacher_train.py --resume can continue it on this machine."""
    ensure_private(repo)
    root = snapshot_download(repo, allow_patterns=[f"runs/{run_name}/*"], local_dir=destination)
    return Path(root)/"runs"/run_name


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("init", "push", "pull"))
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--run", help="Run directory (push) or run name (pull)")
    parser.add_argument("--epoch", type=int)
    parser.add_argument("--destination", default="results/hub")
    args = parser.parse_args()
    if args.action == "init":
        ensure_private(args.repo); print(f"https://huggingface.co/{args.repo} (private)")
    elif args.action == "push":
        push_epoch(args.run, args.epoch, args.repo)
    else:
        print(pull(args.run, args.destination, args.repo))
