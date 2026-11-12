import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from .agent import RecurrentPolicy
from .communication.server import serve
from .config import defaultConfig, loadConfig, saveConfig
from .evaluation import compareModels, evaluate, runKnowledgeTransferEvaluation
from .storage.checkpoint import getCheckpointMetadata, loadCheckpointFull
from .training import discoverMaps, train


def checkStatus(modelPath="models/dog.pt", port=8765):
    meta = getCheckpointMetadata(modelPath)
    output = {
        "checkpoint": str(modelPath),
        "checkpointExists": meta["exists"],
        "modelId": meta.get("modelId"),
        "architecture": meta.get("architecture"),
        "modelVersion": meta["version"],
        "updates": meta["updates"],
        "totalEpisodes": meta["totalEpisodes"],
        "totalSteps": meta["totalSteps"],
        "bestWinRate": meta["bestRate"],
        "bestScore": meta["bestScore"],
        "freshInit": meta.get("freshInit"),
        "serverOnline": False,
    }
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/agent/status", timeout=1.5) as resp:
            if resp.status == 200:
                serverData = json.loads(resp.read().decode("utf-8"))
                output["serverOnline"] = True
                output["server"] = serverData
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    print(json.dumps(output, indent=2))
    return output


def main():
    parser = argparse.ArgumentParser(prog="python -m doobyscoo")
    sub = parser.add_subparsers(dest="command", required=True)

    training = sub.add_parser("train", help="Train or resume training the Recurrent PPO dog agent")
    training.add_argument("--maps", default="maps/train", help="Directory containing training maze JSON files")
    training.add_argument("--model", default="models/dog.pt", help="Path to model checkpoint")
    training.add_argument("--updates", type=int, default=60, help="Number of PPO updates to run")
    training.add_argument("--episodes", type=int, default=16, help="Episodes collected per PPO update")
    training.add_argument("--max-steps", type=int, default=300, help="Maximum steps per episode")
    training.add_argument("--lr", type=float, default=None, help="Learning rate override")
    training.add_argument("--rehearsal", default=None, help="Optional rehearsal map directory")
    training.add_argument("--val-maps", default="maps/validation", help="Optional validation map directory")
    training.add_argument("--config", default=None, help="Optional path to training_config.json")
    training.add_argument("--seed", type=int, default=None, help="Optional random seed")
    training.add_argument("--resume", action="store_true", default=True, help="Resume from checkpoint if it exists")
    training.add_argument("--fresh", action="store_true", help="Delete old checkpoint and start a brand-new model")
    training.add_argument("--threads", type=int, default=4, help="CPU threads to use")

    testing = sub.add_parser("evaluate", help="Evaluate a trained model on a set of maps")
    testing.add_argument("--maps", default="maps/test", help="Directory containing evaluation maze JSON files")
    testing.add_argument("--model", default="models/dog.pt", help="Path to model checkpoint")
    testing.add_argument("--max-steps", type=int, default=300, help="Maximum steps per episode")
    testing.add_argument("--episodes-per-map", type=int, default=1, help="Evaluation episodes per map")
    testing.add_argument("--compare-untrained", action="store_true", help="Compare against an untrained baseline")
    testing.add_argument("--compare-checkpoint", default=None, help="Compare against another checkpoint file")

    transferCmd = sub.add_parser("transfer-eval", help="Run the 5-phase knowledge-transfer & retention experiment")
    transferCmd.add_argument("--train-maps", default="maps/train", help="Directory containing training maps")
    transferCmd.add_argument("--test-maps", default="maps/test", help="Directory containing held-out test maps")
    transferCmd.add_argument("--phase1-updates", type=int, default=25, help="PPO updates on initial training maps")
    transferCmd.add_argument("--phase2-updates", type=int, default=20, help="PPO updates on newly introduced maps")
    transferCmd.add_argument("--seed", type=int, default=42, help="Random seed")
    transferCmd.add_argument("--report", default="models/knowledge_transfer_report.json", help="Output JSON report path")

    hosting = sub.add_parser("serve", help="Start the local HTTP RL agent service for Godot")
    hosting.add_argument("--maps", default="maps/played", help="Directory to store and rehearse played maps")
    hosting.add_argument("--train-maps", default="maps/train", help="Directory of original training maps for rehearsal")
    hosting.add_argument("--val-maps", default="maps/validation", help="Directory of validation maps")
    hosting.add_argument("--model", default="models/dog.pt", help="Path to model checkpoint")
    hosting.add_argument("--port", type=int, default=8765, help="Local HTTP server port")
    hosting.add_argument("--learn-updates", type=int, default=3, help="Continual PPO updates per learning cycle")

    statusCmd = sub.add_parser("status", help="Check local model checkpoint and agent server status")
    statusCmd.add_argument("--model", default="models/dog.pt", help="Path to model checkpoint")
    statusCmd.add_argument("--port", type=int, default=8765, help="Local HTTP server port")

    args = parser.parse_args()

    if args.command == "train":
        cfg = loadConfig(args.config) if args.config else defaultConfig()
        resumeFlag = (not args.fresh) and bool(args.resume)
        train(
            mapsFolder=args.maps,
            checkpoint=args.model,
            updates=args.updates,
            episodesPerUpdate=args.episodes,
            maxSteps=args.max_steps,
            learningRate=args.lr,
            rehearsalFolder=args.rehearsal,
            validationFolder=args.val_maps,
            resume=resumeFlag,
            cpuThreads=args.threads,
            config=cfg,
            seed=args.seed,
        )
    elif args.command == "evaluate":
        if not Path(args.model).exists():
            parser.error(f"Model not found: {args.model}")
        testPaths = discoverMaps(args.maps)
        if args.compare_untrained or args.compare_checkpoint:
            modelsToCompare = {}
            if args.compare_untrained:
                modelsToCompare["untrained"] = "untrained"
            if args.compare_checkpoint and Path(args.compare_checkpoint).exists():
                modelsToCompare["baseline"] = args.compare_checkpoint
            modelsToCompare["current"] = args.model
            result = compareModels(modelsToCompare, testPaths, episodesPerMap=args.episodes_per_map, maxSteps=args.max_steps)
            print(json.dumps(result, indent=2))
        else:
            model = RecurrentPolicy()
            meta = loadCheckpointFull(args.model, model)
            result = evaluate(
                model,
                testPaths,
                episodesPerMap=args.episodes_per_map,
                maxSteps=args.max_steps,
                modelVersion=meta.get("version", 1),
            )
            print(json.dumps(result, indent=2))
    elif args.command == "transfer-eval":
        report, _ = runKnowledgeTransferEvaluation(
            trainMapsFolder=args.train_maps,
            testMapsFolder=args.test_maps,
            phase1Updates=args.phase1_updates,
            phase2Updates=args.phase2_updates,
            seed=args.seed,
            reportPath=args.report,
        )
        print(json.dumps(report["verdict"], indent=2))
    elif args.command == "serve":
        serve(
            checkpoint=args.model,
            mapsFolder=args.maps,
            port=args.port,
            learnUpdates=args.learn_updates,
            trainMapsFolder=args.train_maps,
            validationFolder=args.val_maps,
        )
    elif args.command == "status":
        checkStatus(modelPath=args.model, port=args.port)


if __name__ == "__main__":
    main()
