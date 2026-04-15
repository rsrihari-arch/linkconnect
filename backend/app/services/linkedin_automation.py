import asyncio
import json
import random
from playwright.async_api import async_playwright, Browser, Page


class LinkedInAutomation:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser: Browser | None = None
        self.page: Page | None = None

    async def _ensure_browser(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
        if not self.browser:
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )

    async def login(self, email: str, password: str) -> list[dict]:
        await self._ensure_browser()
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        try:
            await page.goto("https://www.linkedin.com/login", wait_until="networkidle")
            await page.fill("#username", email)
            await page.fill("#password", password)
            await page.click('button[type="submit"]')

            await page.wait_for_url("**/feed/**", timeout=30000)
            await asyncio.sleep(3)

            cookies = await context.cookies()
            return [
                {"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c["path"]}
                for c in cookies
            ]
        finally:
            await context.close()

    async def send_connection_request(
        self,
        cookies: list[dict],
        profile_url: str,
        message: str | None = None,
    ) -> dict:
        await self._ensure_browser()
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        await context.add_cookies(cookies)
        page = await context.new_page()

        try:
            await page.goto(profile_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(random.uniform(2, 5))

            # Check if already connected
            page_text = await page.text_content("body")
            if page_text and ("Message" in page_text and "Following" in page_text):
                return {"status": "already_connected"}

            # Try to find and click the Connect button
            connect_btn = await self._find_connect_button(page)
            if not connect_btn:
                # Try the "More" dropdown
                more_btn = page.locator('button:has-text("More")')
                if await more_btn.count() > 0:
                    await more_btn.first.click()
                    await asyncio.sleep(1)
                    connect_btn = await self._find_connect_button(page)

            if not connect_btn:
                return {"status": "no_connect_button"}

            await connect_btn.click()
            await asyncio.sleep(2)

            # Add a note if message template is provided
            if message:
                add_note_btn = page.locator('button:has-text("Add a note")')
                if await add_note_btn.count() > 0:
                    await add_note_btn.click()
                    await asyncio.sleep(1)

                    note_field = page.locator('textarea[name="message"]')
                    if await note_field.count() == 0:
                        note_field = page.locator("#custom-message")
                    if await note_field.count() > 0:
                        await note_field.fill(message[:300])  # LinkedIn limits to 300 chars
                        await asyncio.sleep(1)

            # Click Send
            send_btn = page.locator('button:has-text("Send")')
            if await send_btn.count() > 0:
                await send_btn.first.click()
                await asyncio.sleep(2)
                return {"status": "sent"}

            # If no Send button, try Send without a note
            send_now_btn = page.locator('button:has-text("Send without a note")')
            if await send_now_btn.count() > 0:
                await send_now_btn.click()
                await asyncio.sleep(2)
                return {"status": "sent"}

            return {"status": "send_failed"}

        except Exception as e:
            return {"status": "error", "error": str(e)}
        finally:
            await context.close()

    async def _find_connect_button(self, page: Page):
        selectors = [
            'button:has-text("Connect")',
            'button[aria-label*="connect" i]',
            'button[aria-label*="Connect" i]',
        ]
        for selector in selectors:
            btn = page.locator(selector)
            count = await btn.count()
            for i in range(count):
                text = await btn.nth(i).text_content()
                if text and "connect" in text.lower().strip() and "connected" not in text.lower():
                    return btn.nth(i)
        return None

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.browser = None
        self.playwright = None
