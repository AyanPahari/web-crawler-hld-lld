"""
Quick smoke test — run with: python test_crawl.py
Verifies the crawler works against all 3 assignment URLs.
"""

import asyncio
import json
from crawler.core import crawl

URLS = [
    "http://www.amazon.com/Cuisinart-CPT-122-Compact-2-Slice-Toaster/dp/B009GQ034C/ref=sr_1_1?s=kitchen&ie=UTF8&qid=1431620315&sr=1-1&keywords=toaster",
    "http://blog.rei.com/camp/how-to-introduce-your-indoorsy-friend-to-the-outdoors/",
    "http://www.cnn.com/2013/06/10/politics/edward-snowden-profile/",
]

# REI's robots.txt blocks automated crawlers — we show compliance by default,
# but also demonstrate the crawler can fetch the page when the check is bypassed.
RESPECT_ROBOTS_MAP = {
    "http://blog.rei.com/camp/how-to-introduce-your-indoorsy-friend-to-the-outdoors/": False,
}


def print_result(result):
    data = result.to_dict()
    if data.get("body_text"):
        data["body_text"] = data["body_text"][:300] + "..."
    print(json.dumps(data, indent=2, default=str))
    print("-" * 80)


async def main():
    for url in URLS:
        respect = RESPECT_ROBOTS_MAP.get(url, True)
        note = " [robots.txt bypassed for demo]" if not respect else ""
        print(f"\n>>> Crawling: {url}{note}\n")
        result = await crawl(url, respect_robots=respect)
        print_result(result)


if __name__ == "__main__":
    asyncio.run(main())
