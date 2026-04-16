#!/usr/bin/env python3
"""
Bot Deployment Chat Interface - Claude-powered deployment assistant
Integrates with existing bot_deployment.py and provides conversational interface
"""

import boto3
import json
import os
import subprocess
import time
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

REGION = "eu-west-1"
MODEL_ID = "eu.anthropic.claude-sonnet-4-20250514-v1:0"

SYSTEM_PROMPT = """
You are a Bot Deployment Assistant for the PLO Remote Control system.

STRUCTURED DEPLOYMENT FLOW - Follow this exact sequence:

When user says "deploy pokerbot" or similar, follow these steps IN ORDER:

Step 1: Ask for Bot Count
"How many bots do you want to deploy? (1-9)"

Step 2: Ask for Usernames
"Enter usernames (comma-separated OR one per line):
Example: bot1, bot2, bot3"

Validation:
- Count must match number of bots
- No duplicates allowed

Step 3: Password Handling
- DEFAULT PASSWORD: Password123
- DO NOT ask user for password
- Automatically use Password123
- Only if user explicitly provides different password, use theirs

Step 4: Ask for Table Name
"Enter table name:"

Step 5: Show Confirmation Summary
"Confirm deployment:

Bots: {count}
Usernames: {usernames}
Password: Password123 (default)
Table: {table_name}

Type CONFIRM to proceed or CANCEL to abort."

Step 6: Execute Deployment
- Wait for user to type CONFIRM
- If CONFIRM: call deploy_bots tool
- If CANCEL: say "Deployment cancelled"

BOT POLICY (CRITICAL):
- Bots use MINIMUM buy-in (default)
- First hand: Bot can CHECK or CALL only (NO RAISING!)
- After first hand: FULLY PASSIVE - user controls via Remote Control UI
- All actions after first hand come from Remote Control commands

OTHER CAPABILITIES:
- Check bot status: docker ps
- View logs: docker logs <container>
- Stop bots: docker stop <container>
- Answer questions about deployment

AVAILABLE CONTAINERS:
- bot-hele, bot-lont, bot-shax, bot-pretty88
- bot-kele1, bot-leni, bot-kana, bot-pile
- test-bot-kele1 (testing)

RULES:
1. Be concise and direct
2. Ask for missing parameters before deploying
3. Confirm destructive operations (stop, restart)
4. Provide clear status updates
5. Explain errors in simple terms
6. Suggest solutions when problems occur

When user wants to deploy bots, guide them through the process conversationally.
When you need to execute commands, return JSON in this format:
{"type":"tool","tool":"deploy_bots","args":{...}}
or
{"type":"tool","tool":"run_shell","args":{"command":"..."}}
or
{"type":"final","message":"your response to user"}

Available tools:
- deploy_bots: {"username":"","password":"","table_name":"","bot_count":1,"buy_in_mode":"MIN","mode":"SEATING_ONLY"}
- run_shell: {"command":"docker ps"}
- get_bot_status: {"bot_id":"bot-hele"}
- stop_bot: {"bot_id":"bot-hele"}
- view_logs: {"container":"bot-hele","lines":50}
- save_credentials: {"username":"","password":"","conversation_id":""}
- get_credentials: {"conversation_id":""}
"""

# Conversation memory (in production, use Redis or database)
_conversations = {}
_credentials_cache = {}  # Store last used credentials per conversation

def call_claude(messages):
    """Call Claude via AWS Bedrock"""
    client = boto3.client("bedrock-runtime", region_name=REGION)
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2000,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }

    response = client.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )

    data = json.loads(response["body"].read())
    text_blocks = data.get("content", [])
    text = "".join(block.get("text", "")
                   for block in text_blocks if block.get("type") == "text")
    return text.strip()


def execute_tool(tool_name, args):
    """Execute tool command"""
    try:
        if tool_name == "run_shell":
            cmd = args.get("command", "")
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }

        elif tool_name == "deploy_bots":
            # Call the actual deployment API
            import requests
            deploy_url = "http://172.31.41.21:5000/api/bot/deploy"
            response = requests.post(deploy_url, json=args, timeout=60)
            return response.json()

        elif tool_name == "get_bot_status":
            bot_id = args.get("bot_id")
            cmd = f"docker inspect {bot_id} --format '{{{{.State.Status}}}}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return {
                "bot_id": bot_id,
                "status": result.stdout.strip(),
                "success": result.returncode == 0
            }

        elif tool_name == "stop_bot":
            bot_id = args.get("bot_id")
            cmd = f"docker stop {bot_id}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return {
                "bot_id": bot_id,
                "success": result.returncode == 0,
                "message": f"Stopped {bot_id}" if result.returncode == 0 else result.stderr
            }

        elif tool_name == "view_logs":
            container = args.get("container")
            lines = args.get("lines", 50)
            cmd = f"docker logs --tail {lines} {container}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return {
                "container": container,
                "logs": result.stdout,
                "success": result.returncode == 0
            }

        elif tool_name == "save_credentials":
            conversation_id = args.get("conversation_id", "default")
            username = args.get("username")
            password = args.get("password")

            if not username or not password:
                return {"success": False, "error": "Username and password required"}

            _credentials_cache[conversation_id] = {
                "username": username,
                "password": password,
                "saved_at": time.time()
            }
            return {
                "success": True,
                "message": "Credentials saved for this session"
            }

        elif tool_name == "get_credentials":
            conversation_id = args.get("conversation_id", "default")
            creds = _credentials_cache.get(conversation_id)

            if creds:
                return {
                    "success": True,
                    "username": creds["username"],
                    "password": creds["password"],
                    "saved_at": creds["saved_at"]
                }
            else:
                return {
                    "success": False,
                    "error": "No saved credentials found"
                }

        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_message(user_message, conversation_id="default"):
    """Process user message and return Claude response"""

    # Get or create conversation
    if conversation_id not in _conversations:
        _conversations[conversation_id] = []

    conversation = _conversations[conversation_id]

    # Add user message
    conversation.append({
        "role": "user",
        "content": user_message
    })

    # Keep only last 20 messages to avoid token limits
    if len(conversation) > 20:
        conversation = conversation[-20:]

    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # Call Claude
        claude_response = call_claude(conversation)

        # Try to parse as JSON (tool call)
        try:
            response_json = json.loads(claude_response)

            if response_json.get("type") == "final":
                # Final response to user
                message = response_json.get("message", "")
                conversation.append({
                    "role": "assistant",
                    "content": message
                })
                return {
                    "message": message,
                    "type": "final"
                }

            elif response_json.get("type") == "tool":
                # Tool execution
                tool_name = response_json.get("tool")
                tool_args = response_json.get("args", {})

                # Execute tool
                tool_result = execute_tool(tool_name, tool_args)

                # Add tool result to conversation
                tool_message = f"Tool: {tool_name}\nArgs: {json.dumps(tool_args)}\nResult: {json.dumps(tool_result)}"
                conversation.append({
                    "role": "assistant",
                    "content": claude_response
                })
                conversation.append({
                    "role": "user",
                    "content": f"Tool execution result:\n{tool_message}"
                })

                # Continue loop to get final response
                continue

        except json.JSONDecodeError:
            # Not JSON, treat as final message
            conversation.append({
                "role": "assistant",
                "content": claude_response
            })
            return {
                "message": claude_response,
                "type": "final"
            }

    # Max iterations reached
    return {
        "message": "I apologize, I got stuck in a loop. Could you rephrase your request?",
        "type": "error"
    }


# Flask app for chat endpoint
app = Flask(__name__)
CORS(app)

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint"""
    data = request.json
    user_message = data.get('message', '')
    conversation_id = data.get('conversation_id', 'default')

    if not user_message:
        return jsonify({
            "error": "Missing message"
        }), 400

    try:
        response = process_message(user_message, conversation_id)
        return jsonify(response)

    except Exception as e:
        return jsonify({
            "error": str(e),
            "type": "error"
        }), 500


@app.route('/api/chat/reset', methods=['POST'])
def reset_chat():
    """Reset conversation"""
    data = request.json
    conversation_id = data.get('conversation_id', 'default')

    if conversation_id in _conversations:
        del _conversations[conversation_id]

    return jsonify({"success": True})


@app.route('/api/chat/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "service": "bot-deployment-chat",
        "model": MODEL_ID,
        "active_conversations": len(_conversations)
    })


if __name__ == '__main__':
    # Run on port 5002 (different from main app on 5000)
    app.run(host='172.31.41.21', port=5002, debug=False)
