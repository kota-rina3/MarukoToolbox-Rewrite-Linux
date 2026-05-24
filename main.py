import traceback
from pathlib import Path


def main():
    try:
        from gui import run_app
    except Exception:
        crash_log = Path.cwd() / "crash.log"
        crash_log.write_text(traceback.format_exc(), encoding="utf-8")
        raise
    run_app()


if __name__ == "__main__":
    main()
