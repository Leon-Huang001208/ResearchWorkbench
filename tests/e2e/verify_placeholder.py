#!/usr/bin/env python3
"""Verify that the placeholder text is correctly displayed as '代码/名称/简拼'"""

from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        # 1. Navigate to homepage
        print("Navigating to http://127.0.0.1:8000...")
        page.goto("http://127.0.0.1:8000", wait_until="networkidle")

        # 2. Click on Asset Analysis section (the icon button on the left activity bar)
        print("Clicking Asset Analysis...")
        page.click('button.activity-btn[data-section="asset-analysis"]')

        # Wait for the section to become active
        page.wait_for_selector("section#section-asset-analysis.content-section.active")

        # 3. Find the input element
        input_elem = page.locator("input#asset-code")
        input_elem.wait_for(state="visible")

        # 4. Get the placeholder attribute
        placeholder = input_elem.get_attribute("placeholder")
        print(f"Current placeholder text: '{placeholder}'")

        # 5. Verify it's correct
        expected = "代码/名称/简拼"
        if placeholder == expected:
            print(f"✅ SUCCESS: Placeholder is correctly '{expected}'")
        else:
            print(f"❌ FAIL: Expected '{expected}', got '{placeholder}'")

        # 6. Take screenshot
        screenshot_path = "/Users/leon/Desktop/Projects/ResearchWorkbench/tests/e2e/screenshots/asset-placeholder-verification.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"📸 Screenshot saved to {screenshot_path}")

        # Also take a screenshot focusing on the input area
        input_bounding = input_elem.bounding_box()
        if input_bounding:
            # Expand the area a bit
            clip = {
                "x": max(0, input_bounding["x"] - 20),
                "y": max(0, input_bounding["y"] - 20),
                "width": input_bounding["width"] + 40,
                "height": input_bounding["height"] + 40,
            }
            detail_screenshot = "/Users/leon/Desktop/Projects/ResearchWorkbench/tests/e2e/screenshots/asset-placeholder-detail.png"
            page.screenshot(path=detail_screenshot, clip=clip)
            print(f"📸 Detail screenshot saved to {detail_screenshot}")

        # Keep browser open for a moment
        page.wait_for_timeout(2000)
        browser.close()

        return placeholder == expected


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
