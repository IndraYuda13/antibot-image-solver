from __future__ import annotations

import json
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from antibot_image_solver.models import AntibotChallenge, OptionImage


class EarnCryptoWrsAdapterError(RuntimeError):
    pass


@dataclass
class EarnCryptoWrsForm:
    action: str
    csrf_token: str
    server_token: str
    wallet: str
    challenge: AntibotChallenge


def extract_option_entries(html: str) -> list[OptionImage]:
    match = re.search(r"ablinks\s*=\s*(\[.*?\])\s*</script>", html, re.S | re.I)
    if not match:
        return []
    raw = match.group(1)
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EarnCryptoWrsAdapterError(f"failed to parse ablinks JSON: {exc}") from exc

    options: list[OptionImage] = []
    for item in items:
        rel_match = re.search(r'rel=\\"([^\\"]+)\\"', item) or re.search(r'rel="([^"]+)"', item)
        img_match = re.search(r'src=\\"data:image/[^;]+;base64,([^\\"]+)\\"', item) or re.search(
            r'src="data:image/[^;]+;base64,([^"]+)"', item
        )
        if not rel_match or not img_match:
            raise EarnCryptoWrsAdapterError("ablinks item missing rel or image data")
        options.append(OptionImage(id=rel_match.group(1), image_base64=img_match.group(1)))
    return options


def parse_faucet_form(html: str, *, request_id: str | None = None) -> EarnCryptoWrsForm:
    if "Verification Required" in html and "/telegram/verify" in html:
        raise EarnCryptoWrsAdapterError("verification required")

    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", id="fauform")
    if not form:
        raise EarnCryptoWrsAdapterError("faucet form not found")

    action = form.get("action") or ""
    if not action or "/faucet/verify/" not in action:
        raise EarnCryptoWrsAdapterError(f"invalid faucet action: {action!r}")

    csrf = form.find("input", {"name": "csrf_token_name"})
    token = form.find("input", {"name": "token"})
    wallet = form.find("input", {"name": "wallet"})
    warning = form.find(string=re.compile(r"Anti-Bot links", re.I))
    if not csrf or not token or not wallet:
        raise EarnCryptoWrsAdapterError("missing hidden faucet inputs")
    if not warning:
        raise EarnCryptoWrsAdapterError("anti-bot warning not found")

    image = form.find("img", src=re.compile(r"^data:image/", re.I))
    if not image or not isinstance(image.get("src"), str) or "," not in image["src"]:
        raise EarnCryptoWrsAdapterError("instruction image not found")
    instruction_base64 = image["src"].split(",", 1)[1]

    options = extract_option_entries(html)
    if not options:
        raise EarnCryptoWrsAdapterError("ablinks options not found")

    challenge = AntibotChallenge(
        instruction_image_base64=instruction_base64,
        options=options,
        domain_hint="earncryptowrs",
        request_id=request_id,
    )
    return EarnCryptoWrsForm(
        action=action,
        csrf_token=csrf.get("value", ""),
        server_token=token.get("value", ""),
        wallet=wallet.get("value", ""),
        challenge=challenge,
    )


def build_challenge_from_faucet_html(html: str, *, request_id: str | None = None) -> AntibotChallenge:
    return parse_faucet_form(html, request_id=request_id).challenge
