"""
COMPASS — ChatGPT Interactive Guide
Demonstrates using the Playwright Browser Adapter to guide a user.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation.browser_adapter import BrowserAdapter


def inject_guide_styles(browser: BrowserAdapter):
    """Inject CSS for the guided tour."""
    style_js = """
    const style = document.createElement('style');
    style.innerHTML = `
        .compass-guide-tooltip {
            position: fixed;
            background: rgba(0, 120, 215, 0.95);
            color: white;
            padding: 16px 24px;
            border-radius: 8px;
            font-family: 'Segoe UI', system-ui, sans-serif;
            font-size: 16px;
            font-weight: 500;
            z-index: 999999;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            pointer-events: none;
            transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            opacity: 0;
            transform: translateY(20px);
            max-width: 300px;
            border: 1px solid rgba(255,255,255,0.2);
            backdrop-filter: blur(8px);
        }
        .compass-guide-tooltip.visible {
            opacity: 1;
            transform: translateY(0);
        }
        .compass-guide-highlight {
            position: fixed;
            border: 3px solid #0078d7;
            border-radius: 6px;
            z-index: 999998;
            pointer-events: none;
            transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 0 0 4000px rgba(0,0,0,0.4);
            opacity: 0;
        }
        .compass-guide-highlight.visible {
            opacity: 1;
        }
    `;
    document.head.appendChild(style);
    
    // Create tooltip container
    const tooltip = document.createElement('div');
    tooltip.id = 'compass-tooltip';
    tooltip.className = 'compass-guide-tooltip';
    document.body.appendChild(tooltip);
    
    // Create highlight box
    const highlight = document.createElement('div');
    highlight.id = 'compass-highlight';
    highlight.className = 'compass-guide-highlight';
    document.body.appendChild(highlight);
    """
    browser.evaluate_js(style_js)


def show_guide(
    browser: BrowserAdapter, text: str, element_selector: str = None, duration: int = 5  # noqa: RUF013
):
    """Show a tooltip and optionally highlight an element."""
    print(f"Guide: {text}")

    if element_selector:
        # Find element bounding box and position tooltip
        js = f"""
        (function() {{
            const el = document.querySelector("{element_selector}");
            const tooltip = document.getElementById('compass-tooltip');
            const highlight = document.getElementById('compass-highlight');
            
            tooltip.textContent = "{text}";
            
            if (el) {{
                const rect = el.getBoundingClientRect();
                
                // Position highlight
                highlight.style.left = (rect.left - 4) + 'px';
                highlight.style.top = (rect.top - 4) + 'px';
                highlight.style.width = (rect.width + 8) + 'px';
                highlight.style.height = (rect.height + 8) + 'px';
                highlight.classList.add('visible');
                
                // Position tooltip below element
                let tooltipTop = rect.bottom + 16;
                if (tooltipTop + 100 > window.innerHeight) {{
                    tooltipTop = rect.top - 100; // put above if no space
                }}
                
                tooltip.style.left = Math.max(16, rect.left) + 'px';
                tooltip.style.top = tooltipTop + 'px';
                tooltip.classList.add('visible');
            }} else {{
                // Center tooltip if element not found
                highlight.classList.remove('visible');
                tooltip.style.left = '50%';
                tooltip.style.top = '50%';
                tooltip.style.transform = 'translate(-50%, -50%)';
                tooltip.classList.add('visible');
            }}
        }})();
        """
    else:
        # Just show tooltip in center
        js = f"""
        (function() {{
            const tooltip = document.getElementById('compass-tooltip');
            const highlight = document.getElementById('compass-highlight');
            
            highlight.classList.remove('visible');
            tooltip.textContent = "{text}";
            tooltip.style.left = '50%';
            tooltip.style.top = '50%';
            tooltip.style.transform = 'translate(-50%, -50%)';
            tooltip.classList.add('visible');
        }})();
        """

    browser.evaluate_js(js)
    time.sleep(duration)

    # Hide
    browser.evaluate_js("""
        document.getElementById('compass-tooltip').classList.remove('visible');
        document.getElementById('compass-highlight').classList.remove('visible');
    """)
    time.sleep(0.5)


def run_chatgpt_guide():
    print("Starting ChatGPT Guide...")
    browser = BrowserAdapter(headless=False, timeout_ms=60000)
    browser.start()

    print("Navigating to ChatGPT...")
    browser.navigate("https://chatgpt.com")
    time.sleep(3)  # Let the page settle

    inject_guide_styles(browser)

    # 1. Welcome
    show_guide(
        browser,
        "Welcome to ChatGPT! I am COMPASS, your AI assistant. I will guide you through this interface.",
        duration=5,
    )

    # Check if we are on login screen or main chat
    # We will just try to select common elements

    # 2. Main Prompt Box
    # ChatGPT uses textarea with id 'prompt-textarea'
    res = browser.evaluate_js("document.querySelector('#prompt-textarea') !== null")
    if res.success and "true" in str(res.data.get("value")).lower():
        # Logged in or free access mode
        show_guide(
            browser,
            "This is the main chat box. You can type any question or prompt here.",
            "#prompt-textarea",
            duration=6,
        )

        # 3. New Chat button
        show_guide(
            browser,
            "Click the 'New Chat' button in the top left to start a fresh conversation.",
            "[data-testid='new-chat-button'], a[href='/']",
            duration=5,
        )

        # 4. Profile / Settings
        show_guide(
            browser,
            "Your settings and history are usually located in the sidebar or bottom left.",
            "nav",
            duration=5,
        )

    else:
        # Login screen
        show_guide(
            browser,
            "It looks like you need to log in first. Click the 'Log in' button to sign into your account.",
            "[data-testid='login-button']",
            duration=6,
        )
        show_guide(
            browser,
            "If you don't have an account, click 'Sign up' to create a free one.",
            "[data-testid='signup-button']",
            duration=5,
        )

    show_guide(
        browser,
        "You are now ready to use ChatGPT! I will leave this window open for you.",
        duration=5,
    )

    print("Guide finished. Leaving browser open for 60 seconds.")
    time.sleep(60)
    browser.stop()


if __name__ == "__main__":
    run_chatgpt_guide()
