"""
COMPASS Gemini Function Calling Tools
Defines callable function tools for Gemini 3.8 Flash to interact with Windows,
applications, files, and UI elements.
"""

from __future__ import annotations

import json
from typing import Any

from automation.action_dispatcher import (
    click_element,
    dispatch_highlight,
    dispatch_key_combination,
    dispatch_scroll,
    focus_element,
    launch_application,
    move_cursor,
    open_url,
    send_key,
    type_text,
)
from automation.app_discovery import get_app_discovery
from backend.app.logging_config import logger


# Define concrete tool functions for Gemini Function Calling
def launch_app(app_name: str) -> str:
    """
    Launch a Windows application by name or executable.
    
    Args:
        app_name: The common name or executable of the application (e.g. 'Spotify', 'Notepad', 'Chrome', 'calc').
    """
    res = launch_application(app_name=app_name)
    return json.dumps(res.to_dict())


def open_website(url: str, browser: str = "") -> str:
    """
    Open a web URL in a browser.
    
    Args:
        url: The web URL to navigate to (e.g. 'https://google.com').
        browser: Optional browser name (e.g. 'chrome', 'edge', 'firefox').
    """
    res = open_url(url=url, browser=browser or None)
    return json.dumps(res.to_dict())


def click_ui_element(description: str, x: int = 0, y: int = 0) -> str:
    """
    Click a user interface element either by name/description or coordinates.
    
    Args:
        description: Description of the element to click (e.g. 'Save Button', 'File Menu').
        x: Optional horizontal screen coordinate.
        y: Optional vertical screen coordinate.
    """
    snapshot = {
        "name": description,
        "control_type": "Button",
        "bounds": {"left": x - 5, "top": y - 5, "right": x + 5, "bottom": y + 5} if (x > 0 or y > 0) else {},
    }
    res = click_element(snapshot)
    return json.dumps(res.to_dict())


def type_into_element(text: str, description: str = "focused") -> str:
    """
    Type text into the currently active or target input element.
    
    Args:
        text: The text string to type.
        description: Description of the input field.
    """
    snapshot = {"name": description, "control_type": "Edit"}
    res = type_text(snapshot, text=text)
    return json.dumps(res.to_dict())


def press_keyboard_key(key: str) -> str:
    """
    Press a single keyboard key (e.g. 'enter', 'tab', 'escape', 'space', 'backspace').
    
    Args:
        key: The key name to press.
    """
    res = send_key(key_name=key)
    return json.dumps(res.to_dict())


def press_key_combo(combination: str) -> str:
    """
    Press a combination of keys together (e.g. 'ctrl+s', 'alt+f4', 'ctrl+shift+esc').
    
    Args:
        combination: Key combination string joined with '+'.
    """
    res = dispatch_key_combination(combination=combination)
    return json.dumps(res.to_dict())


def scroll_screen(direction: str = "down", amount: int = 120) -> str:
    """
    Scroll the mouse wheel up or down.
    
    Args:
        direction: 'up' or 'down'.
        amount: Scroll distance magnitude (standard is 120 per notch).
    """
    delta = amount if direction.lower() == "up" else -amount
    res = dispatch_scroll({}, delta=delta)
    return json.dumps(res.to_dict())


def ask_user(question: str) -> str:
    """
    Ask the human user a question or ask for clarification.
    
    Args:
        question: The question to present to the user.
    """
    return json.dumps({"action": "ask_user", "question": question, "status": "waiting_user"})


def create_code_file(path: str, content: str) -> str:
    """
    Create or overwrite a file with the given code/text content.
    
    Args:
        path: Relative or absolute file path to create.
        content: The text content of the file.
    """
    try:
        import os
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return json.dumps({"success": True, "path": path, "bytes_written": len(content)})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "path": path})


def read_code_file(path: str) -> str:
    """
    Read the contents of a file.
    
    Args:
        path: File path to read.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return json.dumps({"success": True, "path": path, "content": content})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "path": path})


# Registry of callable tools for google-genai SDK
COMPASS_CALLABLE_TOOLS = [
    launch_app,
    open_website,
    click_ui_element,
    type_into_element,
    press_keyboard_key,
    press_key_combo,
    scroll_screen,
    ask_user,
    create_code_file,
    read_code_file,
]

TOOL_FUNCTION_MAP = {
    "launch_app": launch_app,
    "open_website": open_website,
    "click_ui_element": click_ui_element,
    "type_into_element": type_into_element,
    "press_keyboard_key": press_keyboard_key,
    "press_key_combo": press_key_combo,
    "scroll_screen": scroll_screen,
    "ask_user": ask_user,
    "create_code_file": create_code_file,
    "read_code_file": read_code_file,
}


def execute_tool_call(name: str, arguments: dict[str, Any]) -> str:
    """Execute a function call by name with arguments."""
    func = TOOL_FUNCTION_MAP.get(name)
    if not func:
        return json.dumps({"error": f"Unknown tool: '{name}'"})
    try:
        return func(**arguments)
    except Exception as e:
        logger.error(f"Error executing tool '{name}': {e}")
        return json.dumps({"error": str(e), "tool": name})
