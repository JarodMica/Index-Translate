#!/usr/bin/env python3
"""Launch the clip and continuous-audio demos with the standard model runtime."""
import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", choices=["2b", "9b"], default="2b")
    parser.add_argument("--model-dir", type=Path, help="Use an existing local package without downloading")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    from web_demo.engine import Engine
    from web_demo.ui import create_app
    import uvicorn
    engine = Engine(Path(__file__).resolve().parents[2], args.size, args.model_dir)
    print(f"Clip demo: http://localhost:{args.port}/", flush=True)
    print(f"Continuous audio: http://localhost:{args.port}/live", flush=True)
    uvicorn.run(create_app(engine), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
