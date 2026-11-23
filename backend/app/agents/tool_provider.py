"""Wire adapters for native provider function calling."""
import json
import requests


def provider_turn(provider, system, messages, tools, exchanges, *, gemini=False):
    if gemini:
        model = provider.model.removeprefix("models/")
        if model in {"gemini-1.5-flash", "gemini-2.5-flash"}:
            model = "gemini-flash-latest"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages
        ]
        for _, original, results in exchanges:
            contents.extend([original, {"role": "user", "parts": [
                {"functionResponse": {
                    "name": call["name"], "response": result,
                    **({"id": call["id"]} if call["id"] else {}),
                }}
                for call, result in results
            ]}])
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "tools": [{"functionDeclarations": [
                {"name": tool["name"], "description": tool["description"],
                 "parametersJsonSchema": tool["parameters"]}
                for tool in tools
            ]}],
            "generationConfig": {"maxOutputTokens": 2048},
        }
        headers = {"x-goog-api-key": provider.api_key}
        data = _post(url, headers, payload, provider.timeout_seconds)
        message = data["candidates"][0]["content"]
        parts = message["parts"]
        return (
            [{"name": p["functionCall"]["name"], "arguments": p["functionCall"].get("args", {}),
              "id": p["functionCall"].get("id")} for p in parts if "functionCall" in p],
            message,
            "".join(p.get("text", "") for p in parts if not p.get("thought")),
        )

    url = "https://api.openai.com/v1/chat/completions"
    history = [{"role": "system", "content": system}, *messages]
    for _, original, results in exchanges:
        history.append(original)
        history.extend({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)}
                       for call, result in results)
    data = _post(url, {"Authorization": f"Bearer {provider.api_key}"}, {
        "model": provider.model, "messages": history,
        "tools": [{"type": "function", "function": tool} for tool in tools],
        "max_completion_tokens": 1024,
    }, provider.timeout_seconds)
    message = data["choices"][0]["message"]
    return (
        [{"name": c["function"]["name"], "arguments": c["function"]["arguments"], "id": c["id"]}
         for c in (message.get("tool_calls") or [])],
        {key: message[key] for key in ("role", "content", "tool_calls") if key in message},
        message.get("content") or "",
    )


def _post(url, headers, payload, timeout):
    for attempt in range(2):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.ConnectionError:
            if attempt:
                raise
            continue
        if attempt == 0 and response.status_code in {429, 502, 503, 504}:
            continue
        response.raise_for_status()
        return response.json()
