import argparse
from pathlib import Path
from .training import train, evaluate, discoverMaps, loadCheckpoint
from .agent import RecurrentPolicy
from .server import serve


def main():
    parser = argparse.ArgumentParser(prog="python -m doobyscoo")
    sub = parser.add_subparsers(dest="command", required=True)
    training = sub.add_parser("train")
    training.add_argument("--maps", required=True)
    training.add_argument("--model", default="models/dog.pt")
    training.add_argument("--updates", type=int, default=100)
    training.add_argument("--episodes", type=int, default=8)
    training.add_argument("--max-steps", type=int, default=300)
    training.add_argument("--rehearsal", default=None)
    testing = sub.add_parser("evaluate")
    testing.add_argument("--maps", required=True)
    testing.add_argument("--model", default="models/dog.pt")
    testing.add_argument("--max-steps", type=int, default=300)
    hosting = sub.add_parser("serve")
    hosting.add_argument("--maps", required=True)
    hosting.add_argument("--model", default="models/dog.pt")
    hosting.add_argument("--port", type=int, default=8765)
    hosting.add_argument("--learn-updates", type=int, default=5)
    args = parser.parse_args()
    if args.command == "train":
        train(args.maps, args.model, args.updates, args.episodes, args.max_steps, rehearsalFolder=args.rehearsal)
    elif args.command == "evaluate":
        model = RecurrentPolicy()
        if not Path(args.model).exists():
            parser.error(f"Model not found: {args.model}")
        loadCheckpoint(args.model, model)
        print(evaluate(model, discoverMaps(args.maps), maxSteps=args.max_steps))
    else:
        serve(args.model, args.maps, args.port, args.learn_updates)


if __name__ == "__main__":
    main()
