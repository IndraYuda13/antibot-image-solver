from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Sequence

from antibot_image_solver.api.app import run as run_api
from antibot_image_solver.capture import CaptureRequest
from antibot_image_solver.models import AntibotChallenge, OptionImage
from antibot_image_solver.solver import analyze_instruction_image, solve_challenge


def _read_file_base64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode()


def cmd_serve(args: argparse.Namespace) -> int:
    run_api(host=args.host, port=args.port)
    return 0


def cmd_analyze_image(args: argparse.Namespace) -> int:
    payload = analyze_instruction_image(_read_file_base64(args.image))
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload)
    return 0


def _capture_request_from_args(args: argparse.Namespace) -> CaptureRequest | None:
    if not getattr(args, "capture_dir", None):
        return None
    return CaptureRequest(
        output_dir=args.capture_dir,
        verdict=args.capture_verdict or "uncertain",
        source="cli",
        notes=args.capture_notes,
        tags=[item.strip() for item in (args.capture_tags or "").split(",") if item.strip()],
        challenge_id=args.capture_challenge_id,
    )


def cmd_solve_image(args: argparse.Namespace) -> int:
    challenge = AntibotChallenge(
        instruction_image_base64=_read_file_base64(args.image),
        candidates=[item.strip() for item in args.candidates.split(",") if item.strip()],
        domain_hint=args.domain_hint,
    )
    result = solve_challenge(challenge, debug=args.debug, capture=_capture_request_from_args(args))
    payload = result.to_dict(include_debug=args.debug)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload)
    return 0 if result.success else 2


def cmd_solve_options(args: argparse.Namespace) -> int:
    options: list[OptionImage] = []
    for item in args.option:
        if "=" not in item:
            raise SystemExit(f"invalid --option {item!r}; expected id=path")
        option_id, path = item.split("=", 1)
        options.append(OptionImage(id=option_id.strip(), image_base64=_read_file_base64(path.strip())))
    challenge = AntibotChallenge(
        instruction_image_base64=_read_file_base64(args.instruction_image),
        options=options,
        domain_hint=args.domain_hint,
    )
    result = solve_challenge(challenge, debug=args.debug, capture=_capture_request_from_args(args))
    payload = result.to_dict(include_debug=args.debug)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload)
    return 0 if result.success else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="antibot-image-solver")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run FastAPI server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8010)
    serve.set_defaults(func=cmd_serve)

    analyze = sub.add_parser("analyze-image", help="Analyze one instruction image")
    analyze.add_argument("--image", required=True)
    analyze.add_argument("--json", action="store_true")
    analyze.set_defaults(func=cmd_analyze_image)

    solve = sub.add_parser("solve-image", help="Solve using instruction image plus text candidates")
    solve.add_argument("--image", required=True)
    solve.add_argument("--candidates", required=True, help="Comma-separated text candidates")
    solve.add_argument("--domain-hint")
    solve.add_argument("--debug", action="store_true")
    solve.add_argument("--json", action="store_true")
    solve.add_argument("--capture-dir")
    solve.add_argument("--capture-verdict")
    solve.add_argument("--capture-notes")
    solve.add_argument("--capture-tags", help="Comma-separated tags")
    solve.add_argument("--capture-challenge-id")
    solve.set_defaults(func=cmd_solve_image)

    solve_opts = sub.add_parser("solve-options", help="Solve using instruction image plus option images")
    solve_opts.add_argument("--instruction-image", required=True)
    solve_opts.add_argument("--option", action="append", required=True, help="Option spec: id=path")
    solve_opts.add_argument("--domain-hint")
    solve_opts.add_argument("--debug", action="store_true")
    solve_opts.add_argument("--json", action="store_true")
    solve_opts.add_argument("--capture-dir")
    solve_opts.add_argument("--capture-verdict")
    solve_opts.add_argument("--capture-notes")
    solve_opts.add_argument("--capture-tags", help="Comma-separated tags")
    solve_opts.add_argument("--capture-challenge-id")
    solve_opts.set_defaults(func=cmd_solve_options)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
