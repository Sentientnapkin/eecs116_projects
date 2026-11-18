"""Private Hugging Face sync for training runs: create the repo, push a run, pull one to resume."""
import argparse
import threading
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


class BackgroundSync:
    """Pushes epochs without blocking training. Hub rate limits make an upload wait up to an
    hour inside huggingface_hub's retries; meanwhile later epochs are skipped (each push
    carries the newest metrics, best weights and checkpoint) and failures only warn.
    `finish()` waits for the in-flight upload and pushes the final epoch if it was skipped."""

    def __init__(self, run_dir, repo):
        self.run_dir, self.repo = Path(run_dir), repo
        self.thread, self.pushed, self.latest = None, 0, 0

    def _push(self, epoch):
        try:
            push_epoch(self.run_dir, epoch, self.repo); self.pushed = epoch
        except Exception as error:  # a failed sync never stops training
            print(f"Hub sync of epoch {epoch} failed: {type(error).__name__}: {str(error)[:200]}", flush=True)

    def epoch(self, epoch):
        self.latest = epoch
        if self.thread is not None and self.thread.is_alive():
            print(f"Hub sync busy; epoch {epoch} will be covered by a later push", flush=True)
            return
        self.thread = threading.Thread(target=self._push, args=(epoch,), daemon=True); self.thread.start()

    def finish(self):
        if self.thread is not None: self.thread.join()
        if self.latest and self.pushed != self.latest: self._push(self.latest)


def pull(run_name, destination, repo=DEFAULT_REPO):
    """Download a run so odometry_train.py --resume can continue it on this machine."""
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
