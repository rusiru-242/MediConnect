"""Wire adapters for native provider function calling."""
import json
import requests


def provider_turn(provider, system, messages, tools, exchanges, *, gemini=False):
    if gemini:
        from app.agents.provider_gateway import resolve_gemini_model
        model = resolve_gemini_model(provider.model)
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
        data = _post(url, headers, payload, provider.timeout_seconds, "gemini", model)
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
    }, provider.timeout_seconds, "openai", provider.model)
    message = data["choices"][0]["message"]
    return (
        [{"name": c["function"]["name"], "arguments": c["function"]["arguments"], "id": c["id"]}
         for c in (message.get("tool_calls") or [])],
        {key: message[key] for key in ("role", "content", "tool_calls") if key in message},
        message.get("content") or "",
    )


def _post(url, headers, payload, timeout, provider_name="gemini", model=""):
    """All tool-calling requests go through the provider gateway (limits, circuit breaker, metrics; Phase 05)."""
    from app.agents.provider_gateway import send
    return send(provider_name, model, url, headers, payload, timeout)
