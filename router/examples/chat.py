"""Buildbox's documented subset. No SDK, provider credential, or automatic retry."""

import argparse
import json
import os
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--alias")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--tool-roundtrip", action="store_true")
    args = parser.parse_args()
    base = os.environ["BUILDBOX_API_BASE"].rstrip("/")
    key = os.environ["BUILDBOX_API_KEY"]

    def call(body=None):
        request = urllib.request.Request(
            base + ("/v1/models" if body is None else "/v1/chat/completions"),
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "Idempotency-Key": uuid.uuid4().hex,
            },
        )
        return urllib.request.urlopen(request, timeout=120)

    if args.list:
        with call() as response:
            print(response.read().decode())
        return
    if not args.alias:
        parser.error("--alias must be an authorized immutable route alias")
    messages = [
        {
            "role": "user",
            "content": "What is the shipping policy? Use the read-only support lookup if provided.",
        }
    ]
    body = {"model": args.alias, "messages": messages, "max_tokens": 32, "stream": args.stream}
    if args.tool_roundtrip:
        if args.stream:
            parser.error("Tool roundtrip example is nonstream")
        body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "lookup_support",
                    "strict": True,
                    "parameters": {
                        "type": "object",
                        "properties": {"key": {"type": "string"}},
                        "required": ["key"],
                        "additionalProperties": False,
                    },
                },
            }
        ]
    with call(body) as response:
        if args.stream:
            for line in response:
                print(line.decode().rstrip(), flush=True)
            return
        first = json.load(response)
    if args.tool_roundtrip:
        reply = first["choices"][0]["message"]
        calls = reply.get("tool_calls") or []
        if len(calls) != 1:
            raise ValueError("Expected one read-only tool call; nothing executed")
        tool = calls[0]
        arguments = json.loads(tool["function"]["arguments"])
        if tool["function"]["name"] != "lookup_support" or arguments != {"key": "shipping"}:
            raise ValueError("Undeclared/write/unknown tool request denied")
        messages.extend(
            [
                reply,
                {
                    "role": "tool",
                    "tool_call_id": tool["id"],
                    "content": "SIMULATED read-only policy: shipping takes 3 days.",
                },
            ]
        )
        with call(body) as response:
            first = json.load(response)
    print(json.dumps(first))


if __name__ == "__main__":
    main()
