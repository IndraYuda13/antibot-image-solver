# API

## Health

### `GET /health`

Response:

```json
{
  "ok": true,
  "service": "antibot-image-solver",
  "version": "0.1.0"
}
```

## Analyze instruction image

### `POST /analyze/antibot-image`

Request:

```json
{
  "instruction_image_base64": "..."
}
```

Response shape:

```json
{
  "success": true,
  "ocr": {
    "raw_variants": ["DOG CAT MOUSE", "D0G CAT M0USE"],
    "best_text": "DOG CAT MOUSE"
  },
  "tokens": ["dog", "cat", "mouse"],
  "family_guess": "animals"
}
```

## Solve anti-bot image

### `POST /solve/antibot-image`

You can solve in two ways.

### Mode A: instruction image plus text candidates

```json
{
  "instruction_image_base64": "...",
  "candidates": ["dog", "cat", "mouse"],
  "domain_hint": "earncryptowrs",
  "debug": true
}
```

### Mode B: instruction image plus option images

```json
{
  "instruction_image_base64": "...",
  "options": [
    {"id": "6940", "image_base64": "..."},
    {"id": "6138", "image_base64": "..."},
    {"id": "4910", "image_base64": "..."}
  ],
  "domain_hint": "earncryptowrs",
  "debug": true
}
```

### Successful response

```json
{
  "success": true,
  "status": "solved",
  "solution": {
    "ordered_ids": ["6940", "6138", "4910"],
    "ordered_candidates": ["4", "3", "2"],
    "indexes_1based": [1, 3, 2]
  },
  "confidence": 0.55,
  "meta": {
    "family": "numbers",
    "tokens_detected": ["four", "three", "two"],
    "domain_hint": "earncryptowrs",
    "mode": "option_images"
  },
  "debug": {
    "instruction_ocr": ["four, three, two"],
    "instruction_token_sets": [["four", "three", "two"]]
  }
}
```

### Uncertain response

```json
{
  "success": false,
  "status": "uncertain",
  "confidence": 0.0,
  "error": {
    "code": "LOW_CONFIDENCE",
    "message": "failed to extract instruction token set"
  }
}
```

## Notes

- This service solves the image-to-order problem only.
- It does not handle login, session state, browser clicks, or target-site telemetry.
- `domain_hint` is optional metadata. It can help future site-specific tuning without changing the generic API contract.
