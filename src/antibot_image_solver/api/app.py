from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from antibot_image_solver import __version__
from antibot_image_solver.models import AntibotChallenge, OptionImage
from antibot_image_solver.solver import analyze_instruction_image, solve_challenge
from antibot_image_solver.api.schemas import AnalyzeRequest, ErrorPayload, SolveRequest, SolveResponse

app = FastAPI(title="antibot-image-solver", version=__version__)


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "service": "antibot-image-solver", "version": __version__}


@app.post("/analyze/antibot-image", response_model=dict)
def analyze_antibot_image(payload: AnalyzeRequest) -> dict:
    return {
        "success": True,
        **analyze_instruction_image(payload.instruction_image_base64),
    }


@app.post("/solve/antibot-image", response_model=SolveResponse)
def solve_antibot_image(payload: SolveRequest) -> SolveResponse:
    challenge = AntibotChallenge(
        instruction_image_base64=payload.instruction_image_base64,
        options=[OptionImage(id=item.id, image_base64=item.image_base64) for item in payload.options],
        candidates=payload.candidates,
        domain_hint=payload.domain_hint,
        request_id=payload.request_id,
    )
    result = solve_challenge(challenge, debug=payload.debug)
    data = result.to_dict(include_debug=payload.debug)
    return SolveResponse(
        success=data["success"],
        status=data["status"],
        request_id=payload.request_id,
        solution=data.get("solution"),
        confidence=data.get("confidence"),
        meta=data.get("meta") or {},
        error=ErrorPayload(**data["error"]) if data.get("error") else None,
        debug=data.get("debug"),
    )


def run(host: str = "127.0.0.1", port: int = 8010) -> None:
    uvicorn.run("antibot_image_solver.api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
